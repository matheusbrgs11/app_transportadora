BEGIN;
CREATE EXTENSION IF NOT EXISTS postgis;

-- A API deve assumir este papel sem privilégios de proprietário/superusuário.
CREATE ROLE coleta_app NOLOGIN NOSUPERUSER NOBYPASSRLS;
CREATE SCHEMA app;
CREATE FUNCTION app.empresa_atual() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app.empresa_id', true), '')::uuid
$$;

CREATE TABLE empresas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nome text NOT NULL CHECK (length(trim(nome)) > 0),
  fuso_horario text NOT NULL DEFAULT 'America/Sao_Paulo',
  ativa boolean NOT NULL DEFAULT true,
  criado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE usuarios (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES empresas(id),
  nome text NOT NULL,
  login text NOT NULL CHECK (login = lower(trim(login))),
  senha_hash text NOT NULL,
  perfil text NOT NULL CHECK (perfil IN ('admin','operador','motorista')),
  ativo boolean NOT NULL DEFAULT true,
  UNIQUE (empresa_id,id), UNIQUE (empresa_id,login)
);

CREATE TABLE veiculos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES empresas(id),
  tipo text NOT NULL CHECK (tipo IN ('carro','moto','van','caminhao','outro')),
  placa text NOT NULL,
  ativo boolean NOT NULL DEFAULT true,
  UNIQUE (empresa_id,id), UNIQUE (empresa_id,placa)
);

CREATE TABLE motoristas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES empresas(id),
  usuario_id uuid NOT NULL,
  veiculo_id uuid,
  ativo boolean NOT NULL DEFAULT true,
  UNIQUE (empresa_id,id), UNIQUE (empresa_id,usuario_id),
  FOREIGN KEY (empresa_id,usuario_id) REFERENCES usuarios(empresa_id,id),
  FOREIGN KEY (empresa_id,veiculo_id) REFERENCES veiculos(empresa_id,id)
);

CREATE TABLE clientes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES empresas(id),
  nome text NOT NULL CHECK (length(trim(nome)) > 0),
  cnpj text NOT NULL,
  endereco text NOT NULL,
  numero text,
  complemento text,
  bairro text,
  cidade text NOT NULL,
  estado text NOT NULL CHECK (estado ~ '^[A-Z]{2}$'),
  cep text CHECK (cep ~ '^[0-9]{8}$'),
  telefone text,
  email text,
  contrato_status text NOT NULL DEFAULT 'nao_informado'
    CHECK (contrato_status IN ('nao_informado','sem_contrato','com_contrato')),
  numero_contrato text,
  localizacao geography(Point,4326),
  localizacao_confirmada boolean NOT NULL DEFAULT false,
  ativo boolean NOT NULL DEFAULT true,
  criado_em timestamptz NOT NULL DEFAULT now(),
  CHECK ((contrato_status = 'com_contrato' AND nullif(trim(numero_contrato),'') IS NOT NULL)
      OR (contrato_status <> 'com_contrato' AND numero_contrato IS NULL)),
  UNIQUE (empresa_id,id), UNIQUE (empresa_id,cnpj)
);
CREATE INDEX clientes_localizacao ON clientes USING gist(localizacao);

CREATE TABLE modalidades (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES empresas(id),
  nome text NOT NULL,
  ativa boolean NOT NULL DEFAULT true,
  UNIQUE (empresa_id,id), UNIQUE (empresa_id,nome)
);

CREATE TABLE rotas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES empresas(id),
  motorista_id uuid NOT NULL,
  nome text NOT NULL,
  dias_semana smallint[] NOT NULL CHECK (
    cardinality(dias_semana) > 0 AND dias_semana <@ ARRAY[1,2,3,4,5,6,7]::smallint[]
    AND array_position(dias_semana,NULL) IS NULL),
  ativa boolean NOT NULL DEFAULT true,
  UNIQUE (empresa_id,id),
  FOREIGN KEY (empresa_id,motorista_id) REFERENCES motoristas(empresa_id,id)
);
CREATE TABLE rota_paradas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES empresas(id),
  rota_id uuid NOT NULL,
  cliente_id uuid NOT NULL,
  ordem integer NOT NULL CHECK (ordem > 0),
  UNIQUE (empresa_id,id),
  UNIQUE (empresa_id,rota_id,ordem) DEFERRABLE INITIALLY IMMEDIATE,
  FOREIGN KEY (empresa_id,rota_id) REFERENCES rotas(empresa_id,id),
  FOREIGN KEY (empresa_id,cliente_id) REFERENCES clientes(empresa_id,id)
);

