import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import pytest
import psycopg
from fastapi.testclient import TestClient
from coleta_api.cli import migrate, provision
from coleta_api.config import Settings
from coleta_api.main import create_app, PASSWORDS


@pytest.fixture(scope='session')
def database():
    """Cluster descartável privado, sem conexão ao PostgreSQL do usuário."""
    bins = Path(os.environ.get('PG_BIN','/usr/lib/postgresql/17/bin'))
    if not (bins/'initdb').exists():
        pytest.fail('Instale PostgreSQL/PostGIS ou configure PG_BIN para executar os testes de integração.')
    folder = Path(tempfile.mkdtemp(prefix='coleta-tests-'))
    started = False
    def run(command):
        return subprocess.run(command,check=True,capture_output=True,text=True)
    try:
        run([str(bins/'initdb'),'-D',str(folder/'data'),'-A','trust','-U','test_owner','--no-locale','--encoding=UTF8'])
        run([str(bins/'pg_ctl'),'-D',str(folder/'data'),'-l',str(folder/'postgres.log'),
             '-o',f"-k {folder} -h '' -p 55439",'-w','start'])
        started = True
        admin = f'host={folder} port=55439 dbname=postgres user=test_owner'
        migrate(admin)
        migrate(admin)  # A reaplicação não recria tabelas.
        with psycopg.connect(admin) as conn:
            conn.execute('CREATE ROLE test_api LOGIN NOSUPERUSER NOBYPASSRLS')
            conn.execute('GRANT coleta_app TO test_api')
        yield admin,f'host={folder} port=55439 dbname=postgres user=test_api'
    except subprocess.CalledProcessError as exc:
        log = (folder/'postgres.log').read_text() if (folder/'postgres.log').exists() else ''
        raise RuntimeError(f'{exc.stderr}\n{log}') from exc
    finally:
        if started:
            subprocess.run([str(bins/'pg_ctl'),'-D',str(folder/'data'),'-m','fast','-w','stop'],capture_output=True)
        shutil.rmtree(folder)


@pytest.fixture
def context(database):
    admin, runtime = database
    empresa_a = provision(admin,'Empresa A','admin','senha-segura-teste')
    empresa_b = provision(admin,'Empresa B','admin','senha-segura-teste')
    settings = Settings(runtime,'segredo-de-testes-com-mais-de-trinta-e-dois-caracteres')
    with TestClient(create_app(settings)) as client:
        def login(empresa=empresa_a,usuario='admin',senha='senha-segura-teste'):
            response = client.post('/auth/login',json={'empresa_id':str(empresa),'usuario_login':usuario,'senha':senha})
            assert response.status_code==200,response.text
            return {'Authorization':'Bearer '+response.json()['access_token']}
        yield client,empresa_a,empresa_b,login,admin,settings


@pytest.fixture
def customer():
    return {'nome':'Cliente fictício','cnpj':'00.958.251/0001-83','endereco':'Rua de teste',
            'cidade':'Goiania','estado':'GO','cep':'74911-190'}
