from datetime import datetime, timedelta, timezone
from uuid import uuid4
import psycopg
from coleta_api.maintenance import run as run_maintenance

from test_operations import setup_route, DRIVER


def test_call_accept_complete_replay_and_company_isolation(context, customer):
    client, company, other_company, login, *_ = context
    staff, driver, first, _, _ = setup_route(context, customer)
    driver_auth = login(usuario=DRIVER['login'], senha=DRIVER['senha'])
    modality = client.get('/modalidades', headers=staff).json()['items'][0]
    body = {'id_local_dispositivo':str(uuid4()), 'cliente_id':first['id'], 'motorista_id':driver['id'],
            'prazo':(datetime.now(timezone.utc)+timedelta(hours=4)).isoformat(), 'prioridade':'urgente',
            'itens':[{'modalidade_id':modality['id'], 'quantidade':1, 'quantidade_status':'confirmada'}]}
    created = client.post('/chamados', json=body, headers=staff)
    assert created.status_code == 201, created.text
    call = created.json()
    assert client.post('/chamados', json=body, headers=staff).status_code == 200
    assert client.post('/chamados', json={**body, 'prioridade':'normal'}, headers=staff).status_code == 409
    assert client.get('/motorista/chamados', headers=login(other_company)).status_code == 403
    assert client.get('/motorista/chamados', headers=driver_auth).json()['items'][0]['id'] == call['id']
    day = client.post('/motorista/rota-do-dia/preparar', headers=driver_auth).json()
    assert any(r.get('chamado_id') == call['id'] for r in day['rotas'])
    answer = {'versao':1, 'aceitar':True}
    reply = client.post(f"/motorista/chamados/{call['id']}/responder", json=answer, headers=driver_auth)
    assert reply.status_code == 200, reply.text
    assert reply.json()['estado'] == 'aceito'
    assert client.post(f"/motorista/chamados/{call['id']}/responder", json=answer, headers=driver_auth).status_code == 200
    visit = {'id_local_dispositivo':str(uuid4()), 'coleta_id':call['coleta_id'], 'rota_id':call['id'],
             'versao_rota':1, 'cliente_id':first['id'], 'concluida_em':datetime.now(timezone.utc).isoformat(),
             'itens':[{'modalidade_id':modality['id'], 'quantidade':2, 'quantidade_status':'confirmada'}]}
    done = client.post('/motorista/coletas', json=visit, headers=driver_auth)
    assert done.status_code == 200, done.text
    assert client.post('/motorista/coletas', json=visit, headers=driver_auth).status_code == 200
    assert client.get('/chamados', headers=staff).json()['items'][0]['estado'] == 'concluido'
    assert client.get('/coletas/'+call['coleta_id'], headers=staff).json()['origem'] == 'chamado_imprevisto'


def test_call_refusal_and_reassign(context, customer):
    client, _, _, login, *_ = context
    staff, driver, first, _, _ = setup_route(context, customer)
    other = client.post('/motoristas', json={**DRIVER, 'login':'segundo', 'placa':'SEG1234'}, headers=staff)
    assert other.status_code == 201, other.text
    other_id = other.json()['id']
    modality = client.get('/modalidades', headers=staff).json()['items'][0]
    body = {'id_local_dispositivo':str(uuid4()), 'cliente_id':first['id'], 'motorista_id':driver['id'],
            'prazo':(datetime.now(timezone.utc)+timedelta(hours=4)).isoformat(),
            'itens':[{'modalidade_id':modality['id']} ]}
    call = client.post('/chamados', json=body, headers=staff).json()
    driver_auth = login(usuario=DRIVER['login'], senha=DRIVER['senha'])
    denied = client.post(f"/motorista/chamados/{call['id']}/responder", json={'versao':1,'aceitar':False}, headers=driver_auth)
    assert denied.status_code == 422
    refused = client.post(f"/motorista/chamados/{call['id']}/responder", json={'versao':1,'aceitar':False,'motivo':'Sem espaço'}, headers=driver_auth)
    assert refused.status_code == 200, refused.text
    changed = client.post(f"/chamados/{call['id']}/reatribuir", json={'versao':2,'motorista_id':other_id,'motivo':'Outro motorista disponível'}, headers=staff)
    assert changed.status_code == 200, changed.text
    assert changed.json()['estado'] == 'enviado'
    assert client.get('/motorista/chamados', headers=driver_auth).json()['items'] == []
    new_auth = login(usuario='segundo', senha=DRIVER['senha'])
    assert client.get('/motorista/chamados', headers=new_auth).json()['items'][0]['id'] == call['id']
    assert client.post(f"/motorista/chamados/{call['id']}/responder", json={'versao':1,'aceitar':True}, headers=driver_auth).status_code == 404


