"""Registro de visitas, histórico por cliente e conferência auditável de volumes."""
from datetime import date,datetime,time,timedelta,timezone
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import Depends,HTTPException,Query,Response
from pydantic import AwareDatetime,Field,StrictInt,field_validator,model_validator
from psycopg.types.json import Jsonb
from .models import StrictModel

Status=Literal['agendada','concluida','cancelada','nao_atendida']
Origin=Literal['rota_fixa','chamado_imprevisto']
QuantityStatus=Literal['a_conferir','confirmada']


class Item(StrictModel):
    modalidade_id: UUID
    quantidade: StrictInt | None = Field(default=None,ge=0,le=2147483647)
    quantidade_status: QuantityStatus = 'a_conferir'

    @model_validator(mode='after')
    def confirmed(self):
        if self.quantidade_status=='confirmada' and self.quantidade is None:
            raise ValueError('Informe a quantidade confirmada.')
        return self


def unique_items(items):
    if items is not None and len({i.modalidade_id for i in items})!=len(items):
        raise ValueError('Cada modalidade deve aparecer uma única vez na coleta.')
    return items


class CollectionCreate(StrictModel):
    id_local_dispositivo: UUID
    cliente_id: UUID
    motorista_id: UUID
    status: Literal['agendada','concluida'] = 'agendada'
    origem: Origin
    agendada_para: AwareDatetime | None = None
    concluida_em: AwareDatetime | None = None
    observacoes: str | None = Field(default=None,max_length=2000)
    itens: list[Item] = Field(min_length=1,max_length=50)

    _unique=field_validator('itens')(unique_items)

    @field_validator('agendada_para','concluida_em')
    @classmethod
    def utc(cls,value):
        return value.astimezone(timezone.utc) if value else None

    @model_validator(mode='after')
    def dates(self):
        if self.status=='agendada' and (self.agendada_para is None or self.concluida_em is not None):
            raise ValueError('Uma coleta agendada exige agendada_para e não pode ter concluida_em.')
        if self.status=='concluida' and self.concluida_em is None:
            raise ValueError('Informe quando a coleta foi realizada.')
        if self.concluida_em and self.concluida_em>datetime.now(timezone.utc)+timedelta(minutes=5):
            raise ValueError('A realização não pode estar no futuro.')
        return self


class StatusChange(StrictModel):
    versao: StrictInt = Field(ge=1)
    status: Literal['concluida','cancelada','nao_atendida']
    concluida_em: AwareDatetime | None = None
    motivo: str | None = Field(default=None,max_length=1000)
    itens: list[Item] | None = Field(default=None,min_length=1,max_length=50)
    _unique=field_validator('itens')(unique_items)

    @model_validator(mode='after')
    def required_fields(self):
        if self.status=='concluida':
            if self.concluida_em is None or self.itens is None:
                raise ValueError('Informe data de realização e os volumes coletados por modalidade.')
            if self.concluida_em>datetime.now(timezone.utc)+timedelta(minutes=5):
                raise ValueError('A realização não pode estar no futuro.')
        elif self.concluida_em is not None or self.itens is not None or not self.motivo:
            raise ValueError('Informe o motivo. Cancelamento/não atendimento não aceita volumes nem data de realização.')
        return self


class QuantityCorrection(StrictModel):
    versao: StrictInt = Field(ge=1)
    quantidade: StrictInt = Field(ge=0,le=2147483647)
    motivo: str = Field(min_length=1,max_length=1000)


SELECT_COLLECTION='''SELECT c.id,c.cliente_id,c.motorista_id,c.status,c.origem,c.agendada_para,c.concluida_em,
 c.criado_em,c.versao,c.tentativa,c.revisita_de,c.observacoes,c.dados_registro,c.assinatura_chave,
 coalesce(c.concluida_em,c.agendada_para,c.criado_em) AS data_referencia,
 coalesce(c.dados_registro->>'cliente_nome',cl.nome) AS cliente_nome,
 coalesce(c.dados_registro->>'cliente_cnpj',cl.cnpj) AS cliente_cnpj,
 coalesce(c.dados_registro->>'motorista_nome',u.nome) AS motorista_nome
 FROM coletas c JOIN clientes cl ON cl.id=c.cliente_id AND cl.empresa_id=c.empresa_id
 JOIN motoristas m ON m.id=c.motorista_id AND m.empresa_id=c.empresa_id
 JOIN usuarios u ON u.id=m.usuario_id AND u.empresa_id=m.empresa_id'''


