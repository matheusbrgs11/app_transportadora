from uuid import uuid4
from test_operations import setup_route, DRIVER


def prepare(context,customer):
    client,a,b,login,admin,settings=context
    h,driver,first,second,route_body=setup_route(context,customer)
    route=client.post('/rotas',json=route_body,headers=h).json()
    dh=login(usuario=DRIVER['login'],senha=DRIVER['senha'])
    mod=client.get('/motorista/modalidades',headers=dh).json()['items'][0]
    body={'id_local_dispositivo':str(uuid4()),'rota_id':route['id'],'versao_rota':1,
          'cliente_id':first['id'],'concluida_em':'2026-05-07T12:00:00Z',
          'itens':[{'modalidade_id':mod['id'],'quantidade':None,'quantidade_status':'a_conferir'}]}
    return h,dh,body,route_body


def test_driver_visit_history_replay_and_changed_route(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,route=prepare(context,customer)
    created=client.post('/motorista/coletas',json=body,headers=dh)
    assert created.status_code==201,created.text
    cid=created.json()['id']
    detail=client.get('/coletas/'+cid,headers=h).json()
    assert detail['status']=='concluida' and detail['itens'][0]['quantidade_status']=='a_conferir'
    assert detail['eventos'][0]['dados']['execucao_rota']['rota_id']==body['rota_id']
    client.put('/rotas/'+body['rota_id'],json={**route,'versao':1,'ativa':False},headers=h).raise_for_status()
    retry=client.post('/motorista/coletas',json=body,headers=dh)
    assert retry.status_code==200 and retry.json()['id']==cid
    assert client.post('/motorista/coletas',json={**body,'versao_rota':2},headers=dh).status_code==409
    assert client.post('/motorista/coletas',json={**body,'observacoes':'alterado'},headers=dh).status_code==409
    assert client.get('/coletas',headers=h).json()['total']==1


def test_driver_visit_authorization_and_validation(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,route=prepare(context,customer)
    assert client.post('/motorista/coletas',json=body,headers=h).status_code==403
    assert client.post('/motorista/coletas',json=body).status_code==401
    for changes,status in [({'rota_id':str(uuid4())},403),({'cliente_id':str(uuid4())},403),
        ({'versao_rota':2},409),({'concluida_em':'2026-05-10T12:00:00Z'},422),
        ({'concluida_em':'2099-05-07T12:00:00Z'},422),({'itens':body['itens']*2},422),
        ({'motorista_id':str(uuid4())},422)]:
        r=client.post('/motorista/coletas',json={**body,**changes},headers=dh)
        assert r.status_code==status,r.text
    client.post('/motoristas',json={**DRIVER,'login':'outro','placa':'DEF1234'},headers=h).raise_for_status()
    other=login(usuario='outro',senha=DRIVER['senha'])
    assert client.post('/motorista/coletas',json=body,headers=other).status_code==403
    client.post('/motoristas',json=DRIVER,headers=login(b)).raise_for_status()
    foreign=login(b,usuario=DRIVER['login'],senha=DRIVER['senha'])
    assert client.post('/motorista/coletas',json=body,headers=foreign).status_code==403
    assert client.get('/coletas',headers=h).json()['total']==0
