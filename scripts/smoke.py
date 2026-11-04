"""Synthetic empty installation smoke test for CI, never run in an existing install."""
import io,json,os,sys,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from setup_install import main as setup

def prepare():
    if Path('data/go.sqlite').exists() or Path('secrets/installation.json').exists():raise SystemExit('Refusing to overwrite an existing installation')
    with patch('builtins.input',side_effect=['https://insta.example.com','admin','Synthetic CI operator','demo@example.com']),patch('getpass.getpass',return_value='synthetic-ci-password-only'):
        setup()

def check():
    root='http://127.0.0.1:18766'
    with urllib.request.urlopen(root+'/health',timeout=10) as r:assert json.load(r)['ok'] is True
    try:urllib.request.urlopen(root+'/api/dashboard',timeout=10)
    except urllib.error.HTTPError as e:assert e.code==401
    else:raise AssertionError('Dashboard exposed without login')
    req=urllib.request.Request(root+'/api/login',data=json.dumps({'username':'admin','password':'synthetic-ci-password-only'}).encode(),headers={'Origin':'https://insta.example.com','Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=10) as r:cookie=r.headers['Set-Cookie'].split(';')[0];assert json.load(r)['ok'] is True
    for path,key,expected in [('dashboard','campaigns',[]),('connection','connected',False)]:
        with urllib.request.urlopen(urllib.request.Request(root+'/api/'+path,headers={'Cookie':cookie}),timeout=10) as r:assert json.load(r)[key]==expected
    print('HTTP health, authentication, empty campaigns and disconnected account: OK (synthetic only).')

if __name__=='__main__':{'prepare':prepare,'check':check}[sys.argv[1]]()