def collection_detail(conn,cid):
    record=conn.execute(SELECT_COLLECTION+' WHERE c.id=%s',(cid,)).fetchone()
    if not record:
        raise HTTPException(404,'Coleta não encontrada.')
    record['tem_comprovante']=bool(conn.execute('SELECT 1 FROM comprovantes WHERE coleta_id=%s',(cid,)).fetchone())
    record['itens']=conn.execute('''SELECT i.id,i.modalidade_id,coalesce(i.modalidade_nome,m.nome) AS modalidade_nome,
        i.quantidade,i.quantidade_status FROM coleta_itens i JOIN modalidades m ON m.id=i.modalidade_id
        AND m.empresa_id=i.empresa_id WHERE i.coleta_id=%s ORDER BY modalidade_nome,i.id''',(cid,)).fetchall()
    record['eventos']=conn.execute('''SELECT id,usuario_nome,status_anterior,status_novo,motivo,dados,criado_em
        FROM coleta_eventos WHERE coleta_id=%s ORDER BY criado_em,id''',(cid,)).fetchall()
    record['conferencias']=conn.execute('''SELECT a.id,a.item_id,a.quantidade_anterior,a.quantidade_nova,a.status_anterior,
        a.status_novo,a.motivo,a.criado_em,coalesce(a.usuario_nome,u.nome) AS usuario_nome,i.modalidade_nome
        FROM auditoria_quantidades a JOIN coleta_itens i ON i.id=a.item_id AND i.empresa_id=a.empresa_id
        JOIN usuarios u ON u.id=a.usuario_id AND u.empresa_id=a.empresa_id WHERE i.coleta_id=%s
        ORDER BY a.criado_em,a.id''',(cid,)).fetchall()
    return record


def lock_collection(conn,cid,version):
    current=conn.execute('SELECT * FROM coletas WHERE id=%s FOR UPDATE',(cid,)).fetchone()
    if not current:
        raise HTTPException(404,'Coleta não encontrada.')
    if current['versao']!=version:
        raise HTTPException(409,'A coleta foi alterada. Atualize os detalhes antes de salvar.')
    return current


def add_event(conn,user,cid,old,new,motivo=None,dados=None):
    conn.execute('''INSERT INTO coleta_eventos(empresa_id,coleta_id,usuario_id,usuario_nome,status_anterior,status_novo,motivo,dados)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
        (user['empresa_id'],cid,user['id'],user['nome'],old,new,motivo,Jsonb(dados or {})))


def create_collection(body, response, auth, source=None):
    conn,user,_=auth
    content=body.model_dump(mode='json')
    if source is not None:
        content['execucao_rota']=source
    content['itens']=sorted(content['itens'],key=lambda i:i['modalidade_id'])
    digest=sha256(json.dumps(content,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                 (str(user['empresa_id'])+str(body.id_local_dispositivo),))
    previous=conn.execute('SELECT id,requisicao_hash FROM coletas WHERE id_local_dispositivo=%s',(body.id_local_dispositivo,)).fetchone()
    if previous:
        if previous['requisicao_hash']!=digest:
            raise HTTPException(409,'Este identificador já foi usado com outros dados. Reabra a coleta existente.')
        response.status_code=200
        return collection_detail(conn,previous['id'])
    # Mesma ordem de bloqueio da gestão de rotas: motorista, depois cliente.
    driver=conn.execute('''SELECT m.id,m.ativo,u.nome,u.ativo AS usuario_ativo FROM motoristas m
        JOIN usuarios u ON u.id=m.usuario_id AND u.empresa_id=m.empresa_id WHERE m.id=%s FOR UPDATE OF m''',
        (body.motorista_id,)).fetchone()
    client=conn.execute('SELECT * FROM clientes WHERE id=%s FOR UPDATE',(body.cliente_id,)).fetchone()
    if not driver or not driver['ativo'] or not driver['usuario_ativo'] or not client or not client['ativo']:
        raise HTTPException(422,'Selecione cliente e motorista ativos da sua transportadora.')
    mods=conn.execute('SELECT id,nome,ativa FROM modalidades WHERE id=ANY(%s)',([i.modalidade_id for i in body.itens],)).fetchall()
    if len(mods)!=len(body.itens) or any(not m['ativa'] for m in mods):
        raise HTTPException(422,'Selecione modalidades ativas da sua transportadora.')
    names={m['id']:m['nome'] for m in mods}
    snapshot={'cliente_nome':client['nome'],'cliente_cnpj':client['cnpj'],'motorista_nome':driver['nome'],
              'endereco':{k:client[k] for k in ['endereco','numero','complemento','bairro','cidade','estado','cep']}}
    cid=conn.execute('''INSERT INTO coletas(empresa_id,cliente_id,motorista_id,id_local_dispositivo,status,origem,
        agendada_para,concluida_em,observacoes,criado_por,dados_registro,requisicao_hash)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
        (user['empresa_id'],body.cliente_id,body.motorista_id,body.id_local_dispositivo,body.status,body.origem,
         body.agendada_para,body.concluida_em,body.observacoes,user['id'],Jsonb(snapshot),digest)).fetchone()['id']
    for item in body.itens:
        conn.execute('''INSERT INTO coleta_itens(empresa_id,coleta_id,modalidade_id,modalidade_nome,quantidade,quantidade_status)
            VALUES (%s,%s,%s,%s,%s,%s)''',
            (user['empresa_id'],cid,item.modalidade_id,names[item.modalidade_id],item.quantidade,item.quantidade_status))
    add_event(conn,user,cid,None,body.status,dados=content)
    return collection_detail(conn,cid)


