"""Ferramentas administrativas: migrações e provisionamento explícito."""
import argparse
from getpass import getpass
from hashlib import sha256
from pathlib import Path
import psycopg
from pwdlib import PasswordHash

ROOT = Path(__file__).resolve().parents[2]
MODALITIES = ['PAC','SEDEX','PAC Mini','SEDEX 12','SEDEX 10','SEDEX Hoje','Logística Reversa',
              'Carta Simples','Carta Registrada','Impresso Normal','Mala Direta','Telegrama']


def migrate(dsn, baseline_foundation=False):
    with psycopg.connect(dsn,autocommit=True) as conn:
        conn.execute('SELECT pg_advisory_lock(71024501)')
        try:
            conn.execute('''CREATE TABLE IF NOT EXISTS public.schema_migrations
                (nome text PRIMARY KEY,checksum text NOT NULL,aplicada_em timestamptz NOT NULL DEFAULT now())''')
            for path in sorted((ROOT/'database').glob('[0-9][0-9][0-9]_*.sql')):
                content = path.read_text()
                digest = sha256(content.encode()).hexdigest()
                applied = conn.execute('SELECT checksum FROM schema_migrations WHERE nome=%s',(path.name,)).fetchone()
                if applied:
                    if applied[0] != digest:
                        raise RuntimeError(f'Migração alterada depois de aplicada: {path.name}')
                    continue
                if path.name == '001_foundation.sql' and conn.execute("SELECT to_regclass('public.empresas')").fetchone()[0]:
                    if not baseline_foundation:
                        raise RuntimeError('Banco existente sem histórico. Use --baseline-foundation após verificar a estrutura 001.')
                    tables = ['empresas','usuarios','veiculos','motoristas','clientes','modalidades','rotas',
                              'rota_paradas','coletas','coleta_itens','auditoria_quantidades','posicoes_motorista']
                    found = conn.execute('''SELECT relname FROM pg_class WHERE relnamespace='public'::regnamespace
                        AND relname=ANY(%s) AND relrowsecurity AND relforcerowsecurity''',(tables,)).fetchall()
                    if {r[0] for r in found} != set(tables):
                        raise RuntimeError('Estrutura inicial incompleta ou sem RLS; baseline recusado.')
                    conn.execute('INSERT INTO schema_migrations(nome,checksum) VALUES (%s,%s)',(path.name,digest))
                    continue
                # Os arquivos existentes contêm BEGIN/COMMIT; o marcador precisa da mesma transação.
                statements = content.strip().removeprefix('BEGIN;').removesuffix('COMMIT;')
                with conn.transaction():
                    conn.execute(statements)
                    conn.execute('INSERT INTO schema_migrations(nome,checksum) VALUES (%s,%s)',(path.name,digest))
            conn.execute('REVOKE ALL ON schema_migrations FROM coleta_app')
        finally:
            conn.execute('SELECT pg_advisory_unlock(71024501)')


def provision(dsn,name,login,password):
    if len(password)<12:
        raise ValueError('Use uma senha com pelo menos 12 caracteres.')
    with psycopg.connect(dsn) as conn:
        empresa_id = conn.execute('INSERT INTO empresas(nome) VALUES (%s) RETURNING id',(name,)).fetchone()[0]
        conn.execute('INSERT INTO usuarios(empresa_id,nome,login,senha_hash,perfil) VALUES (%s,%s,%s,%s,%s)',
            (empresa_id,'Administrador',login.strip().lower(),PasswordHash.recommended().hash(password),'admin'))
        for modality in MODALITIES:
            conn.execute('INSERT INTO modalidades(empresa_id,nome) VALUES (%s,%s)',(empresa_id,modality))
        return empresa_id


def main():
    import os
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['migrate','provision'])
    parser.add_argument('--nome')
    parser.add_argument('--login')
    parser.add_argument('--baseline-foundation',action='store_true',help='Reconhece a 001 já aplicada manualmente; exige revisão prévia da estrutura.')
    args = parser.parse_args()
    dsn = os.environ['ADMIN_DATABASE_URL']
    if args.action == 'migrate':
        migrate(dsn,args.baseline_foundation)
        print('Migrações aplicadas.')
    else:
        if not args.nome or not args.login:
            parser.error('--nome e --login são obrigatórios.')
        password = getpass('Senha do administrador: ')
        if password != getpass('Confirme a senha: '):
            raise ValueError('Senhas diferentes.')
        print('Empresa criada:',provision(dsn,args.nome,args.login,password))


if __name__ == '__main__':
    main()
