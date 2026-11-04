"""Independent installation contract, synthetic accounts only; no network requests."""
import hashlib,hmac,io,json,os,sqlite3,tempfile,unittest
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
from config import read_connection,save_private,secrets_dir
from connection import connect,public_status,subscribe,refresh_if_due
from application import create_app
from go_store import Store,stamp,password_hash
from setup_install import validate_origin

OWNER='100000000000001'
TOKEN='synthetic-for-tests-only-'+'x'*40
SECRET='a'*32
class FakeAPI:
    def __init__(self,token=None):self.token=token
    def get(self,*a,**kw):return {'ok':True,'body':{'id':'12345','user_id':OWNER,'username':'demo_account','name':'Demo','account_type':'BUSINESS'}}

class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        p=patch.dict(os.environ,{'GO_SECRETS':str(self.root/'secrets'),'GO_EVENTS':str(self.root/'events.sqlite'),'GO_SECURE':'0'});p.start();self.addCleanup(p.stop)
        save_private(secrets_dir()/'installation.json',{'admin_username':'owner','verify_token':'synthetic-webhook-verifier','operator':'Demo','contact_email':'demo@example.com'})
        save_private(secrets_dir()/'auth-seed.json',{'password_hash':password_hash('synthetic-admin-password')})
        self.store=Store(self.root/'go.sqlite');self.app=create_app(self.store,'https://insta.example.com')
        self.data={'app_id':'123456789','app_secret':SECRET,'token':TOKEN}
    def request(self,path,method='GET',raw=b'',headers=None,query=''):
        result={}
        def start(status,head):result.update(code=int(status.split()[0]),headers=dict(head))
        env={'PATH_INFO':path,'REQUEST_METHOD':method,'CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw),'QUERY_STRING':query}
        env.update(headers or {});result['body']=b''.join(self.app(env,start));return result
    def event(self,owner=OWNER):return {'object':'instagram','entry':[{'id':owner,'changes':[{'field':'comments','value':{'id':'400000000000001','from':{'id':'300000000000001','username':'demo_contact'},'media':{'id':'200000000000001'},'text':'do not persist'}}]}]}
    def send_event(self,event,secret=SECRET):
        raw=json.dumps(event).encode();sig='sha256='+hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
        return self.request('/webhooks/instagram','POST',raw,{'HTTP_X_HUB_SIGNATURE_256':sig})
    def test_clean_install_has_no_campaigns_or_credentials(self):
        self.assertEqual(self.store.campaigns(),[]);self.assertFalse(public_status(self.store,'https://insta.example.com')['connected'])
        self.assertEqual(self.request('/api/connection')['code'],401)
        self.assertEqual(self.request('/secrets/instagram.json')['code'],401)
    def test_verify_account_and_redact_secrets(self):
        connect(self.store,self.data,FakeAPI)
        self.assertEqual(read_connection()['account_id'],OWNER)
        status=json.dumps(public_status(self.store,'https://insta.example.com'))
        self.assertNotIn(TOKEN,status);self.assertNotIn(SECRET,status)
        self.assertEqual(self.store.campaigns(),[])
    def test_invalid_token_preserves_existing_connection(self):
        connect(self.store,self.data,FakeAPI)
        class Invalid(FakeAPI):
            def get(self,*a,**kw):return {'ok':False,'body':{}}
        with self.assertRaises(ValueError):connect(self.store,self.data,Invalid)
        self.assertEqual(read_connection()['token'],TOKEN)
    def test_account_switch_rejected_even_after_file_removed(self):
        connect(self.store,self.data,FakeAPI);(secrets_dir()/'instagram.json').unlink()
        class Other(FakeAPI):
            def get(self,*a,**kw):
                out=super().get();out['body']['user_id']='900000000000001';return out
        with self.assertRaises(ValueError):connect(self.store,self.data,Other)
        self.assertEqual(read_connection(),{})
    def test_reconnect_pauses_campaigns(self):
        with self.store.db() as db:db.execute('INSERT INTO campaigns VALUES (?,?,?,?,?,?)',('demo','{}','active',1,0,stamp()))
        connect(self.store,self.data,FakeAPI)
        self.assertEqual(self.store.campaigns()[0]['status'],'paused')
    def test_webhook_challenge_requires_secret(self):
        self.assertEqual(self.request('/webhooks/instagram',query='hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=123')['code'],403)
        out=self.request('/webhooks/instagram',query='hub.mode=subscribe&hub.verify_token=synthetic-webhook-verifier&hub.challenge=123')
        self.assertEqual(out['body'],b'123');self.assertTrue(self.store.setting('webhook_verified_at'))
    def test_signature_account_scope_dedup_and_privacy(self):
        connect(self.store,self.data,FakeAPI)
        self.assertEqual(self.send_event(self.event(),secret='wrong')['code'],403)
        self.assertEqual(self.send_event(self.event('900000000000001'))['code'],200)
        self.assertEqual(public_status(self.store,'')['test_contacts'],[])
        self.assertEqual(self.send_event(self.event())['code'],200);self.send_event(self.event())
        with closing(sqlite3.connect(self.root/'events.sqlite')) as db:rows=db.execute('SELECT * FROM go_events').fetchall()
        self.assertEqual(len(rows),1);self.assertNotIn('do not persist',str(rows))
        self.assertEqual(public_status(self.store,'')['test_contacts'][0]['username'],'demo_contact')
    def test_invalid_signed_payload_is_rejected(self):
        connect(self.store,self.data,FakeAPI)
        self.assertEqual(self.send_event({'object':'instagram','entry':[{'id':OWNER,'changes':[None]}]})['code'],400)
    def test_connection_endpoint_requires_login_csrf_and_origin(self):
        headers={'HTTP_ORIGIN':'https://insta.example.com','CONTENT_TYPE':'application/json'}
        login=self.request('/api/login','POST',json.dumps({'username':'owner','password':'synthetic-admin-password'}).encode(),headers)
        self.assertEqual(login['code'],200);csrf=json.loads(login['body'])['csrf']
        headers['HTTP_COOKIE']=login['headers']['Set-Cookie'].split(';')[0]
        raw=json.dumps(self.data).encode()
        self.assertEqual(self.request('/api/connection','POST',raw,headers)['code'],403)
        headers['HTTP_X_CSRF_TOKEN']=csrf
        with patch('go_app.connect') as fn:
            self.assertEqual(self.request('/api/connection','POST',raw,headers)['code'],200);fn.assert_called_once()
        headers['HTTP_ORIGIN']='https://other.example.com'
        self.assertEqual(self.request('/api/connection','POST',raw,headers)['code'],403)
    def test_renewal_failure_keeps_token_and_warns(self):
        connect(self.store,self.data,FakeAPI);c=read_connection();c['last_refresh']=stamp()-21*86400;save_private(secrets_dir()/'instagram.json',c)
        with patch('connection.urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=OSError('synthetic failure')
            refresh_if_due(self.store);refresh_if_due(self.store)
            self.assertEqual(opener.return_value.open.call_count,1)
        self.assertEqual(read_connection()['token'],TOKEN);self.assertTrue(read_connection()['refresh_error'])
    def test_installer_rejects_insecure_or_nested_origin(self):
        self.assertEqual(validate_origin('https://insta.example.com/'),'https://insta.example.com')
        for v in ['http://insta.example.com','https://insta.example.com/path','https://u:p@insta.example.com','https://insta.example.com:123','https://insta.example.com?x=1']:
            with self.assertRaises(ValueError):validate_origin(v)

if __name__=='__main__':unittest.main()
