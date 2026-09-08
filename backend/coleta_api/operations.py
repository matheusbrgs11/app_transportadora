"""Gestão administrativa de motoristas, veículos e rotas fixas."""
from datetime import time
from typing import Literal
from uuid import UUID
import re
from fastapi import Depends, HTTPException
from pydantic import ConfigDict, Field, field_validator, model_validator
from .models import StrictModel


class Driver(StrictModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=False)
    nome: str = Field(min_length=1,max_length=250)
    login: str = Field(min_length=1,max_length=150)
    senha: str | None = Field(default=None,min_length=12,max_length=256)
    tipo: Literal['carro','moto','van','caminhao','outro']
    placa: str
    ativo: bool = True

    @field_validator('nome','login')
    @classmethod
    def non_blank(cls,value):
        value=value.strip()
        if not value:
            raise ValueError('Campo obrigatório.')
        return value

    @field_validator('placa')
    @classmethod
    def plate(cls,value):
        value=value.upper().replace('-','').replace(' ','')
        if not re.fullmatch(r'[A-Z]{3}[0-9][A-Z0-9][0-9]{2}',value):
            raise ValueError('Informe uma placa válida, como ABC1234 ou ABC1D23.')
        return value


class Stop(StrictModel):
    cliente_id: UUID
    janela_inicio: time | None = None
    janela_fim: time | None = None

    @model_validator(mode='after')
    def window(self):
        if (self.janela_inicio is None) != (self.janela_fim is None):
            raise ValueError('Informe início e fim da janela de atendimento.')
        if self.janela_inicio is not None and self.janela_inicio >= self.janela_fim:
            raise ValueError('O início deve ser anterior ao fim da janela.')
        return self


class Route(StrictModel):
    nome: str = Field(min_length=1,max_length=200)
    motorista_id: UUID
    dias_semana: list[int] = Field(min_length=1,max_length=7)
    ativa: bool = True
    paradas: list[Stop] = Field(min_length=1,max_length=200)
    versao: int | None = Field(default=None,ge=1)

    @field_validator('dias_semana')
    @classmethod
    def days(cls,value):
        if len(value)!=len(set(value)) or any(day not in range(1,8) for day in value):
            raise ValueError('Selecione dias distintos entre segunda e domingo.')
        return sorted(value)

    @model_validator(mode='after')
    def unique_clients(self):
        if len({stop.cliente_id for stop in self.paradas})!=len(self.paradas):
            raise ValueError('Cada cliente deve aparecer apenas uma vez na rota.')
        return self


DRIVERS = '''SELECT m.id,m.ativo,u.nome,u.login,v.tipo,v.placa,m.veiculo_id,
 (SELECT count(*) FROM rotas r WHERE r.motorista_id=m.id AND r.ativa) AS rotas_ativas
 FROM motoristas m JOIN usuarios u ON u.id=m.usuario_id AND u.empresa_id=m.empresa_id
 LEFT JOIN veiculos v ON v.id=m.veiculo_id AND v.empresa_id=m.empresa_id'''


