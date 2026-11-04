"""Signed webhook metadata for Go Insta. No comment or DM text is persisted."""
import hashlib
import json
import re
import time

from config import account_id

def init_go_queue(c):
    c.execute('CREATE TABLE IF NOT EXISTS go_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT UNIQUE, kind TEXT, sender TEXT, media TEXT, comment TEXT, action TEXT, event_at INTEGER, received_at INTEGER)')

def queue_go_events(c, payload):
    ACCOUNT = account_id()
    now = int(time.time())
    for entry in payload.get('entry', []):
        if str(entry.get('id')) != ACCOUNT:
            continue
        for change in entry.get('changes', []):
            v = change.get('value', {})
            if change.get('field') != 'comments' or not isinstance(v, dict):
                continue
            sender, media, comment = (str(v.get('from', {}).get('id', '')), str(v.get('media', {}).get('id', '')), str(v.get('id', '')))
            if not all(x.isdigit() and len(x) < 40 for x in (sender, media, comment)) or sender == ACCOUNT:
                continue
            c.execute('INSERT OR IGNORE INTO go_events(event_key,kind,sender,media,comment,action,event_at,received_at) VALUES (?,?,?,?,?,?,?,?)', ('c:'+comment,'comment',sender,media,comment,'',now,now))
        for e in entry.get('messaging', []):
            sender = str(e.get('sender', {}).get('id', ''))
            m = e.get('message', {})
            if str(e.get('recipient', {}).get('id')) != ACCOUNT or not sender.isdigit() or sender == ACCOUNT or m.get('is_echo') or m.get('is_deleted'):
                continue
            action = e.get('postback', {}).get('payload') or m.get('quick_reply', {}).get('payload', '')
            # Continue only through the explicit button of a specific flow.
            if not isinstance(action, str) or not re.fullmatch(r'GO:[a-f0-9]{32}', action):
                continue
            ts = e.get('timestamp', 0)
            if not isinstance(ts, (int, float)) or not now-86400 < ts/1000 <= now+60:
                continue
            key = hashlib.sha256(json.dumps(e,sort_keys=True).encode()).hexdigest()
            c.execute('INSERT OR IGNORE INTO go_events(event_key,kind,sender,media,comment,action,event_at,received_at) VALUES (?,?,?,?,?,?,?,?)', (key,'continue',sender,'','',action,int(ts/1000),now))
    c.execute('DELETE FROM go_events WHERE received_at < ?', (now-30*86400,))
