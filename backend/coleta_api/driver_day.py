"""Consulta operacional do motorista, restrita ao próprio usuário autenticado."""
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo
from fastapi import Depends, HTTPException, Response, Query
from uuid import UUID
from pydantic import AwareDatetime, Field, model_validator
from .models import StrictModel
from .proofs import Proof
from .daily import prepare, display, complete, route_lock
from .collections import CollectionCreate, Item, create_collection
from .calls import expire_calls


class DriverVisit(StrictModel):
    coleta_id: UUID | None = None
    comprovante: Proof | None = None
    id_local_dispositivo: UUID
    rota_id: UUID
    cliente_id: UUID
    versao_rota: int = Field(ge=1)
    concluida_em: AwareDatetime
    status: Literal['concluida','nao_atendida'] = 'concluida'
    motivo: str | None = Field(default=None,max_length=1000)
    itens: list[Item] = Field(default_factory=list,max_length=50)
    observacoes: str | None = Field(default=None,max_length=2000)

    @model_validator(mode='after')
    def validate_collection(self):
        if self.comprovante and (not self.coleta_id or self.status!='concluida' or abs((self.concluida_em-self.comprovante.capturado_em).total_seconds())>1800):
            raise ValueError('Comprovante exige coleta planejada concluída e captura até 30 minutos da conclusão.')
        if self.status=='nao_atendida':
            if not self.coleta_id or self.itens or not self.motivo:
                raise ValueError('Não atendimento exige coleta planejada e motivo, sem volumes.')
            if self.concluida_em>datetime.now(timezone.utc)+timedelta(minutes=5):
                raise ValueError('A ocorrência não pode estar no futuro.')
            return self
        CollectionCreate(id_local_dispositivo=self.id_local_dispositivo,cliente_id=self.cliente_id,
            motorista_id=self.cliente_id,status='concluida',origem='rota_fixa',
            concluida_em=self.concluida_em,itens=self.itens,observacoes=self.observacoes)
        return self


