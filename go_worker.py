"""One serial campaign worker; no ambiguous sends are retried automatically."""
import json
import os
import secrets
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path
from contextlib import closing
from datetime import datetime, timezone
from instagram_api import Instagram
from config import account_id, read_connection, read_install, save_private, secrets_dir
from go_store import Store, stamp, matches

def message(config, flow, second=False):
    if second:
        text=config['second_text']
        buttons=[{'type':'web_url','title':config['second_title'],'url':config['second_url']}]
    else:
        text=config['first_text']
        buttons=[{'type':'web_url','title':config['link_title'],'url':config['link_url']}]
        if config['second_enabled']:
            buttons.append({'type':'postback','title':config['continue_title'],'payload':'GO:'+flow})
    return {'attachment':{'type':'template','payload':{'template_type':'button','text':text,'buttons':buttons}}}

class CampaignAPI(Instagram):
    def send(self,recipient,message):
        if set(recipient) not in ({'id'},{'comment_id'}) or not all(str(x).isdigit() for x in recipient.values()):
            raise ValueError('Invalid recipient')
        req=urllib.request.Request('https://graph.instagram.com/'+self.version+'/'+account_id()+'/messages',
            data=json.dumps({'recipient':recipient,'message':message}).encode(),method='POST',
            headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
        try:
            with self.opener.open(req,timeout=25) as response:
                body=json.load(response)
                return {'ok':bool(body.get('message_id')),'status':response.status,'code':''}
        except urllib.error.HTTPError as e:
            try: code=str(json.load(e).get('error',{}).get('code','HTTP'))
            except (ValueError,TypeError): code='HTTP'
            return {'ok':False,'status':e.code,'code':code}
        except (OSError,TimeoutError,ValueError):
            return {'ok':False,'status':None,'code':'unknown'}

class Engine:
    def __init__(self,store,api):
        self.store,self.api=store,api

    def send(self,flow,second=False):
        now=stamp()
        step='second' if second else 'first'
        key=flow['id']+':'+step
        with self.store.db() as c:
            c.execute('BEGIN IMMEDIATE')
            campaign=c.execute('SELECT * FROM campaigns WHERE id=?',(flow['campaign'],)).fetchone()
            if not campaign or campaign['revision']!=flow['revision'] or campaign['status'] not in ('test','active'):
                return
            cfg=json.loads(flow['config'])
            if campaign['status']=='test' and flow['sender']!=cfg['test_user']:
                return
            if second and (not flow['interacted'] or not flow['created']<=flow['interacted']<=now+60 or now-flow['interacted']>=86400):
                return
            if not second and now-flow['created']>=7*86400:
                return
            if c.execute('SELECT 1 FROM sends WHERE id=?',(key,)).fetchone():
                return
            c.execute('INSERT INTO sends VALUES (?,?,?,?,?,?,?)',(key,flow['id'],step,'sending',None,'',now))
        # Commit claim before transport. A crash becomes visible, never a duplicate.
        result=self.api.send({'id':flow['sender']} if second else {'comment_id':flow['comment']},message(cfg,flow['id'],second))
        state='sent' if result.get('ok') else 'review'
        stage=('done' if second or not cfg['second_enabled'] else 'waiting') if state=='sent' else 'review'
        with self.store.db() as c:
            c.execute('UPDATE sends SET state=?,http=?,code=? WHERE id=?',(state,result.get('status'),str(result.get('code',''))[:50],key))
            c.execute('UPDATE flows SET stage=? WHERE id=?',(stage,flow['id']))
        label='Segunda mensagem' if second else 'Primeira mensagem'
        detail=label+' aceita pela API.' if state=='sent' else label+' sem confirmação. Verifique no Instagram antes de repetir. Código: '+str(result.get('code',''))
        self.store.activity(flow['campaign'],state,detail)

    def handle(self,event):
        now=stamp()
        with self.store.db() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT 1 FROM processed WHERE event_key=?',(event['event_key'],)).fetchone():
                return
            c.execute('INSERT INTO processed VALUES (?,?)',(event['event_key'],now))
        if event['kind']=='continue':
            with self.store.db() as c:
                f=c.execute('SELECT * FROM flows WHERE id=?',(event['action'][3:],)).fetchone()
                if not f or f['sender']!=event['sender'] or f['stage']!='waiting' or not f['created']<=event['event_at']<=now+60 or now-event['event_at']>=86400:
                    return
                c.execute('UPDATE flows SET interacted=? WHERE id=?',(event['event_at'],f['id']))
                f=dict(f,interacted=event['event_at'])
            self.send(f,True)
            return
        candidates=[c for c in self.store.campaigns() if c['status'] in ('active','test') and event['received_at']>=c['activated'] and event['media'] in c['config']['media'] and (c['status']=='active' or event['sender']==c['config']['test_user'])]
        if not candidates:
            return
        result=self.api.get(event['comment'],fields='id,timestamp,from,text')
        if not result.get('ok'):
            self.store.activity('', 'review','Não foi possível conferir um comentário na API. Nenhuma mensagem enviada.')
            return
        v=result.get('body',{})
        try: created=datetime.fromisoformat(v['timestamp'].replace('Z','+00:00')).timestamp()
        except (KeyError,TypeError,ValueError): return
        if str(v.get('from',{}).get('id'))!=event['sender'] or not now-7*86400<created<=now+60:
            return
        for campaign in candidates:
            if created<campaign['activated'] or not matches(str(v.get('text','')),campaign['config']['keywords']):
                continue
            cid=campaign['id']
            fid=secrets.token_hex(16)
            with self.store.db() as c:
                c.execute('BEGIN IMMEDIATE')
                # Real campaigns: 24h across campaigns. Explicit test mode: 60s.
                cooldown=60 if campaign['status']=='test' else 86400
                if c.execute('SELECT 1 FROM flows WHERE comment=? OR (sender=? AND created>?)',(event['comment'],event['sender'],now-cooldown)).fetchone():
                    self_note='Comentário reconhecido; conversa recente. Intervalo: '+('60 segundos no teste.' if campaign['status']=='test' else '24 horas no público.')
                    c.execute('INSERT INTO activity(campaign,kind,detail,at) VALUES (?,?,?,?)',(cid,'skipped',self_note,now))
                    return
                count=c.execute('SELECT count(*) FROM flows WHERE campaign=? AND created>?',(cid,now-86400)).fetchone()[0]
                if count>=campaign['config']['daily_limit']:
                    c.execute('INSERT INTO activity(campaign,kind,detail,at) VALUES (?,?,?,?)',(cid,'limit','Limite de conversas em 24 horas atingido. Comentário não enviado.',now))
                    return
                c.execute('INSERT INTO flows VALUES (?,?,?,?,?,?,?,?,?,?)',(fid,cid,event['sender'],event['comment'],json.dumps(campaign['config']),campaign['revision'],campaign['status'],'initial',now,0))
                flow=dict(c.execute('SELECT * FROM flows WHERE id=?',(fid,)).fetchone())
            self.send(flow)
            return

def daily_backup(store):
    if stamp()-int(store.setting('backup_at','0'))<=86400:
        return
    backup_dir=Path(store.path).parent/'backups'
    backup_dir.mkdir(exist_ok=True)
    target=backup_dir/('go-'+datetime.now(timezone.utc).strftime('%Y%m%d')+'.sqlite')
    with closing(sqlite3.connect(store.path)) as source, closing(sqlite3.connect(target)) as dest:
        source.backup(dest)
    store.set_setting('backup_at',stamp())

def run():
    store=Store(os.environ.get('GO_DB','data/go.sqlite'))
    events=os.environ.get('GO_EVENTS','data/events.sqlite')
    # Recover only the visible status, never retry a possibly accepted send.
    with store.db() as c:
        n=c.execute("UPDATE sends SET state='review',code='interrupted' WHERE state='sending'").rowcount
        if n:
            c.execute("UPDATE flows SET stage='review' WHERE stage='initial'")
            c.execute('INSERT INTO activity(campaign,kind,detail,at) VALUES (?,?,?,?)',('','review','Execução interrompida: conferir envios pendentes no Instagram.',stamp()))
    while True:
        if not account_id():
            store.set_setting('worker_error','Conecte o Instagram primeiro.');time.sleep(5);continue
        try:
            cursor=int(store.setting('cursor','0'))
            with closing(sqlite3.connect('file:'+events+'?mode=ro',uri=True)) as c:
                c.row_factory=sqlite3.Row
                rows=c.execute('SELECT * FROM go_events WHERE seq>? ORDER BY seq LIMIT 100',(cursor,)).fetchall()
            engine=Engine(store,CampaignAPI())
            for row in rows:
                try: engine.handle(dict(row))
                except Exception as e:
                    store.activity('','review','Evento requer revisão; não houve repetição automática. '+type(e).__name__)
                store.set_setting('cursor',row['seq'])
            store.set_setting('worker_at',stamp())
            store.set_setting('worker_error','')
            daily_backup(store)
        except Exception as e:
            store.set_setting('worker_error',type(e).__name__)
            print(json.dumps({'event':'go_worker_error','type':type(e).__name__}),flush=True)
        time.sleep(3)

if __name__=='__main__': run()
