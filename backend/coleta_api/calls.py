"""Chamados imprevistos, com despacho auditado e resposta explícita do motorista."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID

from fastapi import Depends, HTTPException, Response
from pydantic import AwareDatetime, Field, StrictInt, field_validator
from psycopg.types.json import Jsonb

from .collections import CollectionCreate, Item, add_event, create_collection
from .models import StrictModel


class CallCreate(StrictModel):
    id_local_dispositivo: UUID
    cliente_id: UUID
    motorista_id: UUID
    prazo: AwareDatetime
    prioridade: Literal['normal', 'urgente'] = 'normal'
    observacoes: str | None = Field(default=None, max_length=2000)
    itens: list[Item] = Field(min_length=1, max_length=50)

    @field_validator('prazo')
    @classmethod
    def check_deadline(cls, value):
        now = datetime.now(timezone.utc)
        if value <= now or value > now + timedelta(days=7):
            raise ValueError('O prazo deve estar no futuro, em até sete dias.')
        return value


class CallChange(StrictModel):
    versao: StrictInt = Field(ge=1)
    motorista_id: UUID
    motivo: str = Field(min_length=1, max_length=1000)


class CallReply(StrictModel):
    versao: StrictInt = Field(ge=1)
    aceitar: bool
    motivo: str | None = Field(default=None, max_length=1000)


def call_row(conn, cid, lock=False):
    if lock:
        reference=conn.execute('SELECT coleta_id FROM chamados_imprevistos WHERE id=%s',(cid,)).fetchone()
        if not reference:
            raise HTTPException(404, 'Chamado não encontrado.')
        # Mesma ordem da conclusão do motorista: coleta, depois chamado.
        conn.execute('SELECT id FROM coletas WHERE id=%s FOR UPDATE',(reference['coleta_id'],)).fetchone()
    row = conn.execute('''SELECT h.*,c.cliente_id,c.status AS coleta_status,c.dados_registro,
        c.observacoes,c.agendada_para FROM chamados_imprevistos h
        JOIN coletas c ON c.id=h.coleta_id AND c.empresa_id=h.empresa_id
        WHERE h.id=%s''' + (' FOR UPDATE OF h' if lock else ''), (cid,)).fetchone()
    if not row:
        raise HTTPException(404, 'Chamado não encontrado.')
    return row


def expire_calls(conn, user):
    expired = conn.execute("SELECT id FROM chamados_imprevistos WHERE estado='enviado' AND prazo<=now()").fetchall()
    for candidate in expired:
        row=call_row(conn,candidate['id'],True)
        if row['estado']!='enviado' or row['prazo']>datetime.now(timezone.utc):
            continue
        creator=conn.execute('SELECT criado_por FROM coletas WHERE id=%s',(row['coleta_id'],)).fetchone()['criado_por']
        conn.execute("UPDATE chamados_imprevistos SET estado='expirado',versao=versao+1,atualizado_em=now() WHERE id=%s", (row['id'],))
        conn.execute("UPDATE coletas SET status='cancelada',versao=versao+1 WHERE id=%s AND status='agendada'", (row['coleta_id'],))
        conn.execute('''INSERT INTO coleta_eventos
            (empresa_id,coleta_id,usuario_id,usuario_nome,status_anterior,status_novo,motivo,dados)
            VALUES(%s,%s,%s,'Sistema','agendada','cancelada',%s,%s)''',
            (user['empresa_id'],row['coleta_id'],creator,'Prazo do chamado expirado.',
             Jsonb({'acao':'chamado_expirado','chamado_id':str(row['id'])})))


def register_calls(app, authenticated, staff):
    def driver(auth=Depends(authenticated)):
        conn, user, _ = auth
        if user['perfil'] != 'motorista':
            raise HTTPException(403, 'Acesso restrito a motoristas.')
        row = conn.execute('SELECT id FROM motoristas WHERE usuario_id=%s AND ativo', (user['id'],)).fetchone()
        if not row:
            raise HTTPException(403, 'Motorista inativo.')
        return auth, row['id']

    @app.get('/chamados/sugestoes/{cliente_id}', tags=['Chamados'])
    def suggestions(cliente_id: UUID, auth=Depends(staff)):
        conn, _, _ = auth
        client = conn.execute('SELECT id,localizacao_confirmada,localizacao FROM clientes WHERE id=%s AND ativo', (cliente_id,)).fetchone()
        if not client:
            raise HTTPException(404, 'Cliente ativo não encontrado.')
        rows = conn.execute('''SELECT m.id,u.nome,v.tipo,v.placa,
            t.id AS turno_id,p.capturada_em,
            CASE WHEN c.localizacao_confirmada AND p.capturada_em>now()-interval '2 minutes'
              THEN round((ST_Distance(c.localizacao,p.localizacao)/1000)::numeric,1) END AS distancia_km
            FROM motoristas m JOIN usuarios u ON u.id=m.usuario_id AND u.empresa_id=m.empresa_id
            LEFT JOIN veiculos v ON v.id=m.veiculo_id AND v.empresa_id=m.empresa_id
            LEFT JOIN turnos_motorista t ON t.motorista_id=m.id AND t.empresa_id=m.empresa_id
              AND t.encerrado_em IS NULL AND t.expira_em>now()
            LEFT JOIN posicoes_motorista p ON p.turno_id=t.id AND p.empresa_id=t.empresa_id
            CROSS JOIN clientes c WHERE c.id=%s AND m.ativo AND u.ativo
            ORDER BY (p.capturada_em>now()-interval '2 minutes') DESC NULLS LAST,
              distancia_km ASC NULLS LAST,u.nome''', (cliente_id,)).fetchall()
        for row in rows:
            row['situacao'] = 'fora_turno' if not row['turno_id'] else 'recente' if row['distancia_km'] is not None else 'sem_posicao_recente'
        return {'items': rows, 'distancia_em_linha_reta': True}

    @app.post('/chamados', status_code=201, tags=['Chamados'])
    def create(body: CallCreate, response: Response, auth=Depends(staff)):
        conn, user, _ = auth
        content = body.model_dump(mode='json')
        digest = sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (str(user['empresa_id']) + str(body.id_local_dispositivo),))
        old = conn.execute('''SELECT h.id,h.requisicao_hash,c.criado_por FROM chamados_imprevistos h
            JOIN coletas c ON c.id=h.coleta_id WHERE c.id_local_dispositivo=%s''', (body.id_local_dispositivo,)).fetchone()
        if old:
            if old['requisicao_hash'] != digest or old['criado_por'] != user['id']:
                raise HTTPException(409, 'Identificador já utilizado com outros dados.')
            response.status_code = 200
            return call_row(conn, old['id'])
        if conn.execute('SELECT id FROM coletas WHERE id_local_dispositivo=%s', (body.id_local_dispositivo,)).fetchone():
            raise HTTPException(409, 'Identificador já utilizado.')
        scheduled = CollectionCreate(id_local_dispositivo=body.id_local_dispositivo,
            cliente_id=body.cliente_id, motorista_id=body.motorista_id, origem='chamado_imprevisto',
            agendada_para=body.prazo, observacoes=body.observacoes, itens=body.itens)
        collection = create_collection(scheduled, response, auth)
        cid = conn.execute('''INSERT INTO chamados_imprevistos
            (empresa_id,coleta_id,motorista_id,prioridade,prazo,requisicao_hash)
            VALUES(%s,%s,%s,%s,%s,%s) RETURNING id''',
            (user['empresa_id'], collection['id'], body.motorista_id, body.prioridade, body.prazo, digest)).fetchone()['id']
        add_event(conn, user, collection['id'], 'agendada', 'agendada', dados={'acao':'chamado_despachado','chamado_id':str(cid),'prioridade':body.prioridade})
        return call_row(conn, cid)

    @app.get('/chamados', tags=['Chamados'])
    def list_calls(auth=Depends(staff)):
        conn, user, _ = auth
        expire_calls(conn, user)
        return {'items': conn.execute('''SELECT h.id,h.coleta_id,h.motorista_id,h.estado,h.prioridade,h.prazo,h.versao,
            h.criado_em,h.respondido_em,c.dados_registro->>'cliente_nome' AS cliente_nome,
            c.dados_registro->>'motorista_nome' AS motorista_nome,c.observacoes
            FROM chamados_imprevistos h JOIN coletas c ON c.id=h.coleta_id
            ORDER BY h.criado_em DESC,h.id LIMIT 100''').fetchall()}

    @app.post('/chamados/{cid}/reatribuir', tags=['Chamados'])
    def reassign(cid: UUID, body: CallChange, auth=Depends(staff)):
        conn, user, _ = auth
        old = call_row(conn, cid, True)
        if old['versao'] != body.versao or old['estado'] not in ('enviado','recusado','aceito') or old['prazo'] <= datetime.now(timezone.utc):
            raise HTTPException(409, 'Chamado alterado ou expirado. Atualize a tela.')
        if old['motorista_id'] == body.motorista_id:
            raise HTTPException(422, 'Escolha outro motorista.')
        driver = conn.execute('''SELECT m.id,u.nome FROM motoristas m JOIN usuarios u ON u.id=m.usuario_id
            AND u.empresa_id=m.empresa_id WHERE m.id=%s AND m.ativo AND u.ativo''', (body.motorista_id,)).fetchone()
        if not driver:
            raise HTTPException(422, 'Motorista ativo não encontrado.')
        snapshot = {**old['dados_registro'], 'motorista_nome': driver['nome']}
        conn.execute('UPDATE coletas SET motorista_id=%s,dados_registro=%s,versao=versao+1 WHERE id=%s',
                     (body.motorista_id, Jsonb(snapshot), old['coleta_id']))
        conn.execute('''UPDATE chamados_imprevistos SET motorista_id=%s,estado='enviado',respondido_em=NULL,
            versao=versao+1,atualizado_em=now() WHERE id=%s''', (body.motorista_id, cid))
        add_event(conn, user, old['coleta_id'], 'agendada', 'agendada', body.motivo,
                  {'acao':'chamado_reatribuido','motorista_anterior':str(old['motorista_id']),
                   'motorista_novo':str(body.motorista_id)})
        return call_row(conn, cid)

    @app.get('/motorista/chamados', tags=['Aplicativo do motorista'])
    def driver_calls(context=Depends(driver)):
        (conn, user, _), mid = context
        expire_calls(conn, user)
        return {'items': conn.execute('''SELECT h.id,h.coleta_id,h.estado,h.prioridade,h.prazo,h.versao,
            c.cliente_id,c.dados_registro,c.observacoes FROM chamados_imprevistos h
            JOIN coletas c ON c.id=h.coleta_id WHERE h.motorista_id=%s
              AND h.estado IN ('enviado','aceito') ORDER BY h.prioridade DESC,h.prazo''', (mid,)).fetchall()}

    @app.post('/motorista/chamados/{cid}/responder', tags=['Aplicativo do motorista'])
    def reply(cid: UUID, body: CallReply, context=Depends(driver)):
        (conn, user, _), mid = context
        old = call_row(conn, cid, True)
        if old['motorista_id'] != mid:
            raise HTTPException(404, 'Chamado não encontrado.')
        next_state = 'aceito' if body.aceitar else 'recusado'
        if old['versao'] == body.versao + 1 and old['estado'] == next_state:
            return call_row(conn, cid)
        if old['versao'] != body.versao or old['estado'] != 'enviado' or old['prazo'] <= datetime.now(timezone.utc):
            raise HTTPException(409, 'Chamado alterado ou expirado. Atualize a tela.')
        if not body.aceitar and not (body.motivo or '').strip():
            raise HTTPException(422, 'Informe o motivo da recusa.')
        conn.execute('''UPDATE chamados_imprevistos SET estado=%s,versao=versao+1,
            respondido_em=now(),atualizado_em=now() WHERE id=%s''', (next_state, cid))
        add_event(conn, user, old['coleta_id'], 'agendada', 'agendada', body.motivo,
                  {'acao':'chamado_'+next_state,'chamado_id':str(cid)})
        return call_row(conn, cid)
