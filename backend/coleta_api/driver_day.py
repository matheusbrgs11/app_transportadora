"""Consulta operacional do motorista, restrita ao próprio usuário autenticado."""
from datetime import date, datetime
from zoneinfo import ZoneInfo
from fastapi import Depends, HTTPException, Response
from uuid import UUID
from pydantic import AwareDatetime, Field, model_validator
from .models import StrictModel
from .daily import prepare, display, complete, route_lock
from .collections import CollectionCreate, Item, create_collection


class DriverVisit(StrictModel):
    coleta_id: UUID | None = None
    id_local_dispositivo: UUID
    rota_id: UUID
    cliente_id: UUID
    versao_rota: int = Field(ge=1)
    concluida_em: AwareDatetime
    itens: list[Item] = Field(min_length=1,max_length=50)
    observacoes: str | None = Field(default=None,max_length=2000)

    @model_validator(mode='after')
    def validate_collection(self):
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
        routes=conn.execute('SELECT id FROM rotas WHERE motorista_id=%s AND ativa AND %s=ANY(dias_semana) ORDER BY id',
                            (mid,day.isoweekday())).fetchall()
        for route in routes:
            # Uma execução emitida não troca de motorista quando muda a rota recorrente.
            existing=conn.execute('SELECT motorista_id FROM execucoes_rotas WHERE rota_id=%s AND data=%s',(route['id'],day)).fetchone()
            if existing and existing['motorista_id']!=mid:
                continue
            prepare(conn,user,route['id'],day,mid)
        runs=conn.execute('SELECT * FROM execucoes_rotas WHERE motorista_id=%s AND data=%s ORDER BY rota_id',(mid,day)).fetchall()
        plans=[display(conn,run) for run in runs]
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
                c.nome,c.endereco,c.numero,c.complemento,c.bairro,c.cidade,c.estado,c.cep,c.telefone
                FROM rota_paradas p JOIN clientes c ON c.id=p.cliente_id AND c.empresa_id=p.empresa_id
                WHERE p.rota_id=%s AND c.ativo ORDER BY p.ordem,p.id''', (route['id'],)).fetchall()
        return {'data': day, 'fuso_horario': zone, 'motorista': driver, 'rotas': routes,
                'total_paradas': sum(len(route['paradas']) for route in routes)}
