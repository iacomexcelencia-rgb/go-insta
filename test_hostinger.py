"""Path isolation and reuse of an existing proxy; only synthetic fixtures."""
import io,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from application import create_app
from config import save_private
from go_store import Store,password_hash
from hostinger import hostinger_origin,discover,compose_override,verify_https
from manage import command

HOST='n8n.srv123456.hstgr.cloud'
ORIGIN='https://'+HOST

def fixtures():
    return [{'image':'traefik:v3','labels':{},'networks':['fixture_proxy']},
            {'image':'synthetic-n8n','networks':['fixture_proxy'],
             'labels':{'traefik.http.routers.n8n.rule':f'Host(`{HOST}`)',
                       'traefik.http.routers.n8n.entrypoints':'websecure',
                       'traefik.http.routers.n8n.tls':'true',
                       'traefik.http.routers.n8n.tls.certresolver':'mytlschallenge'}}]

class HostingerTests(unittest.TestCase):
    def test_address_accepts_provided_hostname_and_optional_path(self):
        for value in [ORIGIN,ORIGIN+'/',ORIGIN+'/go-insta/']:
            self.assertEqual(hostinger_origin(value),ORIGIN)
        for value in ['http://'+HOST,'https://example.com',ORIGIN+'/other',ORIGIN+':443',ORIGIN+'?x=1','https://a..hstgr.cloud','https://a.hstgr.cloud.evil.com','https://bad@'+HOST]:
            with self.assertRaises(ValueError):hostinger_origin(value)

    def test_route_uses_actual_network_tls_and_boundary_without_strip(self):
        route=discover(fixtures(),HOST)
        cfg=compose_override(HOST,route);app=cfg['services']['app'];labels=app['labels']
        self.assertEqual(cfg['networks']['hostinger_proxy'],{'external':True,'name':'fixture_proxy'})
        self.assertEqual(set(cfg['services']),{'app'})
        self.assertNotIn('ports',app)
        self.assertEqual(labels['traefik.http.routers.goinsta-panel.tls.certresolver'],'mytlschallenge')
        self.assertIn('PathPrefix(`/go-insta/`)',labels['traefik.http.routers.goinsta-panel.rule'])
        self.assertNotIn('stripprefix',json.dumps(cfg))
        self.assertGreater(int(labels['traefik.http.routers.goinsta-panel.priority']),len(f'Host(`{HOST}`)'))

    def test_missing_ambiguous_and_conflicting_routes_fail_closed(self):
        for data in [[],fixtures()+[fixtures()[1]]]:
            with self.assertRaises(ValueError):discover(data,HOST)
        data=fixtures();data[1]['labels']['traefik.http.routers.occupied.rule']=f'Host(`{HOST}`) && PathPrefix(`/go-insta/`)'
        with self.assertRaises(ValueError):discover(data,HOST)
        data=fixtures();data[0]['networks']=['another_network']
        with self.assertRaises(ValueError):discover(data,HOST)

    def test_multiple_shared_networks_need_explicit_choice(self):
        data=fixtures()
        for c in data:c['networks'].append('other')
        with self.assertRaises(ValueError):discover(data,HOST)
        data[1]['labels']['traefik.docker.network']='fixture_proxy'
        self.assertEqual(discover(data,HOST)['network'],'fixture_proxy')

    def test_tls_errors_do_not_fall_back_to_unverified_https(self):
        with patch('hostinger.urllib.request.urlopen',side_effect=OSError('bad TLS')) as call:
            with self.assertRaises(ValueError):verify_https(ORIGIN)
            self.assertNotIn('context',call.call_args.kwargs)

    def test_management_preserves_override_and_never_starts_caddy(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'.go-insta-mode').write_text('hostinger')
            with self.assertRaises(ValueError):command(root,['up','-d'])
            (root/'compose.hostinger.json').write_text('{}')
            cmd=command(root,['up','-d'])
            self.assertIn(str(root/'compose.hostinger.json'),cmd);self.assertNotIn('--profile',cmd)
            self.assertEqual(cmd[-2:],['up','-d'])

class PrefixTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);root=Path(self.tmp.name)
        env=patch.dict(os.environ,{'GO_BASE':'/go-insta','GO_SECRETS':str(root/'secrets'),'GO_EVENTS':str(root/'events.sqlite'),'GO_SECURE':'1'})
        env.start();self.addCleanup(env.stop)
        save_private(root/'secrets/installation.json',{'admin_username':'admin','verify_token':'synthetic-verifier','operator':'Example','contact_email':'demo@example.com'})
        save_private(root/'secrets/auth-seed.json',{'password_hash':password_hash('synthetic-password')})
        self.app=create_app(Store(root/'go.sqlite'),ORIGIN)

    def request(self,path,method='GET',data=None,headers=None,query=''):
        raw=json.dumps(data).encode() if data is not None else b'';out={}
        def start(status,head):out.update(code=int(status.split()[0]),headers=dict(head))
        env={'PATH_INFO':path,'REQUEST_METHOD':method,'CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw),'QUERY_STRING':query}
        env.update(headers or {});out['body']=b''.join(self.app(env,start));return out

    def test_prefix_isolation_redirect_assets_public_pages_and_webhook(self):
        for path in ['/','/health','/api/login','/go-instax/','/go-insta-other/']:
            self.assertEqual(self.request(path)['code'],404,path)
        redirect=self.request('/go-insta');self.assertEqual(redirect['code'],308)
        self.assertEqual(redirect['headers']['Location'],'/go-insta/')
        for path in ['/','/health','/style.css','/app.js','/onboarding.js','/analytics.js','/privacy','/data-deletion']:
            self.assertEqual(self.request('/go-insta'+path)['code'],200,path)
        self.assertEqual(self.request('/go-insta/api/dashboard')['code'],401)
        result=self.request('/go-insta/webhooks/instagram',query='hub.mode=subscribe&hub.verify_token=synthetic-verifier&hub.challenge=123')
        self.assertEqual(result['body'],b'123')

    def test_login_cookie_csrf_and_connection_urls_keep_prefix(self):
        headers={'HTTP_ORIGIN':ORIGIN,'CONTENT_TYPE':'application/json'}
        login=self.request('/go-insta/api/login','POST',{'username':'admin','password':'synthetic-password'},headers)
        self.assertEqual(login['code'],200)
        cookie=login['headers']['Set-Cookie'];self.assertIn('Path=/go-insta/',cookie);self.assertIn('Secure',cookie)
        headers['HTTP_COOKIE']=cookie.split(';')[0]
        status=json.loads(self.request('/go-insta/api/connection',headers=headers)['body'])
        for key,path in [('webhook_url','webhooks/instagram'),('privacy_url','privacy'),('deletion_url','data-deletion')]:
            self.assertEqual(status[key],ORIGIN+'/go-insta/'+path)
        self.assertEqual(self.request('/go-insta/api/logout','POST',{},headers)['code'],403)
        headers['HTTP_X_CSRF_TOKEN']=json.loads(login['body'])['csrf'];headers['HTTP_ORIGIN']='https://other.example.com'
        self.assertEqual(self.request('/go-insta/api/logout','POST',{},headers)['code'],403)
        headers['HTTP_ORIGIN']=ORIGIN
        logout=self.request('/go-insta/api/logout','POST',{},headers)
        self.assertEqual(logout['code'],200);self.assertIn('Path=/go-insta/',logout['headers']['Set-Cookie'])

if __name__=='__main__':unittest.main()
