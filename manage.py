"""Use the same Compose configuration on install, update and maintenance."""
import subprocess,sys
from pathlib import Path

def command(root,args):
    mode=(root/'.go-insta-mode').read_text(encoding='utf-8').strip()
    cmd=['docker','compose','--project-directory',str(root),'-f',str(root/'compose.yaml')]
    if mode=='hostinger':
        if not (root/'compose.hostinger.json').is_file():raise ValueError('Falta compose.hostinger.json; restaure o arquivo do backup.')
        cmd+=['-f',str(root/'compose.hostinger.json')]
    elif mode=='https':cmd+=['--profile','https']
    elif mode!='proxy':raise ValueError('Modo de instalação desconhecido.')
    return cmd+args

if __name__=='__main__':
    try:
        if len(sys.argv)<2:raise ValueError('Uso: python3 manage.py up -d --build --wait | ps | logs --tail 60')
        raise SystemExit(subprocess.call(command(Path(__file__).resolve().parent,sys.argv[1:])))
    except (OSError,ValueError) as e:raise SystemExit('Não foi possível operar a instalação: '+str(e)+' Consulte docs/OPERACAO.md.')
