"""Read-only discovery of an existing Hostinger Traefik route. No Docker mutations."""
import json,re,socket,subprocess,urllib.request
from urllib.parse import urlparse

BASE='/go-insta'
PREFIX='traefik.http.routers.'

def hostinger_origin(value):
    from setup_install import validate_origin
    value=value.strip().rstrip('/')
    if value.endswith(BASE):value=value[:-len(BASE)]
    value=validate_origin(value)
    if not urlparse(value).hostname.endswith('.hstgr.cloud'):
        raise ValueError('Cole o endereço HTTPS fornecido pela Hostinger, terminado em .hstgr.cloud.')
    return value

def docker(*args):
    try:return subprocess.run(['docker',*args],check=True,capture_output=True,text=True,timeout=30).stdout.strip()
    except (OSError,subprocess.SubprocessError):
        raise ValueError('Não foi possível consultar Docker. Execute na VPS com sudo e confira docker compose version.') from None

def inventory():
    # Only routing metadata, never container environment variables or mount contents.
    ids=docker('ps','-q').split()
    result=[]
    for ident in ids:
        labels=json.loads(docker('inspect','--format','{{json .Config.Labels}}',ident)) or {}
        networks=json.loads(docker('inspect','--format','{{json .NetworkSettings.Networks}}',ident)) or {}
        image=docker('inspect','--format','{{.Config.Image}}',ident)
        result.append({'labels':{k.lower():v for k,v in labels.items()},'networks':list(networks),'image':image})
    return result

def discover(containers,host):
    proxies=[c for c in containers if re.search(r'(^|/)traefik([:@]|$)',c['image'])]
    candidates=[]
    for c in containers:
        labels=c['labels']
        if labels.get('traefik.enable','true').lower()=='false':continue
        for key,rule in labels.items():
            if not (key.startswith(PREFIX) and key.endswith('.rule')):continue
            if host in rule and BASE in rule:
                raise ValueError('Já existe uma rota /go-insta para esse endereço. Atualize a instalação existente; não crie outra.')
            if not re.fullmatch(r'\s*Host\(\s*`'+re.escape(host)+r'`\s*\)\s*',rule):continue
            router=key[:-5]
            # Explicit TLS settings are required for automatic discovery; no guessed entrypoints.
            if labels.get(router+'.tls','').lower()!='true' and not labels.get(router+'.tls.certresolver'):continue
            entry=labels.get(router+'.entrypoints','')
            resolver=labels.get(router+'.tls.certresolver','')
            if not re.fullmatch(r'[A-Za-z0-9_-]+(?:,[A-Za-z0-9_-]+)*',entry):continue
            if resolver and not re.fullmatch(r'[A-Za-z0-9_-]+',resolver):continue
            priority=labels.get(router+'.priority','0')
            if not priority.isdigit() or int(priority)>100000000:continue
            for proxy in proxies:
                shared=set(c['networks'])&set(proxy['networks'])-{'bridge','host','none'}
                preferred=labels.get('traefik.docker.network')
                if preferred:shared=shared&{preferred}
                if len(shared)!=1:continue
                network=next(iter(shared))
                if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',network):continue
                candidates.append({'network':network,'entrypoints':entry,'resolver':resolver,'priority':max(1000,int(priority)+1)})
    if len(candidates)!=1:
        raise ValueError('Não encontrei uma única rota Traefik HTTPS compatível para esse hostname. Nada foi alterado. Veja docs/INSTALACAO.md; não reinstale sua VPS.')
    return candidates[0]

def compose_override(host,route):
    router=PREFIX+'goinsta-panel'
    labels={'traefik.enable':'true','traefik.docker.network':route['network'],
            router+'.rule':f'Host(`{host}`) && (Path(`{BASE}`) || PathPrefix(`{BASE}/`))',
            router+'.entrypoints':route['entrypoints'],router+'.tls':'true',
            router+'.priority':str(route['priority']),router+'.service':'goinsta-panel',
            'traefik.http.services.goinsta-panel.loadbalancer.server.port':'8766'}
    if route['resolver']:labels[router+'.tls.certresolver']=route['resolver']
    return {'services':{'app':{'networks':['default','hostinger_proxy'],'labels':labels}},
            'networks':{'hostinger_proxy':{'external':True,'name':route['network']}}}

def preflight(site_origin):
    docker('compose','version')
    if docker('ps','-aq','--filter','label=com.docker.compose.project=go-insta'):
        raise ValueError('Já existem containers do projeto go-insta. Use a pasta original para atualizar.')
    try:
        with socket.socket() as probe:probe.bind(('127.0.0.1',18766))
    except OSError:raise ValueError('A porta local 18766 já está em uso. Não pare outros serviços para continuar.') from None
    route=discover(inventory(),urlparse(site_origin).hostname)
    verify_https(site_origin)
    return compose_override(urlparse(site_origin).hostname,route)

def verify_https(site_origin):
    try:
        with urllib.request.urlopen(site_origin+'/',timeout=20) as response:
            final=urlparse(response.url)
            if final.scheme!='https' or final.hostname!=urlparse(site_origin).hostname:raise ValueError()
    except Exception:
        raise ValueError('O HTTPS existente não pôde ser validado. Abra o n8n pelo endereço correto e resolva DNS/certificado antes de instalar. Não desative a validação TLS.') from None
