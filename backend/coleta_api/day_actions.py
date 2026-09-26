"""Intervenções auditadas da operação sobre atendimentos diários."""
from datetime import date
from uuid import UUID
from hashlib import sha256
import json
from fastapi import Depends, HTTPException
from pydantic import Field, StrictInt
from psycopg.types.json import Jsonb
from .models import StrictModel
from .daily import route_lock, display
from .collections import add_event


class ExceptionDay(StrictModel):
    operar: bool
    motivo: str = Field(min_length=1,max_length=1000)


class Change(StrictModel):
    versao: StrictInt = Field(ge=1)
    motivo: str = Field(min_length=1,max_length=1000)


class Transfer(Change):
    motorista_id: UUID


class Revisit(Change):
    id_local_dispositivo: UUID


def register_day_actions(app,staff):
    @app.get('/rotas/{rota_id}/execucoes',tags=['Rotas'])
    def read(rota_id:UUID,data:date,auth=Depends(staff)):
        conn,_,_=auth
        if not conn.execute('SELECT id FROM rotas WHERE id=%s',(rota_id,)).fetchone():
            raise HTTPException(404,'Rota não encontrada.')
        run=conn.execute('SELECT * FROM execucoes_rotas WHERE rota_id=%s AND data=%s',(rota_id,data)).fetchone()
        exception=conn.execute('SELECT operar,motivo FROM rota_excecoes WHERE rota_id=%s AND data=%s',(rota_id,data)).fetchone()
        return {'execucao':display(conn,run) if run else None,'excecao':exception}

    @app.put('/rotas/{rota_id}/excecoes/{data}',tags=['Rotas'])
    def exception(rota_id:UUID,data:date,body:ExceptionDay,auth=Depends(staff)):
        conn,user,_=auth
        route_lock(conn,user['empresa_id'],rota_id)
        if not conn.execute('SELECT id FROM rotas WHERE id=%s',(rota_id,)).fetchone():
            raise HTTPException(404,'Rota não encontrada.')
        if conn.execute('SELECT id FROM execucoes_rotas WHERE rota_id=%s AND data=%s',(rota_id,data)).fetchone():
            raise HTTPException(409,'Dia já emitido. Altere os atendimentos individualmente em Coletas.')
        conn.execute('''INSERT INTO rota_excecoes VALUES(%s,%s,%s,%s,%s,%s)
            ON CONFLICT(empresa_id,rota_id,data) DO UPDATE SET operar=EXCLUDED.operar,
            motivo=EXCLUDED.motivo,usuario_id=EXCLUDED.usuario_id''',
            (user['empresa_id'],rota_id,data,body.operar,body.motivo,user['id']))
        conn.execute('INSERT INTO rota_excecao_eventos(empresa_id,rota_id,data,operar,motivo,usuario_id) VALUES(%s,%s,%s,%s,%s,%s)',
            (user['empresa_id'],rota_id,data,body.operar,body.motivo,user['id']))
        return body

    @app.post('/coletas/{coleta_id}/transferir',tags=['Coletas'])
    def transfer(coleta_id:UUID,body:Transfer,auth=Depends(staff)):
        conn,user,_=auth
        old=conn.execute('SELECT * FROM coletas WHERE id=%s FOR UPDATE',(coleta_id,)).fetchone()
        if not old:
            raise HTTPException(404,'Atendimento não encontrado.')
        if old['versao']!=body.versao or old['status']!='agendada' or not old['execucao_id']:
            raise HTTPException(409,'Atualize a tela. Apenas atendimentos diários pendentes podem ser transferidos.')
        driver=conn.execute('''SELECT m.id,u.nome FROM motoristas m JOIN usuarios u ON u.id=m.usuario_id AND u.empresa_id=m.empresa_id
            WHERE m.id=%s AND m.ativo AND u.ativo FOR SHARE OF m,u''',(body.motorista_id,)).fetchone()
        if not driver:
            raise HTTPException(422,'Motorista ativo não encontrado.')
        if old['motorista_id']==driver['id']:
            raise HTTPException(422,'Escolha outro motorista.')
        snapshot={**old['dados_registro'],'motorista_nome':driver['nome']}
        conn.execute('UPDATE coletas SET motorista_id=%s,dados_registro=%s,versao=versao+1 WHERE id=%s',
            (driver['id'],Jsonb(snapshot),coleta_id))
        add_event(conn,user,coleta_id,'agendada','agendada',body.motivo,{
            'acao':'transferencia','motorista_anterior':str(old['motorista_id']),
            'motorista_anterior_nome':old['dados_registro']['motorista_nome'],
            'motorista_novo':str(driver['id']),'motorista_novo_nome':driver['nome']})
        return {'id':coleta_id,'versao':old['versao']+1}

    @app.post('/coletas/{coleta_id}/revisitas',tags=['Coletas'])
    def revisit(coleta_id:UUID,body:Revisit,auth=Depends(staff)):
        conn,user,_=auth
        digest=sha256(json.dumps(body.model_dump(mode='json'),sort_keys=True).encode()).hexdigest()
        # Serialize this request ID, then this parent. A chain has at most one successor.
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(str(user['empresa_id'])+str(body.id_local_dispositivo),))
        old=conn.execute('SELECT * FROM coletas WHERE id=%s FOR UPDATE',(coleta_id,)).fetchone()
        if not old:
            raise HTTPException(404,'Atendimento não encontrado.')
        existing=conn.execute('SELECT id,id_local_dispositivo,requisicao_hash,criado_por FROM coletas WHERE revisita_de=%s',(coleta_id,)).fetchone()
        if existing:
            if existing['id_local_dispositivo']==body.id_local_dispositivo and existing['requisicao_hash']==digest and existing['criado_por']==user['id']:
                return {'id':existing['id']}
            raise HTTPException(409,'Este atendimento já possui uma revisita. Atualize a tela.')
        if old['versao']!=body.versao or old['status']=='agendada' or not old['execucao_id']:
            raise HTTPException(409,'Atualize a tela. Finalize o atendimento antes de criar uma revisita.')
        if conn.execute('SELECT id FROM coletas WHERE id_local_dispositivo=%s',(body.id_local_dispositivo,)).fetchone():
            raise HTTPException(409,'Identificador já usado.')
        if not conn.execute('''SELECT m.id FROM motoristas m JOIN usuarios u ON u.id=m.usuario_id AND u.empresa_id=m.empresa_id
            WHERE m.id=%s AND m.ativo AND u.ativo''',(old['motorista_id'],)).fetchone():
            raise HTTPException(422,'Motorista inativo.')
        cid=conn.execute('''INSERT INTO coletas(empresa_id,cliente_id,motorista_id,id_local_dispositivo,status,origem,
            agendada_para,criado_por,dados_registro,execucao_id,tentativa,revisita_de,observacoes,requisicao_hash)
            VALUES(%s,%s,%s,%s,'agendada','rota_fixa',%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            (user['empresa_id'],old['cliente_id'],old['motorista_id'],body.id_local_dispositivo,old['agendada_para'],
             user['id'],Jsonb(old['dados_registro']),old['execucao_id'],old['tentativa']+1,coleta_id,body.motivo,digest)).fetchone()['id']
        add_event(conn,user,cid,None,'agendada',body.motivo,{'acao':'revisita','revisita_de':str(coleta_id)})
        add_event(conn,user,coleta_id,old['status'],old['status'],body.motivo,{'acao':'revisita_criada','revisita_id':str(cid)})
        return {'id':cid}