def history_filter(conn,user,cliente_id=None,motorista_id=None,modalidade_id=None,
                   data_inicio=None,data_fim=None,status=None,origem=None,quantidade_status=None):
    if data_inicio and data_fim and data_inicio>data_fim:
        raise HTTPException(422,'A data inicial deve ser anterior ou igual à final.')
    zone=conn.execute('SELECT fuso_horario FROM empresas WHERE id=%s',(user['empresa_id'],)).fetchone()['fuso_horario']
    where=[];params=[]
    for field,value in [('cliente_id',cliente_id),('motorista_id',motorista_id),('status',status),('origem',origem)]:
        if value is not None:
            where.append(f'c.{field}=%s');params.append(value)
    ref='coalesce(c.concluida_em,c.agendada_para,c.criado_em)'
    if data_inicio:
        where.append(ref+'>=%s');params.append(datetime.combine(data_inicio,time.min,ZoneInfo(zone)))
    if data_fim:
        if data_fim==date.max:
            raise HTTPException(422,'Data final fora do intervalo permitido.')
        where.append(ref+'<%s');params.append(datetime.combine(data_fim+timedelta(days=1),time.min,ZoneInfo(zone)))
    item_where=[];item_params=[]
    if modalidade_id:
        item_where.append('i.modalidade_id=%s');item_params.append(modalidade_id)
    if quantidade_status:
        item_where.append('i.quantidade_status=%s');item_params.append(quantidade_status)
    if item_where:
        where.append('EXISTS(SELECT 1 FROM coleta_itens i WHERE i.coleta_id=c.id AND '+' AND '.join(item_where)+')')
        params.extend(item_params)
    clause=' WHERE '+' AND '.join(where) if where else ''
    return zone,clause,params,item_where,item_params


