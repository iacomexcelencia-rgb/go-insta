"""Read-only analytics collector. Explicit periods, nulls, provenance and coverage."""
import csv
import io
import json
import os
import statistics
import time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from instagram_api import Instagram
from config import account_id, read_connection
from go_store import stamp

ACCOUNT_METRICS='reach,views,accounts_engaged,total_interactions,likes,comments,saves,shares,replies,reposts,profile_views,website_clicks,profile_links_taps'.split(',')
MEDIA_METRICS='reach,views,likes,comments,saved,shares,total_interactions'.split(',')
REEL_METRICS='ig_reels_avg_watch_time,ig_reels_video_view_total_time,reels_skip_rate,facebook_views,crossposted_views'.split(',')
EXTRA_METRICS='follows,profile_visits,profile_activity,reposts'.split(',')
STORY_METRICS='reach,views,shares,replies,total_interactions,follows,profile_visits,profile_activity,navigation,link_clicks'.split(',')
LABELS={'reach':'Contas alcançadas','views':'Visualizações','accounts_engaged':'Contas engajadas','total_interactions':'Interações','likes':'Curtidas','comments':'Comentários','saved':'Salvamentos','saves':'Salvamentos','shares':'Compartilhamentos','replies':'Respostas','reposts':'Republicações','profile_views':'Visitas ao perfil','website_clicks':'Toques no link do site','profile_links_taps':'Toques em botões de contato','follows':'Seguidores gerados','profile_visits':'Visitas ao perfil pelo post','profile_activity':'Atividade no perfil','ig_reels_avg_watch_time':'Tempo médio assistido','ig_reels_video_view_total_time':'Tempo total assistido','reels_skip_rate':'Pularam nos primeiros 3 segundos','facebook_views':'Visualizações no Facebook','crossposted_views':'Visualizações entre plataformas','navigation':'Navegação nos Stories','link_clicks':'Toques em links do Story','follows_and_unfollows':'Entradas e saídas de seguidores','online_followers':'Seguidores online'}

def numeric(value):
    return type(value) in (int,float)

def extract(metric):
    total=metric.get('total_value',{})
    series=metric.get('values',[])
    value=total.get('value')
    if value is None and len(series)==1:
        value=series[0].get('value')
    breakdowns=total.get('breakdowns',[])
    available=numeric(value) or bool(breakdowns and any(x.get('results') for x in breakdowns)) or bool(series and any(numeric(x.get('value')) or isinstance(x.get('value'),dict) and bool(x['value']) for x in series))
    return {'value':value if numeric(value) else None,'state':'available' if available else 'unavailable',
            'series':series,'breakdowns':breakdowns,'title':metric.get('title',''),'description':metric.get('description',''),
            'reason':'' if available else 'A Meta respondeu sem valores para esta consulta.'}

def missing(reason,code=None):
    return {'value':None,'state':'unavailable','series':[],'breakdowns':[],'reason':reason,'code':code}

def value(metrics,key):
    return metrics.get(key,{}).get('value')

def ratio(n,d,scale=100):
    return round(n/d*scale,3) if numeric(n) and numeric(d) and d>0 else None

def derived(metrics):
    reach=value(metrics,'reach')
    return {'engagement_rate':ratio(value(metrics,'total_interactions'),reach),
            'save_rate':ratio(value(metrics,'saved'),reach),'share_rate':ratio(value(metrics,'shares'),reach),
            'comment_rate':ratio(value(metrics,'comments'),reach),
            'watch_seconds':round(value(metrics,'ig_reels_avg_watch_time')/1000,3) if numeric(value(metrics,'ig_reels_avg_watch_time')) else None,
            'watch_total_hours':round(value(metrics,'ig_reels_video_view_total_time')/3600000,3) if numeric(value(metrics,'ig_reels_video_view_total_time')) else None}

