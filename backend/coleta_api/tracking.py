from datetime import datetime,timedelta,timezone
from uuid import UUID
from fastapi import Depends,HTTPException,Response
from pydantic import AwareDatetime,Field,FiniteFloat
from .models import StrictModel

class Start(StrictModel):
    id:UUID

class Position(StrictModel):
    latitude:FiniteFloat=Field(ge=-90,le=90)
    longitude:FiniteFloat=Field(ge=-180,le=180)
    precisao_metros:FiniteFloat=Field(ge=0,le=1000)
    capturada_em:AwareDatetime


def cleanup(conn):
    conn.execute('UPDATE turnos_motorista SET encerrado_em=expira_em WHERE encerrado_em IS NULL AND expira_em<=now()')
    conn.execute('''DELETE FROM posicoes_motorista p WHERE p.turno_id IS NULL OR NOT EXISTS
        (SELECT 1 FROM turnos_motorista t WHERE t.id=p.turno_id AND t.empresa_id=p.empresa_id
         AND t.encerrado_em IS NULL AND t.expira_em>now())''')


def register_tracking(app,authenticated,staff):
    def driver(auth=Depends(authenticated)):
        conn,user,_=auth
        if user['perfil']!='motorista':raise HTTPException(403,'Acesso restrito ao motorista.')
        row=conn.execute('SELECT id FROM motoristas WHERE usuario_id=%s AND ativo',(user['id'],)).fetchone()
        if not row:raise HTTPException(403,'Motorista inativo.')
        return auth,row['id']

    @app.post('/motorista/turnos',tags=['Rastreamento'])
    def start(body:Start,context=Depends(driver)):
        (conn,user,_),mid=context
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(f'turno:{user["empresa_id"]}:{mid}',))
        cleanup(conn)
        old=conn.execute('SELECT * FROM turnos_motorista WHERE id=%s',(body.id,)).fetchone()
        if old:
            if old['motorista_id']!=mid:raise HTTPException(409,'Identificador já utilizado.')
            return old
        if conn.execute('SELECT id FROM turnos_motorista WHERE motorista_id=%s AND encerrado_em IS NULL',(mid,)).fetchone():
            raise HTTPException(409,'Já existe turno aberto. Encerre-o antes de iniciar outro aparelho.')
        return conn.execute('INSERT INTO turnos_motorista(id,empresa_id,motorista_id) VALUES(%s,%s,%s) RETURNING *',
                            (body.id,user['empresa_id'],mid)).fetchone()

    @app.get('/motorista/turnos/atual',tags=['Rastreamento'])
    def current(context=Depends(driver)):
        (conn,_,_),mid=context;cleanup(conn)
        return {'turno':conn.execute('SELECT * FROM turnos_motorista WHERE motorista_id=%s AND encerrado_em IS NULL',(mid,)).fetchone()}

    @app.post('/motorista/turnos/{turno_id}/encerrar',tags=['Rastreamento'])
    def end(turno_id:UUID,context=Depends(driver)):
        (conn,_,_),mid=context
        row=conn.execute('SELECT * FROM turnos_motorista WHERE id=%s AND motorista_id=%s FOR UPDATE',(turno_id,mid)).fetchone()
        if not row:raise HTTPException(404,'Turno não encontrado.')
        conn.execute('UPDATE turnos_motorista SET encerrado_em=coalesce(encerrado_em,now()) WHERE id=%s',(turno_id,))
        conn.execute('DELETE FROM posicoes_motorista WHERE turno_id=%s',(turno_id,))
        return {'id':turno_id,'status':'encerrado'}

    @app.post('/motorista/turnos/{turno_id}/posicao',tags=['Rastreamento'])
    def position(turno_id:UUID,body:Position,context=Depends(driver)):
        (conn,user,_),mid=context
        row=conn.execute('SELECT * FROM turnos_motorista WHERE id=%s AND motorista_id=%s FOR UPDATE',(turno_id,mid)).fetchone()
        if not row:raise HTTPException(404,'Turno não encontrado.')
        now=datetime.now(timezone.utc)
        if row['encerrado_em'] or row['expira_em']<=now:raise HTTPException(409,'Turno encerrado ou expirado.')
        if body.capturada_em<row['iniciado_em'] or body.capturada_em<now-timedelta(minutes=5) or body.capturada_em>now+timedelta(seconds=30):
            raise HTTPException(422,'Horário da posição inválido ou antigo. Aguarde uma nova leitura.')
        changed=conn.execute('''INSERT INTO posicoes_motorista(empresa_id,motorista_id,turno_id,localizacao,capturada_em,precisao_metros)
            VALUES(%s,%s,%s,ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography,%s,%s)
            ON CONFLICT(empresa_id,motorista_id) DO UPDATE SET turno_id=EXCLUDED.turno_id,localizacao=EXCLUDED.localizacao,
            capturada_em=EXCLUDED.capturada_em,recebida_em=now(),precisao_metros=EXCLUDED.precisao_metros
            WHERE posicoes_motorista.capturada_em<EXCLUDED.capturada_em RETURNING motorista_id''',
            (user['empresa_id'],mid,turno_id,body.longitude,body.latitude,body.capturada_em,body.precisao_metros)).fetchone()
        return {'atualizada':bool(changed)}

    @app.get('/rastreamento',tags=['Rastreamento'])
    def tracking(response:Response,auth=Depends(staff)):
        conn,_,_=auth;cleanup(conn)
        rows=conn.execute('''SELECT m.id,u.nome,v.tipo,v.placa,t.id AS turno_id,t.iniciado_em,t.expira_em,
            p.capturada_em,p.recebida_em,p.precisao_metros,ST_Y(p.localizacao::geometry) AS latitude,
            ST_X(p.localizacao::geometry) AS longitude
            FROM motoristas m JOIN usuarios u ON u.id=m.usuario_id AND u.empresa_id=m.empresa_id
            LEFT JOIN veiculos v ON v.id=m.veiculo_id AND v.empresa_id=m.empresa_id
            LEFT JOIN turnos_motorista t ON t.motorista_id=m.id AND t.empresa_id=m.empresa_id AND t.encerrado_em IS NULL
            LEFT JOIN posicoes_motorista p ON p.turno_id=t.id AND p.empresa_id=t.empresa_id
            WHERE m.ativo AND u.ativo ORDER BY u.nome,m.id''').fetchall()
        now=datetime.now(timezone.utc)
        for row in rows:
            row['situacao']='fora_turno' if not row['turno_id'] else 'sem_posicao' if not row['capturada_em'] else 'antiga' if (now-row['capturada_em']).total_seconds()>120 else 'recente'
        response.headers['Cache-Control']='no-store'
        return {'items':rows,'agora':now,'intervalo_sugerido_segundos':60}
