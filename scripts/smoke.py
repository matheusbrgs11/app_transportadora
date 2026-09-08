"""Verifica a instância local sem imprimir senha/token nem cadastrar clientes."""
import json
import os
from pathlib import Path
import httpx

root=Path(__file__).resolve().parents[1]
base_url=os.environ.get('COLETA_SMOKE_URL','http://127.0.0.1:8000')
with httpx.Client(base_url=base_url,timeout=10,trust_env=False) as client:
    client.get('/health').raise_for_status()
    client.get('/docs').raise_for_status()
    credentials=json.loads((root/'.local/access.json').read_text())
    login=client.post('/auth/login',json=credentials)
    login.raise_for_status()
    headers={'Authorization':'Bearer '+login.json()['access_token']}
    me=client.get('/auth/me',headers=headers)
    me.raise_for_status()
    assert me.json()['perfil']=='admin'
    client.get('/clientes',headers=headers).raise_for_status()
    for endpoint in ['/motoristas','/rotas','/operacao/resumo','/modalidades','/coletas']:
        client.get(endpoint,headers=headers).raise_for_status()
    client.post('/auth/logout',headers=headers).raise_for_status()
    assert client.get('/auth/me',headers=headers).status_code==401
    print('Health, documentação, login, perfil, listagem e logout: OK.')
