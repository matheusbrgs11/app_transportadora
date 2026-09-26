"""Comprovantes pequenos e privados, gravados atomicamente com a coleta."""
import base64
import binascii
import hashlib
import json
import struct
import zlib
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID
from fastapi import Depends, HTTPException, Response
from pydantic import AwareDatetime, Field, model_validator
from psycopg.types.json import Jsonb
from .models import StrictModel


def png_bytes(value):
    try:
        raw=base64.b64decode(value,validate=True)
        if len(raw)>131072 or raw[:8]!=b'\x89PNG\r\n\x1a\n':
            raise ValueError()
        offset=8; compressed=b''; width=height=channels=0; ended=False; seen_data=False
        while offset<len(raw):
            size=struct.unpack('>I',raw[offset:offset+4])[0]
            kind=raw[offset+4:offset+8]; data=raw[offset+8:offset+8+size]
            checksum=struct.unpack('>I',raw[offset+8+size:offset+12+size])[0]
            if len(data)!=size or zlib.crc32(kind+data)&0xffffffff!=checksum:
                raise ValueError()
            if offset==8:
                if kind!=b'IHDR' or size!=13: raise ValueError()
                width,height,bits,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',data)
                if not (1<=width<=1024 and 1<=height<=512) or bits!=8 or color not in (2,6) or compression or filtering or interlace:
                    raise ValueError()
                channels=3 if color==2 else 4
            elif kind==b'IDAT':
                compressed+=data;seen_data=True
            elif kind==b'IEND':
                if size or not seen_data or offset+12!=len(raw): raise ValueError()
                ended=True
            elif kind not in (b'sRGB',b'gAMA',b'cHRM',b'pHYs',b'sBIT'):
                raise ValueError()
            offset+=12+size
        if not ended: raise ValueError()
        expected=height*(1+width*channels)
        decoder=zlib.decompressobj()
        pixels=decoder.decompress(compressed,expected+1)
        if len(pixels)!=expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError()
        if any(pixels[y*(1+width*channels)]>4 for y in range(height)): raise ValueError()
        return raw
    except (ValueError,struct.error,zlib.error,binascii.Error):
        raise ValueError('Assinatura inválida. Use PNG RGB/RGBA de até 128 KB e 1024 × 512 pixels.')


class Proof(StrictModel):
    tipo: Literal['assinatura','ausencia','recusa']
    responsavel: str | None = Field(default=None,max_length=200)
    capturado_em: AwareDatetime
    motivo: str | None = Field(default=None,max_length=1000)
    imagem_png: str | None = Field(default=None,max_length=174764)

    @model_validator(mode='after')
    def validate_proof(self):
        if self.capturado_em>datetime.now(timezone.utc)+timedelta(minutes=5):
            raise ValueError('Horário do comprovante no futuro.')
        if self.tipo=='assinatura':
            if not self.responsavel or not self.imagem_png or self.motivo:
                raise ValueError('Assinatura exige nome e imagem, sem motivo de exceção.')
            png_bytes(self.imagem_png)
        elif self.imagem_png is not None or not self.motivo:
            raise ValueError('Ausência/recusa exige justificativa e não aceita assinatura.')
        return self


def save_proof(conn,user,old,body,names):
    proof=body.comprovante
    if proof is None: return
    data=png_bytes(proof.imagem_png) if proof.imagem_png else None
    snapshot={**old['dados_registro'],'coleta_id':str(old['id']),'concluida_em':body.concluida_em.isoformat(),
              'itens':[{**i.model_dump(mode='json'),'modalidade_nome':names[i.modalidade_id]} for i in body.itens]}
    metadata=proof.model_dump(mode='json',exclude={'imagem_png'})
    digest=hashlib.sha256(json.dumps({'metadados':metadata,'registro':snapshot},sort_keys=True).encode()+(data or b'')).hexdigest()
    conn.execute('''INSERT INTO comprovantes(empresa_id,coleta_id,usuario_id,metadados,registro,imagem,sha256)
        VALUES(%s,%s,%s,%s,%s,%s,%s)''',(user['empresa_id'],old['id'],user['id'],Jsonb(metadata),Jsonb(snapshot),data,digest))


def register_proofs(app,staff):
    @app.get('/coletas/{coleta_id}/comprovante',tags=['Comprovantes'])
    def get(coleta_id:UUID,response:Response,auth=Depends(staff)):
        conn,_,_=auth
        row=conn.execute('SELECT metadados,registro,imagem,sha256,criado_em FROM comprovantes WHERE coleta_id=%s',(coleta_id,)).fetchone()
        if not row:
            raise HTTPException(404,'Esta coleta não possui comprovante registrado.')
        response.headers['Cache-Control']='no-store'
        image=row.pop('imagem')
        return {**row,'imagem_png':base64.b64encode(bytes(image)).decode() if image else None}
