BEGIN;
CREATE TABLE rota_excecoes (
 empresa_id uuid NOT NULL REFERENCES empresas(id), rota_id uuid NOT NULL, data date NOT NULL,
 operar boolean NOT NULL, motivo text NOT NULL, usuario_id uuid NOT NULL,
 PRIMARY KEY(empresa_id,rota_id,data),
 FOREIGN KEY(empresa_id,rota_id) REFERENCES rotas(empresa_id,id),
 FOREIGN KEY(empresa_id,usuario_id) REFERENCES usuarios(empresa_id,id)
);
ALTER TABLE rota_excecoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE rota_excecoes FORCE ROW LEVEL SECURITY;
CREATE POLICY isolamento ON rota_excecoes USING(empresa_id=app.empresa_atual()) WITH CHECK(empresa_id=app.empresa_atual());
GRANT SELECT,INSERT,UPDATE ON rota_excecoes TO coleta_app;
ALTER TABLE coletas ADD COLUMN tentativa integer NOT NULL DEFAULT 1 CHECK(tentativa>0);
ALTER TABLE coletas ADD COLUMN revisita_de uuid;
ALTER TABLE coletas ADD CONSTRAINT revisita_empresa FOREIGN KEY(empresa_id,revisita_de) REFERENCES coletas(empresa_id,id);
DROP INDEX coleta_parada_diaria;
CREATE UNIQUE INDEX coleta_parada_diaria ON coletas(empresa_id,execucao_id,cliente_id,tentativa) WHERE execucao_id IS NOT NULL;
CREATE UNIQUE INDEX revisita_unica ON coletas(empresa_id,revisita_de) WHERE revisita_de IS NOT NULL;
ALTER TABLE envios_motorista ADD COLUMN status text NOT NULL DEFAULT 'concluida' CHECK(status IN ('concluida','nao_atendida'));
CREATE TABLE rota_excecao_eventos (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), empresa_id uuid NOT NULL REFERENCES empresas(id),
 rota_id uuid NOT NULL, data date NOT NULL, operar boolean NOT NULL, motivo text NOT NULL,
 usuario_id uuid NOT NULL, criado_em timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(empresa_id,rota_id) REFERENCES rotas(empresa_id,id),
 FOREIGN KEY(empresa_id,usuario_id) REFERENCES usuarios(empresa_id,id)
);
ALTER TABLE rota_excecao_eventos ENABLE ROW LEVEL SECURITY;
ALTER TABLE rota_excecao_eventos FORCE ROW LEVEL SECURITY;
CREATE POLICY isolamento ON rota_excecao_eventos USING(empresa_id=app.empresa_atual()) WITH CHECK(empresa_id=app.empresa_atual());
GRANT SELECT,INSERT ON rota_excecao_eventos TO coleta_app;
COMMIT;
