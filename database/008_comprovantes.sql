BEGIN;
CREATE TABLE comprovantes (
 empresa_id uuid NOT NULL REFERENCES empresas(id), coleta_id uuid NOT NULL, usuario_id uuid NOT NULL,
 metadados jsonb NOT NULL, registro jsonb NOT NULL, imagem bytea CHECK(octet_length(imagem)<=131072),
 sha256 text NOT NULL, criado_em timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(empresa_id,coleta_id),
 FOREIGN KEY(empresa_id,coleta_id) REFERENCES coletas(empresa_id,id),
 FOREIGN KEY(empresa_id,usuario_id) REFERENCES usuarios(empresa_id,id)
);
ALTER TABLE comprovantes ENABLE ROW LEVEL SECURITY;
ALTER TABLE comprovantes FORCE ROW LEVEL SECURITY;
CREATE POLICY isolamento ON comprovantes USING(empresa_id=app.empresa_atual()) WITH CHECK(empresa_id=app.empresa_atual());
GRANT SELECT,INSERT ON comprovantes TO coleta_app;
COMMIT;
