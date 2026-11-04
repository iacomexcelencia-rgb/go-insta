"""Private dashboard and public signed webhook on a single HTTPS origin."""
import hashlib,hmac,html,json,os,re,sqlite3,time
from pathlib import Path
from contextlib import closing
from urllib.parse import parse_qs
from config import read_connection,read_install,account_id,origin
from go_app import make_app
from go_store import Store,stamp
from go_queue import init_go_queue,queue_go_events

def create_app(store,site_origin):
    private=make_app(store,site_origin,secure=os.environ.get('GO_SECURE','1')=='1')
    events_path=os.environ.get('GO_EVENTS','data/events.sqlite')
    Path(events_path).parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(events_path)) as db,db:init_go_queue(db)
    def app(env,start):
        path=env.get('PATH_INFO','/');method=env.get('REQUEST_METHOD','GET')
        def reply(code,text,kind='text/plain; charset=utf-8'):
            body=text.encode();start(str(code)+' '+{200:'OK',400:'Bad Request',403:'Forbidden',405:'Method Not Allowed',413:'Payload Too Large',503:'Service Unavailable'}[code],[('Content-Type',kind),('Content-Length',str(len(body))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer'),('Content-Security-Policy',"default-src 'none'; frame-ancestors 'none'")]);return [body]
        if path in ('/privacy','/data-deletion') and method=='GET':
            cfg=read_install();who=html.escape(cfg.get('operator','Responsável pela instalação'));contact=html.escape(cfg.get('contact_email','Contato não configurado'))
            text=(f'<h1>Privacidade — Go Insta!</h1><p>Esta instalação é operada por {who}. Contato: {contact}.</p><p>O responsável conecta a própria conta profissional à API oficial. São armazenados credenciais de conexão no servidor, estatísticas agregadas, legendas e identificadores de suas publicações, configurações de campanhas, identificadores dos participantes e histórico técnico de entregas. Mensagens privadas recebidas não são armazenadas integralmente. Registros comerciais são informados manualmente pelo operador.</p><p>Os dados são usados para análises e automações solicitadas pelo operador. A Meta processa as requisições à sua API; a infraestrutura é contratada pelo operador. O projeto público não recebe cópias destes dados. Eventos pendentes são retidos por até 30 dias; campanhas, estatísticas, entregas e backups permanecem até remoção pelo operador. Não insira dados pessoais de compradores nas observações de vendas.</p>' if path=='/privacy' else f'<h1>Solicitar exclusão de dados</h1><p>Entre em contato com {who}: {contact}. Informe seu identificador do Instagram e quais registros deseja excluir, sem enviar sua senha. O operador verificará o pedido e tratará também os backups aplicáveis. Para revogar o acesso à sua conta, remova este aplicativo nas configurações de aplicativos e sites do Instagram. Revogar acesso não apaga automaticamente os registros já salvos no servidor.</p>')
            return reply(200,'<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Go Insta!</title><body>'+text+'</body></html>','text/html; charset=utf-8')
        if path!='/webhooks/instagram':return private(env,start)
        cfg=read_install();connection=read_connection()
        if method=='GET':
            q=parse_qs(env.get('QUERY_STRING',''));verify=cfg.get('verify_token','');challenge=q.get('hub.challenge',[''])[0]
            if verify and q.get('hub.mode')==['subscribe'] and hmac.compare_digest(q.get('hub.verify_token',[''])[0].encode(),verify.encode()) and challenge.isascii() and challenge.isdigit() and len(challenge)<=100:
                store.set_setting('webhook_verified_at',stamp());return reply(200,challenge)
            return reply(403,'verification rejected')
        if method!='POST':return reply(405,'method rejected')
        try:length=int(env.get('CONTENT_LENGTH','0'))
        except ValueError:return reply(400,'invalid size')
        if not 0<length<=1048576:return reply(413,'invalid size')
        raw=env['wsgi.input'].read(length);secret=connection.get('app_secret','');signature=env.get('HTTP_X_HUB_SIGNATURE_256','')
        expected='sha256='+hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
        if len(raw)!=length or not secret or not signature.isascii() or not hmac.compare_digest(signature,expected):return reply(403,'signature rejected')
        try:
            payload=json.loads(raw)
            if not isinstance(payload,dict) or payload.get('object')!='instagram' or not isinstance(payload.get('entry'),list):raise ValueError()
            contacts=[];matched=False
            for entry in payload['entry']:
                if not isinstance(entry,dict):raise ValueError()
                if str(entry.get('id',''))!=account_id():continue
                matched=True
                if not isinstance(entry.get('changes',[]),list) or not isinstance(entry.get('messaging',[]),list):raise ValueError()
                for change in entry.get('changes',[]):
                    sender=change.get('value',{}).get('from',{});ident=str(sender.get('id',''));name=sender.get('username','')
                    if change.get('field')=='comments' and re.fullmatch(r'\d{5,35}',ident) and ident!=account_id():
                        contacts.append({'id':ident,'username':name if isinstance(name,str) and re.fullmatch(r'[\w.]{1,50}',name) else '', 'at':stamp()})
            with closing(sqlite3.connect(events_path,timeout=10)) as db,db:queue_go_events(db,payload)
            if matched:store.set_setting('webhook_event_at',stamp())
            if contacts:
                old=json.loads(store.setting('test_contacts','[]'));by_id={c['id']:c for c in old+contacts}
                store.set_setting('test_contacts',json.dumps(sorted(by_id.values(),key=lambda c:c['at'],reverse=True)[:30]))
        except (ValueError,TypeError,KeyError,AttributeError):return reply(400,'invalid event')
        except sqlite3.Error:return reply(503,'storage unavailable')
        return reply(200,'EVENT_RECEIVED')
    return app

def configured_app():
    return create_app(Store(os.environ.get('GO_DB','data/go.sqlite')),origin())
