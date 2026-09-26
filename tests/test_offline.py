from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import psycopg
from psycopg.rows import dict_row
from test_daily import issue
from test_driver_visits import prepare
from test_operations import DRIVER


def test_conflict_preserves_payload_is_idempotent_and_company_scoped(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,_=prepare(context,customer)
    _,body=issue(client,h,body)
    request={'id_local_dispositivo':body['id_local_dispositivo'],'payload':body}
    assert client.post('/motorista/conflitos',headers=h,json=request).status_code==403
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda _:client.post('/motorista/conflitos',headers=dh,json=request),range(2)))
    assert all(r.status_code==200 for r in results)
    cid=results[0].json()['id'];assert results[1].json()['id']==cid
    changed={**request,'payload':{**body,'observacoes':'alterado'}}
    assert client.post('/motorista/conflitos',headers=dh,json=changed).status_code==409
    assert client.get('/conflitos',headers=dh).status_code==403
    assert client.get('/conflitos',headers=login(b)).json()['total']==0
    assert client.get('/conflitos',headers=h).json()['items'][0]['payload']==body
    assert client.get('/conflitos',headers=h).json()['items'][0]['cliente_nome']==customer['nome']
    resolution={'motivo':'Duplicidade conferida com a operação','coleta_id':body['coleta_id']}
    path='/conflitos/'+cid+'/resolver'
    assert client.post(path,headers=dh,json=resolution).status_code==403
    assert client.post(path,headers=login(b),json=resolution).status_code==404
    assert client.post(path,headers=h,json={**resolution,'coleta_id':str(uuid4())}).status_code==422
    assert client.post(path,headers=h,json={**resolution,'motivo':' '}).status_code==422
    client.post(path,headers=h,json=resolution).raise_for_status()
    client.post(path,headers=h,json=resolution).raise_for_status()
    assert client.post(path,headers=h,json={**resolution,'motivo':'Outro parecer'}).status_code==409
    own=client.get('/motorista/conflitos/'+body['id_local_dispositivo'],headers=dh).json()
    assert own['status']=='resolvido' and own['resolucao']==resolution['motivo']
    assert client.get('/conflitos',headers=h).json()['total']==0
    resolved=client.get('/conflitos?status=resolvido',headers=h).json()['items'][0]
    assert resolved['payload']==body and resolved['resolvido_nome']
    # Conferencing does not silently conclude or overwrite the collection.
    assert client.get('/coletas/'+body['coleta_id'],headers=h).json()['status']=='agendada'
    client.post('/motoristas',json={**DRIVER,'login':'outro','placa':'DEF1234'},headers=h).raise_for_status()
    other=login(usuario='outro',senha=DRIVER['senha'])
    assert client.get('/motorista/conflitos/'+body['id_local_dispositivo'],headers=other).status_code==404
    # Raw payload and author cannot be changed even with a direct runtime-role query.
    with psycopg.connect(settings.database_url) as conn:
        conn.execute('SET LOCAL ROLE coleta_app')
        conn.execute("SELECT set_config('app.empresa_id',%s,true)",(str(a),))
        try:
            conn.execute("UPDATE conflitos_motorista SET payload='{}' WHERE id=%s",(cid,))
        except psycopg.errors.InsufficientPrivilege:
            pass
        else:
            raise AssertionError('Payload must be append-only')


def test_conflict_validation_and_cross_client_link(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,_=prepare(context,customer)
    run,body=issue(client,h,body)
    request={'id_local_dispositivo':body['id_local_dispositivo'],'payload':body}
    for payload in ({**body,'id_local_dispositivo':str(uuid4())},{**body,'senha':'secret'}, {**body,'observacoes':'x'*33000}):
        assert client.post('/motorista/conflitos',headers=dh,json={**request,'payload':payload}).status_code==422
    cid=client.post('/motorista/conflitos',headers=dh,json=request).json()['id']
    other=next(p['coleta_id'] for p in run['paradas'] if p['coleta_id']!=body['coleta_id'])
    assert client.post('/conflitos/'+cid+'/resolver',headers=h,json={'coleta_id':other,'motivo':'Vínculo errado'}).status_code==422
    client.post('/conflitos/'+cid+'/resolver',headers=h,json={'motivo':'Registro inválido, conferido sem lançamento.'}).raise_for_status()
    assert client.get('/coletas',headers=h).json()['total']==2


def test_driver_session_lifetime_and_revocation(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,_=prepare(context,customer)
    response=client.post('/auth/login',json={'empresa_id':str(a),'usuario_login':DRIVER['login'],'senha':DRIVER['senha']}).json()
    assert response['expires_in']==12*60*60
    token={'Authorization':'Bearer '+response['access_token']}
    assert client.get('/auth/me',headers=token).status_code==200
    client.post('/auth/logout',headers=token).raise_for_status()
    assert client.get('/auth/me',headers=token).status_code==401
    admin_login=client.post('/auth/login',json={'empresa_id':str(a),'usuario_login':'admin','senha':'senha-segura-teste'}).json()
    assert admin_login['expires_in']==60*60
