BEGIN;
ALTER TABLE clientes ADD COLUMN localizacao_versao integer NOT NULL DEFAULT 1;
ALTER TABLE clientes ADD COLUMN localizacao_fonte text;
CREATE TABLE localizacao_eventos (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), empresa_id uuid NOT NULL REFERENCES empresas(id), cliente_id uuid NOT NULL,
 usuario_id uuid NOT NULL, motivo text NOT NULL, anterior jsonb NOT NULL, nova jsonb NOT NULL,
 criado_em timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(empresa_id,cliente_id) REFERENCES clientes(empresa_id,id),
 FOREIGN KEY(empresa_id,usuario_id) REFERENCES usuarios(empresa_id,id)
);
ALTER TABLE localizacao_eventos ENABLE ROW LEVEL SECURITY;
ALTER TABLE localizacao_eventos FORCE ROW LEVEL SECURITY;
CREATE POLICY isolamento ON localizacao_eventos USING(empresa_id=app.empresa_atual()) WITH CHECK(empresa_id=app.empresa_atual());
GRANT SELECT,INSERT ON localizacao_eventos TO coleta_app;
COMMIT;