def test_call_expires_in_scheduled_maintenance(context, customer):
    client, _, _, _, admin_dsn, settings = context
    staff, driver, first, _, _ = setup_route(context, customer)
    modality = client.get('/modalidades', headers=staff).json()['items'][0]
    call = client.post('/chamados', json={'id_local_dispositivo':str(uuid4()), 'cliente_id':first['id'],
        'motorista_id':driver['id'], 'prazo':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
        'itens':[{'modalidade_id':modality['id']}]}, headers=staff).json()
    with psycopg.connect(admin_dsn) as conn:
        conn.execute("UPDATE chamados_imprevistos SET prazo=now()-interval '1 minute' WHERE id=%s", (call['id'],))
    assert run_maintenance(admin_dsn, settings.database_url) >= 1
    assert client.get('/chamados', headers=staff).json()['items'][0]['estado'] == 'expirado'
    assert client.get('/coletas/'+call['coleta_id'], headers=staff).json()['status'] == 'cancelada'


def test_call_nonattendance_and_stale_driver_reassignment(context, customer):
    client, _, _, login, *_ = context
    staff, driver, first, _, _ = setup_route(context, customer)
    second = client.post('/motoristas', json={**DRIVER,'login':'substituto','placa':'SUB1234'}, headers=staff).json()
    modality = client.get('/modalidades', headers=staff).json()['items'][0]
    call = client.post('/chamados', json={'id_local_dispositivo':str(uuid4()),'cliente_id':first['id'],
        'motorista_id':driver['id'],'prazo':(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat(),
        'itens':[{'modalidade_id':modality['id']}]}, headers=staff).json()
    old_auth=login(usuario=DRIVER['login'],senha=DRIVER['senha'])
    assert client.post(f"/motorista/chamados/{call['id']}/responder",
        json={'versao':1,'aceitar':True},headers=old_auth).status_code==200
    reassigned=client.post(f"/chamados/{call['id']}/reatribuir",
        json={'versao':2,'motorista_id':second['id'],'motivo':'Mudança operacional'},headers=staff)
    assert reassigned.status_code==200,reassigned.text
    stale={'id_local_dispositivo':str(uuid4()),'coleta_id':call['coleta_id'],'rota_id':call['id'],
        'versao_rota':1,'cliente_id':first['id'],'concluida_em':datetime.now(timezone.utc).isoformat(),
        'status':'nao_atendida','motivo':'Cliente fechado','itens':[]}
    assert client.post('/motorista/coletas',json=stale,headers=old_auth).status_code==404
    new_auth=login(usuario='substituto',senha=DRIVER['senha'])
    assert client.post(f"/motorista/chamados/{call['id']}/responder",
        json={'versao':3,'aceitar':True},headers=new_auth).status_code==200
    done=client.post('/motorista/coletas',json=stale,headers=new_auth)
    assert done.status_code==200,done.text
    assert client.post('/motorista/coletas',json=stale,headers=new_auth).status_code==200
    assert client.get('/chamados',headers=staff).json()['items'][0]['estado']=='nao_atendido'
