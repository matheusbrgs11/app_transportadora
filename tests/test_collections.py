from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import psycopg
from test_operations import DRIVER


def setup(context,customer):
    client,a,b,login,admin,settings=context
    h=login()
    customer_id=client.post('/clientes',json=customer,headers=h).json()['id']
    driver=client.post('/motoristas',json=DRIVER,headers=h).json()['id']
    mods=client.get('/modalidades',headers=h).json()['items']
    ids={m['nome']:m['id'] for m in mods}
    body={'id_local_dispositivo':str(uuid4()),'cliente_id':customer_id,'motorista_id':driver,'origem':'rota_fixa',
          'status':'concluida','concluida_em':'2026-05-10T12:30:00-03:00',
          'itens':[{'modalidade_id':ids['PAC'],'quantidade':10,'quantidade_status':'confirmada'},
                   {'modalidade_id':ids['SEDEX'],'quantidade':7,'quantidade_status':'a_conferir'}]}
    return h,body,ids


def create(client,h,body):
    response=client.post('/coletas',json=body,headers=h)
    assert response.status_code==201,response.text
    return response.json()


def test_collection_summary_and_snapshot(context,customer):
    client,a,b,login,admin,settings=context
    h,body,ids=setup(context,customer)
    record=create(client,h,body)
    assert len(record['itens'])==2 and len(record['eventos'])==1
    assert record['dados_registro']['cliente_nome']==customer['nome']
    result=client.get('/coletas',headers=h).json()
    assert result['total']==1 and result['concluidas']==1
    summary={x['modalidade_nome']:x for x in result['por_modalidade']}
    assert summary['PAC']['volumes_confirmados']==10
    assert summary['SEDEX']['volumes_confirmados']==0
    assert summary['SEDEX']['itens_a_conferir']==1
    assert client.put('/clientes/'+body['cliente_id'],json={**customer,'nome':'Nome alterado','endereco':'Rua nova','ativo':False},headers=h).status_code==200
    with psycopg.connect(admin) as conn:
        conn.execute("UPDATE modalidades SET nome='PAC alterado',ativa=false WHERE id=%s",(ids['PAC'],))
    detail=client.get('/coletas/'+record['id'],headers=h).json()
    assert detail['cliente_nome']==customer['nome']
    assert detail['dados_registro']['endereco']['endereco']==customer['endereco']
    assert any(i['modalidade_nome']=='PAC' for i in detail['itens'])
    assert client.get('/coletas',params={'cliente_id':body['cliente_id']},headers=h).json()['total']==1


def test_idempotency_conflict_and_concurrent_retry(context,customer):
    client,a,b,login,admin,settings=context
    h,body,ids=setup(context,customer)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda _:client.post('/coletas',json=body,headers=h),range(2)))
    assert sorted(r.status_code for r in responses)==[200,201]
    assert responses[0].json()['id']==responses[1].json()['id']
    assert client.post('/coletas',json={**body,'itens':list(reversed(body['itens']))},headers=h).status_code==200
    assert client.post('/coletas',json={**body,'observacoes':'conteúdo diferente'},headers=h).status_code==409
    assert client.get('/coletas',headers=h).json()['total']==1


def test_tenant_and_role_permissions(context,customer):
    client,a,b,login,admin,settings=context
    h,body,ids=setup(context,customer)
    record=create(client,h,body)
    hb=login(b)
    assert client.get('/coletas',headers=hb).json()['total']==0
    assert client.get('/coletas/'+record['id'],headers=hb).status_code==404
    assert client.post('/coletas',json={**body,'id_local_dispositivo':str(uuid4())},headers=hb).status_code==422
    item=record['itens'][0]
    path=f'/coletas/{record["id"]}/itens/{item["id"]}/quantidade'
    assert client.put(path,json={'versao':1,'quantidade':99,'motivo':'Teste'},headers=hb).status_code==404
    operator={'nome':'Operador','login':'op','senha':'senha-segura-teste','perfil':'operador'}
    client.post('/usuarios',json=operator,headers=h)
    oh=login(usuario='op')
    assert client.get('/coletas',headers=oh).status_code==200
    assert client.put(path,json={'versao':1,'quantidade':99,'motivo':'Teste'},headers=oh).status_code==403
    driver=login(usuario=DRIVER['login'],senha=DRIVER['senha'])
    for endpoint in ['/coletas','/modalidades','/coletas/'+record['id']]:
        assert client.get(endpoint,headers=driver).status_code==403


def test_lifecycle_and_event_history(context,customer):
    client,a,b,login,admin,settings=context
    h,body,ids=setup(context,customer)
    scheduled={**body,'status':'agendada','concluida_em':None,'agendada_para':'2026-05-10T09:00:00-03:00'}
    record=create(client,h,scheduled)
    assert client.get('/coletas',headers=h).json()['por_modalidade']==[]
    data={'versao':1,'status':'concluida','concluida_em':body['concluida_em'],'itens':body['itens']}
    updated=client.put('/coletas/'+record['id']+'/status',json=data,headers=h)
    assert updated.status_code==200,updated.text
    result=updated.json()
    assert result['status']=='concluida' and result['versao']==2 and len(result['eventos'])==2
    assert result['agendada_para'] is not None
    assert client.put('/coletas/'+record['id']+'/status',json=data,headers=h).status_code==409
    assert client.put('/coletas/'+record['id']+'/status',json={'versao':2,'status':'cancelada','motivo':'Mudou'},headers=h).status_code==409


