from datetime import datetime,timedelta,timezone
from io import BytesIO
from uuid import uuid4
import jwt
import psycopg
from openpyxl import Workbook
from coleta_api.db import transaction


def workbook(rows):
    book=Workbook()
    for row in rows:
        book.active.append(row)
    data=BytesIO()
    book.save(data)
    return data.getvalue()


HEADERS=['NOME','','ENDERECO','','NUMERO','COMPL','BAIRRO','CIDADE','ESTADO','CEP','TELEFONE','CGC']
ROW=['Fictício','','Rua teste','','','Quadra 1','Centro','Goiania','GO','74911-190','','00.958.251/0001-83']


def test_health_and_requires_login(context):
    client,*_=context
    assert client.get('/health').json()=={'status':'ok'}
    assert client.get('/clientes').status_code==401


def test_crud_and_isolation(context,customer):
    client,a,b,login,admin,settings=context
    ha,hb=login(a),login(b)
    response=client.post('/clientes',json=customer,headers=ha)
    assert response.status_code==201,response.text
    ca=response.json()
    assert ca['cnpj']=='00958251000183'
    assert ca['contrato_status']=='nao_informado'
    assert client.get('/clientes',headers=hb).json()['total']==0
    assert client.get('/clientes/'+ca['id'],headers=hb).status_code==404
    assert client.put('/clientes/'+ca['id'],json=customer,headers=hb).status_code==404
    assert client.post('/clientes',json=customer,headers=hb).status_code==201
    assert client.post('/clientes',json=customer,headers=ha).status_code==409
    assert client.post('/clientes',json={**customer,'empresa_id':str(b)},headers=ha).status_code==422
    updated={**customer,'nome':'Editado','ativo':False}
    assert client.put('/clientes/'+ca['id'],json=updated,headers=ha).status_code==200
    assert client.get('/clientes?ativo=true',headers=ha).json()['total']==0
    assert client.get('/clientes?q=Editado&ativo=false',headers=ha).json()['total']==1
    with transaction(settings) as conn:
        assert conn.execute('SELECT count(*) AS total FROM clientes').fetchone()['total']==0


def test_login_logout_and_disabled_user(context):
    client,a,b,login,admin,settings=context
    assert client.post('/auth/login',json={'empresa_id':str(a),'usuario_login':'admin','senha':'errada'}).status_code==401
    h=login()
    assert client.get('/auth/me',headers=h).json()['perfil']=='admin'
    assert client.post('/auth/logout',headers=h).status_code==204
    assert client.get('/auth/me',headers=h).status_code==401
    h=login()
    with psycopg.connect(admin) as conn:
        conn.execute('UPDATE usuarios SET ativo=false WHERE empresa_id=%s',(a,))
    assert client.get('/clientes',headers=h).status_code==401


def test_token_tampering_and_expiry(context):
    client,a,b,login,admin,settings=context
    h=login()
    token=h['Authorization'].split()[1]
    payload=jwt.decode(token,settings.jwt_secret,algorithms=['HS256'],audience='coleta')
    payload['empresa_id']=str(b)
    forged=jwt.encode(payload,'attacker-secret-which-is-long-enough',algorithm='HS256')
    assert client.get('/clientes',headers={'Authorization':'Bearer '+forged}).status_code==401
    payload['exp']=datetime.now(timezone.utc)-timedelta(seconds=1)
    expired=jwt.encode(payload,settings.jwt_secret,algorithm='HS256')
    assert client.get('/clientes',headers={'Authorization':'Bearer '+expired}).status_code==401


def test_driver_and_operator_permissions(context,customer):
    client,a,b,login,admin,settings=context
    h=login()
    for role in ['motorista','operador']:
        assert client.post('/usuarios',json={'nome':role,'login':role,'senha':'senha-segura-teste','perfil':role},headers=h).status_code==201
    driver=login(usuario='motorista')
    assert client.get('/clientes',headers=driver).status_code==403
    assert client.post('/clientes',json=customer,headers=driver).status_code==403
    operator=login(usuario='operador')
    assert client.post('/clientes',json=customer,headers=operator).status_code==201
    assert client.post('/usuarios',json={'nome':'X','login':'x','senha':'senha-segura-teste','perfil':'admin'},headers=operator).status_code==403
    assert client.post('/clientes/importacoes/previa',files={'arquivo':('teste.xlsx',workbook([HEADERS,ROW]))},headers=operator).status_code==403


