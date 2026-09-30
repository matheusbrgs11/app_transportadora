import csv
from datetime import datetime,timezone
from io import StringIO
from uuid import uuid4
from test_collections import setup,create


def test_company_and_modalities_are_managed_per_tenant(context):
    client,a,b,login,_,_=context
    ha,hb=login(a),login(b)
    before=client.get('/empresa',headers=ha).json()
    assert before['id']==str(a)
    changed=client.put('/empresa',headers=ha,json={'nome':'Empresa A Atualizada','fuso_horario':'America/Manaus'})
    assert changed.status_code==200,changed.text
    assert client.get('/empresa',headers=ha).json()['fuso_horario']=='America/Manaus'
    assert client.get('/empresa',headers=hb).json()['nome']=='Empresa B'
    assert client.put('/empresa',headers=ha,json={'nome':'Teste','fuso_horario':'Fuso/Inexistente'}).status_code==422
    new=client.post('/modalidades',headers=ha,json={'nome':'Entrega especial','ativa':True})
    assert new.status_code==201,new.text
    mid=new.json()['id']
    assert all(m['id']!=mid for m in client.get('/modalidades',headers=hb).json()['items'])
    assert client.put('/modalidades/'+mid,headers=hb,json={'nome':'Alterada','ativa':False}).status_code==404
    off=client.put('/modalidades/'+mid,headers=ha,json={'nome':'Entrega especial','ativa':False})
    assert off.status_code==200 and off.json()['ativa'] is False
    assert client.post('/modalidades',headers=ha,json={'nome':'Entrega especial'}).status_code==409
    scheduler=client.post('/usuarios',headers=ha,json={'nome':'Agenda','login':'agenda','senha':'senha-segura-teste','perfil':'agendamento'})
    assert scheduler.status_code==201
    hs=login(usuario='agenda')
    assert client.get('/empresa',headers=hs).status_code==200
    assert client.put('/empresa',headers=hs,json={'nome':'X','fuso_horario':'UTC'}).status_code==403
    assert client.post('/modalidades',headers=hs,json={'nome':'Outra'}).status_code==403


def test_recovery_codes_are_one_time_and_revoke_sessions(context):
    client,a,b,login,_,_=context
    first,second=login(a),login(a)
    assert client.get('/auth/recuperacao/codigos',headers=first).json()['total']==0
    assert client.post('/auth/recuperacao/codigos',headers=first,json={'senha_atual':'errada'}).status_code==400
    issued=client.post('/auth/recuperacao/codigos',headers=first,json={'senha_atual':'senha-segura-teste'})
    assert issued.status_code==200,issued.text
    codes=issued.json()['codigos']
    assert len(codes)==8 and len(set(codes))==8
    assert client.get('/auth/recuperacao/codigos',headers=first).json()=={'total':8}
    body={'empresa_id':str(a),'usuario_login':'admin','codigo':codes[0],'nova_senha':'nova-senha-segura'}
    assert client.post('/auth/recuperacao',json={**body,'empresa_id':str(b)}).status_code==400
    assert client.post('/auth/recuperacao',json=body).status_code==204
    assert client.get('/auth/me',headers=first).status_code==401
    assert client.get('/auth/me',headers=second).status_code==401
    assert client.post('/auth/recuperacao',json=body).status_code==400
    fresh=login(a,senha='nova-senha-segura')
    assert client.get('/auth/recuperacao/codigos',headers=fresh).json()['total']==0


def test_changing_password_invalidates_saved_recovery_codes(context):
    client,a,_,login,_,_=context
    h=login(a)
    issued=client.post('/auth/recuperacao/codigos',headers=h,json={'senha_atual':'senha-segura-teste'})
    code=issued.json()['codigos'][0]
    assert client.post('/auth/senha',headers=h,json={'senha_atual':'senha-segura-teste','nova_senha':'nova-senha-segura'}).status_code==204
    attempt=client.post('/auth/recuperacao',json={'empresa_id':str(a),'usuario_login':'admin',
        'codigo':code,'nova_senha':'terceira-senha-segura'})
    assert attempt.status_code==400


def test_filtered_exports_match_history_and_neutralize_spreadsheet_formulas(context,customer):
    client,a,b,login,_,_=context
    h,body,mods=setup(context,{**customer,'nome':'=HYPERLINK("https://example.invalid")'})
    first=create(client,h,body)
    create(client,h,{**body,'id_local_dispositivo':str(uuid4()),'status':'agendada',
        'concluida_em':None,'agendada_para':'2026-06-10T12:30:00-03:00'})
    params={'data_inicio':'2026-05-10','data_fim':'2026-05-10','status':'concluida','modalidade_id':mods['PAC']}
    history=client.get('/coletas',params=params,headers=h).json()
    assert history['total']==1
    csv_response=client.get('/coletas/exportar.csv',params=params,headers=h)
    assert csv_response.status_code==200,csv_response.text
    assert csv_response.headers['content-type'].startswith('text/csv')
    csv_rows=list(csv.reader(StringIO(csv_response.text.lstrip('\ufeff')),delimiter=';'))
    assert len(csv_rows)==3
    assert csv_rows[1][1].startswith("'=HYPERLINK")
    assert 'PAC: 10' in csv_rows[1][6] and 'SEDEX' not in csv_rows[1][6]
    assert csv_rows[1][7]=='10'
    assert csv_rows[2][0]=='TOTAL (1 coleta)' and csv_rows[2][7]=='10'
    pdf_response=client.get('/coletas/exportar.pdf',params=params,headers=h)
    assert pdf_response.status_code==200,pdf_response.text[:100]
    assert pdf_response.content.startswith(b'%PDF-') and len(pdf_response.content)>1500
    assert client.get('/coletas/exportar.csv',headers=login(b)).text.count('HYPERLINK')==0
    assert client.get('/coletas/exportar.pdf',params={'data_inicio':'2026-05-11','data_fim':'2026-05-10'},headers=h).status_code==422
    indicators=client.get('/operacao/indicadores',headers=h)
    assert indicators.status_code==200 and 'itens_a_conferir' in indicators.json()
    scheduler=client.post('/usuarios',headers=h,json={'nome':'Agenda','login':'agenda','senha':'senha-segura-teste','perfil':'agendamento'})
    assert scheduler.status_code==201
    hs=login(usuario='agenda')
    assert client.get('/coletas/exportar.csv',params=params,headers=hs).status_code==200