def register_collections(app,staff,admin):
    @app.get('/modalidades',tags=['Coletas'])
    def modalities(auth=Depends(staff)):
        return {'items':auth[0].execute('SELECT id,nome,ativa FROM modalidades ORDER BY nome,id').fetchall()}

    @app.post('/coletas',status_code=201,tags=['Coletas'])
    def create(body: CollectionCreate,response:Response,auth=Depends(staff)):
        return create_collection(body,response,auth)

    @app.get('/coletas',tags=['Histórico'])
    def history(cliente_id:UUID|None=None,motorista_id:UUID|None=None,modalidade_id:UUID|None=None,
                data_inicio:date|None=None,data_fim:date|None=None,status:Status|None=None,
                origem:Origin|None=None,quantidade_status:QuantityStatus|None=None,
                limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0),auth=Depends(staff)):
        conn,user,_=auth
        zone,clause,params,item_where,item_params=history_filter(conn,user,cliente_id,motorista_id,
            modalidade_id,data_inicio,data_fim,status,origem,quantidade_status)
        filtered='WITH filtered AS (SELECT c.* FROM coletas c'+clause+') '
        totals=conn.execute(filtered+'''SELECT count(*) AS total,
            count(*) FILTER(WHERE status='concluida') AS concluidas,
            count(*) FILTER(WHERE status='agendada') AS agendadas FROM filtered''',params).fetchone()
        # Quantidades somadas apenas para visitas concluídas e itens do filtro selecionado.
        breakdown=conn.execute(filtered+'''SELECT i.modalidade_id,i.modalidade_nome,
            count(DISTINCT c.id) AS coletas,
            coalesce(sum(i.quantidade) FILTER(WHERE i.quantidade_status='confirmada'),0) AS volumes_confirmados,
            count(*) FILTER(WHERE i.quantidade_status='a_conferir') AS itens_a_conferir
            FROM filtered c JOIN coleta_itens i ON i.coleta_id=c.id AND i.empresa_id=c.empresa_id
            WHERE c.status='concluida' '''+(' AND '+' AND '.join(item_where) if item_where else '')+
            ' GROUP BY i.modalidade_id,i.modalidade_nome ORDER BY i.modalidade_nome',[*params,*item_params]).fetchall()
        records=conn.execute(SELECT_COLLECTION+clause+' ORDER BY data_referencia DESC,c.id LIMIT %s OFFSET %s',
                             [*params,limit,offset]).fetchall()
        ids=[r['id'] for r in records]
        items=conn.execute('''SELECT id,coleta_id,modalidade_id,modalidade_nome,quantidade,quantidade_status
            FROM coleta_itens WHERE coleta_id=ANY(%s) ORDER BY modalidade_nome,id''',(ids,)).fetchall()
        by_id={cid:[] for cid in ids}
        for item in items:
            by_id[item.pop('coleta_id')].append(item)
        for record in records:
            record['itens']=by_id[record['id']]
        return {'items':records,**totals,'por_modalidade':breakdown,'limit':limit,'offset':offset,'fuso_horario':zone}

    @app.get('/coletas/{coleta_id}',tags=['Histórico'])
    def detail(coleta_id:UUID,auth=Depends(staff)):
        return collection_detail(auth[0],coleta_id)

    @app.put('/coletas/{coleta_id}/status',tags=['Coletas'])
    def change_status(coleta_id:UUID,body:StatusChange,auth=Depends(staff)):
        conn,user,_=auth
        old=lock_collection(conn,coleta_id,body.versao)
        if old['status']!='agendada':
            raise HTTPException(409,'Somente coletas agendadas podem mudar de situação nesta etapa.')
        if body.status=='concluida':
            existing=conn.execute('SELECT modalidade_id FROM coleta_itens WHERE coleta_id=%s',(coleta_id,)).fetchall()
            if not existing and old['execucao_id']:
                mods=conn.execute('SELECT id,nome FROM modalidades WHERE id=ANY(%s) AND ativa',([i.modalidade_id for i in body.itens],)).fetchall()
                if len(mods)!=len(body.itens):
                    raise HTTPException(422,'Selecione modalidades ativas da empresa.')
                names={m['id']:m['nome'] for m in mods}
                for item in body.itens:
                    conn.execute('''INSERT INTO coleta_itens(empresa_id,coleta_id,modalidade_id,modalidade_nome,quantidade,quantidade_status)
                        VALUES(%s,%s,%s,%s,%s,%s)''',(user['empresa_id'],coleta_id,item.modalidade_id,names[item.modalidade_id],item.quantidade,item.quantidade_status))
            elif {r['modalidade_id'] for r in existing}!={i.modalidade_id for i in body.itens}:
                raise HTTPException(422,'Informe todas as modalidades já registradas nesta coleta, sem adicionar outras.')
            for item in body.itens:
                conn.execute('''UPDATE coleta_itens SET quantidade=%s,quantidade_status=%s
                    WHERE coleta_id=%s AND modalidade_id=%s''',(item.quantidade,item.quantidade_status,coleta_id,item.modalidade_id))
        conn.execute('UPDATE coletas SET status=%s,concluida_em=%s,versao=versao+1 WHERE id=%s',
                     (body.status,body.concluida_em,coleta_id))
        add_event(conn,user,coleta_id,old['status'],body.status,body.motivo,body.model_dump(mode='json'))
        return collection_detail(conn,coleta_id)

    @app.put('/coletas/{coleta_id}/itens/{item_id}/quantidade',tags=['Conferência'])
    def correct(coleta_id:UUID,item_id:UUID,body:QuantityCorrection,auth=Depends(admin)):
        conn,user,_=auth
        record=lock_collection(conn,coleta_id,body.versao)
        if record['status']!='concluida':
            raise HTTPException(409,'A conferência é permitida após a conclusão da coleta.')
        item=conn.execute('SELECT * FROM coleta_itens WHERE id=%s AND coleta_id=%s',(item_id,coleta_id)).fetchone()
        if not item:
            raise HTTPException(404,'Item da coleta não encontrado.')
        if item['quantidade']==body.quantidade and item['quantidade_status']=='confirmada':
            raise HTTPException(422,'A quantidade já está confirmada com esse valor.')
        conn.execute('''INSERT INTO auditoria_quantidades(empresa_id,item_id,usuario_id,quantidade_anterior,
            quantidade_nova,motivo,status_anterior,status_novo,usuario_nome) VALUES (%s,%s,%s,%s,%s,%s,%s,'confirmada',%s)''',
            (user['empresa_id'],item_id,user['id'],item['quantidade'],body.quantidade,body.motivo,item['quantidade_status'],user['nome']))
        conn.execute("UPDATE coleta_itens SET quantidade=%s,quantidade_status='confirmada' WHERE id=%s",(body.quantidade,item_id))
        conn.execute('UPDATE coletas SET versao=versao+1 WHERE id=%s',(coleta_id,))
        return collection_detail(conn,coleta_id)
