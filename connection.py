"""Connect the operator's own Meta app; tokens never leave the backend."""
import json,re,time,urllib.parse,urllib.request
from config import read_connection,read_install,save_private,secrets_dir,account_id
from instagram_api import Instagram,NoRedirect
from go_store import stamp

FIELDS='comments,messages,messaging_postbacks'

def public_status(store,origin):
    c=read_connection();install=read_install()
    return {'connected':bool(c.get('token')),'username':c.get('username',''),'account_id':c.get('account_id',''),
            'name':c.get('name',''),'app_id':c.get('app_id',''),'connected_at':c.get('connected_at',0),
            'last_verified':c.get('last_verified',0),'last_refresh':c.get('last_refresh',0),'refresh_error':c.get('refresh_error',''),
            'webhook_url':origin+'/webhooks/instagram','verify_token':install.get('verify_token',''),
            'privacy_url':origin+'/privacy','deletion_url':origin+'/data-deletion',
            'subscribed':c.get('subscribed',False),'subscription_error':c.get('subscription_error',''),
            'webhook_verified_at':int(store.setting('webhook_verified_at','0')),
            'webhook_event_at':int(store.setting('webhook_event_at','0')),
            'test_contacts':json.loads(store.setting('test_contacts','[]')),
            'token_policy':'A renovação é tentada após 20 dias. Revogação, senha alterada ou permissões removidas podem exigir reconexão.'}

def connect(store,data,api_factory=Instagram):
    app_id=str(data.get('app_id',''));secret=data.get('app_secret','');token=data.get('token','')
    if not re.fullmatch(r'\d{5,35}',app_id):raise ValueError('Informe o ID do aplicativo Instagram, encontrado na configuração da API na Meta.')
    if not isinstance(secret,str) or not re.fullmatch(r'[a-fA-F0-9]{32,128}',secret):raise ValueError('Informe a chave secreta do aplicativo Instagram. Não use a chave de outro app.')
    if not isinstance(token,str) or not 40<=len(token)<=4096 or any(c.isspace() for c in token):raise ValueError('Token inválido. Gere um token de usuário Instagram no painel da Meta.')
    result=api_factory(token=token).get('me',fields='id,user_id,username,name,account_type')
    profile=result.get('body',{})
    mid=str(profile.get('user_id',''));username=profile.get('username','')
    if not result.get('ok') or not re.fullmatch(r'\d{5,35}',mid) or not isinstance(username,str) or not username:
        raise ValueError('O token não validou uma conta Instagram. Confira a opção API com login do Instagram e as permissões.')
    if profile.get('account_type') not in ('BUSINESS','MEDIA_CREATOR','CREATOR'):
        raise ValueError('Conecte uma conta profissional do Instagram (empresa ou criador).')
    # A persistent owner prevents accidental mixing even if the token file is lost.
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        previous=read_connection();owner=db.execute("SELECT value FROM settings WHERE key='owner_account'").fetchone()
        bound=owner['value'] if owner else previous.get('account_id')
        if bound and str(bound)!=mid:raise ValueError('Esta instalação pertence a outra conta. Use uma instalação e banco separados para o novo perfil.')
        value={'app_id':app_id,'app_secret':secret,'token':token,'account_id':mid,'username':username,'name':profile.get('name',''),
               'connected_at':stamp(),'last_verified':stamp(),'last_refresh':stamp(),'subscribed':False,'subscription_error':'Ainda não configurado.'}
        save_private(secrets_dir()/'instagram.json',value)
        db.execute("INSERT OR REPLACE INTO settings VALUES ('owner_account',?)",(mid,))
        db.execute("UPDATE campaigns SET status='paused',revision=revision+1,updated=?",(stamp(),))
        db.execute("INSERT OR REPLACE INTO settings VALUES ('webhook_event_at','0')")
        db.execute("INSERT OR REPLACE INTO settings VALUES ('webhook_verified_at','0')")
    store.activity('','connection','Conta verificada e conexão salva. Campanhas permanecem pausadas.')

def subscribe(store):
    c=read_connection()
    if not c.get('token'):raise ValueError('Conecte o Instagram primeiro.')
    api=Instagram(token=c['token']);req=urllib.request.Request('https://graph.instagram.com/'+api.version+'/'+c['account_id']+'/subscribed_apps',
        data=urllib.parse.urlencode({'subscribed_fields':FIELDS}).encode(),method='POST',
        headers={'Authorization':'Bearer '+api.token,'Content-Type':'application/x-www-form-urlencoded'})
    try:
        with api.opener.open(req,timeout=30) as r:ok=json.load(r).get('success') is True
    except Exception:ok=False
    # Preserve a connection changed while the request was in flight.
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        latest=read_connection()
        if latest.get('token')!=c['token']:raise ValueError('A conexão mudou. Recarregue o painel.')
        latest.update(subscribed=ok,subscription_error='' if ok else 'A Meta não confirmou a assinatura. Confira campos, webhook e permissões do seu app.')
        save_private(secrets_dir()/'instagram.json',latest)
    if not ok:raise ValueError(latest['subscription_error'])
    store.activity('','connection','Assinatura de eventos confirmada pela API. Faça um teste real para conferir a entrega.')

def refresh_if_due(store):
    c=read_connection();now=stamp()
    if not c.get('token') or now-c.get('last_refresh',now)<20*86400 or now-c.get('refresh_attempt',0)<86400:return
    query=urllib.parse.urlencode({'grant_type':'ig_refresh_token','access_token':c['token']})
    try:
        opener=urllib.request.build_opener(NoRedirect)
        with opener.open('https://graph.instagram.com/refresh_access_token?'+query,timeout=45) as r:out=json.load(r)
        new=out.get('access_token','')
        if not isinstance(new,str) or not 40<=len(new)<=4096:raise ValueError('Invalid response')
        result=Instagram(token=new).get('me',fields='user_id,username')
        if not result.get('ok') or str(result['body'].get('user_id'))!=c['account_id']:raise ValueError('Wrong account')
        with store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            latest=read_connection()
            if latest.get('token')!=c['token']:return
            latest.update(token=new,last_refresh=now,last_verified=now,refresh_attempt=now,refresh_error='')
            save_private(secrets_dir()/'instagram.json',latest)
    except Exception:
        with store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            latest=read_connection()
            if latest.get('token')==c['token']:
                latest.update(refresh_attempt=now,refresh_error='Não foi possível renovar. Gere um novo token no seu app Meta e reconecte a mesma conta.')
                save_private(secrets_dir()/'instagram.json',latest)
