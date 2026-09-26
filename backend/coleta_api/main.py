from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from time import monotonic
from uuid import UUID, uuid4
import jwt
from jwt import InvalidTokenError
from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Query
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from psycopg import IntegrityError, OperationalError, sql
from psycopg.types.json import Jsonb
from pwdlib import PasswordHash
from .config import Settings
from .db import transaction
from .models import Client, Login, UserCreate, Confirmation
from .importer import preview, MAX_BYTES
from .operations import register_operations
from .collections import register_collections
from .driver_day import register_driver_day
from .daily import register_daily
from .offline import register_offline

PASSWORDS = PasswordHash.recommended()
DUMMY_HASH = PASSWORDS.hash(str(uuid4()))
CLIENT_FIELDS = list(Client.model_fields)
CLIENT_SELECT = ','.join(['id','empresa_id',*CLIENT_FIELDS,'localizacao_confirmada','criado_em'])
bearer = HTTPBearer(auto_error=False)


def insert_client(conn,empresa_id,client):
    data = client.model_dump(mode='json')
    query = sql.SQL('INSERT INTO clientes ({}) VALUES ({}) RETURNING '+CLIENT_SELECT).format(
        sql.SQL(',').join(map(sql.Identifier,['empresa_id',*data])),
        sql.SQL(',').join(sql.Placeholder() for _ in range(len(data)+1)))
    return conn.execute(query,[empresa_id,*data.values()]).fetchone()


