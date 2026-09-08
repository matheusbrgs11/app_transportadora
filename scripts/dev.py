"""Inicia API e PostgreSQL de desenvolvimento, sem Docker nem sudo.

O cluster é privado do projeto e não utiliza o banco instalado como serviço.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import psycopg
from psycopg.conninfo import make_conninfo
import uvicorn
from coleta_api.cli import migrate,provision
from coleta_api.config import Settings
from coleta_api.main import create_app


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    os.umask(0o077)
    local=ROOT/'.local'
    local.mkdir(exist_ok=True,mode=0o700)
    socket=local/'socket'
    socket.mkdir(exist_ok=True,mode=0o700)
    data=local/'postgres'
    bins=Path(os.environ.get('PG_BIN','/usr/lib/postgresql/17/bin'))
    def run(command):
        return subprocess.run(command,check=True,capture_output=True,text=True)
    if not (data/'PG_VERSION').exists():
        run([str(bins/'initdb'),'-D',str(data),'--auth-local=trust','--auth-host=scram-sha-256',
             '-U','coleta_dev_owner','--no-locale','--encoding=UTF8'])
    running=subprocess.run([str(bins/'pg_ctl'),'-D',str(data),'status'],capture_output=True).returncode==0
    started=False
    try:
        if not running:
            run([str(bins/'pg_ctl'),'-D',str(data),'-l',str(local/'postgres.log'),
                 '-o',f"-k '{socket}' -h '' -p 55438",'-w','start'])
            started=True
        admin=make_conninfo(host=str(socket),port=55438,dbname='postgres',user='coleta_dev_owner')
        migrate(admin)
        with psycopg.connect(admin) as conn:
            if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname='coleta_dev_api'").fetchone():
                conn.execute('CREATE ROLE coleta_dev_api LOGIN NOSUPERUSER NOBYPASSRLS')
                conn.execute('GRANT coleta_app TO coleta_dev_api')
        runtime=make_conninfo(host=str(socket),port=55438,dbname='postgres',user='coleta_dev_api')
        credentials=local/'access.json'
        if not credentials.exists():
            password=secrets.token_urlsafe(18)
            empresa=provision(admin,'Transportadora piloto (desenvolvimento)','admin',password)
            credentials.write_text(json.dumps({'empresa_id':str(empresa),'usuario_login':'admin','senha':password},indent=2)+'\n')
            credentials.chmod(0o600)
        secret_path=local/'jwt-secret'
        if not secret_path.exists():
            secret_path.write_text(secrets.token_urlsafe(48))
            secret_path.chmod(0o600)
        print(f'API local: http://127.0.0.1:{args.port}/docs',flush=True)
        print(f'Credenciais locais: {credentials}',flush=True)
        print('Banco privado em .local/postgres; nenhum dado do serviço PostgreSQL foi alterado.',flush=True)
        if not args.prepare_only:
            uvicorn.run(create_app(Settings(runtime,secret_path.read_text().strip())),host='127.0.0.1',port=args.port)
    finally:
        if started:
            subprocess.run([str(bins/'pg_ctl'),'-D',str(data),'-m','fast','-w','stop'],capture_output=True)


if __name__=='__main__':
    main()
