"""Interactive local setup. Does not contact Meta, send messages or activate campaigns."""
import argparse,getpass,json,os,re,secrets
from pathlib import Path
from urllib.parse import urlparse
from config import save_private
from go_store import password_hash

def validate_origin(value):
    value=value.strip().rstrip('/');p=urlparse(value)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.path or p.query or p.fragment or p.port:
        raise ValueError('Use um domínio HTTPS sem caminho ou porta, por exemplo https://insta.exemplo.com.br')
    if len(p.hostname)>253 or '.' not in p.hostname or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',part) for part in p.hostname.split('.')):raise ValueError('Informe um domínio válido.')
    return 'https://'+p.hostname

def main(mode='https'):
    root=Path(__file__).resolve().parent
    if any((root/name).exists() for name in ['secrets/installation.json','data/go.sqlite','.env','.go-insta-mode','compose.hostinger.json']):raise SystemExit('Instalação já configurada. Preserve secrets/ e data/. Consulte docs/INSTALACAO.md para atualizar.')
    print('Go Insta! · instalação independente. Uma conta Instagram por instalação.')
    base='';override=None
    if mode=='hostinger':
        from hostinger import hostinger_origin,preflight,BASE
        origin=hostinger_origin(input('Cole o endereço HTTPS que já abre seu n8n na Hostinger: '));base=BASE
        override=preflight(origin)
        print('HTTPS e rota Traefik encontrados. Painel: '+origin+base+'/')
        print('A instalação usará a rede existente; n8n e Traefik não serão recriados.')
    else:origin=validate_origin(input('Endereço HTTPS do painel: '))
    user=input('Usuário administrador [admin]: ').strip() or 'admin'
    if not re.fullmatch(r'[a-zA-Z0-9_.-]{3,50}',user):raise ValueError('Usuário: 3–50 letras, números, ponto, hífen ou sublinhado.')
    operator=input('Nome do responsável por esta instalação: ').strip()
    email=input('E-mail público para privacidade e exclusão: ').strip()
    if not operator or len(operator)>120 or not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',email):raise ValueError('Informe responsável e e-mail válidos.')
    password=getpass.getpass('Crie uma senha de 12 a 128 caracteres: ')
    if not 12<=len(password)<=128 or password!=getpass.getpass('Repita a senha: '):raise ValueError('Senha inválida ou confirmação diferente.')
    for name in ['data','secrets']:
        p=root/name;p.mkdir(exist_ok=True);p.chmod(0o700)
    save_private(root/'secrets/installation.json',{'origin':origin,'base_path':base,'admin_username':user,'operator':operator,'contact_email':email,'verify_token':secrets.token_urlsafe(32)})
    save_private(root/'secrets/auth-seed.json',{'password_hash':password_hash(password)})
    (root/'.env').write_text('GO_DOMAIN='+urlparse(origin).hostname+'\nGO_ORIGIN='+origin+'\nGO_BASE='+base+'\n',encoding='utf-8')
    (root/'.env').chmod(0o600)
    (root/'.go-insta-mode').write_text(mode+'\n',encoding='utf-8')
    if override:(root/'compose.hostinger.json').write_text(json.dumps(override,indent=2)+'\n',encoding='utf-8')
    if hasattr(os,'geteuid') and os.geteuid()==0:
        for name in ['data','secrets','secrets/installation.json','secrets/auth-seed.json']:os.chown(root/name,10002,10002)
        # Compose runs as the invoking operator; only the containers need the private directories.
        os.chown(root/'.env',int(os.environ.get('SUDO_UID','0')),int(os.environ.get('SUDO_GID','0')))
    print('Configuração criada. Execute: sudo python3 manage.py up -d --build --wait')
    print('Depois abra '+origin+base+'/ e siga Conexão. Não publique .env, secrets/ ou data/.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--hostinger',action='store_true',help='Reutiliza o HTTPS e Traefik do n8n Hostinger, em /go-insta/.')
    modes.add_argument('--proxy',action='store_true',help='Proxy externo configurado manualmente, domínio dedicado.')
    args=parser.parse_args()
    try:main('hostinger' if args.hostinger else 'proxy' if args.proxy else 'https')
    except (ValueError,KeyboardInterrupt) as e:raise SystemExit(str(e) or 'Configuração cancelada.')