class Collector:
    def __init__(self,api=None,progress=None):
        self.api=api or Instagram()
        self.progress=progress or (lambda text:None)
        self.requests=0

    def get(self,path,**params):
        self.requests+=1
        if self.requests>1400:
            raise RuntimeError('Limite de consultas desta atualização atingido; dados anteriores preservados.')
        result=self.api.get(path,**params)
        error=result.get('body',{}).get('error',{})
        if not result.get('ok') and error.get('code') in (4,17,32,190,613):
            raise RuntimeError('A Meta pediu pausa ou renovação de acesso; dados anteriores preservados. Código '+str(error.get('code')))
        return result

    def metrics(self,path,names,**params):
        result=self.get(path,metric=','.join(names),**params)
        if not result.get('ok'):
            if len(names)>1:
                out={}
                for name in names:out.update(self.metrics(path,[name],**params))
                return out
            e=result.get('body',{}).get('error',{})
            return {names[0]:missing(str(e.get('message','Não foi possível consultar a métrica.'))[:350],e.get('code',result.get('status')))}
        found={m['name']:extract(m) for m in result.get('body',{}).get('data',[])}
        return {n:found.get(n,missing('A Meta não retornou esta métrica na consulta.')) for n in names}

    def inventory(self,edge,fields):
        out=[];after=None;seen=set();cursors=set()
        for _ in range(100):
            args={'fields':fields,'limit':100}
            if after:args['after']=after
            r=self.get(account_id()+'/'+edge,**args)
            if not r.get('ok'):return out,False
            rows=r.get('body',{}).get('data',[])
            if not rows:return out,True
            for item in rows:
                if item['id'] not in seen:out.append(item);seen.add(item['id'])
            after=r.get('body',{}).get('paging',{}).get('cursors',{}).get('after')
            if not after:return out,True
            if after in cursors:return out,False
            cursors.add(after)
        return out,False

    def window(self,start,end):
        p={'period':'day','metric_type':'total_value','since':int(start.timestamp()),'until':int(end.timestamp())}
        metrics=self.metrics(account_id()+'/insights',ACCOUNT_METRICS,**p)
        metrics.update(self.metrics(account_id()+'/insights',['follows_and_unfollows'],breakdown='follow_type',**p))
        breakdowns={}
        for key,names,dimension in [('views_by_follow',['views'],'follow_type'),('reach_by_follow',['reach'],'follow_type'),('by_format',['views','total_interactions'],'media_product_type'),('contact',['profile_links_taps'],'contact_button_type')]:
            breakdowns[key]=self.metrics(account_id()+'/insights',names,breakdown=dimension,**p)
        return {'since':start.isoformat(),'until_exclusive':end.isoformat(),'metrics':metrics,'breakdowns':breakdowns}

    def stories(self):
        stories,complete=self.inventory('stories','id,media_type,timestamp,permalink')
        for post in stories:
            post['media_product_type']='STORY'
            post['metrics']=self.metrics(post['id']+'/insights',STORY_METRICS)
            for name,breakdown in [('navigation','story_navigation_action_type'),('profile_activity','action_type')]:
                post['metrics'][name]=self.metrics(post['id']+'/insights',[name],breakdown=breakdown)[name]
            post.update(insights_at=stamp(),scope='lifetime')
        return stories,complete

    def collect(self):
        now=datetime.now(timezone.utc);end=now.replace(hour=0,minute=0,second=0,microsecond=0)
        self.progress('Conferindo conta e inventário de publicações')
        r=self.get('me',fields='id,user_id,username,name,account_type,followers_count,follows_count,media_count')
        if not r.get('ok') or str(r.get('body',{}).get('user_id'))!=account_id():
            raise RuntimeError('Não foi possível validar a conta. Dados anteriores preservados.')
        posts,complete=self.inventory('media','id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count')
        if not complete:
            raise RuntimeError('Inventário incompleto nesta tentativa. Dados anteriores preservados.')
        posts.sort(key=lambda x:x.get('timestamp',''),reverse=True)
        windows={}
        for days in (7,28,90):
            self.progress('Consultando perfil: '+str(days)+' dias')
            start=end-timedelta(days=days)
            windows[str(days)]=self.window(start,end)
            windows[str(days)]['previous']=self.window(start-timedelta(days=days),start) if days<=28 else None
        self.progress('Montando evolução diária dos últimos 28 dias')
        daily=[]
        for i in range(28,0,-1):
            start=end-timedelta(days=i);stop=start+timedelta(days=1)
            m=self.metrics(account_id()+'/insights',['reach','views','total_interactions','profile_views','website_clicks'],period='day',metric_type='total_value',since=int(start.timestamp()),until=int(stop.timestamp()))
            daily.append({'since':start.isoformat(),'until_exclusive':stop.isoformat(),'metrics':m})
        self.progress('Consultando público, seguidores e horários disponíveis')
        audience={}
        for group in ('follower_demographics','engaged_audience_demographics','reached_audience_demographics'):
            audience[group]={}
            for dimension in ('age','gender','city','country'):
                audience[group][dimension]=self.metrics(account_id()+'/insights',[group],period='lifetime',metric_type='total_value',timeframe='last_30_days',breakdown=dimension)[group]
        audience['online_followers']=self.metrics(account_id()+'/insights',['online_followers'],period='lifetime')['online_followers']
        eligible=[]
        for post in posts:
            created=datetime.fromisoformat(post['timestamp'].replace('Z','+00:00'))
            if created>=now-timedelta(days=730):eligible.append(post)
        # Lifetime insights are bounded by the API history; old counters remain visible.
        selected=eligible[:500]
        for i,post in enumerate(selected):
            if self.requests>1250:break  # Preserve a partial, explicitly counted sample instead of losing the collection.
            self.progress(f'Analisando publicação {i+1} de {len(selected)}')
            m=self.metrics(post['id']+'/insights',MEDIA_METRICS)
            if post.get('media_product_type')=='REELS':m.update(self.metrics(post['id']+'/insights',REEL_METRICS))
            m.update(self.metrics(post['id']+'/insights',EXTRA_METRICS))
            post.update(metrics=m,derived=derived(m),insights_at=stamp(),scope='lifetime')
        self.progress('Consultando Stories ainda disponíveis')
        stories,stories_complete=self.stories()
        collected=[p for p in selected if 'metrics' in p]
        missing_count=sum(m['state']!='available' for p in collected for m in p.get('metrics',{}).values())
        return {'version':1,'collected_at':stamp(),'api_version':self.api.version,'profile':r['body'],'windows':windows,'daily':daily,'audience':audience,'posts':posts,'stories':stories,
                'labels':LABELS,'coverage':{'inventory':len(posts),'inventory_complete':complete,'eligible_730_days':len(eligible),'media_insights':len(collected),'media_limit':500,'unavailable_media_metrics':missing_count,'requests':self.requests,'stories_complete':stories_complete,'daily_days':28},
                'notes':['Métricas do perfil se referem ao período; métricas individuais dos posts são acumuladas desde a publicação.','Períodos solicitados em UTC, fim exclusivo, sem o dia atual. A Meta pode revisar dados ou entregá-los com atraso.','Alcance é uma contagem única dentro de cada consulta: não somar alcance entre dias ou posts como pessoas distintas.','Tempo médio e tempo total da API vêm em milissegundos. Taxa de pulo já vem em percentual. Não há curva completa de retenção nesta integração.','Resultados observados não comprovam faturamento nem que um tema, formato ou horário causou o desempenho.','Dados de público correspondem à consulta de últimos 30 dias e podem omitir pessoas por limites da Meta.']}

