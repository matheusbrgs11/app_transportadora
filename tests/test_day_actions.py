from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from uuid import uuid4
from test_daily import issue, DAY
from test_driver_visits import prepare as setup
from test_operations import DRIVER


def test_date_exception_and_audit_permissions(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,_=setup(context,customer)
    root='/rotas/'+body['rota_id']
    blocked={'operar':False,'motivo':'Feriado local'}
    assert client.put(root+'/excecoes/'+DAY,json=blocked,headers=dh).status_code==403
    assert client.put(root+'/excecoes/'+DAY,json=blocked,headers=login(b)).status_code==404
    assert client.put(root+'/excecoes/'+DAY,json={**blocked,'motivo':' '},headers=h).status_code==422
    client.put(root+'/excecoes/'+DAY,json=blocked,headers=h).raise_for_status()
    assert client.post(root+'/execucoes?data='+DAY,headers=h).status_code==422
    assert client.post('/motorista/rota-do-dia/preparar?data='+DAY,headers=dh).json()['rotas']==[]
    assert client.get(root+'/execucoes?data='+DAY,headers=h).json()=={'execucao':None,'excecao':blocked}
    extra='2026-05-10'
    client.put(root+'/excecoes/'+extra,json={'operar':True,'motivo':'Atendimento extra'},headers=h).raise_for_status()
    run=client.post('/motorista/rota-do-dia/preparar?data='+extra,headers=dh)
    assert run.status_code==200 and len(run.json()['rotas'])==1
    assert client.put(root+'/excecoes/'+extra,json=blocked,headers=h).status_code==409
    assert client.get(root+'/execucoes?data='+extra,headers=login(b)).status_code==404


def test_transfer_preserves_identity_and_removes_old_driver_access(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,_=setup(context,customer)
    run,body=issue(client,h,body)
    new=client.post('/motoristas',headers=h,json={**DRIVER,'login':'substituto','placa':'DEF1234','nome':'Substituto'}).json()
    other=login(usuario='substituto',senha=DRIVER['senha'])
    change={'versao':1,'motivo':'Veículo parado','motorista_id':new['id']}
    path='/coletas/'+body['coleta_id']+'/transferir'
    assert client.post(path,headers=dh,json=change).status_code==403
    assert client.post(path,headers=login(b),json=change).status_code==404
    client.post(path,headers=h,json=change).raise_for_status()
    assert client.post(path,headers=h,json=change).status_code==409
    assert client.post('/motorista/coletas',headers=dh,json=body).status_code==404
    plan=client.post('/motorista/rota-do-dia/preparar?data='+DAY,headers=other).json()
    assert plan['total_paradas']==1 and plan['rotas'][0]['paradas'][0]['coleta_id']==body['coleta_id']
    assert client.post('/motorista/rota-do-dia/preparar?data='+DAY,headers=dh).json()['total_paradas']==1
    client.post('/motorista/coletas',headers=other,json=body).raise_for_status()
    detail=client.get('/coletas/'+body['coleta_id'],headers=h).json()
    assert detail['motorista_nome']=='Substituto'
    assert detail['eventos'][1]['dados']['acao']=='transferencia'
    assert detail['eventos'][1]['dados']['motorista_anterior_nome']!=detail['motorista_nome']
    assert client.post(path,headers=h,json={**change,'versao':3}).status_code==409


def test_nonattendance_idempotence_history_and_revisit_chain(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,_=setup(context,customer)
    run,body=issue(client,h,body)
    failed={**body,'status':'nao_atendida','motivo':'Cliente fechado','itens':[]}
    for invalid in ({'motivo':' '},{'itens':body['itens']},{'concluida_em':'2099-01-01T12:00:00Z'}):
        assert client.post('/motorista/coletas',headers=dh,json={**failed,**invalid}).status_code==422
    for _ in range(2):
        r=client.post('/motorista/coletas',headers=dh,json=failed)
        assert r.status_code==200 and r.json()['status']=='nao_atendida'
    detail=client.get('/coletas/'+body['coleta_id'],headers=h).json()
    assert detail['concluida_em'] is None and detail['eventos'][-1]['motivo']=='Cliente fechado'
    request={'versao':2,'motivo':'Cliente reabriu','id_local_dispositivo':str(uuid4())}
    path='/coletas/'+body['coleta_id']+'/revisitas'
    assert client.post(path,headers=dh,json=request).status_code==403
    assert client.post(path,headers=login(b),json=request).status_code==404
    with ThreadPoolExecutor(2) as pool:
        responses=list(pool.map(lambda _:client.post(path,headers=h,json=request),range(2)))
    assert all(r.status_code==200 for r in responses)
    cid=responses[0].json()['id']
    assert cid==responses[1].json()['id'] and cid!=body['coleta_id']
    assert client.post(path,headers=h,json={**request,'id_local_dispositivo':str(uuid4())}).status_code==409
    assert client.post(path,headers=h,json={**request,'motivo':'Mudou'}).status_code==409
    second={**body,'id_local_dispositivo':str(uuid4()),'coleta_id':cid}
    client.post('/motorista/coletas',headers=dh,json=second).raise_for_status()
    detail=client.get('/coletas/'+cid,headers=h).json()
    assert detail['tentativa']==2 and detail['revisita_de']==body['coleta_id']
    assert client.get('/coletas/'+body['coleta_id'],headers=h).json()['status']=='nao_atendida'
    history=client.get('/motorista/historico?data_inicio='+DAY+'&data_fim='+DAY,headers=dh).json()
    assert history['total']==3
    assert {row['status'] for row in history['items']}=={'agendada','concluida','nao_atendida'}
    assert all('cnpj' not in row and 'cliente_cnpj' not in row for row in history['items'])
    page=client.get('/motorista/historico?data_inicio='+DAY+'&data_fim='+DAY+'&limit=1&offset=1',headers=dh).json()
    assert page['total']==3 and len(page['items'])==1
    six_month_start=(date.fromisoformat(DAY)-timedelta(days=183)).isoformat()
    assert client.get('/motorista/historico?data_inicio='+six_month_start+'&data_fim='+DAY,headers=dh).json()['total']==3
    outside_range=(date.fromisoformat(DAY)-timedelta(days=184)).isoformat()
    assert client.get('/motorista/historico?data_inicio='+outside_range+'&data_fim='+DAY,headers=dh).status_code==422
    assert client.get('/motorista/historico',headers=h).status_code==403
    client.post('/motoristas',headers=login(b),json=DRIVER).raise_for_status()
    foreign=login(b,usuario=DRIVER['login'],senha=DRIVER['senha'])
    assert client.get('/motorista/historico?data_inicio='+DAY+'&data_fim='+DAY,headers=foreign).json()['total']==0
    plan=client.post('/motorista/rota-do-dia/preparar?data='+DAY,headers=dh).json()['rotas'][0]
    assert plan['progresso']=={'agendada':1,'concluida':1,'nao_atendida':1,'cancelada':0}
    # Revisits can themselves receive a successor without modifying the prior attempts.
    r=client.post('/coletas/'+cid+'/revisitas',headers=h,json={**request,'id_local_dispositivo':str(uuid4())})
    assert r.status_code==200,r.text
    assert client.get('/coletas/'+r.json()['id'],headers=h).json()['tentativa']==3
