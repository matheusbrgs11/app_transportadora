import re
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator, model_validator


def normalize_cnpj(value: str) -> str:
    value = re.sub(r'[. /\-]', '', value).upper()
    if not re.fullmatch(r'[A-Z0-9]{12}[0-9]{2}', value) or len(set(value)) == 1:
        raise ValueError('CNPJ inválido.')
    base = value[:12]
    for weights in ([5,4,3,2,9,8,7,6,5,4,3,2], [6,5,4,3,2,9,8,7,6,5,4,3,2]):
        remainder = sum((ord(char)-48)*weight for char,weight in zip(base,weights)) % 11
        base += str(0 if remainder < 2 else 11-remainder)
    if base != value:
        raise ValueError('Dígitos verificadores do CNPJ inválidos.')
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Login(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    empresa_id: UUID
    usuario_login: str = Field(min_length=1, max_length=150)
    senha: str = Field(min_length=1, max_length=256)


class Client(StrictModel):
    nome: str = Field(min_length=1, max_length=250)
    cnpj: str
    endereco: str = Field(min_length=1, max_length=300)
    numero: str | None = Field(default=None, max_length=30)
    complemento: str | None = Field(default=None, max_length=250)
    bairro: str | None = Field(default=None, max_length=150)
    cidade: str = Field(min_length=1, max_length=150)
    estado: str
    cep: str | None = None
    telefone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    contrato_status: Literal['nao_informado','sem_contrato','com_contrato'] = 'nao_informado'
    numero_contrato: str | None = Field(default=None, max_length=100)
    ativo: bool = True

    @field_validator('cnpj')
    @classmethod
    def cnpj_valid(cls, value):
        return normalize_cnpj(value)

    @field_validator('estado')
    @classmethod
    def uf_valid(cls, value):
        value = value.upper()
        if value not in 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split():
            raise ValueError('UF inválida.')
        return value

    @field_validator('cep')
    @classmethod
    def cep_valid(cls, value):
        if value is None:
            return None
        value = re.sub(r'[\s.\-]', '', value)
        if not re.fullmatch(r'[0-9]{8}', value):
            raise ValueError('CEP deve ter 8 dígitos.')
        return value

    @model_validator(mode='after')
    def contract_valid(self):
        if self.contrato_status == 'com_contrato' and not self.numero_contrato:
            raise ValueError('Informe o número do contrato.')
        if self.contrato_status != 'com_contrato' and self.numero_contrato is not None:
            raise ValueError('Número do contrato exige situação com_contrato.')
        return self


class Confirmation(StrictModel):
    linhas: list[int] = Field(min_length=1, max_length=5000)


class UserCreate(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    nome: str = Field(min_length=1, max_length=250)
    login: str = Field(min_length=1, max_length=150)
    senha: str = Field(min_length=12, max_length=256)
    perfil: Literal['admin','operador','motorista','agendamento']

    @field_validator('nome','login')
    @classmethod
    def non_blank(cls,value):
        value=value.strip()
        if not value:
            raise ValueError('Campo obrigatório.')
        return value


class PasswordChange(StrictModel):
    senha_atual: str = Field(min_length=1,max_length=256)
    nova_senha: str = Field(min_length=12,max_length=256)


class PasswordReset(StrictModel):
    nova_senha: str = Field(min_length=12,max_length=256)


class UserAccess(StrictModel):
    ativo: bool


class PasswordRecovery(StrictModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=False)
    empresa_id: UUID
    usuario_login: str = Field(min_length=1,max_length=150)
    codigo: str = Field(min_length=24,max_length=100)
    nova_senha: str = Field(min_length=12,max_length=256)


class RecoveryGenerate(StrictModel):
    senha_atual: str = Field(min_length=1,max_length=256)
