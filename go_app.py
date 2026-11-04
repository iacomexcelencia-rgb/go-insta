"""Private Go Insta panel. Server-side sessions; strict origin+CSRF; no token in UI."""
import csv
import io
import json
import os
import secrets
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs
from go_store import Store, stamp, digest, password_hash, password_ok, DEFAULT
from instagram_api import Instagram
from config import account_id, read_connection, read_install, save_private, secrets_dir
from connection import public_status,connect,subscribe
from go_insights import init_analytics,analytics_payload,request_refresh,save_editorial,record_sale,export_csv

STATIC=Path(__file__).parent/'go-public'

def make_app(store,origin,base='',secure=True,api_factory=Instagram):
    init_analytics(store)
    def app(env,start_response):
        path=env.get('PATH_INFO','/')
        method=env.get('REQUEST_METHOD','GET')
        headers=[('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer'),('X-Frame-Options','DENY'),('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")]
        def reply(code,obj,kind='application/json; charset=utf-8',extra=None):
            raw=obj if isinstance(obj,bytes) else json.dumps(obj,ensure_ascii=False).encode()
            start_response(str(code)+' '+{200:'OK',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',409:'Conflict',429:'Too Many Requests',500:'Internal Server Error',503:'Service Unavailable'}.get(code,'Error'),headers+[('Content-Type',kind),('Content-Length',str(len(raw)))]+(extra or []))
            return [raw]
        cookie=SimpleCookie()
        try: cookie.load(env.get('HTTP_COOKIE',''))
        except Exception: pass
        token=cookie['go_session'].value if 'go_session' in cookie else ''
        with store.db() as c:
            session=c.execute('SELECT * FROM sessions WHERE hash=? AND expires>?',(digest(token),stamp())).fetchone() if token else None
        try:
            if method=='GET' and path in ('/','/index.html','/app.js','/style.css','/analytics.js','/analytics.css','/favicon.svg','/onboarding.js'):
                file={'/':'index.html'}.get(path,path[1:])
                kind={'html':'text/html','js':'text/javascript','css':'text/css','svg':'image/svg+xml'}[file.split('.')[-1]]
                return reply(200,(STATIC/file).read_bytes(),kind+'; charset=utf-8')
            if method=='GET' and path=='/health':
                return reply(200,{'ok':True})
            if method=='POST':
                if env.get('HTTP_ORIGIN')!=origin or env.get('CONTENT_TYPE','').split(';')[0]!='application/json':
                    return reply(403,{'error':'Origem da solicitação não permitida.'})
                length=int(env.get('CONTENT_LENGTH','0'))
                if not 0<length<=64000: raise ValueError('Solicitação inválida.')
                data=json.loads(env['wsgi.input'].read(length))
                if not isinstance(data,dict): raise ValueError('Solicitação inválida.')
                if path=='/api/login':
                    # Bounded login work even if source IP is behind the proxy.
                    with store.db() as c:
                        c.execute('BEGIN IMMEDIATE')
                        c.execute('DELETE FROM attempts WHERE at<?',(stamp()-900,))
                        count=c.execute('SELECT count(*) FROM attempts').fetchone()[0]
                        if count>=20: return reply(429,{'error':'Muitas tentativas. Aguarde 15 minutos.'})
                        c.execute('INSERT INTO attempts VALUES (?,?)',('login',stamp()))
                    saved=store.setting('password')
                    password=data.get('password','')
                    if not isinstance(password,str) or len(password)>256 or not saved or data.get('username')!=read_install().get('admin_username','admin') or not password_ok(password,saved):
                        return reply(401,{'error':'Usuário ou senha incorretos.'})
                    token=secrets.token_urlsafe(32)
                    csrf=secrets.token_urlsafe(32)
                    with store.db() as c:
                        c.execute('DELETE FROM attempts')
                        c.execute('DELETE FROM sessions WHERE expires<?',(stamp(),))
                        c.execute('INSERT INTO sessions VALUES (?,?,?)',(digest(token),csrf,stamp()+43200))
                    value=f'go_session={token}; HttpOnly; SameSite=Strict; Path={base}/; Max-Age=43200'+('; Secure' if secure else '')
                    return reply(200,{'ok':True,'csrf':csrf,'username':read_install().get('admin_username','admin')},extra=[('Set-Cookie',value)])
            if not session:
                return reply(401,{'error':'Entre para acessar o painel.'})
            if method=='POST' and not secrets.compare_digest(env.get('HTTP_X_CSRF_TOKEN',''),session['csrf']):
                return reply(403,{'error':'Sua sessão mudou. Recarregue a página.'})
            if method=='GET' and path=='/api/me':
                return reply(200,{'username':read_install().get('admin_username','admin'),'account':read_connection().get('username',''),'csrf':session['csrf']})
            if method=='GET' and path=='/api/connection':
                return reply(200,public_status(store,origin))
            if method=='POST' and path=='/api/connection':
                connect(store,data)
                return reply(200,public_status(store,origin))
            if method=='POST' and path=='/api/connection/subscribe':
                subscribe(store)
                return reply(200,public_status(store,origin))
            if method=='GET' and path=='/api/dashboard':
                return reply(200,store.dashboard())
            if method=='GET' and path=='/api/analytics':
                return reply(200,analytics_payload(store))
            if method=='POST' and path=='/api/analytics/refresh':
                return reply(200,{'job':request_refresh(store)})
            if method=='POST' and path=='/api/analytics/editorial':
                save_editorial(store,data)
                return reply(200,{'ok':True})
            if method=='POST' and path=='/api/analytics/sale':
                record_sale(store,data)
                return reply(200,{'ok':True})
            if method=='POST' and path=='/api/analytics/sale/void':
                ident=data.get('id')
                if type(ident) is not int:raise ValueError('Registro inválido.')
                with store.db() as c:
                    c.execute("UPDATE sales SET status='void' WHERE id=?",(ident,))
                return reply(200,{'ok':True})
            if method=='GET' and path=='/api/analytics/export':
                payload=analytics_payload(store)
                if parse_qs(env.get('QUERY_STRING','')).get('format')==['csv']:
                    return reply(200,export_csv(payload['snapshot'] or {}),'text/csv; charset=utf-8',extra=[('Content-Disposition','attachment; filename="go-insta-insights.csv"')])
                return reply(200,payload,extra=[('Content-Disposition','attachment; filename="go-insta-insights.json"')])
            if method=='GET' and path=='/api/media':
                cached=store.setting('media_cache')
                return reply(200,json.loads(cached) if cached else {'items':[],'at':0})
            if method=='POST' and path=='/api/media/refresh':
                api=api_factory()
                items=[]
                after=None
                for _ in range(10):
                    params={'fields':'id,caption,permalink,media_type,timestamp','limit':100}
                    if after: params['after']=after
                    r=api.get(account_id()+'/media',**params)
                    if not r.get('ok'): return reply(503,{'error':'A API não respondeu. As publicações salvas foram preservadas.'})
                    body=r.get('body',{})
                    items.extend({k:v for k,v in m.items() if k in ('id','caption','permalink','media_type','timestamp')} for m in body.get('data',[]))
                    after=body.get('paging',{}).get('cursors',{}).get('after')
                    if not after or not body.get('data'): break
                result={'items':items,'at':stamp()}
                store.set_setting('media_cache',json.dumps(result,ensure_ascii=False))
                return reply(200,result)
            if method=='POST' and path=='/api/campaign/save':
                cid=store.save(data.get('id'),data.get('config',{}),data.get('revision'))
                return reply(200,{'ok':True,'id':cid})
            if method=='POST' and path=='/api/campaign/status':
                if data.get('status')=='active' and data.get('confirm')!='ACTIVATE':
                    raise ValueError('Revise e confirme a ativação da campanha.')
                # Public activation requires the server to have the selected media in its account inventory.
                if data.get('status') in ('active','test'):
                    cfg=next((x['config'] for x in store.campaigns() if x['id']==data.get('id')),None)
                    cache=json.loads(store.setting('media_cache','{"items":[]}'))
                    known={x['id'] for x in cache['items']}
                    if not cfg or not set(cfg['media'])<=known:
                        raise ValueError('Atualize as publicações e selecione somente posts desta conta.')
                    if stamp()-int(store.setting('worker_at','0'))>30 or store.setting('worker_error',''):
                        raise ValueError('O serviço de envio não está pronto. Veja Conexão.')
                store.status(data.get('id'),data.get('status'),data.get('revision'))
                return reply(200,{'ok':True})
            if method=='POST' and path=='/api/password':
                current=data.get('current',''); new=data.get('password','')
                if not isinstance(current,str) or len(current)>256 or not password_ok(current,store.setting('password','')):
                    raise ValueError('Senha atual incorreta.')
                if not isinstance(new,str) or not 12<=len(new)<=128:
                    raise ValueError('Use uma senha de 12 a 128 caracteres.')
                with store.db() as c:
                    c.execute('UPDATE settings SET value=? WHERE key=?',(password_hash(new),'password'))
                    c.execute('DELETE FROM sessions')
                return reply(200,{'ok':True})
            if method=='POST' and path=='/api/logout':
                with store.db() as c: c.execute('DELETE FROM sessions WHERE hash=?',(digest(token),))
                return reply(200,{'ok':True},extra=[('Set-Cookie',f'go_session=; Path={base}/; Max-Age=0; HttpOnly; SameSite=Strict'+('; Secure' if secure else ''))])
            if method=='GET' and path=='/api/export':
                return reply(200,{'exported_at':stamp(),'campaigns':store.campaigns()},extra=[('Content-Disposition','attachment; filename="go-insta-campanhas.json"')])
            return reply(404,{'error':'Recurso não encontrado.'})
        except (ValueError,TypeError,KeyError) as e:
            return reply(400,{'error':str(e)[:200]})
        except Exception as e:
            print(json.dumps({'event':'go_panel_error','type':type(e).__name__}),flush=True)
            return reply(500,{'error':'Não foi possível concluir. Tente novamente.'})
    return app

def from_environment():
    from config import origin
    return make_app(Store(os.environ.get('GO_DB','data/go.sqlite')),origin(),'',os.environ.get('GO_SECURE','1')=='1')

if __name__=='__main__':
    from wsgiref.simple_server import make_server, WSGIRequestHandler
    class Quiet(WSGIRequestHandler):
        def log_message(self,*args): pass
    with make_server('127.0.0.1',8766,from_environment(),handler_class=Quiet) as server:
        server.serve_forever()