CREATE TABLE coletas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES empresas(id),
  cliente_id uuid NOT NULL,
  motorista_id uuid NOT NULL,
  id_local_dispositivo uuid NOT NULL,
  agendada_para timestamptz,
  concluida_em timestamptz,
  criado_em timestamptz NOT NULL DEFAULT now(),
  status text NOT NULL DEFAULT 'agendada' CHECK (status IN ('agendada','concluida','cancelada','nao_atendida')),
  origem text NOT NULL CHECK (origem IN ('rota_fixa','chamado_imprevisto')),
  assinatura_chave text,
  nome_signatario text,
  observacoes text,
  CHECK (status <> 'concluida' OR concluida_em IS NOT NULL),
  UNIQUE (empresa_id,id), UNIQUE (empresa_id,id_local_dispositivo),
  FOREIGN KEY (empresa_id,cliente_id) REFERENCES clientes(empresa_id,id),
  FOREIGN KEY (empresa_id,motorista_id) REFERENCES motoristas(empresa_id,id)
);
CREATE INDEX coletas_cliente_data ON coletas(empresa_id,cliente_id,concluida_em DESC);
CREATE TABLE coleta_itens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES empresas(id),
  coleta_id uuid NOT NULL,
  modalidade_id uuid NOT NULL,
  quantidade integer CHECK (quantidade >= 0),
  quantidade_status text NOT NULL DEFAULT 'a_conferir' CHECK (quantidade_status IN ('a_conferir','confirmada')),
  CHECK (quantidade_status <> 'confirmada' OR quantidade IS NOT NULL),
  UNIQUE (empresa_id,id), UNIQUE (empresa_id,coleta_id,modalidade_id),
  FOREIGN KEY (empresa_id,coleta_id) REFERENCES coletas(empresa_id,id),
  FOREIGN KEY (empresa_id,modalidade_id) REFERENCES modalidades(empresa_id,id)
);

CREATE TABLE auditoria_quantidades (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  empresa_id uuid NOT NULL REFERENCES empresas(id),
  item_id uuid NOT NULL,
  usuario_id uuid NOT NULL,
  quantidade_anterior integer,
  quantidade_nova integer NOT NULL CHECK (quantidade_nova >= 0),
  motivo text NOT NULL,
  criado_em timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (empresa_id,item_id) REFERENCES coleta_itens(empresa_id,id),
  FOREIGN KEY (empresa_id,usuario_id) REFERENCES usuarios(empresa_id,id)
);

CREATE TABLE posicoes_motorista (
  empresa_id uuid NOT NULL REFERENCES empresas(id),
  motorista_id uuid NOT NULL,
  localizacao geography(Point,4326) NOT NULL,
  capturada_em timestamptz NOT NULL,
  recebida_em timestamptz NOT NULL DEFAULT now(),
  precisao_metros numeric CHECK (precisao_metros >= 0),
  PRIMARY KEY (empresa_id,motorista_id),
  FOREIGN KEY (empresa_id,motorista_id) REFERENCES motoristas(empresa_id,id)
);

-- Sem contexto de empresa, o papel de aplicação não enxerga linhas.
ALTER TABLE empresas ENABLE ROW LEVEL SECURITY;
ALTER TABLE empresas FORCE ROW LEVEL SECURITY;
CREATE POLICY isolamento ON empresas USING (id = app.empresa_atual()) WITH CHECK (id = app.empresa_atual());
DO $$
DECLARE tabela text;
BEGIN
  FOREACH tabela IN ARRAY ARRAY['usuarios','veiculos','motoristas','clientes','modalidades','rotas','rota_paradas','coletas','coleta_itens','auditoria_quantidades','posicoes_motorista'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tabela);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', tabela);
    EXECUTE format('CREATE POLICY isolamento ON %I USING (empresa_id = app.empresa_atual()) WITH CHECK (empresa_id = app.empresa_atual())', tabela);
    EXECUTE format('CREATE INDEX ON %I (empresa_id)', tabela);
  END LOOP;
END $$;
GRANT USAGE ON SCHEMA public,app TO coleta_app;
GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA public TO coleta_app;
REVOKE INSERT,UPDATE ON empresas FROM coleta_app;
REVOKE UPDATE ON auditoria_quantidades FROM coleta_app;
COMMIT;
