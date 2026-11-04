"""Administrative recovery from the server console, never a public endpoint."""
import getpass,os
from go_store import Store,password_hash

def main():
    first=getpass.getpass('Nova senha do administrador (12–128 caracteres): ')
    if not 12<=len(first)<=128 or first!=getpass.getpass('Repita a senha: '):raise SystemExit('Senha inválida ou confirmação diferente. Nada alterado.')
    store=Store(os.environ.get('GO_DB','data/go.sqlite'))
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE');db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('password',password_hash(first)));db.execute('DELETE FROM sessions');db.execute('DELETE FROM attempts')
    print('Senha atualizada. Todas as sessões anteriores foram encerradas.')

if __name__=='__main__':main()
