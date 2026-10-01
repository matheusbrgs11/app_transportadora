#!/usr/bin/env python3
"""Cria snapshot PostgreSQL local em diretório privado; exige armazenamento externo seguro."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from psycopg.conninfo import conninfo_to_dict


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True,help='Diretório privado, em volume criptografado e fora do checkout.')
    args=parser.parse_args()
    folder=Path(args.directory).resolve()
    if not folder.is_dir() or folder.stat().st_mode & 0o077:
        parser.error('Crie um diretório existente com permissão 0700 antes de fazer backup.')
    dsn=os.environ.get('ADMIN_DATABASE_URL')
    if not dsn:
        parser.error('Configure ADMIN_DATABASE_URL fora do repositório.')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination=folder/f'coleta-{stamp}.dump'
    temporary=folder/f'.coleta-{stamp}.tmp'
    if destination.exists() or temporary.exists():
        parser.error('Nome de backup já existe. Tente novamente em outro instante.')
    options=conninfo_to_dict(dsn)
    mapping={'host':'PGHOST','port':'PGPORT','dbname':'PGDATABASE','user':'PGUSER',
             'password':'PGPASSWORD','sslmode':'PGSSLMODE','sslrootcert':'PGSSLROOTCERT',
             'sslcert':'PGSSLCERT','sslkey':'PGSSLKEY','options':'PGOPTIONS'}
    env={k:v for k,v in os.environ.items() if not k.startswith('PG')}
    env.update({mapping[key]:value for key,value in options.items() if key in mapping})
    os.umask(0o077)
    try:
        with temporary.open('xb') as output:
            subprocess.run(['pg_dump','--format=custom','--no-owner'],env=env,stdout=output,check=True)
        subprocess.run(['pg_restore','--list',str(temporary)],stdout=subprocess.DEVNULL,check=True)
        digest=sha256()
        with temporary.open('rb') as source:
            for chunk in iter(lambda:source.read(1024*1024),b''):
                digest.update(chunk)
        temporary.rename(destination)
        metadata={'arquivo':destination.name,'criado_em':datetime.now(timezone.utc).isoformat(),
                  'bytes':destination.stat().st_size,'sha256':digest.hexdigest(),
                  'aviso':'Arquivo contém dados sensíveis. Guardar em volume criptografado, fora deste servidor.'}
        (folder/f'{destination.name}.json').write_text(json.dumps(metadata,indent=2)+'\n')
        print('Backup verificado estruturalmente:',destination)
        print('Restauração integral em ambiente isolado ainda precisa ser testada.')
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


if __name__=='__main__':
    main()
