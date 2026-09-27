from uuid import uuid4
from test_operations import setup_route, DRIVER


def test_scheduler_can_plan_but_cannot_change_customer_or_access(context,customer):
    client,a,b,login,_,_=context
    admin,driver,first,second,route_body=setup_route(context,customer)
    user={'nome':'Agendamento','login':'agenda','senha':'senha-segura-teste','perfil':'agendamento'}
    r=client.post('/usuarios',json=user,headers=admin)
    assert r.status_code==201,r.text
    h=login(usuario='agenda')
    assert client.get('/auth/me',headers=h).json()['perfil']=='agendamento'
    for path in ['/rastreamento','/motoristas','/rotas','/coletas','/clientes','/operacao/resumo']:
        assert client.get(path,headers=h).status_code==200,path
    assert client.get('/clientes/'+first['id'],headers=h).status_code==200
    assert client.post('/clientes',json={**customer,'cnpj':'11.222.333/0001-81'},headers=h).status_code==403
    for changes in [{'nome':'Alterado'},{'ativo':False}]:
        assert client.put('/clientes/'+first['id'],json={**customer,**changes},headers=h).status_code==403
    assert client.put('/clientes/'+first['id']+'/localizacao',
        json={'versao':1,'latitude':0,'longitude':0,'fonte':'gps_campo','motivo':'Teste'},headers=h).status_code==403
    assert client.post('/clientes/importacoes/previa',files={'arquivo':('teste.xlsx',b'test')},headers=h).status_code==403
    assert client.post('/clientes/importacoes/'+str(uuid4())+'/confirmar',json={'linhas':[1]},headers=h).status_code==403
    assert client.post('/usuarios',json={**user,'login':'outro','perfil':'admin'},headers=h).status_code==403
    assert client.post('/motoristas',json={**DRIVER,'login':'outro'},headers=h).status_code==403
    assert client.put('/motoristas/'+driver['id'],json=DRIVER,headers=h).status_code==403
    route=client.post('/rotas',json=route_body,headers=h)
    assert route.status_code==201,route.text
    updated=client.put('/rotas/'+route.json()['id'],json={**route_body,'versao':1,'nome':'Rota agendada'},headers=h)
    assert updated.status_code==200,updated.text
    mod=client.get('/modalidades',headers=h).json()['items'][0]['id']
    body={'id_local_dispositivo':str(uuid4()),'cliente_id':first['id'],'motorista_id':driver['id'],
        'status':'agendada','origem':'rota_fixa','agendada_para':'2026-10-01T12:00:00Z',
        'itens':[{'modalidade_id':mod,'quantidade':None,'quantidade_status':'a_conferir'}]}
    result=client.post('/coletas',json=body,headers=h)
    assert result.status_code==201,result.text
    foreign=client.post('/clientes',json=customer,headers=login(b)).json()['id']
    assert client.get('/clientes/'+foreign,headers=h).status_code==404
    assert client.post('/coletas',json={**body,'id_local_dispositivo':str(uuid4()),'cliente_id':foreign},headers=h).status_code in (404,422)
    assert client.get('/coletas',headers=login(b)).json()['total']==0
    # Administrator retains customer management.
    assert client.put('/clientes/'+first['id'],json={**customer,'nome':'Atualizado pelo administrador'},headers=admin).status_code==200
