"""Per-installation configuration. No shared developer credentials."""
import json,os,tempfile
from pathlib import Path

def secrets_dir():return Path(os.environ.get('GO_SECRETS','secrets'))

def read_json(path):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:return {}

def read_install():return read_json(secrets_dir()/'installation.json')
def read_connection():return read_json(secrets_dir()/'instagram.json')
def account_id():return str(read_connection().get('account_id',''))

def save_private(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.pending-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(value,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
        os.chmod(name,0o600);os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

def origin():
    return os.environ.get('GO_ORIGIN') or read_install().get('origin','')

def base_path():
    value=os.environ.get('GO_BASE',read_install().get('base_path',''))
    if value not in ('','/go-insta'):raise ValueError('GO_BASE deve ser vazio ou /go-insta.')
    return value
