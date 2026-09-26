from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from test_driver_visits import prepare as setup
from test_operations import DRIVER

DAY='2026-05-07'


def issue(client,h,body):
    r=client.post('/rotas/'+body['rota_id']+'/execucoes?data='+DAY,headers=h)
    assert r.status_code==200,r.text
    run=r.json()
    stop=next(s for s in run['paradas'] if s['cliente_id']==body['cliente_id'])
    return run,{**body,'coleta_id':stop['coleta_id']}


def test_preparation_is_concurrent_idempotent_and_readonly_get(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,route=setup(context,customer)
    assert client.get('/motorista/rota-do-dia?data='+DAY,headers=dh).status_code==200
    assert client.get('/coletas',headers=h).json()['total']==0
    with ThreadPoolExecutor(2) as pool:
        runs=list(pool.map(lambda _:issue(client,h,body)[0],range(2)))
    assert runs[0]['execucao_id']==runs[1]['execucao_id']
    assert len(runs[0]['paradas'])==2
    assert client.get('/coletas',headers=h).json()['agendadas']==2
    assert 'cnpj' not in runs[0]['paradas'][0]


def test_execution_keeps_snapshot_and_completes_same_collection(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,route=setup(context,customer)
    run,body=issue(client,h,body)
    client.put('/rotas/'+body['rota_id'],headers=h,json={**route,'versao':1,'nome':'Alterada','ativa':False,'paradas':list(reversed(route['paradas']))}).raise_for_status()
    plan=client.post('/motorista/rota-do-dia/preparar?data='+DAY,headers=dh).json()
    assert plan['rotas'][0]['nome']==run['nome']
    assert plan['rotas'][0]['paradas'][0]['cliente_id']==run['paradas'][0]['cliente_id']
    result=client.post('/motorista/coletas',json=body,headers=dh)
    assert result.status_code==200,result.text
    assert result.json()['id']==body['coleta_id']
    assert client.post('/motorista/coletas',json=body,headers=dh).status_code==200
    assert client.post('/motorista/coletas',json={**body,'observacoes':'outro'},headers=dh).status_code==409
    detail=client.get('/coletas/'+body['coleta_id'],headers=h).json()
    assert [e['status_novo'] for e in detail['eventos']]==['agendada','concluida']
    assert client.get('/coletas',headers=h).json()['total']==2
    assert client.post('/motorista/coletas',json={**body,'id_local_dispositivo':str(uuid4())},headers=dh).status_code==409


def test_two_devices_finish_one_visit(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,route=setup(context,customer)
    _,body=issue(client,h,body)
    bodies=[body,{**body,'id_local_dispositivo':str(uuid4())}]
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda x:client.post('/motorista/coletas',headers=dh,json=x),bodies))
    assert sorted(r.status_code for r in results)==[200,409]
    assert client.get('/coletas',headers=h).json()['concluidas']==1
    detail=client.get('/coletas/'+body['coleta_id'],headers=h).json()
    assert len(detail['eventos'])==2


def test_daily_permissions_date_and_legacy_protection(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,route=setup(context,customer)
    _,body=issue(client,h,body)
    assert client.post('/rotas/'+body['rota_id']+'/execucoes?data='+DAY,headers=dh).status_code==403
    assert client.post('/rotas/'+body['rota_id']+'/execucoes?data='+DAY,headers=login(b)).status_code==404
    client.post('/motoristas',json={**DRIVER,'login':'outro','placa':'DEF1234'},headers=h).raise_for_status()
    other=login(usuario='outro',senha=DRIVER['senha'])
    assert client.post('/motorista/coletas',json=body,headers=other).status_code==404
    assert client.post('/motorista/coletas',json={**body,'concluida_em':'2026-05-08T12:00:00Z'},headers=dh).status_code==422
    assert client.post('/motorista/coletas',json={k:v for k,v in body.items() if k!='coleta_id'},headers=dh).status_code==409
    assert client.post('/motorista/rota-do-dia/preparar?data=2026-05-10',headers=dh).json()['rotas']==[]
    assert client.get('/coletas',headers=h).json()['concluidas']==0


def test_staff_can_complete_untyped_scheduled_visit_and_driver_cannot_overwrite(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,route=setup(context,customer)
    _,body=issue(client,h,body)
    result=client.put('/coletas/'+body['coleta_id']+'/status',headers=h,json={
        'versao':1,'status':'concluida','concluida_em':body['concluida_em'],'itens':body['itens']})
    assert result.status_code==200,result.text
    assert len(result.json()['itens'])==1
    assert client.post('/motorista/coletas',headers=dh,json=body).status_code==409


def test_legacy_visits_block_daily_generation(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,route=setup(context,customer)
    client.post('/motorista/coletas',headers=dh,json=body).raise_for_status()
    result=client.post('/rotas/'+body['rota_id']+'/execucoes?data='+DAY,headers=h)
    assert result.status_code==409,result.text
    assert client.get('/coletas',headers=h).json()['total']==1
