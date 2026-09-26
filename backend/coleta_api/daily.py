"""Planejamento imutável da rota e tentativas explícitas de atendimento."""
from datetime import datetime, time, date
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo
from hashlib import sha256
import json
from fastapi import Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from psycopg.types.json import Jsonb
from .collections import add_event


def route_lock(conn,company,rid):
    conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(f'daily:{company}:{rid}',))


def prepare(conn,user,rid,day,expected_driver=None):
    route_lock(conn,user['empresa_id'],rid)
    existing=conn.execute('SELECT * FROM execucoes_rotas WHERE rota_id=%s AND data=%s',(rid,day)).fetchone()
    if existing:
        if expected_driver and existing['motorista_id']!=expected_driver:
            raise HTTPException(409,'A execução deste dia pertence a outro motorista. Consulte a operação.')
        return existing
    route=conn.execute('SELECT * FROM rotas WHERE id=%s FOR SHARE',(rid,)).fetchone()
    if not route or (expected_driver and route['motorista_id']!=expected_driver):
        raise HTTPException(404,'Rota não encontrada.')
    exception=conn.execute('SELECT operar FROM rota_excecoes WHERE rota_id=%s AND data=%s',(rid,day)).fetchone()
    operates=exception['operar'] if exception else day.isoweekday() in route['dias_semana']
    if not route['ativa'] or not operates:
        raise HTTPException(422,'Rota não programada para esta data.')
    driver=conn.execute('''SELECT m.id,u.nome FROM motoristas m JOIN usuarios u ON u.id=m.usuario_id
        AND u.empresa_id=m.empresa_id WHERE m.id=%s AND m.ativo AND u.ativo FOR SHARE OF m''',(route['motorista_id'],)).fetchone()
    if not driver:
        raise HTTPException(422,'Motorista inativo.')
    zone=conn.execute('SELECT fuso_horario FROM empresas WHERE id=%s',(user['empresa_id'],)).fetchone()['fuso_horario']
    if conn.execute('''SELECT id FROM coletas WHERE execucao_id IS NULL AND
        dados_registro IS NOT NULL AND id IN
        (SELECT coleta_id FROM coleta_eventos WHERE dados->'execucao_rota'->>'rota_id'=%s)
        AND (concluida_em AT TIME ZONE %s)::date=%s LIMIT 1''',(str(rid),zone,day)).fetchone():
        raise HTTPException(409,'Já há visitas antigas nesta rota/data. A operação precisa conferir antes de gerar atendimentos.')
    stops=conn.execute('''SELECT p.cliente_id,p.ordem,p.janela_inicio,p.janela_fim,
        c.nome,c.cnpj,c.endereco,c.numero,c.complemento,c.bairro,c.cidade,c.estado,c.cep,c.telefone
        FROM rota_paradas p JOIN clientes c ON c.id=p.cliente_id AND c.empresa_id=p.empresa_id
        WHERE p.rota_id=%s AND c.ativo ORDER BY p.ordem FOR SHARE OF c''',(rid,)).fetchall()
    if not stops:
        raise HTTPException(422,'Rota sem clientes ativos.')
    plan=jsonable_encoder({'id':route['id'],'nome':route['nome'],'versao':route['versao'],'paradas':stops})
    run=conn.execute('''INSERT INTO execucoes_rotas(empresa_id,rota_id,motorista_id,data,fuso_horario,planejamento)
        VALUES(%s,%s,%s,%s,%s,%s) RETURNING *''',
        (user['empresa_id'],rid,driver['id'],day,zone,Jsonb(plan))).fetchone()
    for stop in stops:
        snapshot={'cliente_nome':stop['nome'],'cliente_cnpj':stop['cnpj'],'motorista_nome':driver['nome'],
                  'endereco':{k:stop[k] for k in ('endereco','numero','complemento','bairro','cidade','estado','cep')}}
        cid=conn.execute('''INSERT INTO coletas(empresa_id,cliente_id,motorista_id,id_local_dispositivo,
            status,origem,agendada_para,criado_por,dados_registro,execucao_id)
            VALUES(%s,%s,%s,%s,'agendada','rota_fixa',%s,%s,%s,%s) RETURNING id''',
            (user['empresa_id'],stop['cliente_id'],driver['id'],uuid4(),
             datetime.combine(day,stop['janela_inicio'] or time(8),ZoneInfo(zone)),user['id'],Jsonb(snapshot),run['id'])).fetchone()['id']
        add_event(conn,user,cid,None,'agendada',dados={'execucao_id':str(run['id']),'rota_id':str(rid),'data':day.isoformat()})
    return run