def init_analytics(store):
    with store.db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS analytics_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT,at INTEGER,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS analytics_jobs (id INTEGER PRIMARY KEY AUTOINCREMENT,status TEXT,stage TEXT,created INTEGER,updated INTEGER,error TEXT);
        CREATE TABLE IF NOT EXISTS editorial (media_id TEXT PRIMARY KEY,series TEXT,theme TEXT,goal TEXT,notes TEXT,updated INTEGER);
        CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT,media_id TEXT,product TEXT,amount_cents INTEGER,sold_at TEXT,note TEXT,status TEXT,created INTEGER);
        CREATE INDEX IF NOT EXISTS analytics_at ON analytics_snapshots(at);
        CREATE TABLE IF NOT EXISTS story_samples (id TEXT PRIMARY KEY,payload TEXT NOT NULL,updated INTEGER);
        ''')

def archive_stories(store,stories,complete):
    with store.db() as c:
        for p in stories:
            c.execute('INSERT OR REPLACE INTO story_samples VALUES (?,?,?)',(p['id'],json.dumps(p,ensure_ascii=False),stamp()))
    store.set_setting('stories_last_at',str(stamp()))
    store.set_setting('stories_error','' if complete else 'A Meta retornou uma lista incompleta; leituras anteriores foram preservadas.')

def request_refresh(store):
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute("SELECT * FROM analytics_jobs WHERE status IN ('queued','running') ORDER BY id DESC LIMIT 1").fetchone()
        if old:return dict(old)
        latest=c.execute('SELECT * FROM analytics_jobs ORDER BY id DESC LIMIT 1').fetchone()
        if latest and stamp()-latest['updated']<300:raise ValueError('Aguarde cinco minutos entre atualizações completas para preservar o limite da Meta.')
        ident=c.execute('INSERT INTO analytics_jobs(status,stage,created,updated,error) VALUES (?,?,?,?,?)',('queued','Aguardando coleta',stamp(),stamp(),'')).lastrowid
        return dict(c.execute('SELECT * FROM analytics_jobs WHERE id=?',(ident,)).fetchone())

def analytics_payload(store):
    with store.db() as c:
        last=c.execute('SELECT at,payload FROM analytics_snapshots ORDER BY id DESC LIMIT 1').fetchone()
        job=c.execute('SELECT * FROM analytics_jobs ORDER BY id DESC LIMIT 1').fetchone()
        annotations={r['media_id']:dict(r) for r in c.execute('SELECT * FROM editorial')}
        sales=[dict(r) for r in c.execute('SELECT * FROM sales ORDER BY sold_at DESC,id DESC LIMIT 500')]
        history=[];seen=set()
        for r in c.execute('SELECT at,payload FROM analytics_snapshots ORDER BY id DESC LIMIT 120'):
            day=datetime.fromtimestamp(r['at'],timezone.utc).date().isoformat()
            if day not in seen:
                p=json.loads(r['payload'])['profile'];history.append({'day':day,'at':r['at'],'followers':p.get('followers_count')});seen.add(day)
        campaigns=store.dashboard()
        stories=[json.loads(r['payload']) for r in c.execute('SELECT payload FROM story_samples ORDER BY updated DESC LIMIT 500')]
    return {'snapshot':json.loads(last['payload']) if last else None,'job':dict(job) if job else None,'editorial':annotations,'sales':sales,'follower_history':list(reversed(history)),'story_archive':stories,'stories_last_at':store.setting('stories_last_at'),'stories_error':store.setting('stories_error'),'automation':{'conversations':campaigns['conversations'],'interactions':campaigns['interactions'],'counts':campaigns['counts'],'per_campaign':campaigns['per_campaign']}}

def save_editorial(store,data):
    mid=str(data.get('media_id',''))
    payload=analytics_payload(store)['snapshot']
    if not payload or mid not in {x['id'] for x in payload['posts']}:raise ValueError('Publicação não encontrada no inventário.')
    vals=[]
    for k,limit in [('series',80),('theme',120),('goal',80),('notes',1000)]:
        v=data.get(k,'')
        if not isinstance(v,str) or len(v)>limit:raise ValueError('Campo editorial inválido: '+k)
        vals.append(v.strip())
    with store.db() as c:c.execute('INSERT OR REPLACE INTO editorial VALUES (?,?,?,?,?,?)',(mid,*vals,stamp()))

def record_sale(store,data):
    mid=str(data.get('media_id',''))
    snapshot=analytics_payload(store)['snapshot']
    if mid and (not snapshot or mid not in {p['id'] for p in snapshot['posts']}):raise ValueError('Publicação não encontrada.')
    amount=data.get('amount_cents')
    if type(amount) is not int or not 1<=amount<=100000000:raise ValueError('Informe o valor recebido em reais.')
    product=data.get('product','');note=data.get('note','');sold_at=data.get('sold_at','')
    if not isinstance(product,str) or not 1<=len(product.strip())<=100 or not isinstance(note,str) or len(note)>500:raise ValueError('Produto ou observação inválidos.')
    try:date=datetime.fromisoformat(sold_at)
    except (ValueError,TypeError):raise ValueError('Data da venda inválida.')
    if date.date()>datetime.now(timezone(timedelta(hours=-3))).date():raise ValueError('Registre somente vendas já realizadas.')
    with store.db() as c:c.execute('INSERT INTO sales(media_id,product,amount_cents,sold_at,note,status,created) VALUES (?,?,?,?,?,?,?)',(mid,product.strip(),amount,date.date().isoformat(),note.strip(),'paid',stamp()))

def export_csv(snapshot):
    keys=['reach','views','likes','comments','saved','shares','total_interactions','follows','profile_visits','ig_reels_avg_watch_time','ig_reels_video_view_total_time','reels_skip_rate','facebook_views','crossposted_views']
    cols=['id','timestamp','media_product_type','media_type','permalink','caption','insights_at','scope']+keys+['engagement_rate','share_rate','save_rate','comment_rate','watch_seconds']
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=cols,extrasaction='ignore');writer.writeheader()
    for p in snapshot.get('posts',[]):
        row=dict(p);row.update({k:value(p.get('metrics',{}),k) for k in keys});row.update(p.get('derived',{}))
        for k,v in row.items():
            if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')):row[k]="'"+v
        writer.writerow(row)
    return ('\ufeff'+stream.getvalue()).encode('utf-8')

def run_service(store):
    init_analytics(store)
    with store.db() as c:c.execute("UPDATE analytics_jobs SET status='failed',error='Coleta interrompida pelo reinício. Solicite uma nova atualização.',updated=? WHERE status='running'",(stamp(),))
    while True:
        if not account_id():
            time.sleep(10);continue
        from connection import refresh_if_due
        refresh_if_due(store)
        with store.db() as c:
            row=c.execute('SELECT at FROM analytics_snapshots ORDER BY id DESC LIMIT 1').fetchone()
            job=c.execute("SELECT * FROM analytics_jobs WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
            latest=c.execute('SELECT * FROM analytics_jobs ORDER BY id DESC LIMIT 1').fetchone()
        if not job and (not row or stamp()-row['at']>=86400) and (not latest or stamp()-latest['updated']>=3600):
            request_refresh(store);continue
        if job:
            jid=job['id']
            with store.db() as c:c.execute("UPDATE analytics_jobs SET status='running',updated=? WHERE id=?",(stamp(),jid))
            def progress(stage):
                with store.db() as c:c.execute('UPDATE analytics_jobs SET stage=?,updated=? WHERE id=?',(stage,stamp(),jid))
            try:
                snapshot=Collector(progress=progress).collect()
                archive_stories(store,snapshot['stories'],snapshot['coverage']['stories_complete'])
                with store.db() as c:
                    c.execute('INSERT INTO analytics_snapshots(at,payload) VALUES (?,?)',(stamp(),json.dumps(snapshot,ensure_ascii=False)))
                    c.execute("UPDATE analytics_jobs SET status='done',stage='Atualização concluída',updated=?,error='' WHERE id=?",(stamp(),jid))
                store.activity('','analytics','Insights atualizados: '+str(snapshot['coverage']['media_insights'])+' publicações com métricas individuais.')
            except Exception as e:
                msg=str(e) if isinstance(e,RuntimeError) else 'Falha de coleta: '+type(e).__name__+'. Os dados anteriores foram preservados.'
                with store.db() as c:c.execute("UPDATE analytics_jobs SET status='failed',updated=?,error=? WHERE id=?",(stamp(),msg,jid))
        if not job and stamp()-int(store.setting('stories_last_at') or 0)>=3600:
            try:
                stories,complete=Collector().stories()
                archive_stories(store,stories,complete)
            except Exception:
                store.set_setting('stories_last_at',str(stamp()))
                store.set_setting('stories_error','Não foi possível atualizar Stories nesta tentativa. Leituras anteriores preservadas; nova tentativa em uma hora.')
        time.sleep(5)

if __name__=='__main__':
    import argparse
    from go_store import Store
    parser=argparse.ArgumentParser();parser.add_argument('--once');args=parser.parse_args()
    if args.once:
        result=Collector(progress=lambda m:print(m,flush=True)).collect()
        Path(args.once).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result['coverage']),flush=True)
    else:run_service(Store(os.environ.get('GO_DB','data/go.sqlite')))