def test_import_preview_confirmation_replay_and_other_tenant(context):
    client,a,b,login,admin,settings=context
    h=login()
    data=workbook([HEADERS,ROW,[*ROW[:11],'00.000.000/0000-00']])
    response=client.post('/clientes/importacoes/previa',files={'arquivo':('teste.xlsx',data)},headers=h)
    assert response.status_code==201,response.text
    batch=response.json()
    assert batch['validas']==1
    assert client.get('/clientes',headers=h).json()['total']==0
    path=f'/clientes/importacoes/{batch["id"]}/confirmar'
    assert client.post(path,json={'linhas':[2]},headers=login(b)).status_code==404
    assert client.post(path,json={'linhas':[3]},headers=h).status_code==422
    assert client.post(path,json={'linhas':[2,2]},headers=h).status_code==422
    assert client.post(path,json={'linhas':[2]},headers=h).json()=={'importados':1,'ja_confirmada':False}
    assert client.post(path,json={'linhas':[2]},headers=h).json()=={'importados':1,'ja_confirmada':True}
    assert client.get('/clientes',headers=h).json()['total']==1
    again=client.post('/clientes/importacoes/previa',files={'arquivo':('teste.xlsx',data)},headers=h).json()
    assert again['validas']==0


def test_import_expiry_and_transaction_rollback(context,customer):
    client,a,b,login,admin,settings=context
    h=login()
    row2=[*ROW[:11],'25.107.087/0001-21']
    batch=client.post('/clientes/importacoes/previa',files={'arquivo':('teste.xlsx',workbook([HEADERS,ROW,row2]))},headers=h).json()
    assert batch['validas']==2
    assert client.post('/clientes',json={**customer,'cnpj':row2[-1]},headers=h).status_code==201
    path=f'/clientes/importacoes/{batch["id"]}/confirmar'
    assert client.post(path,json={'linhas':[2,3]},headers=h).status_code==409
    assert client.get('/clientes',headers=h).json()['total']==1
    with psycopg.connect(admin) as conn:
        conn.execute("UPDATE importacoes SET expira_em=now()-interval '1 second' WHERE id=%s",(batch['id'],))
    assert client.post(path,json={'linhas':[2]},headers=h).status_code==410


def test_wrong_company_and_rate_limit(context):
    client,a,b,login,admin,settings=context
    body={'empresa_id':str(uuid4()),'usuario_login':'admin','senha':'senha-segura-teste'}
    for _ in range(15):
        assert client.post('/auth/login',json=body).status_code==401
    assert client.post('/auth/login',json=body).status_code==429


def test_position_invalidated_on_address_edit(context,customer):
    client,a,b,login,admin,settings=context
    h=login()
    cid=client.post('/clientes',json=customer,headers=h).json()['id']
    with psycopg.connect(admin) as conn:
        conn.execute('UPDATE clientes SET localizacao=ST_SetSRID(ST_MakePoint(-49,-16),4326),localizacao_confirmada=true WHERE id=%s',(cid,))
    response=client.put('/clientes/'+cid,json={**customer,'endereco':'Rua nova'},headers=h)
    assert response.status_code==200
    assert response.json()['localizacao_confirmada'] is False


def test_rls_cross_write_and_fk(context):
    _,a,b,_,admin,settings=context
    try:
        with transaction(settings,a) as conn:
            conn.execute('INSERT INTO veiculos(empresa_id,tipo,placa) VALUES (%s,%s,%s)',(b,'moto','TESTE'))
        assert False,'RLS deveria rejeitar escrita cruzada'
    except psycopg.errors.InsufficientPrivilege:
        pass
    with psycopg.connect(admin) as conn:
        uid=conn.execute('SELECT id FROM usuarios WHERE empresa_id=%s',(b,)).fetchone()[0]
    try:
        with transaction(settings,a) as conn:
            conn.execute('INSERT INTO motoristas(empresa_id,usuario_id) VALUES (%s,%s)',(a,uid))
        assert False,'FK deveria rejeitar vínculo cruzado'
    except psycopg.errors.ForeignKeyViolation:
        pass
