"""Prepara somente dados fictícios no PostgreSQL privado de desenvolvimento."""
import json
import os
from pathlib import Path
import secrets
import sys

import httpx
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from coleta_api.cli import provision

def main():
    os.umask(0o077)
    local=ROOT/'.local'
    state_path=local/'device-test.json'
    with httpx.Client(base_url='http://127.0.0.1:8000',timeout=20,trust_env=False) as api:
        api.get('/health').raise_for_status()
        if state_path.exists():
            state=json.loads(state_path.read_text())
        else:
            password=secrets.token_urlsafe(18)
            dsn=make_conninfo(host=str(local/'socket'),port=55438,dbname='postgres',user='coleta_dev_owner')
            company=provision(dsn,'Homologação Android — dados fictícios','admin-aparelho',password)
            state={'admin':{'empresa_id':str(company),'usuario_login':'admin-aparelho','senha':password},
                   'motorista':{'empresa_id':str(company),'usuario_login':'motorista-aparelho','senha':secrets.token_urlsafe(12)}}
            state_path.write_text(json.dumps(state,indent=2)+'\n');state_path.chmod(0o600)
        token=api.post('/auth/login',json=state['admin']);token.raise_for_status()
        api.headers['Authorization']='Bearer '+token.json()['access_token']
        def get(path):
            r=api.get(path);r.raise_for_status();return r.json()
        def post(path,body):
            r=api.post(path,json=body);r.raise_for_status();return r.json()
        try:
            drivers=get('/motoristas')['items']
            driver=next((d for d in drivers if d['login']==state['motorista']['usuario_login']),None)
            if not driver:
                driver=post('/motoristas',{'nome':'Motorista do aparelho — TESTE','login':state['motorista']['usuario_login'],
                    'senha':state['motorista']['senha'],'tipo':'carro','placa':'TST1A23','ativo':True})
            clients=get('/clientes')['items']
            client=next((c for c in clients if c['nome']=='Cliente fictício — TESTE ANDROID'),None)
            if not client:
                client=post('/clientes',{'nome':'Cliente fictício — TESTE ANDROID','cnpj':'00.958.251/0001-83',
                    'endereco':'Endereço fictício para teste; não navegar','cidade':'Goiânia','estado':'GO'})
            routes=get('/rotas')['items']
            if not any(r['nome']=='Rota fictícia — aparelho' for r in routes):
                post('/rotas',{'nome':'Rota fictícia — aparelho','motorista_id':driver['id'],
                    'dias_semana':[1,2,3,4,5,6,7],'ativa':True,'paradas':[{'cliente_id':client['id']}]})
        finally:
            api.post('/auth/logout').raise_for_status()
        api.headers.pop('Authorization',None)
        token=api.post('/auth/login',json=state['motorista']);token.raise_for_status()
        api.headers['Authorization']='Bearer '+token.json()['access_token']
        try:
            day=post('/motorista/rota-do-dia/preparar',{})
            print('Conta motorista validada; rotas do dia:',len(day['rotas']))
        finally:
            api.post('/auth/logout').raise_for_status()
    access=local/'acesso-aparelho.txt'
    access.write_text('TESTE LOCAL POR USB — manter cabo e servidor ativos\n'
        'App: Coleta Teste USB\nServidor: http://127.0.0.1:8000\n'
        f"Empresa: {state['motorista']['empresa_id']}\nUsuário: {state['motorista']['usuario_login']}\nSenha: {state['motorista']['senha']}\n"
        '\nPainel: http://127.0.0.1:5173/\n'
        f"Empresa: {state['admin']['empresa_id']}\nUsuário: {state['admin']['usuario_login']}\nSenha: {state['admin']['senha']}\n"
        '\nUse exclusivamente os dados fictícios desta empresa. Não navegar para o endereço fictício.\n')
    access.chmod(0o600)
    print('Acessos locais protegidos em:',access)

if __name__=='__main__':
    main()
