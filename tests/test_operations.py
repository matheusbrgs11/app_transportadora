from uuid import uuid4
import psycopg

DRIVER={'nome':'Motorista de teste','login':'motorista-teste','senha':'uma-senha-segura-123','tipo':'carro','placa':'ABC1D23','ativo':True}


def setup_route(context,customer):
    client,a,b,login,admin,settings=context
    headers=login()
    driver=client.post('/motoristas',json=DRIVER,headers=headers)
    assert driver.status_code==201,driver.text
    first=client.post('/clientes',json=customer,headers=headers).json()
    second=client.post('/clientes',json={**customer,'cnpj':'25.107.087/0001-21','nome':'Segundo'},headers=headers).json()
    body={'nome':'Rota manhã','motorista_id':driver.json()['id'],'dias_semana':[1,2,3,4,5],'ativa':True,
          'paradas':[{'cliente_id':first['id'],'janela_inicio':'08:00','janela_fim':'10:00'},{'cliente_id':second['id']}]}
    return headers,driver.json(),first,second,body


def test_driver_atomic_creation_and_vehicle_exclusivity(context):
    client,a,b,login,admin,settings=context
    h=login()
    result=client.post('/motoristas',json=DRIVER,headers=h)
    assert result.status_code==201,result.text
    driver=result.json()
    assert 'senha' not in driver and 'senha_hash' not in driver
    assert client.post('/motoristas',json={**DRIVER,'login':'outro'},headers=h).status_code==409
    assert len(client.get('/motoristas',headers=h).json()['items'])==1
    assert client.post('/motoristas',json={**DRIVER,'placa':'DEF5678'},headers=h).status_code==409
    with psycopg.connect(admin) as conn:
        assert conn.execute('SELECT count(*) FROM veiculos WHERE empresa_id=%s',(a,)).fetchone()[0]==1
    assert client.post('/motoristas',json=DRIVER,headers=login(b)).status_code==201
    assert client.put('/motoristas/'+driver['id'],json=DRIVER,headers=login(b)).status_code==404


def test_driver_password_change_and_deactivation(context):
    client,a,b,login,admin,settings=context
    h=login()
    did=client.post('/motoristas',json=DRIVER,headers=h).json()['id']
    old=login(usuario=DRIVER['login'],senha=DRIVER['senha'])
    assert client.put('/motoristas/'+did,json={**DRIVER,'senha':' senha-com-espacos '},headers=h).status_code==200
    assert client.get('/auth/me',headers=old).status_code==401
    new=login(usuario=DRIVER['login'],senha=' senha-com-espacos ')
    assert client.put('/motoristas/'+did,json={**DRIVER,'senha':None,'ativo':False},headers=h).status_code==200
    assert client.get('/auth/me',headers=new).status_code==401


def test_route_creation_reordering_and_stale_version(context,customer):
    client,a,b,login,admin,settings=context
    h,driver,first,second,body=setup_route(context,customer)
    response=client.post('/rotas',json=body,headers=h)
    assert response.status_code==201,response.text
    route=response.json()
    assert [s['ordem'] for s in route['paradas']]==[1,2]
    assert route['paradas'][0]['janela_inicio']=='08:00:00'
    assert client.get('/rotas',headers=login(b)).json()['items']==[]
    assert client.get('/rotas/'+route['id'],headers=login(b)).status_code==404
    changed={**body,'versao':route['versao'],'paradas':list(reversed(body['paradas']))}
    update=client.put('/rotas/'+route['id'],json=changed,headers=h)
    assert update.status_code==200,update.text
    assert update.json()['paradas'][0]['cliente_id']==second['id']
    assert update.json()['paradas'][1]['janela_inicio']=='08:00:00'
    assert update.json()['versao']==2
    assert client.put('/rotas/'+route['id'],json=changed,headers=h).status_code==409
    assert client.put('/rotas/'+route['id'],json=changed,headers=login(b)).status_code==404


def test_route_blocks_invalid_cross_company_and_duplicate_stops(context,customer):
    client,a,b,login,admin,settings=context
    h,driver,first,second,body=setup_route(context,customer)
    other=client.post('/clientes',json=customer,headers=login(b)).json()
    assert client.post('/rotas',json={**body,'paradas':[{'cliente_id':other['id']}]},headers=h).status_code==422
    assert client.post('/rotas',json={**body,'motorista_id':str(uuid4())},headers=h).status_code==422
    assert client.post('/rotas',json={**body,'paradas':[body['paradas'][0],body['paradas'][0]]},headers=h).status_code==422
    assert client.post('/rotas',json={**body,'dias_semana':[0,9]},headers=h).status_code==422
    assert client.post('/rotas',json={**body,'paradas':[{'cliente_id':first['id'],'janela_inicio':'09:00'}]},headers=h).status_code==422
    assert client.post('/rotas',json={**body,'paradas':[{'cliente_id':first['id'],'janela_inicio':'10:00','janela_fim':'09:00'}]},headers=h).status_code==422
    assert client.get('/rotas',headers=h).json()['items']==[]


def test_active_route_protects_driver_and_client(context,customer):
    client,a,b,login,admin,settings=context
    h,driver,first,second,body=setup_route(context,customer)
    route=client.post('/rotas',json=body,headers=h).json()
    assert client.put('/motoristas/'+driver['id'],json={**DRIVER,'senha':None,'ativo':False},headers=h).status_code==409
    assert client.put('/clientes/'+first['id'],json={**customer,'ativo':False},headers=h).status_code==409
    assert client.put('/rotas/'+route['id'],json={**body,'ativa':False,'versao':1},headers=h).status_code==200
    assert client.put('/motoristas/'+driver['id'],json={**DRIVER,'senha':None,'ativo':False},headers=h).status_code==200
    assert client.put('/clientes/'+first['id'],json={**customer,'ativo':False},headers=h).status_code==200
    assert client.put('/rotas/'+route['id'],json={**body,'versao':2},headers=h).status_code==422
    assert client.get('/rotas/'+route['id'],headers=h).json()['ativa'] is False


def test_operation_permissions(context,customer):
    client,a,b,login,admin,settings=context
    h,driver,first,second,body=setup_route(context,customer)
    dh=login(usuario=DRIVER['login'],senha=DRIVER['senha'])
    for endpoint in ['/motoristas','/rotas','/operacao/resumo']:
        assert client.get(endpoint,headers=dh).status_code==403
    assert client.post('/rotas',json=body,headers=dh).status_code==403
    user={'nome':'Operador','login':'operador','senha':'uma-senha-segura-123','perfil':'operador'}
    assert client.post('/usuarios',json=user,headers=h).status_code==201
    oh=login(usuario='operador',senha=user['senha'])
    assert client.post('/motoristas',json={**DRIVER,'placa':'DEF5678','login':'novo'},headers=oh).status_code==403
    assert client.post('/rotas',json=body,headers=oh).status_code==201
    counts=client.get('/operacao/resumo',headers=oh).json()
    assert counts['clientes_ativos']==2 and counts['motoristas_ativos']==1 and counts['rotas_ativas']==1
