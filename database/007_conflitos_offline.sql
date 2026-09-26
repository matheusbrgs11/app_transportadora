BEGIN;
CREATE TABLE conflitos_motorista (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), empresa_id uuid NOT NULL REFERENCES empresas(id),
 usuario_id uuid NOT NULL, id_local uuid NOT NULL, payload jsonb NOT NULL, requisicao_hash text NOT NULL,
 status text NOT NULL DEFAULT 'aberto' CHECK(status IN ('aberto','resolvido')),
 resolucao text, coleta_id uuid, resolvido_por uuid, criado_em timestamptz NOT NULL DEFAULT now(), resolvido_em timestamptz,
 UNIQUE(empresa_id,usuario_id,id_local),
 FOREIGN KEY(empresa_id,usuario_id) REFERENCES usuarios(empresa_id,id),
 FOREIGN KEY(empresa_id,coleta_id) REFERENCES coletas(empresa_id,id),
 FOREIGN KEY(empresa_id,resolvido_por) REFERENCES usuarios(empresa_id,id)
);
CREATE INDEX conflitos_fila ON conflitos_motorista(empresa_id,status,criado_em,id);
ALTER TABLE conflitos_motorista ENABLE ROW LEVEL SECURITY;
ALTER TABLE conflitos_motorista FORCE ROW LEVEL SECURITY;
CREATE POLICY isolamento ON conflitos_motorista USING(empresa_id=app.empresa_atual()) WITH CHECK(empresa_id=app.empresa_atual());
GRANT SELECT,INSERT ON conflitos_motorista TO coleta_app;
GRANT UPDATE(status,resolucao,coleta_id,resolvido_por,resolvido_em) ON conflitos_motorista TO coleta_app;
COMMIT;
