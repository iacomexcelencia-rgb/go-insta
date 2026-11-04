"""Interactive local setup. Does not contact Meta, send messages or activate campaigns."""
import getpass,json,os,re,secrets
from pathlib import Path
from urllib.parse import urlparse
from config import save_private
from go_store import password_hash

def validate_origin(value):
    value=value.strip().rstrip('/');p=urlparse(value)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.path or p.query or p.fragment or p.port:
        raise ValueError('Use um domínio HTTPS sem caminho ou porta, por exemplo https://insta.exemplo.com.br')
    if not re.fullmatch(r'[a-zA-Z0-9.-]+',p.hostname) or '.' not in p.hostname:raise ValueError('Informe um domínio válido.')
    return value

def main():
    root=Path(__file__).resolve().parent
    if (root/'secrets/installation.json').exists():raise SystemExit('Instalação já configurada. Preserve secrets/ e data/. Consulte docs/INSTALACAO.md para atualizar.')
    print('Go Insta! · instalação independente. Uma conta Instagram por instalação.')
    origin=validate_origin(input('Endereço HTTPS do painel: '))
    user=input('Usuário administrador [admin]: ').strip() or 'admin'
    if not re.fullmatch(r'[a-zA-Z0-9_.-]{3,50}',user):raise ValueError('Usuário: 3–50 letras, números, ponto, hífen ou sublinhado.')
    operator=input('Nome do responsável por esta instalação: ').strip()
    email=input('E-mail público para privacidade e exclusão: ').strip()
    if not operator or len(operator)>120 or not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',email):raise ValueError('Informe responsável e e-mail válidos.')
    password=getpass.getpass('Crie uma senha de 12 a 128 caracteres: ')
    if not 12<=len(password)<=128 or password!=getpass.getpass('Repita a senha: '):raise ValueError('Senha inválida ou confirmação diferente.')
    for name in ['data','secrets']:
        p=root/name;p.mkdir(exist_ok=True);p.chmod(0o700)
    save_private(root/'secrets/installation.json',{'origin':origin,'admin_username':user,'operator':operator,'contact_email':email,'verify_token':secrets.token_urlsafe(32)})
    save_private(root/'secrets/auth-seed.json',{'password_hash':password_hash(password)})
    (root/'.env').write_text('GO_DOMAIN='+urlparse(origin).hostname+'\nGO_ORIGIN='+origin+'\n',encoding='utf-8')
    (root/'.env').chmod(0o600)
    if hasattr(os,'geteuid') and os.geteuid()==0:
        for name in ['data','secrets','secrets/installation.json','secrets/auth-seed.json']:os.chown(root/name,10002,10002)
    print('Configuração criada. VPS sem proxy existente: docker compose --profile https up -d --build')
    print('Se já existe proxy nas portas 80/443, siga docs/INSTALACAO.md antes de subir os serviços.')
    print('Depois abra '+origin+' e siga Conexão. Não publique .env, secrets/ ou data/.')

if __name__=='__main__':
    try:main()
    except (ValueError,KeyboardInterrupt) as e:raise SystemExit(str(e) or 'Configuração cancelada.')
