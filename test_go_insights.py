import io,json,csv,tempfile,unittest,os
from unittest.mock import patch
from pathlib import Path
from go_store import Store,stamp,password_hash
from go_insights import extract,derived,Collector,init_analytics,request_refresh,analytics_payload,save_editorial,record_sale,export_csv,archive_stories
from go_app import make_app

class InsightsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env_patch=patch.dict(os.environ,{'GO_SECRETS':str(Path(self.tmp.name)/'secrets')});self.env_patch.start();self.addCleanup(self.env_patch.stop)
        self.store=Store(Path(self.tmp.name)/'test.sqlite');init_analytics(self.store)
        self.snapshot={'profile':{'followers_count':100},'posts':[{'id':'123','caption':'=SUM(A1:A2)','metrics':{'reach':{'value':0}}}]}
        with self.store.db() as c:c.execute('INSERT INTO analytics_snapshots(at,payload) VALUES (?,?)',(stamp(),json.dumps(self.snapshot)))
    def tearDown(self):self.tmp.cleanup()
    def test_zero_missing_and_breakdowns(self):
        self.assertEqual(extract({'values':[{'value':0}]})['state'],'available')
        self.assertEqual(extract({'values':[{'value':0},{'value':0}]})['state'],'available')
        self.assertIsNone(extract({'values':[]})['value'])
        self.assertEqual(extract({'total_value':{'breakdowns':[{'results':[{'value':0}]}]}})['state'],'available')
    def test_units_and_denominators(self):
        m={k:{'value':v} for k,v in {'reach':100,'total_interactions':8,'shares':0,'ig_reels_avg_watch_time':16570,'ig_reels_video_view_total_time':3600000}.items()}
        d=derived(m);self.assertEqual(d['engagement_rate'],8);self.assertEqual(d['share_rate'],0);self.assertIsNone(d['save_rate']);self.assertEqual(d['watch_seconds'],16.57);self.assertEqual(d['watch_total_hours'],1)
        m['reach']['value']=0;self.assertIsNone(derived(m)['engagement_rate'])
    def test_bad_metric_does_not_lose_valid_metric(self):
        class API:
            def get(self,path,**kw):
                if kw['metric']=='reach':return {'ok':True,'body':{'data':[{'name':'reach','values':[{'value':9}]}]}}
                return {'ok':False,'body':{'error':{'code':100,'message':'unsupported'}}}
        out=Collector(API()).metrics('1/insights',['reach','bad']);self.assertEqual(out['reach']['value'],9);self.assertIsNone(out['bad']['value'])
    def test_rate_limit_aborts(self):
        class API:
            def get(self,*a,**kw):return {'ok':False,'body':{'error':{'code':4}}}
        with self.assertRaises(RuntimeError):Collector(API()).metrics('1/insights',['reach','views'])
    def test_refresh_dedup_and_cooldown(self):
        a=request_refresh(self.store);self.assertEqual(a['id'],request_refresh(self.store)['id'])
        with self.store.db() as c:c.execute("UPDATE analytics_jobs SET status='done'")
        with self.assertRaises(ValueError):request_refresh(self.store)
        self.assertEqual(analytics_payload(self.store)['snapshot'],self.snapshot)
    def test_editorial_validation_and_storage(self):
        save_editorial(self.store,{'media_id':'123','series':'IA no trabalho','theme':'Reuniões'})
        self.assertEqual(analytics_payload(self.store)['editorial']['123']['series'],'IA no trabalho')
        with self.assertRaises(ValueError):save_editorial(self.store,{'media_id':'unknown'})
        with self.assertRaises(ValueError):save_editorial(self.store,{'media_id':'123','series':'x'*81})
    def test_manual_sales_are_explicit_cents(self):
        sale={'media_id':'123','product':'Teste local','amount_cents':1990,'sold_at':'2026-01-01'}
        record_sale(self.store,sale);self.assertEqual(analytics_payload(self.store)['sales'][0]['amount_cents'],1990)
        for invalid in [True,19.90,-1,0]:
            with self.assertRaises(ValueError):record_sale(self.store,dict(sale,amount_cents=invalid))
        with self.assertRaises(ValueError):record_sale(self.store,dict(sale,sold_at='2999-01-01'))
    def test_csv_injection_and_null(self):
        rows=list(csv.DictReader(io.StringIO(export_csv(self.snapshot).decode('utf-8-sig'))))
        self.assertEqual(rows[0]['reach'],'0');self.assertEqual(rows[0]['views'],'');self.assertTrue(rows[0]['caption'].startswith("'="))
    def test_story_archive_preserved_when_empty(self):
        archive_stories(self.store,[{'id':'456','metrics':{'reach':{'value':10}}}],True)
        archive_stories(self.store,[],True)
        self.assertEqual(len(analytics_payload(self.store)['story_archive']),1)
    def request(self,path,method='GET',data=None,cookie='',csrf=''):
        app=make_app(self.store,'https://example.test');raw=json.dumps(data or {}).encode();status=[];headers=[]
        env={'PATH_INFO':path,'REQUEST_METHOD':method,'wsgi.input':io.BytesIO(raw),'CONTENT_LENGTH':str(len(raw)),'CONTENT_TYPE':'application/json','HTTP_ORIGIN':'https://example.test','HTTP_COOKIE':cookie,'HTTP_X_CSRF_TOKEN':csrf}
        def start(s,h):status.append(int(s.split()[0]));headers.extend(h)
        body=b''.join(app(env,start));return status[0],dict(headers),json.loads(body)
    def test_analytics_auth_csrf_and_sale_void(self):
        for path in ['/api/analytics','/api/analytics/export']:self.assertEqual(self.request(path)[0],401)
        self.store.set_setting('password',password_hash('valid-test-password'))
        _,h,b=self.request('/api/login','POST',{'username':'admin','password':'valid-test-password'});cookie=h['Set-Cookie'].split(';')[0];csrf=b['csrf']
        self.assertEqual(self.request('/api/analytics',cookie=cookie)[0],200)
        self.assertEqual(self.request('/api/analytics/refresh','POST',{},cookie)[0],403)
        sale={'product':'Teste local','amount_cents':1990,'sold_at':'2026-01-01'}
        self.assertEqual(self.request('/api/analytics/sale','POST',sale,cookie,csrf)[0],200)
        self.assertEqual(self.request('/api/analytics/sale/void','POST',{'id':1},cookie,csrf)[0],200)
        self.assertEqual(analytics_payload(self.store)['sales'][0]['status'],'void')

if __name__=='__main__':unittest.main()
