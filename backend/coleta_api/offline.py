"""Conferência operacional de registros recusados, sem sobrescrever o original."""
from hashlib import sha256
import json
from uuid import UUID
from typing import Literal
from fastapi import Depends, HTTPException, Query
from pydantic import Field
from psycopg.types.json import Jsonb
from .models import StrictModel


class Conflict(StrictModel):
    id_local_dispositivo: UUID
    payload: dict


class Resolve(StrictModel):
    motivo: str = Field(min_length=1,max_length=2000)
    coleta_id: UUID | None = None


def register_offline(app,authenticated,staff):
    def driver(auth=Depends(authenticated)):
        conn,user,_=auth
        if user['perfil']!='motorista' or not conn.execute('SELECT id FROM motoristas WHERE usuario_id=%s AND ativo',(user['id'],)).fetchone():
            raise HTTPException(403,'Acesso restrito a motoristas ativos.')
        return auth

    @app.post('/motorista/conflitos',tags=['Offline'])
    def submit(body:Conflict,auth=Depends(driver)):
        conn,user,_=auth
        # Preserve even invalid legacy payloads for staff review; never execute them as a collection.
        encoded=json.dumps(body.payload,sort_keys=True,ensure_ascii=False)
        if len(encoded.encode())>230000 or str(body.payload.get('id_local_dispositivo'))!=str(body.id_local_dispositivo):
            raise HTTPException(422,'Registro inválido ou maior que 230 KB.')
        allowed={'id_local_dispositivo','coleta_id','rota_id','cliente_id','versao_rota','concluida_em','status','motivo','itens','observacoes','comprovante'}
        if set(body.payload)-allowed:
            raise HTTPException(422,'Campos não permitidos no registro.')
        digest=sha256(encoded.encode()).hexdigest()
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                     (f"conflict:{user['empresa_id']}:{user['id']}:{body.id_local_dispositivo}",))
        old=conn.execute('SELECT * FROM conflitos_motorista WHERE usuario_id=%s AND id_local=%s',(user['id'],body.id_local_dispositivo)).fetchone()
        if old:
            if old['requisicao_hash']!=digest:
                raise HTTPException(409,'Registro já enviado com outro conteúdo.')
            return {'id':old['id'],'status':old['status']}
        row=conn.execute('''INSERT INTO conflitos_motorista(empresa_id,usuario_id,id_local,payload,requisicao_hash)
            VALUES(%s,%s,%s,%s,%s) RETURNING id,status''',(user['empresa_id'],user['id'],body.id_local_dispositivo,Jsonb(body.payload),digest)).fetchone()
        return row

    @app.get('/motorista/conflitos/{id_local}',tags=['Offline'])
    def own(id_local:UUID,auth=Depends(driver)):
        conn,user,_=auth
        row=conn.execute('''SELECT id,status,resolucao,coleta_id,resolvido_em FROM conflitos_motorista
            WHERE usuario_id=%s AND id_local=%s''',(user['id'],id_local)).fetchone()
        if not row:
            raise HTTPException(404,'Conferência não encontrada.')
        return row

    @app.get('/conflitos',tags=['Offline'])
    def listing(status:Literal['aberto','resolvido']='aberto',limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0),auth=Depends(staff)):
        conn,_,_=auth
        rows=conn.execute('''SELECT c.id,c.id_local,c.payload,c.criado_em,c.status,c.resolucao,c.coleta_id,c.resolvido_em,u.nome AS motorista_nome,
            coalesce(cl.nome,'Cliente não localizado') AS cliente_nome, resolver.nome AS resolvido_nome
            FROM conflitos_motorista c JOIN usuarios u ON u.id=c.usuario_id AND u.empresa_id=c.empresa_id
            LEFT JOIN clientes cl ON cl.empresa_id=c.empresa_id AND cl.id::text=c.payload->>'cliente_id'
            LEFT JOIN usuarios resolver ON resolver.empresa_id=c.empresa_id AND resolver.id=c.resolvido_por
            WHERE c.status=%s ORDER BY c.criado_em,c.id LIMIT %s OFFSET %s''',(status,limit,offset)).fetchall()
        return {'items':rows,'total':conn.execute("SELECT count(*) AS n FROM conflitos_motorista WHERE status=%s",(status,)).fetchone()['n']}

    @app.post('/conflitos/{conflict_id}/resolver',tags=['Offline'])
    def resolve(conflict_id:UUID,body:Resolve,auth=Depends(staff)):
        conn,user,_=auth
        row=conn.execute('SELECT * FROM conflitos_motorista WHERE id=%s FOR UPDATE',(conflict_id,)).fetchone()
        if not row:
            raise HTTPException(404,'Conferência não encontrada.')
        if row['status']=='resolvido':
            if row['resolucao']==body.motivo and row['coleta_id']==body.coleta_id and row['resolvido_por']==user['id']:
                return {'id':row['id'],'status':'resolvido'}
            raise HTTPException(409,'Conferência já encerrada.')
        if body.coleta_id:
            collection=conn.execute('SELECT cliente_id FROM coletas WHERE id=%s',(body.coleta_id,)).fetchone()
            if not collection or str(collection['cliente_id'])!=str(row['payload'].get('cliente_id')):
                raise HTTPException(422,'Vincule uma coleta desta empresa e do mesmo cliente.')
        conn.execute("""UPDATE conflitos_motorista SET status='resolvido',resolucao=%s,coleta_id=%s,
            resolvido_por=%s,resolvido_em=now() WHERE id=%s""",(body.motivo,body.coleta_id,user['id'],conflict_id))
        return {'id':row['id'],'status':'resolvido'}
