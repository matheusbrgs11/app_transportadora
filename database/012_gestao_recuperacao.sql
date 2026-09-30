BEGIN;
GRANT UPDATE ON empresas TO coleta_app;
CREATE TABLE codigos_recuperacao (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 empresa_id uuid NOT NULL REFERENCES empresas(id),
 usuario_id uuid NOT NULL,
 codigo_hash text NOT NULL,
 criado_em timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY (empresa_id,usuario_id) REFERENCES usuarios(empresa_id,id),
 UNIQUE (empresa_id,codigo_hash)
);
CREATE INDEX ON codigos_recuperacao (empresa_id,usuario_id);
ALTER TABLE codigos_recuperacao ENABLE ROW LEVEL SECURITY;
ALTER TABLE codigos_recuperacao FORCE ROW LEVEL SECURITY;
CREATE POLICY isolamento ON codigos_recuperacao USING (empresa_id=app.empresa_atual()) WITH CHECK (empresa_id=app.empresa_atual());
GRANT SELECT,INSERT,DELETE ON codigos_recuperacao TO coleta_app;
COMMIT;
