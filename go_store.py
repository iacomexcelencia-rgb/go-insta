"""Go Insta persistent configuration, sessions and auditable delivery state."""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

def stamp():
    return int(time.time())

def digest(s):
    return hashlib.sha256(s.encode()).hexdigest()

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()

def password_ok(password, encoded):
    try:
        return hmac.compare_digest(password_hash(password,encoded.split(':')[0]), encoded)
    except (ValueError, TypeError):
        return False

def normalized(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s.casefold()) if unicodedata.category(c) != 'Mn')

def matches(text, keywords):
    return any(re.search(r'(?<!\w)'+re.escape(normalized(k))+r'(?!\w)', normalized(text)) for k in keywords)

def safe_url(value):
    p = urlparse(value)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or len(value) > 1500 or any(ord(c)<33 for c in value):
        raise ValueError('Use um link HTTPS válido, sem espaços.')
    return value

DEFAULT = {
    'name':'Minha campanha', 'keywords':['QUERO'], 'media':[], 'test_user':'',
    'first_text':'Olá! Aqui está o conteúdo que você pediu.',
    'link_title':'Abrir conteúdo', 'link_url':'https://example.com/',
    'continue_title':'Recebi o link', 'second_enabled':False,
    'second_text':'Acompanhe nosso perfil para receber mais conteúdos.',
    'second_title':'Ir para o perfil', 'second_url':'https://www.instagram.com/', 'daily_limit':100,
}


def validate(data):
    out = {}
    limits = {'name':80,'first_text':640,'link_title':21,'continue_title':20,'second_text':640,'second_title':20}
    for key, limit in limits.items():
        value = data.get(key)
        if not isinstance(value,str) or not value.strip() or len(value.strip()) > limit:
            raise ValueError(f'Campo {key}: preencha entre 1 e {limit} caracteres.')
        out[key] = value.strip()
    for key in ('link_url','second_url'):
        out[key] = safe_url(str(data.get(key,'')))
    words = data.get('keywords')
    if not isinstance(words,list) or not 1 <= len(words) <= 10 or any(not isinstance(x,str) or not 1<=len(x.strip())<=40 for x in words):
        raise ValueError('Defina de 1 a 10 palavras-chave, com até 40 caracteres cada.')
    out['keywords'] = list(dict.fromkeys(x.strip() for x in words))
    media = data.get('media')
    if not isinstance(media,list) or not 1<=len(media)<=50 or any(not isinstance(x,str) or not re.fullmatch(r'\d{5,35}',x) for x in media):
        raise ValueError('Selecione de 1 a 50 publicações.')
    out['media'] = list(dict.fromkeys(media))
    if not isinstance(data.get('test_user'),str) or not re.fullmatch(r'\d{5,35}',data['test_user']):
        raise ValueError('Informe o identificador da conta de teste.')
    out['test_user'] = data['test_user']
    if type(data.get('daily_limit')) is not int or not 1 <= data['daily_limit'] <= 1000:
        raise ValueError('Defina um limite diário entre 1 e 1.000 conversas.')
    out['daily_limit'] = data['daily_limit']
    if type(data.get('second_enabled')) is not bool:
        raise ValueError('Defina se a segunda mensagem está habilitada.')
    out['second_enabled'] = data['second_enabled']
    return out

