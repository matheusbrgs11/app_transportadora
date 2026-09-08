from datetime import datetime, timezone
import psycopg
from test_operations import DRIVER, setup_route


def test_day_order_windows_and_no_writes(context, customer):
    client,a,b,login,admin,settings=context
    h,driver,first,second,body=setup_route(context,customer)
    route=client.post('/rotas',json=body,headers=h).json()
    dh=login(usuario=DRIVER['login'],senha=DRIVER['senha'])
    response=client.get('/motorista/rota-do-dia?data=2026-09-07',headers=dh)
    assert response.status_code==200,response.text
    day=response.json()
    assert day['data']=='2026-09-07' and day['fuso_horario']=='America/Sao_Paulo'
    assert day['motorista']['id']==driver['id'] and day['total_paradas']==2
    stops=day['rotas'][0]['paradas']
    assert [s['cliente_id'] for s in stops]==[first['id'],second['id']]
    assert stops[0]['janela_inicio']=='08:00:00'
    assert 'cnpj' not in stops[0] and 'numero_contrato' not in stops[0]
    assert client.get('/motorista/rota-do-dia?data=2026-09-06',headers=dh).json()['rotas']==[]
    assert client.get('/coletas',headers=h).json()['total']==0
    client.put('/rotas/'+route['id'],json={**body,'versao':1,'ativa':False},headers=h)
    assert client.get('/motorista/rota-do-dia?data=2026-09-07',headers=dh).json()['rotas']==[]


def test_driver_and_company_isolation(context,customer):
    client,a,b,login,admin,settings=context
    h,driver,first,second,body=setup_route(context,customer)
    client.post('/rotas',json=body,headers=h).raise_for_status()
    other={**DRIVER,'login':'outro','placa':'DEF1234'}
    client.post('/motoristas',json=other,headers=h).raise_for_status()
    client.post('/motoristas',json=DRIVER,headers=login(b)).raise_for_status()
    for dh in [login(usuario='outro',senha=other['senha']),login(b,usuario=DRIVER['login'],senha=DRIVER['senha'])]:
        day=client.get('/motorista/rota-do-dia?data=2026-09-07',headers=dh).json()
        assert day['rotas']==[] and day['total_paradas']==0
    assert client.get('/motorista/rota-do-dia',headers=h).status_code==403
    assert client.get('/motorista/rota-do-dia').status_code==401
    dh=login(usuario=DRIVER['login'],senha=DRIVER['senha'])
    assert client.get('/motorista/rota-do-dia?data=invalid',headers=dh).status_code==422
    with psycopg.connect(admin) as conn:
        conn.execute('UPDATE motoristas SET ativo=false WHERE id=%s',(driver['id'],))
    assert client.get('/motorista/rota-do-dia',headers=dh).status_code==403


def test_default_day_uses_company_timezone(context,customer,monkeypatch):
    from coleta_api import driver_day
    class Clock:
        @staticmethod
        def now(zone):
            return datetime(2026,9,7,1,0,tzinfo=timezone.utc).astimezone(zone)
    monkeypatch.setattr(driver_day,'datetime',Clock)
    client,a,b,login,admin,settings=context
    h,driver,first,second,body=setup_route(context,customer)
    client.post('/rotas',json={**body,'dias_semana':[7]},headers=h).raise_for_status()
    dh=login(usuario=DRIVER['login'],senha=DRIVER['senha'])
    result=client.get('/motorista/rota-do-dia',headers=dh).json()
    assert result['data']=='2026-09-06' and result['total_paradas']==2