def display(conn,run,mid=None):
    plan=json.loads(json.dumps(run['planejamento']))
    records=conn.execute('SELECT id,cliente_id,motorista_id,status,versao,tentativa FROM coletas WHERE execucao_id=%s ORDER BY tentativa,id',(run['id'],)).fetchall()
    stops={p['cliente_id']:p for p in plan['paradas']}
    expanded=[]
    for record in records:
        if mid and record['motorista_id']!=mid:
            continue
        stop=dict(stops[str(record['cliente_id'])])
        stop.pop('cnpj',None)
        stop.update(coleta_id=record['id'],status=record['status'],versao_coleta=record['versao'],
                    motorista_id=record['motorista_id'],tentativa=record['tentativa'])
        expanded.append(stop)
    plan['paradas']=sorted(expanded,key=lambda p:(p['ordem'],p['tentativa']))
    progress={state:sum(p['status']==state for p in expanded) for state in ['agendada','concluida','nao_atendida','cancelada']}
    return {**plan,'execucao_id':run['id'],'data':run['data'],'fuso_horario':run['fuso_horario'],'progresso':progress}


def complete(conn,user,mid,body,response):
    payload=body.model_dump(mode='json')
    payload['itens']=sorted(payload['itens'],key=lambda i:i['modalidade_id'])
    digest=sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(str(user['empresa_id'])+str(body.id_local_dispositivo),))
    previous=conn.execute('SELECT * FROM envios_motorista WHERE id_local=%s',(body.id_local_dispositivo,)).fetchone()
    if previous:
        if previous['usuario_id']!=user['id'] or previous['requisicao_hash']!=digest:
            raise HTTPException(409,'Identificador já usado com outro conteúdo.')
        response.status_code=200
        return {'id':previous['coleta_id'],'status':previous['status']}
    old=conn.execute('''SELECT c.*,e.rota_id,e.planejamento,e.data AS dia,e.fuso_horario FROM coletas c
        JOIN execucoes_rotas e ON e.id=c.execucao_id AND e.empresa_id=c.empresa_id
        WHERE c.id=%s AND c.motorista_id=%s FOR UPDATE OF c''',(body.coleta_id,mid)).fetchone()
    if not old:
        raise HTTPException(404,'Atendimento não encontrado.')
    if old['rota_id']!=body.rota_id or old['cliente_id']!=body.cliente_id or old['planejamento']['versao']!=body.versao_rota:
        raise HTTPException(409,'Dados não correspondem ao atendimento planejado.')
    if body.concluida_em.astimezone(ZoneInfo(old['fuso_horario'])).date()!=old['dia']:
        raise HTTPException(422,'A realização deve pertencer ao dia do atendimento.')
    if old['status']!='agendada':
        raise HTTPException(409,'Atendimento já finalizado. Atualize sua rota; não crie outra visita.')
    if body.status=='concluida':
        mods=conn.execute('SELECT id,nome FROM modalidades WHERE id=ANY(%s) AND ativa',([i.modalidade_id for i in body.itens],)).fetchall()
        if len(mods)!=len(body.itens):
            raise HTTPException(422,'Selecione modalidades ativas da sua empresa.')
        existing=conn.execute('SELECT modalidade_id FROM coleta_itens WHERE coleta_id=%s',(old['id'],)).fetchall()
        if existing and {r['modalidade_id'] for r in existing}!={i.modalidade_id for i in body.itens}:
            raise HTTPException(409,'Modalidades alteradas pela operação. Confira o atendimento.')
        names={r['id']:r['nome'] for r in mods}
        for item in body.itens:
            conn.execute('''INSERT INTO coleta_itens(empresa_id,coleta_id,modalidade_id,modalidade_nome,quantidade,quantidade_status)
                VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(empresa_id,coleta_id,modalidade_id)
                DO UPDATE SET quantidade=EXCLUDED.quantidade,quantidade_status=EXCLUDED.quantidade_status''',
                (user['empresa_id'],old['id'],item.modalidade_id,names[item.modalidade_id],item.quantidade,item.quantidade_status))
    conn.execute("UPDATE coletas SET status=%s,concluida_em=%s,observacoes=%s,versao=versao+1 WHERE id=%s",
                 (body.status,body.concluida_em if body.status=='concluida' else None,body.observacoes,old['id']))
    add_event(conn,user,old['id'],'agendada',body.status,body.motivo,dados=payload)
    conn.execute('INSERT INTO envios_motorista VALUES(%s,%s,%s,%s,%s,%s)',
                 (user['empresa_id'],body.id_local_dispositivo,user['id'],old['id'],digest,body.status))
    response.status_code=200
    return {'id':old['id'],'status':body.status}


def register_daily(app,staff):
    from .day_actions import register_day_actions
    register_day_actions(app,staff)

    @app.post('/rotas/{rota_id}/execucoes',tags=['Rotas'])
    def prepare_route(rota_id:UUID,data:date|None=None,auth=Depends(staff)):
        conn,user,_=auth
        zone=conn.execute('SELECT fuso_horario FROM empresas WHERE id=%s',(user['empresa_id'],)).fetchone()['fuso_horario']
        return display(conn,prepare(conn,user,rota_id,data or datetime.now(ZoneInfo(zone)).date()))
