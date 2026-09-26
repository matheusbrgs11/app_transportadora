import base64
import struct
import zlib
from uuid import uuid4
from test_driver_visits import prepare
from test_daily import issue


def png():
    def chunk(kind,data): return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    # Synthetic raster test fixture, not a person's signature.
    return base64.b64encode(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',2,1,8,6,0,0,0))+
        chunk(b'IDAT',zlib.compress(b'\0\0\0\0\xff\xff\xff\xff\xff'))+chunk(b'IEND',b'')).decode()


def test_proof_atomic_private_and_immutable_replay(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,_=prepare(context,customer);_,body=issue(client,h,body)
    proof={'tipo':'assinatura','responsavel':'Pessoa de teste','capturado_em':body['concluida_em'],'imagem_png':png()}
    body={**body,'comprovante':proof}
    result=client.post('/motorista/coletas',headers=dh,json=body)
    assert result.status_code==200,result.text
    assert client.post('/motorista/coletas',headers=dh,json=body).status_code==200
    assert client.post('/motorista/coletas',headers=dh,json={**body,'comprovante':{**proof,'responsavel':'Alterado'}}).status_code==409
    path='/coletas/'+body['coleta_id']+'/comprovante'
    r=client.get(path,headers=h);assert r.status_code==200 and r.headers['cache-control']=='no-store'
    assert r.json()['imagem_png']==proof['imagem_png']
    assert r.json()['registro']['cliente_nome']==customer['nome']
    assert len(r.json()['sha256'])==64
    assert client.get(path).status_code==401
    assert client.get(path,headers=login(b)).status_code==404
    assert client.get(path,headers=dh).status_code==403
    detail=client.get('/coletas/'+body['coleta_id'],headers=h).json()
    assert detail['tem_comprovante']
    assert 'imagem_png' not in detail['eventos'][-1]['dados']['comprovante']
    # Invalid collection data cannot leave an orphan proof.
    second=next(p for p in client.get('/rotas/'+body['rota_id']+'/execucoes?data=2026-05-07',headers=h).json()['execucao']['paradas'] if p['coleta_id']!=body['coleta_id'])
    invalid={**body,'id_local_dispositivo':str(uuid4()),'coleta_id':second['coleta_id'],'cliente_id':second['cliente_id'],
             'itens':[{'modalidade_id':str(uuid4()),'quantidade':1,'quantidade_status':'confirmada'}]}
    assert client.post('/motorista/coletas',headers=dh,json=invalid).status_code==422
    assert client.get('/coletas/'+second['coleta_id']+'/comprovante',headers=h).status_code==404
    assert client.get('/coletas/'+second['coleta_id'],headers=h).json()['status']=='agendada'


def test_proof_validation_exception_and_legacy(context,customer):
    client,a,b,login,admin,settings=context
    h,dh,body,_=prepare(context,customer);_,body=issue(client,h,body)
    proof={'tipo':'assinatura','responsavel':'Pessoa teste','capturado_em':body['concluida_em'],'imagem_png':png()}
    for changes in [{'imagem_png':'invalid'},{'responsavel':' '},{'imagem_png':base64.b64encode(b'<svg/>').decode()},
                    {'capturado_em':'2026-05-07T10:00:00Z'},{'tipo':'recusa','motivo':'Recusou'},{'imagem_png':'A'*180000}]:
        r=client.post('/motorista/coletas',headers=dh,json={**body,'comprovante':{**proof,**changes}})
        assert r.status_code==422,r.text
    missing={'tipo':'ausencia','capturado_em':body['concluida_em'],'motivo':'Portaria recebeu sem responsável presente'}
    r=client.post('/motorista/coletas',headers=dh,json={**body,'comprovante':missing});assert r.status_code==200,r.text
    result=client.get('/coletas/'+body['coleta_id']+'/comprovante',headers=h).json()
    assert result['imagem_png'] is None and result['metadados']['motivo']==missing['motivo']


def test_png_corruption_and_dimensions():
    from coleta_api.proofs import png_bytes
    import pytest
    original=base64.b64decode(png())
    for raw in [original[:-1],original+b'extra',original[:45]+b'bad'+original[48:],original[:20]]:
        with pytest.raises(ValueError): png_bytes(base64.b64encode(raw).decode())


def test_proof_storage_failure_rolls_back_collection_and_can_retry(context,customer,monkeypatch):
    from coleta_api import proofs
    from fastapi import HTTPException
    client,a,b,login,admin,settings=context
    h,dh,body,_=prepare(context,customer);_,body=issue(client,h,body)
    body={**body,'comprovante':{'tipo':'recusa','motivo':'Pessoa não quis assinar','capturado_em':body['concluida_em']}}
    original=proofs.save_proof
    def failure(*args):
        original(*args)
        raise HTTPException(503,'Falha simulada depois de gravar o comprovante')
    monkeypatch.setattr(proofs,'save_proof',failure)
    assert client.post('/motorista/coletas',headers=dh,json=body).status_code==503
    assert client.get('/coletas/'+body['coleta_id'],headers=h).json()['status']=='agendada'
    assert client.get('/coletas/'+body['coleta_id']+'/comprovante',headers=h).status_code==404
    monkeypatch.setattr(proofs,'save_proof',original)
    client.post('/motorista/coletas',headers=dh,json=body).raise_for_status()
    assert client.get('/coletas/'+body['coleta_id'],headers=h).json()['tem_comprovante']
