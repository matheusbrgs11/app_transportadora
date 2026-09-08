BEGIN;
CREATE TABLE sessoes (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 empresa_id uuid NOT NULL REFERENCES empresas(id),
 usuario_id uuid NOT NULL,
 expira_em timestamptz NOT NULL,
 revogada boolean NOT NULL DEFAULT false,
 FOREIGN KEY (empresa_id,usuario_id) REFERENCES usuarios(empresa_id,id)
);
CREATE INDEX ON sessoes(empresa_id,usuario_id);
CREATE TABLE importacoes (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 empresa_id uuid NOT NULL REFERENCES empresas(id),
 usuario_id uuid NOT NULL,
 arquivo text NOT NULL,
 linhas jsonb NOT NULL,
 criado_em timestamptz NOT NULL DEFAULT now(),
 expira_em timestamptz NOT NULL DEFAULT now() + interval '1 hour',
 confirmada_em timestamptz,
 quantidade_importada integer,
 FOREIGN KEY (empresa_id,usuario_id) REFERENCES usuarios(empresa_id,id)
);
CREATE INDEX ON importacoes(empresa_id);
ALTER TABLE sessoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessoes FORCE ROW LEVEL SECURITY;
ALTER TABLE importacoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE importacoes FORCE ROW LEVEL SECURITY;
CREATE POLICY isolamento ON sessoes USING (empresa_id=app.empresa_atual()) WITH CHECK (empresa_id=app.empresa_atual());
CREATE POLICY isolamento ON importacoes USING (empresa_id=app.empresa_atual()) WITH CHECK (empresa_id=app.empresa_atual());
GRANT SELECT,INSERT,UPDATE ON sessoes,importacoes TO coleta_app;
COMMIT;