def register_operations(app,staff,admin,passwords):
    def get_driver(conn,driver_id):
        driver=conn.execute(DRIVERS+' WHERE m.id=%s',(driver_id,)).fetchone()
        if not driver:
            raise HTTPException(404,'Motorista não encontrado.')
        return driver

    def vehicle(conn,company,body,driver_id=None):
        # A placa é exclusiva na empresa; bloqueia associação simultânea ao mesmo veículo.
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(str(company)+body.placa,))
        found=conn.execute('SELECT * FROM veiculos WHERE placa=%s FOR UPDATE',(body.placa,)).fetchone()
        if found:
            occupied=conn.execute('SELECT id FROM motoristas WHERE veiculo_id=%s AND ativo AND id IS DISTINCT FROM %s',
                                  (found['id'],driver_id)).fetchone()
            if occupied:
                raise HTTPException(409,'Este veículo já está vinculado a outro motorista ativo.')
            conn.execute('UPDATE veiculos SET tipo=%s,ativo=true WHERE id=%s',(body.tipo,found['id']))
            return found['id']
        return conn.execute('INSERT INTO veiculos(empresa_id,tipo,placa) VALUES (%s,%s,%s) RETURNING id',
                            (company,body.tipo,body.placa)).fetchone()['id']

    @app.get('/operacao/resumo',tags=['Operação'])
    def summary(auth=Depends(staff)):
        conn,user,_=auth
        company=conn.execute('SELECT nome FROM empresas WHERE id=%s',(user['empresa_id'],)).fetchone()
        counts=conn.execute('''SELECT
          (SELECT count(*) FROM clientes WHERE ativo) AS clientes_ativos,
          (SELECT count(*) FROM motoristas WHERE ativo) AS motoristas_ativos,
          (SELECT count(*) FROM rotas WHERE ativa) AS rotas_ativas,
          (SELECT count(*) FROM clientes WHERE ativo AND NOT localizacao_confirmada) AS enderecos_a_localizar''').fetchone()
        return {'empresa':company['nome'],**counts}

    @app.get('/motoristas',tags=['Motoristas'])
    def drivers(auth=Depends(staff)):
        return {'items':auth[0].execute(DRIVERS+' ORDER BY u.nome,m.id').fetchall()}

    @app.post('/motoristas',status_code=201,tags=['Motoristas'])
    def create_driver(body: Driver,auth=Depends(admin)):
        conn,user,_=auth
        if body.senha is None:
            raise HTTPException(422,'Informe a senha de acesso do motorista.')
        vid=vehicle(conn,user['empresa_id'],body)
        uid=conn.execute('''INSERT INTO usuarios(empresa_id,nome,login,senha_hash,perfil,ativo)
            VALUES (%s,%s,%s,%s,'motorista',%s) RETURNING id''',
            (user['empresa_id'],body.nome,body.login.lower(),passwords.hash(body.senha),body.ativo)).fetchone()['id']
        mid=conn.execute('INSERT INTO motoristas(empresa_id,usuario_id,veiculo_id,ativo) VALUES (%s,%s,%s,%s) RETURNING id',
                         (user['empresa_id'],uid,vid,body.ativo)).fetchone()['id']
        return get_driver(conn,mid)

    @app.put('/motoristas/{driver_id}',tags=['Motoristas'])
    def update_driver(driver_id: UUID,body: Driver,auth=Depends(admin)):
        conn,user,_=auth
        previous=conn.execute('SELECT * FROM motoristas WHERE id=%s FOR UPDATE',(driver_id,)).fetchone()
        if not previous:
            raise HTTPException(404,'Motorista não encontrado.')
        if not body.ativo and conn.execute('SELECT id FROM rotas WHERE motorista_id=%s AND ativa',(driver_id,)).fetchone():
            raise HTTPException(409,'Desative ou transfira as rotas ativas antes de desativar o motorista.')
        vid=vehicle(conn,user['empresa_id'],body,driver_id)
        conn.execute('UPDATE motoristas SET veiculo_id=%s,ativo=%s WHERE id=%s',(vid,body.ativo,driver_id))
        conn.execute('UPDATE usuarios SET nome=%s,login=%s,ativo=%s WHERE id=%s',
                     (body.nome,body.login.lower(),body.ativo,previous['usuario_id']))
        if body.senha is not None:
            conn.execute('UPDATE usuarios SET senha_hash=%s WHERE id=%s',(passwords.hash(body.senha),previous['usuario_id']))
            conn.execute('UPDATE sessoes SET revogada=true WHERE usuario_id=%s',(previous['usuario_id'],))
        return get_driver(conn,driver_id)

    def route_detail(conn,route_id):
        route=conn.execute('''SELECT r.*,u.nome AS motorista_nome FROM rotas r
          JOIN motoristas m ON m.id=r.motorista_id AND m.empresa_id=r.empresa_id
          JOIN usuarios u ON u.id=m.usuario_id AND u.empresa_id=m.empresa_id WHERE r.id=%s''',(route_id,)).fetchone()
        if not route:
            raise HTTPException(404,'Rota não encontrada.')
        route['paradas']=conn.execute('''SELECT p.id,p.cliente_id,p.ordem,p.janela_inicio,p.janela_fim,
            c.nome,c.endereco,c.numero,c.complemento,c.bairro,c.cidade,c.estado,c.ativo AS cliente_ativo
            FROM rota_paradas p JOIN clientes c ON c.id=p.cliente_id AND c.empresa_id=p.empresa_id
            WHERE p.rota_id=%s ORDER BY p.ordem''',(route_id,)).fetchall()
        return route

    def validate_route(conn,body):
        # Bloqueios são compartilhados entre gravação de rota e desativação de cadastros.
        driver=conn.execute('SELECT id,ativo FROM motoristas WHERE id=%s FOR UPDATE',(body.motorista_id,)).fetchone()
        if not driver or (body.ativa and not driver['ativo']):
            raise HTTPException(422,'Selecione um motorista ativo da sua empresa.')
        ids=[stop.cliente_id for stop in body.paradas]
        clients=conn.execute('SELECT id,ativo FROM clientes WHERE id=ANY(%s) ORDER BY id FOR UPDATE',(ids,)).fetchall()
        if len(clients)!=len(ids) or (body.ativa and any(not c['ativo'] for c in clients)):
            raise HTTPException(422,'Selecione apenas clientes ativos da sua empresa para uma rota ativa.')

    def stops(conn,company,route_id,body):
        conn.execute('DELETE FROM rota_paradas WHERE rota_id=%s',(route_id,))
        for index,stop in enumerate(body.paradas,1):
            conn.execute('''INSERT INTO rota_paradas(empresa_id,rota_id,cliente_id,ordem,janela_inicio,janela_fim)
                VALUES (%s,%s,%s,%s,%s,%s)''',(company,route_id,stop.cliente_id,index,stop.janela_inicio,stop.janela_fim))

    @app.get('/rotas',tags=['Rotas'])
    def routes(auth=Depends(staff)):
        return {'items':auth[0].execute('''SELECT r.id,r.nome,r.motorista_id,r.dias_semana,r.ativa,r.versao,
            u.nome AS motorista_nome,v.tipo,v.placa,(SELECT count(*) FROM rota_paradas p WHERE p.rota_id=r.id) AS total_paradas
            FROM rotas r JOIN motoristas m ON m.id=r.motorista_id AND m.empresa_id=r.empresa_id
            JOIN usuarios u ON u.id=m.usuario_id AND u.empresa_id=m.empresa_id
            LEFT JOIN veiculos v ON v.id=m.veiculo_id AND v.empresa_id=m.empresa_id ORDER BY r.nome,r.id''').fetchall()}

    @app.get('/rotas/{route_id}',tags=['Rotas'])
    def get_route(route_id: UUID,auth=Depends(staff)):
        return route_detail(auth[0],route_id)

    @app.post('/rotas',status_code=201,tags=['Rotas'])
    def create_route(body: Route,auth=Depends(staff)):
        conn,user,_=auth
        validate_route(conn,body)
        rid=conn.execute('''INSERT INTO rotas(empresa_id,motorista_id,nome,dias_semana,ativa)
            VALUES (%s,%s,%s,%s,%s) RETURNING id''',
            (user['empresa_id'],body.motorista_id,body.nome,body.dias_semana,body.ativa)).fetchone()['id']
        stops(conn,user['empresa_id'],rid,body)
        return route_detail(conn,rid)

    @app.put('/rotas/{route_id}',tags=['Rotas'])
    def update_route(route_id: UUID,body: Route,auth=Depends(staff)):
        conn,user,_=auth
        old=conn.execute('SELECT * FROM rotas WHERE id=%s FOR UPDATE',(route_id,)).fetchone()
        if not old:
            raise HTTPException(404,'Rota não encontrada.')
        if body.versao != old['versao']:
            raise HTTPException(409,'Esta rota foi alterada. Reabra o cadastro antes de salvar.')
        validate_route(conn,body)
        conn.execute('''UPDATE rotas SET motorista_id=%s,nome=%s,dias_semana=%s,ativa=%s,versao=versao+1
            WHERE id=%s''',(body.motorista_id,body.nome,body.dias_semana,body.ativa,route_id))
        stops(conn,user['empresa_id'],route_id,body)
        return route_detail(conn,route_id)
