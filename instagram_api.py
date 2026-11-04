"""Cliente oficial de leitura; credenciais da instalação fora do código e dos logs."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from config import read_connection
ROOT = Path(__file__).resolve().parent

def read_secret(name='instagram-token'):
    token=read_connection().get('token','')
    if not token:raise RuntimeError('Conecte o Instagram em Conexão antes de consultar a API.')
    return token


def sanitize(value):
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items() if k not in ('access_token', 'next', 'previous', 'media_url', 'thumbnail_url')}
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        return re.sub(r'\b(?:IG|EA)[A-Za-z0-9_-]{40,}\b', '[REDACTED]', value)
    return value

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

class Instagram:
    def __init__(self, token=None, version='v26.0'):
        self.token = token or read_secret()
        self.version = version
        self.opener = urllib.request.build_opener(NoRedirect)

    def get(self, path, **params):
        if not re.fullmatch(r'[A-Za-z0-9_/]+', path) or 'access_token' in params:
            raise ValueError('Endpoint inválido')
        url = 'https://graph.instagram.com/' + self.version + '/' + path.strip('/')
        if params:
            url += '?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + self.token})
        try:
            with self.opener.open(req, timeout=45) as response:
                return {'ok': True, 'status': response.status, 'api_version': response.headers.get('instagram-api-version'), 'body': sanitize(json.load(response))}
        except urllib.error.HTTPError as exc:
            try:
                body = sanitize(json.load(exc))
            except (ValueError, UnicodeError):
                body = {'error': {'message':'Resposta HTTP sem JSON'}}
            return {'ok': False, 'status': exc.code, 'body': body}
        except (urllib.error.URLError, TimeoutError):
            return {'ok': False, 'status': None, 'body': {'error': {'message':'Falha de conexão com a API'}}}

if __name__ == '__main__':
    api = Instagram()
    print(json.dumps(api.get('me', fields='id,user_id,username'), ensure_ascii=False))
