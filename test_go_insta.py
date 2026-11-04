import io,os
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from go_store import Store,DEFAULT as TEMPLATE,stamp,password_hash,validate,matches
DEFAULT=dict(TEMPLATE,keywords=["COMANDO"],media=["200000000000001"],test_user="300000000000001",second_enabled=True)
from go_worker import Engine,daily_backup
from go_queue import init_go_queue,queue_go_events
from go_app import make_app

class FakeAPI:
    def __init__(self): self.sent=[]; self.outcome=True; self.sender=DEFAULT['test_user']; self.text='Quero COMANDO, por favor'; self.created=stamp()
    def get(self,*args,**kwargs): return {'ok':True,'body':{'id':'123456','timestamp':datetime.fromtimestamp(self.created,timezone.utc).isoformat(),'from':{'id':self.sender},'text':self.text}}
    def send(self,recipient,message):
        self.sent.append((recipient,message))
        return {'ok':self.outcome,'status':200 if self.outcome else None,'code':'' if self.outcome else 'unknown'}

class GoTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env_patch=patch.dict(os.environ,{'GO_SECRETS':str(Path(self.temp.name)/'secrets')});self.env_patch.start();self.addCleanup(self.env_patch.stop)
        self.store=Store(Path(self.temp.name)/'go.sqlite')
        self.owner_patch=patch('config.read_connection',return_value={'account_id':'100000000000001','username':'test_account','token':'synthetic-token'});self.owner_patch.start()
        self.addCleanup(self.owner_patch.stop)
        with self.store.db() as c:c.execute('INSERT INTO campaigns VALUES (?,?,?,?,?,?)',('visual-commands',json.dumps(DEFAULT),'paused',1,0,stamp()))
        self.api=FakeAPI();self.engine=Engine(self.store,self.api)
        self.store.set_setting('password',password_hash('valid-test-password'))
    def tearDown(self): self.temp.cleanup()
    def activate(self,status='test'):
        c=self.store.campaigns()[0];self.store.status(c['id'],status,c['revision']);self.api.created=stamp()
    def event(self,key='123456',sender=None,media=None): return {'event_key':'comment:'+key,'kind':'comment','sender':sender or self.api.sender,'media':media or DEFAULT['media'][0],'comment':key,'action':'','event_at':stamp(),'received_at':stamp()}
    def continuation(self,sender=None,event_at=None,action=None):
        with self.store.db() as c: f=dict(c.execute('SELECT * FROM flows').fetchone())
        return {'event_key':'continue'+str(event_at)+str(sender),'kind':'continue','sender':sender or self.api.sender,'action':action or 'GO:'+f['id'],'event_at':event_at or stamp(),'received_at':stamp(),'comment':'','media':''}
    def test_paused_test_scope_and_media(self):
        self.engine.handle(self.event());self.assertFalse(self.api.sent)
        self.activate()
        self.engine.handle(self.event('111111',sender='999999'));self.engine.handle(self.event('222222',media='999999'))
        self.assertFalse(self.api.sent)
        self.engine.handle(self.event('333333'));self.assertEqual(len(self.api.sent),1)
    def test_full_flow_requires_matching_postback_and_dedup(self):
        self.activate();event=self.event();self.engine.handle(event);self.engine.handle(event)
        self.assertEqual(len(self.api.sent),1)
        self.engine.handle(self.continuation(sender='999999'))
        self.assertEqual(len(self.api.sent),1)
        e=self.continuation();self.engine.handle(e);self.engine.handle(e)
        self.assertEqual(len(self.api.sent),2)
        self.assertEqual(self.api.sent[1][1]['attachment']['payload']['buttons'][0]['url'],DEFAULT['second_url'])
    def test_edit_and_pause_cancel_followup(self):
        self.activate();self.engine.handle(self.event())
        c=self.store.campaigns()[0];self.store.save(c['id'],DEFAULT,c['revision'])
        self.engine.handle(self.continuation());self.assertEqual(len(self.api.sent),1)
        self.assertEqual(self.store.campaigns()[0]['status'],'paused')
    def test_old_comment_and_response_not_sent(self):
        self.activate();self.api.created=stamp()-100
        self.engine.handle(self.event());self.assertFalse(self.api.sent)
        self.api.created=stamp();self.engine.handle(self.event('222222'))
        self.engine.handle(self.continuation(event_at=stamp()-86401));self.assertEqual(len(self.api.sent),1)
    def test_unknown_delivery_not_retried_on_new_comment(self):
        self.activate();self.api.outcome=False
        self.engine.handle(self.event());self.engine.handle(self.event('222222'))
        self.assertEqual(len(self.api.sent),1)
        self.assertEqual(self.store.dashboard()['counts']['review'],1)
    def test_daily_limit_and_public_account(self):
        cfg=dict(DEFAULT,daily_limit=1)
        c=self.store.campaigns()[0];self.store.save(c['id'],cfg,c['revision']);self.activate('active')
        self.api.sender='999999';self.engine.handle(self.event())
        self.api.sender='888888';self.engine.handle(self.event('222222'))
        self.assertEqual(len(self.api.sent),1)
    def test_no_second_message_when_disabled(self):
        c=self.store.campaigns()[0];self.store.save(c['id'],dict(DEFAULT,second_enabled=False),c['revision']);self.activate()
        self.engine.handle(self.event());self.engine.handle(self.continuation())
        self.assertEqual(len(self.api.sent),1)
        self.assertEqual(len(self.api.sent[0][1]['attachment']['payload']['buttons']),1)
    def test_queue_privacy_and_echo(self):
        with closing(sqlite3.connect(':memory:')) as c,c:
            init_go_queue(c)
            payload={'entry':[{'id':'100000000000001','changes':[{'field':'comments','value':{'id':'123456','from':{'id':'999999'},'media':{'id':'222222'},'text':'private-content'}}],'messaging':[{'sender':{'id':'999999'},'recipient':{'id':'100000000000001'},'timestamp':stamp()*1000,'message':{'is_echo':True,'text':'private-dm'},'postback':{'payload':'GO:'+'a'*32}}]}]}
            queue_go_events(c,payload);queue_go_events(c,payload)
            rows=c.execute('SELECT * FROM go_events').fetchall();self.assertEqual(len(rows),1);self.assertNotIn('private',str(rows))
    def test_validation_and_conflict(self):
        self.assertTrue(matches('Quero VÍDEO!',['video']));self.assertFalse(matches('microcomando',['COMANDO']))
        with self.assertRaises(ValueError):validate(dict(DEFAULT,link_url='javascript:alert(1)'))
        with self.assertRaises(ValueError):validate(dict(DEFAULT,media=[]))
        self.activate();other=self.store.save(None,DEFAULT)
        with self.assertRaises(ValueError):self.store.status(other,'active',1)
        with self.assertRaises(ValueError):self.store.save('visual-commands',DEFAULT,1)
    def test_backup_is_readable_and_daily(self):
        daily_backup(self.store);daily_backup(self.store)
        files=list((Path(self.temp.name)/'backups').glob('*.sqlite'))
        self.assertEqual(len(files),1)
        with closing(sqlite3.connect(files[0])) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM campaigns').fetchone()[0],1)
    def request(self,path,method='GET',data=None,cookie='',csrf='',origin='https://example.test'):
        app=make_app(self.store,'https://example.test',api_factory=FakeAPI)
        raw=json.dumps(data or {}).encode();status=[];headers=[]
        env={'PATH_INFO':path,'REQUEST_METHOD':method,'wsgi.input':io.BytesIO(raw),'CONTENT_LENGTH':str(len(raw)),'CONTENT_TYPE':'application/json','HTTP_ORIGIN':origin,'HTTP_COOKIE':cookie,'HTTP_X_CSRF_TOKEN':csrf}
        def start(s,h):status.append(int(s.split()[0]));headers.extend(h)
        body=b''.join(app(env,start))
        return status[0],dict(headers),json.loads(body)
    def test_auth_csrf_password_logout(self):
        self.assertEqual(self.request('/api/dashboard')[0],401)
        self.assertEqual(self.request('/api/login','POST',{'username':'admin','password':'bad'})[0],401)
        s,h,b=self.request('/api/login','POST',{'username':'admin','password':'valid-test-password'})
        self.assertEqual(s,200);self.assertIn('HttpOnly',h['Set-Cookie']);self.assertIn('Secure',h['Set-Cookie'])
        cookie=h['Set-Cookie'].split(';')[0];csrf=b['csrf']
        self.assertEqual(self.request('/api/dashboard',cookie=cookie)[0],200)
        data={'id':'visual-commands','revision':1,'config':DEFAULT}
        self.assertEqual(self.request('/api/campaign/save','POST',data,cookie)[0],403)
        self.assertEqual(self.request('/api/campaign/save','POST',data,cookie,csrf,origin='https://evil.test')[0],403)
        self.assertEqual(self.request('/api/campaign/save','POST',data,cookie,csrf)[0],200)
        self.assertEqual(self.request('/api/password','POST',{'current':'valid-test-password','password':'new-test-password'},cookie,csrf)[0],200)
        self.assertEqual(self.request('/api/dashboard',cookie=cookie)[0],401)
    def test_login_throttle(self):
        for _ in range(20):self.request('/api/login','POST',{'username':'admin','password':'bad'})
        self.assertEqual(self.request('/api/login','POST',{'username':'admin','password':'bad'})[0],429)
    def test_public_activation_requires_review_media_and_worker(self):
        _,h,b=self.request('/api/login','POST',{'username':'admin','password':'valid-test-password'})
        cookie=h['Set-Cookie'].split(';')[0];csrf=b['csrf'];data={'id':'visual-commands','revision':1,'status':'active'}
        self.assertEqual(self.request('/api/campaign/status','POST',data,cookie,csrf)[0],400)
        data['confirm']='ACTIVATE';self.assertEqual(self.request('/api/campaign/status','POST',data,cookie,csrf)[0],400)
        self.store.set_setting('media_cache',json.dumps({'items':[{'id':DEFAULT['media'][0]}]}))
        self.assertEqual(self.request('/api/campaign/status','POST',data,cookie,csrf)[0],400)
        self.store.set_setting('worker_at',stamp())
        self.assertEqual(self.request('/api/campaign/status','POST',data,cookie,csrf)[0],200)

if __name__=='__main__':unittest.main()