def register_driver_day(app, authenticated):
    def driver_auth(auth=Depends(authenticated)):
        conn,user,_=auth
        if user['perfil']!='motorista':
            raise HTTPException(403,'Acesso restrito a motoristas.')
        driver=conn.execute('SELECT id FROM motoristas WHERE usuario_id=%s AND ativo',(user['id'],)).fetchone()
        if not driver:
            raise HTTPException(403,'Cadastro de motorista inativo ou não encontrado.')
        return auth,driver['id']

    @app.get('/motorista/historico',tags=['Aplicativo do motorista'])
    def history(data_inicio:date|None=None,data_fim:date|None=None,
                limit:int=Query(default=100,ge=1,le=200),offset:int=Query(default=0,ge=0),context=Depends(driver_auth)):
        auth,mid=context
        conn,user,_=auth
        zone=conn.execute('SELECT fuso_horario FROM empresas WHERE id=%s',(user['empresa_id'],)).fetchone()['fuso_horario']
        end=data_fim or datetime.now(ZoneInfo(zone)).date()
        start=data_inicio or end-timedelta(days=6)
        if end<start or (end-start).days>183:
            raise HTTPException(422,'Escolha um intervalo de até 184 dias.')
        condition=""" FROM coletas WHERE motorista_id=%s AND
            (coalesce(concluida_em,agendada_para,criado_em) AT TIME ZONE %s)::date BETWEEN %s AND %s"""
        params=(mid,zone,start,end)
        total=conn.execute('SELECT count(*) AS n'+condition,params).fetchone()['n']
        rows=conn.execute("""SELECT id,status,tentativa,dados_registro->>'cliente_nome' AS cliente_nome,
            coalesce(concluida_em,agendada_para,criado_em) AS data_referencia"""+condition+
            ' ORDER BY data_referencia DESC,id LIMIT %s OFFSET %s',(*params,limit,offset)).fetchall()
        return {'items':rows,'total':total,'data_inicio':start,'data_fim':end,'fuso_horario':zone}

    @app.get('/motorista/modalidades',tags=['Aplicativo do motorista'])
    def modalities(context=Depends(driver_auth)):
        return {'items':context[0][0].execute('SELECT id,nome FROM modalidades WHERE ativa ORDER BY nome,id').fetchall()}

    @app.post('/motorista/coletas',status_code=201,tags=['Aplicativo do motorista'])
    def visit(body:DriverVisit,response:Response,context=Depends(driver_auth)):
        auth,mid=context
        conn,user,_=auth
        if body.coleta_id is not None:
            return complete(conn,user,mid,body,response)
        # Compatibilidade com filas de versões antigas do aplicativo.
        route_lock(conn,user['empresa_id'],body.rota_id)
        # Serializa reenvios antes de verificar a rota: uma confirmação já gravada
        # continua recuperável mesmo se o planejamento mudar depois.
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                     (str(user['empresa_id'])+str(body.id_local_dispositivo),))
        previous=conn.execute('SELECT motorista_id,criado_por FROM coletas WHERE id_local_dispositivo=%s',
                              (body.id_local_dispositivo,)).fetchone()
        if previous and (previous['motorista_id']!=mid or previous['criado_por']!=user['id']):
            raise HTTPException(409,'Identificador já utilizado.')
        if not previous:
            zone=conn.execute('SELECT fuso_horario FROM empresas WHERE id=%s',(user['empresa_id'],)).fetchone()['fuso_horario']
            if conn.execute('SELECT id FROM execucoes_rotas WHERE rota_id=%s AND data=%s',
                            (body.rota_id,body.concluida_em.astimezone(ZoneInfo(zone)).date())).fetchone():
                raise HTTPException(409,'Esta rota já possui atendimentos. Atualize o aplicativo e confira o registro pendente com a operação.')
            route=conn.execute('SELECT * FROM rotas WHERE id=%s AND motorista_id=%s AND ativa FOR SHARE',
                               (body.rota_id,mid)).fetchone()
            if not route:
                raise HTTPException(403,'Rota não disponível para este motorista.')
            zone=conn.execute('SELECT fuso_horario FROM empresas WHERE id=%s',(user['empresa_id'],)).fetchone()['fuso_horario']
            if route['versao']!=body.versao_rota:
                raise HTTPException(409,'A rota mudou. Preserve o registro e solicite conferência à operação.')
            if body.concluida_em.astimezone(ZoneInfo(zone)).isoweekday() not in route['dias_semana']:
                raise HTTPException(422,'A rota não atende no dia informado.')
            if not conn.execute('SELECT id FROM rota_paradas WHERE rota_id=%s AND cliente_id=%s',
                                (body.rota_id,body.cliente_id)).fetchone():
                raise HTTPException(403,'Cliente não pertence à rota informada.')
        payload=CollectionCreate(id_local_dispositivo=body.id_local_dispositivo,
            cliente_id=body.cliente_id,motorista_id=mid,status='concluida',origem='rota_fixa',
            concluida_em=body.concluida_em,itens=body.itens,observacoes=body.observacoes)
        result=create_collection(payload,response,auth,source={'rota_id':str(body.rota_id),'versao_rota':body.versao_rota})
        return {'id':result['id'],'status':result['status']}

    @app.post('/motorista/rota-do-dia/preparar',tags=['Aplicativo do motorista'])
    def prepare_day(data:date|None=None,context=Depends(driver_auth)):
        auth,mid=context
        conn,user,_=auth
        zone=conn.execute('SELECT fuso_horario FROM empresas WHERE id=%s',(user['empresa_id'],)).fetchone()['fuso_horario']
        day=data or datetime.now(ZoneInfo(zone)).date()
        routes=conn.execute('''SELECT r.id FROM rotas r LEFT JOIN rota_excecoes x ON x.rota_id=r.id AND x.empresa_id=r.empresa_id AND x.data=%s
            WHERE r.motorista_id=%s AND r.ativa AND coalesce(x.operar,%s=ANY(r.dias_semana)) ORDER BY r.id''',
                            (day,mid,day.isoweekday())).fetchall()
        for route in routes:
            # Uma execução emitida não troca de motorista quando muda a rota recorrente.
            existing=conn.execute('SELECT motorista_id FROM execucoes_rotas WHERE rota_id=%s AND data=%s',(route['id'],day)).fetchone()
            if existing and existing['motorista_id']!=mid:
                continue
            prepare(conn,user,route['id'],day,mid)
        runs=conn.execute('''SELECT e.* FROM execucoes_rotas e WHERE e.data=%s AND EXISTS
            (SELECT 1 FROM coletas c WHERE c.execucao_id=e.id AND c.motorista_id=%s) ORDER BY e.rota_id''',(day,mid)).fetchall()
        plans=[display(conn,run,mid) for run in runs]
        expire_calls(conn,user)
        calls=conn.execute('''SELECT h.id AS chamado_id,h.estado AS chamado_estado,h.versao AS chamado_versao,
            h.prioridade,h.prazo,c.id AS coleta_id,c.cliente_id,c.status,c.tentativa,
            cl.nome,cl.endereco,cl.numero,cl.complemento,cl.bairro,cl.cidade,cl.estado,
            cl.cep,cl.telefone,cl.localizacao_confirmada,
            ST_Y(cl.localizacao::geometry) AS latitude,ST_X(cl.localizacao::geometry) AS longitude
            FROM chamados_imprevistos h JOIN coletas c ON c.id=h.coleta_id
            JOIN clientes cl ON cl.id=c.cliente_id AND cl.empresa_id=c.empresa_id
            WHERE h.motorista_id=%s AND h.estado IN ('enviado','aceito')
            ORDER BY h.prioridade DESC,h.prazo,h.id''',(mid,)).fetchall()
        for call in calls:
            plans.insert(0,{'id':call['chamado_id'],'nome':'Coleta imprevista',
                'versao':1,'paradas':[{**call,'ordem':1}],
                'progresso':{'agendada':1,'concluida':0,'nao_atendida':0,'cancelada':0},
                'chamado_id':call['chamado_id']})
        return {'data':day,'fuso_horario':zone,'rotas':plans,'total_paradas':sum(len(p['paradas']) for p in plans)}

    @app.get('/motorista/rota-do-dia' , tags=['Aplicativo do motorista'])
    def driver_day(data: date | None = None, auth=Depends(authenticated)):
        conn, user, _ = auth
        if user['perfil'] != 'motorista':
            raise HTTPException(403, 'Acesso restrito a motoristas.')
        driver = conn.execute('''SELECT m.id,u.nome,v.tipo,v.placa
            FROM motoristas m JOIN usuarios u ON u.id=m.usuario_id AND u.empresa_id=m.empresa_id
            LEFT JOIN veiculos v ON v.id=m.veiculo_id AND v.empresa_id=m.empresa_id
            WHERE m.usuario_id=%s AND m.ativo''', (user['id'],)).fetchone()
        if not driver:
            raise HTTPException(403, 'Cadastro de motorista inativo ou não encontrado.')
        company = conn.execute('SELECT fuso_horario FROM empresas WHERE id=%s',
                               (user['empresa_id'],)).fetchone()
        zone = company['fuso_horario']
        day = data or datetime.now(ZoneInfo(zone)).date()
        routes = conn.execute('''SELECT id,nome,versao FROM rotas
            WHERE motorista_id=%s AND ativa AND %s=ANY(dias_semana) ORDER BY nome,id''',
            (driver['id'], day.isoweekday())).fetchall()
        # A consulta não cria coletas e não expõe dados comerciais dos clientes.
        for route in routes:
            route['paradas'] = conn.execute('''SELECT p.id,p.cliente_id,p.ordem,p.janela_inicio,p.janela_fim,
                c.nome,c.endereco,c.numero,c.complemento,c.bairro,c.cidade,c.estado,c.cep,c.telefone,c.localizacao_confirmada,ST_Y(c.localizacao::geometry) AS latitude,ST_X(c.localizacao::geometry) AS longitude
                FROM rota_paradas p JOIN clientes c ON c.id=p.cliente_id AND c.empresa_id=p.empresa_id
                WHERE p.rota_id=%s AND c.ativo ORDER BY p.ordem,p.id''', (route['id'],)).fetchall()
        return {'data': day, 'fuso_horario': zone, 'motorista': driver, 'rotas': routes,
                'total_paradas': sum(len(route['paradas']) for route in routes)}
