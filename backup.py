"""Consistent SQLite backup; does not copy credentials or print private data."""
import os,sqlite3
from contextlib import closing
from pathlib import Path
from datetime import datetime,timezone

def main():
    source=Path(os.environ.get('GO_DB','data/go.sqlite'))
    target=source.parent/'backups'/datetime.now(timezone.utc).strftime('manual-%Y%m%d-%H%M%S')
    target.mkdir(parents=True,exist_ok=False)
    for path in [source,Path(os.environ.get('GO_EVENTS','data/events.sqlite'))]:
        if not path.exists():continue
        with closing(sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(target/path.name)) as dst:src.backup(dst)
    print('Backup consistente criado em '+str(target)+'. Proteja também secrets/ e .env separadamente.')

if __name__=='__main__':main()
