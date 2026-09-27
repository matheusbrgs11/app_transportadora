from uuid import UUID
from typing import Literal
from fastapi import Depends, HTTPException
from pydantic import Field, StrictInt, FiniteFloat, model_validator
from psycopg.types.json import Jsonb
from .models import StrictModel

POINT_FIELDS='''localizacao_confirmada,localizacao_versao,localizacao_fonte,
    ST_Y(localizacao::geometry) AS latitude,ST_X(localizacao::geometry) AS longitude'''

class Location(StrictModel):
    versao: StrictInt = Field(ge=1)
    latitude: FiniteFloat | None = Field(default=None,ge=-90,le=90)
    longitude: FiniteFloat | None = Field(default=None,ge=-180,le=180)
    fonte: Literal['cliente','gps_campo'] | None = None
    motivo: str = Field(min_length=1,max_length=1000)

    @model_validator(mode='after')
    def coordinates(self):
        if (self.latitude is None)!=(self.longitude is None):
            raise ValueError('Informe latitude e longitude juntas.')
        if (self.latitude is None)!=(self.fonte is None):
            raise ValueError('Coordenadas exigem fonte; remoção não aceita fonte.')
        return self


def register_locations(app,staff,admin):
    @app.get('/clientes/{cliente_id}/localizacao',tags=['Localização'])
    def get(cliente_id:UUID,auth=Depends(staff)):
        row=auth[0].execute('SELECT '+POINT_FIELDS+' FROM clientes WHERE id=%s',(cliente_id,)).fetchone()
        if not row: raise HTTPException(404,'Cliente não encontrado.')
        return row

    @app.put('/clientes/{cliente_id}/localizacao',tags=['Localização'])
    def update(cliente_id:UUID,body:Location,auth=Depends(admin)):
        conn,user,_=auth
        old=conn.execute('SELECT '+POINT_FIELDS+' FROM clientes WHERE id=%s FOR UPDATE',(cliente_id,)).fetchone()
        if not old: raise HTTPException(404,'Cliente não encontrado.')
        if old['localizacao_versao']!=body.versao:
            raise HTTPException(409,'Endereço ou localização alterados. Reabra a localização antes de salvar.')
        conn.execute('''UPDATE clientes SET localizacao=CASE WHEN %s::double precision IS NULL THEN NULL
            ELSE ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography END,
            localizacao_confirmada=%s,localizacao_fonte=%s,localizacao_versao=localizacao_versao+1 WHERE id=%s''',
            (body.latitude,body.longitude,body.latitude,body.latitude is not None,body.fonte,cliente_id))
        conn.execute('INSERT INTO localizacao_eventos(empresa_id,cliente_id,usuario_id,motivo,anterior,nova) VALUES(%s,%s,%s,%s,%s,%s)',
            (user['empresa_id'],cliente_id,user['id'],body.motivo,Jsonb(old),Jsonb(body.model_dump(mode='json'))))
        return get(cliente_id,auth)
