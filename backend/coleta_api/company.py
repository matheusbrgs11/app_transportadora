"""Configuração própria de cada transportadora e catálogo de modalidades."""
from uuid import UUID
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from fastapi import Depends,HTTPException
from pydantic import Field,field_validator
from .models import StrictModel


class CompanyEdit(StrictModel):
    nome: str = Field(min_length=1,max_length=250)
    fuso_horario: str = Field(min_length=1,max_length=100)

    @field_validator('nome')
    @classmethod
    def nonblank(cls,value):
        if not value.strip():
            raise ValueError('Informe o nome da empresa.')
        return value

    @field_validator('fuso_horario')
    @classmethod
    def timezone(cls,value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError,ValueError,KeyError):
            raise ValueError('Fuso horário inválido.') from None
        return value


class ModalityEdit(StrictModel):
    nome: str = Field(min_length=1,max_length=150)
    ativa: bool = True

    @field_validator('nome')
    @classmethod
    def nonblank(cls,value):
        if not value.strip():
            raise ValueError('Informe o nome da modalidade.')
        return value


def register_company(app,staff,admin):
    @app.get('/empresa',tags=['Empresa'])
    def get_company(auth=Depends(staff)):
        conn,user,_=auth
        return conn.execute('SELECT id,nome,fuso_horario FROM empresas WHERE id=%s',(user['empresa_id'],)).fetchone()

    @app.put('/empresa',tags=['Empresa'])
    def update_company(body:CompanyEdit,auth=Depends(admin)):
        conn,user,_=auth
        return conn.execute('''UPDATE empresas SET nome=%s,fuso_horario=%s WHERE id=%s
            RETURNING id,nome,fuso_horario''',(body.nome,body.fuso_horario,user['empresa_id'])).fetchone()

    @app.post('/modalidades',status_code=201,tags=['Coletas'])
    def add_modality(body:ModalityEdit,auth=Depends(admin)):
        conn,user,_=auth
        return conn.execute('''INSERT INTO modalidades(empresa_id,nome,ativa) VALUES (%s,%s,%s)
            RETURNING id,nome,ativa''',(user['empresa_id'],body.nome,body.ativa)).fetchone()

    @app.put('/modalidades/{modality_id}',tags=['Coletas'])
    def update_modality(modality_id:UUID,body:ModalityEdit,auth=Depends(admin)):
        conn,_,_=auth
        row=conn.execute('''UPDATE modalidades SET nome=%s,ativa=%s WHERE id=%s
            RETURNING id,nome,ativa''',(body.nome,body.ativa,modality_id)).fetchone()
        if not row:
            raise HTTPException(404,'Modalidade não encontrada.')
        return row