def test_cancellation_and_no_show_require_reason(context,customer):
    client,a,b,login,admin,settings=context
    h,body,ids=setup(context,customer)
    for status in ['cancelada','nao_atendida']:
        record=create(client,h,{**body,'id_local_dispositivo':str(uuid4()),'status':'agendada','concluida_em':None,'agendada_para':body['concluida_em']})
        endpoint='/coletas/'+record['id']+'/status'
        assert client.put(endpoint,json={'versao':1,'status':status},headers=h).status_code==422
        assert client.put(endpoint,json={'versao':1,'status':status,'motivo':'Cliente não disponível'},headers=h).status_code==200
        detail=client.get('/coletas/'+record['id'],headers=h).json()
        assert detail['status']==status and detail['concluida_em'] is None
    assert client.get('/coletas',headers=h).json()['por_modalidade']==[]


def test_audited_correction_and_version_conflict(context,customer):
    client,a,b,login,admin,settings=context
    h,body,ids=setup(context,customer)
    body['itens'][1]['quantidade']=None
    record=create(client,h,body)
    item=next(i for i in record['itens'] if i['modalidade_id']==ids['SEDEX'])
    endpoint=f'/coletas/{record["id"]}/itens/{item["id"]}/quantidade'
    response=client.put(endpoint,json={'versao':1,'quantidade':12,'motivo':'Contagem na base'},headers=h)
    assert response.status_code==200,response.text
    result=response.json()
    audit=result['conferencias'][0]
    assert audit['quantidade_anterior'] is None and audit['quantidade_nova']==12
    assert audit['status_anterior']=='a_conferir' and audit['status_novo']=='confirmada'
    assert audit['usuario_nome']=='Administrador' and audit['motivo']=='Contagem na base'
    assert result['versao']==2
    assert client.put(endpoint,json={'versao':1,'quantidade':15,'motivo':'Conflito'},headers=h).status_code==409
    assert client.put(endpoint,json={'versao':2,'quantidade':12,'motivo':'Sem alteração'},headers=h).status_code==422
    assert client.put(endpoint,json={'versao':2,'quantidade':10,'motivo':'Recontagem'},headers=h).status_code==200
    final=client.get('/coletas/'+record['id'],headers=h).json()
    assert len(final['conferencias'])==2
    assert client.get('/coletas',params={'quantidade_status':'a_conferir'},headers=h).json()['total']==0


def test_history_date_bounds_and_item_filters(context,customer):
    client,a,b,login,admin,settings=context
    h,body,ids=setup(context,customer)
    for stamp in ['2026-05-10T03:00:00Z','2026-05-11T02:59:59Z','2026-05-11T03:00:00Z']:
        create(client,h,{**body,'id_local_dispositivo':str(uuid4()),'concluida_em':stamp})
    params={'data_inicio':'2026-05-10','data_fim':'2026-05-10','cliente_id':body['cliente_id'],'motorista_id':body['motorista_id'],
            'modalidade_id':ids['PAC'],'origem':'rota_fixa','status':'concluida','limit':1}
    data=client.get('/coletas',params=params,headers=h).json()
    assert data['total']==2 and len(data['items'])==1
    assert len(data['por_modalidade'])==1 and data['por_modalidade'][0]['volumes_confirmados']==20
    assert data['fuso_horario']=='America/Sao_Paulo'
    assert client.get('/coletas',params={**params,'modalidade_id':ids['PAC'],'quantidade_status':'a_conferir'},headers=h).json()['total']==0
    assert client.get('/coletas',params={'data_inicio':'2026-05-11','data_fim':'2026-05-10'},headers=h).status_code==422


def test_reject_bad_volumes_dates_and_modalities(context,customer):
    client,a,b,login,admin,settings=context
    h,body,ids=setup(context,customer)
    for item in [
        {'modalidade_id':ids['PAC'],'quantidade':None,'quantidade_status':'confirmada'},
        {'modalidade_id':ids['PAC'],'quantidade':-1},
        {'modalidade_id':ids['PAC'],'quantidade':1.5},
        {'modalidade_id':ids['PAC'],'quantidade':True},
        {'modalidade_id':str(uuid4()),'quantidade':1}]:
        assert client.post('/coletas',json={**body,'itens':[item]},headers=h).status_code==422
    assert client.post('/coletas',json={**body,'itens':[body['itens'][0]]*2},headers=h).status_code==422
    assert client.post('/coletas',json={**body,'concluida_em':'2026-05-10T09:00:00'},headers=h).status_code==422
    assert client.post('/coletas',json={**body,'concluida_em':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()},headers=h).status_code==422
    assert client.post('/coletas',json={**body,'empresa_id':str(b)},headers=h).status_code==422
    assert client.get('/coletas',headers=h).json()['total']==0
