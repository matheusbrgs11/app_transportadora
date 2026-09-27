from datetime import datetime,timedelta,timezone
from uuid import uuid4
import psycopg
from test_driver_visits import prepare
from test_operations import DRIVER


def test_tracking_lifecycle_and_isolation(context,customer):
    client,a,b,login,admin,_=context
    h,dh,_,_=prepare(context,customer)
    tid=str(uuid4()); path='/motorista/turnos/'+tid
    assert client.post('/motorista/turnos',json={'id':tid},headers=h).status_code==403
    start=client.post('/motorista/turnos',json={'id':tid},headers=dh)
    assert start.status_code==200,start.text
    assert client.post('/motorista/turnos',json={'id':tid},headers=dh).json()==start.json()
    assert client.post('/motorista/turnos',json={'id':str(uuid4())},headers=dh).status_code==409
    assert client.get('/rastreamento',headers=dh).status_code==403
    client.post('/motoristas',json=DRIVER,headers=login(b)).raise_for_status()
    foreign=login(b,usuario=DRIVER['login'],senha=DRIVER['senha'])
    assert client.post(path+'/encerrar',json={},headers=foreign).status_code==404
    point={'latitude':-16.6,'longitude':-49.2,'precisao_metros':12,'capturada_em':datetime.now(timezone.utc).isoformat()}
    assert client.post(path+'/posicao',json=point,headers=foreign).status_code==404
    assert client.post(path+'/posicao',json=point,headers=dh).json()=={'atualizada':True}
    assert client.post(path+'/posicao',json={**point,'latitude':-17},headers=dh).json()=={'atualizada':False}
    response=client.get('/rastreamento',headers=h)
    assert response.headers['cache-control']=='no-store'
    row=response.json()['items'][0]
    assert row['situacao']=='recente' and row['latitude']==-16.6
    assert client.get('/rastreamento',headers=login(b)).json()['items'][0]['latitude'] is None
    for change in [{'latitude':91},{'precisao_metros':1001},{'capturada_em':(datetime.now(timezone.utc)+timedelta(minutes=2)).isoformat()},
                   {'capturada_em':(datetime.now(timezone.utc)-timedelta(minutes=6)).isoformat()}]:
        assert client.post(path+'/posicao',json={**point,**change},headers=dh).status_code==422
    for _ in range(2):assert client.post(path+'/encerrar',json={},headers=dh).status_code==200
    assert client.post(path+'/posicao',json=point,headers=dh).status_code==409
    assert client.get('/rastreamento',headers=h).json()['items'][0]['situacao']=='fora_turno'
    with psycopg.connect(admin) as conn:
        assert conn.execute('SELECT count(*) FROM posicoes_motorista WHERE empresa_id=%s',(a,)).fetchone()[0]==0


def test_tracking_expiry_and_last_position_only(context,customer):
    client,a,_,_,admin,_=context
    h,dh,_,_=prepare(context,customer)
    tid=str(uuid4());path='/motorista/turnos/'+tid
    client.post('/motorista/turnos',json={'id':tid},headers=dh).raise_for_status()
    now=datetime.now(timezone.utc)
    for seconds in [0,1]:
        client.post(path+'/posicao',headers=dh,json={'latitude':0,'longitude':seconds,'precisao_metros':100,
                    'capturada_em':(now+timedelta(seconds=seconds)).isoformat()}).raise_for_status()
    with psycopg.connect(admin) as conn:
        assert conn.execute('SELECT count(*) FROM posicoes_motorista WHERE empresa_id=%s',(a,)).fetchone()[0]==1
        conn.execute("UPDATE turnos_motorista SET expira_em=now()-interval '1 second' WHERE empresa_id=%s",(a,))
    assert client.get('/rastreamento',headers=h).json()['items'][0]['latitude'] is None
    assert client.get('/motorista/turnos/atual',headers=dh).json()['turno'] is None
    with psycopg.connect(admin) as conn:
        assert conn.execute('SELECT count(*) FROM posicoes_motorista WHERE empresa_id=%s',(a,)).fetchone()[0]==0
