"""Rotina agendada de limpeza. Executar fora da API, com credenciais separadas."""
import argparse
import os
import psycopg

from .db import transaction
from .config import Settings
from .calls import expire_calls
from .tracking import cleanup


def run(admin_dsn: str, runtime_dsn: str) -> int:
    # A credencial administrativa é usada apenas para enumerar empresas, sem
    # alterar dados operacionais. Cada limpeza usa a conta da API e sua RLS.
    with psycopg.connect(admin_dsn) as conn:
        companies = [row[0] for row in conn.execute('SELECT id FROM empresas')]
    settings = Settings(runtime_dsn, 'not-used-by-maintenance-' * 2)
    for company_id in companies:
        with transaction(settings, company_id) as conn:
            cleanup(conn)
            expire_calls(conn, {'empresa_id':company_id})
            conn.execute("DELETE FROM importacoes WHERE expira_em<now() AND confirmada_em IS NULL")
            conn.execute("DELETE FROM sessoes WHERE expira_em<now()-interval '30 days'")
    return len(companies)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Confirma a execução da manutenção.')
    args = parser.parse_args()
    if not args.execute:
        parser.error('Use --execute após configurar ADMIN_DATABASE_URL e DATABASE_URL.')
    print('Empresas verificadas:', run(os.environ['ADMIN_DATABASE_URL'], os.environ['DATABASE_URL']))


if __name__ == '__main__':
    main()