class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.db() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (hash TEXT PRIMARY KEY,csrf TEXT,expires INTEGER);
            CREATE TABLE IF NOT EXISTS attempts (bucket TEXT,at INTEGER);
            CREATE TABLE IF NOT EXISTS campaigns (id TEXT PRIMARY KEY,config TEXT NOT NULL,status TEXT NOT NULL,revision INTEGER NOT NULL,activated INTEGER NOT NULL,updated INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS flows (id TEXT PRIMARY KEY,campaign TEXT,sender TEXT,comment TEXT UNIQUE,config TEXT,revision INTEGER,mode TEXT,stage TEXT,created INTEGER,interacted INTEGER);
            CREATE TABLE IF NOT EXISTS sends (id TEXT PRIMARY KEY,flow TEXT,step TEXT,state TEXT,http INTEGER,code TEXT,at INTEGER);
            CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY AUTOINCREMENT,campaign TEXT,kind TEXT,detail TEXT,at INTEGER);
            CREATE TABLE IF NOT EXISTS processed (event_key TEXT PRIMARY KEY,at INTEGER);
            CREATE INDEX IF NOT EXISTS flows_sender ON flows(sender,created);
            CREATE INDEX IF NOT EXISTS activity_time ON activity(at);
            ''')
            from config import secrets_dir
            seed = str(secrets_dir()/'auth-seed.json')
            if seed and Path(seed).exists():
                account=json.loads(Path(seed).read_text())
                c.execute('INSERT OR IGNORE INTO settings VALUES (?,?)',('password',account['password_hash']))
            c.execute("INSERT OR IGNORE INTO settings VALUES ('cursor','0')")

    @contextmanager
    def db(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory=sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def setting(self,key,default=None):
        with self.db() as c:
            r=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
            return r['value'] if r else default

    def set_setting(self,key,value):
        with self.db() as c:
            c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(key,str(value)))

    def campaigns(self):
        with self.db() as c:
            return [dict(r,config=json.loads(r['config'])) for r in c.execute('SELECT * FROM campaigns ORDER BY updated DESC,id')]

    def save(self, cid, data, expected=None):
        cfg=validate(data)
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT * FROM campaigns WHERE id=?',(cid,)).fetchone() if cid else None
            if cid and not old:
                raise ValueError('Campanha não encontrada.')
            if old and old['revision'] != expected:
                raise ValueError('Esta campanha mudou em outra janela. Recarregue antes de salvar.')
            cid=cid or secrets.token_hex(8)
            revision=old['revision']+1 if old else 1
            # Editing always pauses and invalidates pending flows using older copy.
            c.execute('INSERT OR REPLACE INTO campaigns VALUES (?,?,?,?,?,?)',(cid,json.dumps(cfg,ensure_ascii=False),'paused',revision,0,stamp()))
            c.execute('INSERT INTO activity(campaign,kind,detail,at) VALUES (?,?,?,?)',(cid,'saved','Configuração salva; campanha pausada.',stamp()))
        return cid

    def status(self,cid,status,revision):
        if status not in ('paused','test','active'):
            raise ValueError('Estado inválido.')
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            r=c.execute('SELECT * FROM campaigns WHERE id=?',(cid,)).fetchone()
            if not r or r['revision'] != revision:
                raise ValueError('Recarregue a campanha antes de alterar o estado.')
            cfg=validate(json.loads(r['config']))
            if status != 'paused':
                for other in c.execute("SELECT * FROM campaigns WHERE status!='paused' AND id!=?",(cid,)):
                    o=json.loads(other['config'])
                    if set(cfg['media']) & set(o['media']) and {normalized(x) for x in cfg['keywords']} & {normalized(x) for x in o['keywords']}:
                        raise ValueError('Já existe uma campanha ligada com esta palavra-chave nesta publicação. Pause a outra primeiro.')
            # Each activation gets a new revision: no old message/comment can replay.
            c.execute('UPDATE campaigns SET status=?,revision=revision+1,activated=?,updated=? WHERE id=?',(status,stamp(),stamp(),cid))
            c.execute('INSERT INTO activity(campaign,kind,detail,at) VALUES (?,?,?,?)',(cid,status,{'paused':'Campanha pausada.','test':'Teste iniciado para a conta selecionada.','active':'Campanha ativada pelo administrador.'}[status],stamp()))

    def activity(self,cid,kind,detail):
        with self.db() as c:
            c.execute('INSERT INTO activity(campaign,kind,detail,at) VALUES (?,?,?,?)',(cid,kind,detail,stamp()))

    def dashboard(self):
        with self.db() as c:
            counts={r['state']:r['n'] for r in c.execute('SELECT state,count(*) n FROM sends GROUP BY state')}
            activity=[dict(r) for r in c.execute('SELECT * FROM activity ORDER BY id DESC LIMIT 100')]
            flows=c.execute("SELECT count(*) FROM sends WHERE step='first' AND state='sent'").fetchone()[0]
            interactions=c.execute('SELECT count(*) FROM flows WHERE interacted>0').fetchone()[0]
            per_campaign=[dict(r) for r in c.execute('SELECT campaign,count(*) conversations,sum(CASE WHEN interacted>0 THEN 1 ELSE 0 END) interactions FROM flows GROUP BY campaign')]
            recent=[dict(r) for r in c.execute('SELECT sends.step,sends.state,sends.http,sends.code,sends.at,flows.campaign,flows.mode FROM sends JOIN flows ON sends.flow=flows.id ORDER BY sends.at DESC LIMIT 100')]
        return {'counts':counts,'conversations':flows,'interactions':interactions,'activity':activity,'per_campaign':per_campaign,'recent':recent,'worker_at':int(self.setting('worker_at','0')),'worker_error':self.setting('worker_error',''),'campaigns':self.campaigns()}
