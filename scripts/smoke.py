"""Synthetic empty installation smoke test for CI, never run in an existing install."""
import io,json,os,ssl,sys,time,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from setup_install import main as setup
from config import read_install

def prepare():
    if Path('data/go.sqlite').exists() or Path('secrets/installation.json').exists():raise SystemExit('Refusing to overwrite an existing installation')
    mode=sys.argv[2] if len(sys.argv)>2 else 'root'
    origin='https://n8n.srv123456.hstgr.cloud' if mode=='hostinger' else 'https://insta.example.com'
    with patch('builtins.input',side_effect=[origin,'admin','Synthetic CI operator','demo@example.com']),patch('getpass.getpass',return_value='synthetic-ci-password-only'):
        if mode=='hostinger':
            # The isolated Traefik fixture has a self-signed cert, not public DNS/ACME.
            # Docker discovery and generated routing are real; public TLS is unit-tested separately.
            with patch('hostinger.verify_https'):setup('hostinger')
        else:setup('proxy')

def check():
    cfg=read_install();base=cfg.get('base_path','');root='http://127.0.0.1:18766'+base
    with urllib.request.urlopen(root+'/health',timeout=10) as r:assert json.load(r)['ok'] is True
    try:urllib.request.urlopen(root+'/api/dashboard',timeout=10)
    except urllib.error.HTTPError as e:assert e.code==401
    else:raise AssertionError('Dashboard exposed without login')
    req=urllib.request.Request(root+'/api/login',data=json.dumps({'username':'admin','password':'synthetic-ci-password-only'}).encode(),headers={'Origin':cfg['origin'],'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=10) as r:cookie=r.headers['Set-Cookie'].split(';')[0];assert json.load(r)['ok'] is True
    for path,key,expected in [('dashboard','campaigns',[]),('connection','connected',False)]:
        with urllib.request.urlopen(urllib.request.Request(root+'/api/'+path,headers={'Cookie':cookie}),timeout=10) as r:assert json.load(r)[key]==expected
    print('HTTP health, authentication, empty campaigns and disconnected account: OK (synthetic only).')
    if base:check_proxy(cfg)

def check_proxy(cfg):
    # Only this hardcoded loopback fixture uses an unverified certificate. The installer never does.
    context=ssl._create_unverified_context()
    def fetch(path,data=None,cookie=''):
        headers={'Host':'n8n.srv123456.hstgr.cloud','Origin':cfg['origin'],'Content-Type':'application/json'}
        if cookie:headers['Cookie']=cookie
        req=urllib.request.Request('https://127.0.0.1:18443'+path,data=data,headers=headers)
        return urllib.request.urlopen(req,context=context,timeout=10)
    for attempt in range(20):
        try:
            with fetch('/go-insta/health') as r:assert json.load(r)['ok'] is True
            break
        except (urllib.error.URLError,AssertionError):
            if attempt==19:raise
            time.sleep(1)
    for path in ['/','/go-instax/']:
        with fetch(path) as r:assert b'Hostname:' in r.read(),'Existing root site was intercepted'
    for path in ['/go-insta/','/go-insta/app.js','/go-insta/privacy','/go-insta/data-deletion']:
        with fetch(path) as r:assert r.status==200 and b'Hostname:' not in r.read()
    raw=json.dumps({'username':'admin','password':'synthetic-ci-password-only'}).encode()
    with fetch('/go-insta/api/login',raw) as r:
        cookie=r.headers['Set-Cookie'];assert 'Path=/go-insta/' in cookie
        assert json.load(r)['ok'] is True
    with fetch('/go-insta/api/connection',cookie=cookie.split(';')[0]) as r:
        assert json.load(r)['webhook_url']==cfg['origin']+'/go-insta/webhooks/instagram'
    with fetch('/go-insta/webhooks/instagram?hub.mode=subscribe&hub.verify_token='+cfg['verify_token']+'&hub.challenge=123') as r:
        assert r.read()==b'123'
    print('Real Traefik proxy: root website preserved; prefixed login, assets, public URLs and webhook challenge: OK.')

if __name__=='__main__':{'prepare':prepare,'check':check}[sys.argv[1]]()
