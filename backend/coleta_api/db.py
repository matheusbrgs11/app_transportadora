from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row


@contextmanager
def transaction(settings, empresa_id=None):
    with psycopg.connect(settings.database_url, row_factory=dict_row, connect_timeout=5) as conn:
        role = conn.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
        if role['rolsuper'] or role['rolbypassrls']:
            raise RuntimeError('A API não pode usar superusuário ou BYPASSRLS.')
        conn.execute('SET LOCAL ROLE coleta_app')
        if empresa_id is not None:
            conn.execute("SELECT set_config('app.empresa_id',%s,true)", (str(empresa_id),))
        yield conn