def create_app(settings: Settings | None = None):
    settings = settings or Settings.from_env()
    app = FastAPI(title='Coleta — API', version='0.1.0', description='Gestão de clientes por transportadora. Informe o ID da empresa no login e use o token em Authorize.')
    attempts = defaultdict(deque)
    attempts_lock = Lock()

    @app.exception_handler(IntegrityError)
    async def integrity_error(request,exc):
        return JSONResponse(status_code=409,content={'detail':'Conflito de dados. Confira duplicidades e vínculos antes de tentar novamente.'})

    @app.exception_handler(OperationalError)
    async def connection_error(request,exc):
        return JSONResponse(status_code=503,content={'detail':'Banco indisponível. Tente novamente em instantes.'})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        return JSONResponse(status_code=422,content={'detail':jsonable_encoder([
            {'loc':e['loc'],'msg':e['msg'],'type':e['type']} for e in exc.errors()])})

    def authenticated(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None:
            raise HTTPException(401,'Faça login para continuar.',headers={'WWW-Authenticate':'Bearer'})
        try:
            payload = jwt.decode(credentials.credentials,settings.jwt_secret,algorithms=['HS256'],
                                 issuer='coleta-api',audience='coleta',options={'require':['exp','iat','sub','empresa_id','jti']})
            empresa_id,user_id,session_id = (UUID(payload[key]) for key in ('empresa_id','sub','jti'))
        except (InvalidTokenError,ValueError,TypeError):
            raise HTTPException(401,'Sessão inválida ou expirada.')
        with transaction(settings,empresa_id) as conn:
            user = conn.execute('''SELECT u.id,u.empresa_id,u.nome,u.login,u.perfil FROM usuarios u
                JOIN empresas e ON e.id=u.empresa_id
                JOIN sessoes s ON s.usuario_id=u.id AND s.empresa_id=u.empresa_id
                WHERE u.id=%s AND u.ativo AND e.ativa AND s.id=%s AND NOT s.revogada AND s.expira_em>now()''',
                (user_id,session_id)).fetchone()
            if not user:
                raise HTTPException(401,'Sessão inválida ou expirada.')
            yield conn,user,session_id

    def staff(auth=Depends(authenticated)):
        if auth[1]['perfil'] not in ('admin','operador'):
            raise HTTPException(403,'Acesso restrito à equipe administrativa.')
        return auth

    def admin(auth=Depends(authenticated)):
        if auth[1]['perfil'] != 'admin':
            raise HTTPException(403,'Acesso restrito a administradores.')
        return auth

    @app.get('/health',tags=['Sistema'])
    def health():
        with transaction(settings) as conn:
            conn.execute('SELECT 1')
        return {'status':'ok'}

    @app.post('/auth/login',tags=['Autenticação'])
    def login(body: Login,request: Request):
        now_mono = monotonic()
        key = request.client.host if request.client else 'local'
        with attempts_lock:
            # Limite por IP para esta instância, inclusive para empresas/logins inexistentes.
            for oldkey in list(attempts):
                if not attempts[oldkey] or attempts[oldkey][-1] < now_mono-60:
                    del attempts[oldkey]
            queue = attempts[key]
            while queue and queue[0] < now_mono-60:
                queue.popleft()
            if len(queue)>=15:
                raise HTTPException(429,'Muitas tentativas. Aguarde um minuto.',headers={'Retry-After':'60'})
            queue.append(now_mono)
        with transaction(settings,body.empresa_id) as conn:
            user = conn.execute('''SELECT u.* FROM usuarios u JOIN empresas e ON e.id=u.empresa_id
                WHERE u.login=%s AND u.ativo AND e.ativa''',(body.usuario_login.strip().lower(),)).fetchone()
            valid = PASSWORDS.verify(body.senha,user['senha_hash'] if user else DUMMY_HASH)
            if not user or not valid:
                raise HTTPException(401,'Empresa, usuário ou senha inválidos.')
            issued = datetime.now(timezone.utc)
            duration=settings.driver_token_minutes if user['perfil']=='motorista' else settings.token_minutes
            expires = issued+timedelta(minutes=duration)
            session = conn.execute('INSERT INTO sessoes(empresa_id,usuario_id,expira_em) VALUES (%s,%s,%s) RETURNING id',
                (user['empresa_id'],user['id'],expires)).fetchone()
            token = jwt.encode({'sub':str(user['id']),'empresa_id':str(user['empresa_id']),'jti':str(session['id']),
                'iat':issued,'exp':expires,'iss':'coleta-api','aud':'coleta'},settings.jwt_secret,algorithm='HS256')
            return {'access_token':token,'token_type':'bearer','expires_in':duration*60,
                    'usuario':{k:user[k] for k in ('id','empresa_id','nome','perfil')}}

    @app.get('/auth/me',tags=['Autenticação'])
    def me(auth=Depends(authenticated)):
        return auth[1]

    @app.post('/auth/logout',status_code=204,tags=['Autenticação'])
    def logout(auth=Depends(authenticated)):
        conn,user,session_id = auth
        conn.execute('UPDATE sessoes SET revogada=true WHERE id=%s',(session_id,))

    @app.post('/usuarios',status_code=201,tags=['Usuários'])
    def create_user(body: UserCreate,auth=Depends(admin)):
        conn,user,_ = auth
        return conn.execute('''INSERT INTO usuarios(empresa_id,nome,login,senha_hash,perfil)
            VALUES (%s,%s,%s,%s,%s) RETURNING id,nome,login,perfil,ativo''',
            (user['empresa_id'],body.nome,body.login.strip().lower(),PASSWORDS.hash(body.senha),body.perfil)).fetchone()

    @app.get('/clientes',tags=['Clientes'])
    def clients(q: str = Query('',max_length=150),ativo: bool | None=None,
                limit: int=Query(50,ge=1,le=200),offset: int=Query(0,ge=0),auth=Depends(staff)):
        conn,_,_ = auth
        pattern = '%'+q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        where = 'WHERE (nome ILIKE %s OR cnpj ILIKE %s) AND (%s::boolean IS NULL OR ativo=%s)'
        params = [pattern,pattern,ativo,ativo]
        total = conn.execute('SELECT count(*) AS total FROM clientes '+where,params).fetchone()['total']
        records = conn.execute('SELECT '+CLIENT_SELECT+' FROM clientes '+where+' ORDER BY nome,id LIMIT %s OFFSET %s',
                               [*params,limit,offset]).fetchall()
        return {'items':records,'total':total,'limit':limit,'offset':offset}

    @app.post('/clientes',status_code=201,tags=['Clientes'])
    def create_client(body: Client,auth=Depends(staff)):
        return insert_client(auth[0],auth[1]['empresa_id'],body)

    @app.post('/clientes/importacoes/previa',status_code=201,tags=['Importação'])
    def import_preview(arquivo: UploadFile=File(...),auth=Depends(admin)):
        data = arquivo.file.read(MAX_BYTES+1)
        filename = Path(arquivo.filename or '').name
        if len(filename)>200:
            raise HTTPException(422,'Nome do arquivo muito longo.')
        try:
            rows = preview(data,filename)
        except Exception as exc:
            # Bibliotecas de leitura podem falhar em XML/ZIP inválido. Nunca expor detalhes internos.
            message = str(exc) if type(exc) is ValueError else 'Arquivo inválido ou não suportado.'
            raise HTTPException(422,message) from exc
        conn,user,_ = auth
        cnpjs = [r['dados']['cnpj'] for r in rows if r['dados']]
        existing = {r['cnpj'] for r in conn.execute('SELECT cnpj FROM clientes WHERE cnpj=ANY(%s)',(cnpjs,)).fetchall()}
        for row in rows:
            if row['dados'] and row['dados']['cnpj'] in existing:
                row['erros'].append('CNPJ já cadastrado nesta empresa; use a edição do cliente.')
        batch = conn.execute('''INSERT INTO importacoes(empresa_id,usuario_id,arquivo,linhas)
            VALUES (%s,%s,%s,%s) RETURNING id,expira_em''',
            (user['empresa_id'],user['id'],filename,Jsonb(rows))).fetchone()
        return {**batch,'linhas':rows,'validas':sum(not r['erros'] for r in rows),'total':len(rows)}

    @app.post('/clientes/importacoes/{batch_id}/confirmar',tags=['Importação'])
    def confirm_import(batch_id: UUID,body: Confirmation,auth=Depends(admin)):
        conn,user,_ = auth
        batch = conn.execute('SELECT * FROM importacoes WHERE id=%s FOR UPDATE',(batch_id,)).fetchone()
        if not batch or batch['usuario_id'] != user['id']:
            raise HTTPException(404,'Importação não encontrada.')
        if batch['confirmada_em']:
            return {'importados':batch['quantidade_importada'],'ja_confirmada':True}
        if batch['expira_em'] < datetime.now(timezone.utc):
            raise HTTPException(410,'Prévia expirada. Envie o arquivo novamente.')
        selected = set(body.linhas)
        rows = [r for r in batch['linhas'] if r['linha'] in selected]
        if len(selected)!=len(body.linhas) or len(rows)!=len(selected) or any(r['erros'] for r in rows):
            raise HTTPException(422,'Selecione somente linhas válidas e sem repetição da prévia.')
        for row in rows:
            insert_client(conn,user['empresa_id'],Client.model_validate(row['dados']))
        conn.execute('UPDATE importacoes SET confirmada_em=now(),quantidade_importada=%s WHERE id=%s',(len(rows),batch_id))
        return {'importados':len(rows),'ja_confirmada':False}

    @app.get('/clientes/{client_id}',tags=['Clientes'])
    def get_client(client_id: UUID,auth=Depends(staff)):
        client = auth[0].execute('SELECT '+CLIENT_SELECT+' FROM clientes WHERE id=%s',(client_id,)).fetchone()
        if not client:
            raise HTTPException(404,'Cliente não encontrado.')
        return client

    @app.put('/clientes/{client_id}',tags=['Clientes'])
    def update_client(client_id: UUID,body: Client,auth=Depends(staff)):
        conn,_,_ = auth
        old = conn.execute('SELECT '+CLIENT_SELECT+' FROM clientes WHERE id=%s FOR UPDATE',(client_id,)).fetchone()
        if not old:
            raise HTTPException(404,'Cliente não encontrado.')
        if not body.ativo and conn.execute('''SELECT p.id FROM rota_paradas p JOIN rotas r ON r.id=p.rota_id
                WHERE p.cliente_id=%s AND r.ativa LIMIT 1''',(client_id,)).fetchone():
            raise HTTPException(409,'Remova o cliente das rotas ativas antes de desativá-lo.')
        data = body.model_dump(mode='json')
        assignments = [sql.SQL('{}=%s').format(sql.Identifier(k)) for k in data]
        if any(old[k]!=data[k] for k in ('endereco','numero','complemento','bairro','cidade','estado','cep')):
            assignments.extend([sql.SQL('localizacao=NULL'),sql.SQL('localizacao_confirmada=false')])
        query = sql.SQL('UPDATE clientes SET {} WHERE id=%s RETURNING '+CLIENT_SELECT).format(sql.SQL(',').join(assignments))
        return conn.execute(query,[*data.values(),client_id]).fetchone()

    register_offline(app,authenticated,staff)
    register_daily(app,staff)
    register_driver_day(app,authenticated)
    register_operations(app,staff,admin,PASSWORDS)
    register_collections(app,staff,admin)
    return app
