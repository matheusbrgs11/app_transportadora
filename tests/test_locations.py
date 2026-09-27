from concurrent.futures import ThreadPoolExecutor
from test_driver_visits import prepare
from test_daily import issue,DAY


def test_location_permissions_concurrency_and_history_snapshot(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,_=prepare(context,customer)
    cid=body['cliente_id'];path='/clientes/'+cid+'/localizacao'
    point={'versao':1,'latitude':-16.68,'longitude':-49.25,'fonte':'cliente','motivo':'Entrada conferida pelo cliente'}
    assert client.put(path,headers=dh,json=point).status_code==403
    assert client.put(path,headers=login(b),json=point).status_code==404
    assert client.get(path,headers=dh).status_code==403
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda _:client.put(path,headers=h,json=point),range(2)))
    assert sorted(r.status_code for r in results)==[200,409]
    record=client.get('/clientes/'+cid,headers=h).json()
    assert record['latitude']==point['latitude'] and record['longitude']==point['longitude']
    assert record['localizacao_confirmada'] and record['localizacao_versao']==2
    run,_=issue(client,h,body)
    client.put(path,headers=h,json={**point,'versao':2,'latitude':-17.0}).raise_for_status()
    current=client.get('/rotas/'+body['rota_id'],headers=h).json()
    assert next(p for p in current['paradas'] if p['cliente_id']==cid)['latitude']==-17.0
    frozen=client.post('/motorista/rota-do-dia/preparar?data='+DAY,headers=dh).json()['rotas'][0]
    stop=next(p for p in frozen['paradas'] if p['cliente_id']==cid)
    assert stop['latitude']==-16.68 and stop['localizacao_confirmada']
    # Changing the address invalidates the point and stale location forms.
    client.put('/clientes/'+cid,headers=h,json={**customer,'endereco':'Rua nova'}).raise_for_status()
    record=client.get('/clientes/'+cid,headers=h).json()
    assert record['latitude'] is None and not record['localizacao_confirmada'] and record['localizacao_versao']==4
    assert client.put(path,headers=h,json={**point,'versao':3}).status_code==409


def test_location_validation_removal_and_contact_changes(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,_=prepare(context,customer)
    path='/clientes/'+body['cliente_id']+'/localizacao'
    point={'versao':1,'latitude':0,'longitude':0,'fonte':'gps_campo','motivo':'Ponto de teste'}
    for change in [{'latitude':91},{'longitude':181},{'longitude':None},{'fonte':None},{'motivo':' '},{'latitude':'NaN'}]:
        assert client.put(path,headers=h,json={**point,**change}).status_code==422
    client.put(path,headers=h,json=point).raise_for_status()
    client.put('/clientes/'+body['cliente_id'],headers=h,json={**customer,'telefone':'62999999999'}).raise_for_status()
    record=client.get(path,headers=h).json()
    assert record['localizacao_confirmada'] and record['localizacao_versao']==2
    client.put(path,headers=h,json={'versao':2,'motivo':'Ponto incorreto, aguardando conferência'}).raise_for_status()
    record=client.get(path,headers=h).json()
    assert record['latitude'] is None and record['longitude'] is None and not record['localizacao_confirmada']
