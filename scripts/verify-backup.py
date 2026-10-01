#!/usr/bin/env python3
"""Restaura um backup em cluster PostgreSQL temporário e confere tabelas principais."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import psycopg


TABLES=('empresas','usuarios','clientes','motoristas','rotas','coletas','coleta_itens',
        'comprovantes','turnos_motorista','chamados_imprevistos')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    parser.add_argument('--pg-bin',type=Path,default=Path('/usr/lib/postgresql/17/bin'))
    args=parser.parse_args()
    if not args.archive.is_file():parser.error('Arquivo de backup não encontrado.')
    folder=Path(tempfile.mkdtemp(prefix='coleta-restore-'))
    started=False
    try:
        data=folder/'data'
        subprocess.run([str(args.pg_bin/'initdb'),'-D',str(data),'-A','trust','-U','restore_owner',
                        '--no-locale','--encoding=UTF8'],check=True,capture_output=True)
        subprocess.run([str(args.pg_bin/'pg_ctl'),'-D',str(data),'-l',str(folder/'postgres.log'),
                        '-o',f"-k {folder} -h '' -p 55437",'-w','start'],check=True,capture_output=True)
        started=True
        dsn=f'host={folder} port=55437 dbname=postgres user=restore_owner'
        with psycopg.connect(dsn,autocommit=True) as conn:
            conn.execute('CREATE ROLE coleta_app NOLOGIN NOSUPERUSER NOBYPASSRLS')
        env={'PGHOST':str(folder),'PGPORT':'55437','PGUSER':'restore_owner','PGDATABASE':'postgres',
             'PATH':'/usr/bin:/bin'}
        result=subprocess.run(['pg_restore','--exit-on-error','--no-owner','--dbname=postgres',str(args.archive.resolve())],
                              env=env,capture_output=True,text=True)
        if result.returncode:
            raise RuntimeError('Restauração falhou: '+result.stderr[-1200:])
        with psycopg.connect(dsn) as conn:
            counts={name:conn.execute(f'SELECT count(*) FROM {name}').fetchone()[0] for name in TABLES}
            migrations=conn.execute('SELECT count(*) FROM schema_migrations').fetchone()[0]
            assert migrations>=13,'Histórico de migrações incompleto.'
            for name in TABLES:
                assert conn.execute('SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(name,)).fetchone()[0],name
        print(json.dumps({'restauracao':'ok','migracoes':migrations,'registros':counts},ensure_ascii=False))
    finally:
        if started:
            subprocess.run([str(args.pg_bin/'pg_ctl'),'-D',str(data),'-m','fast','-w','stop'],capture_output=True)
        shutil.rmtree(folder)


if __name__=='__main__':main()
