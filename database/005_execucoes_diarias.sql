BEGIN;
CREATE TABLE execucoes_rotas (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 empresa_id uuid NOT NULL REFERENCES empresas(id),
 rota_id uuid NOT NULL,
 motorista_id uuid NOT NULL,
 data date NOT NULL,
 fuso_horario text NOT NULL,
 planejamento jsonb NOT NULL,
 criado_em timestamptz NOT NULL DEFAULT now(),
 UNIQUE(empresa_id,id), UNIQUE(empresa_id,rota_id,data),
 FOREIGN KEY(empresa_id,rota_id) REFERENCES rotas(empresa_id,id),
 FOREIGN KEY(empresa_id,motorista_id) REFERENCES motoristas(empresa_id,id)
);
ALTER TABLE execucoes_rotas ENABLE ROW LEVEL SECURITY;
ALTER TABLE execucoes_rotas FORCE ROW LEVEL SECURITY;
CREATE POLICY isolamento ON execucoes_rotas USING (empresa_id=app.empresa_atual()) WITH CHECK (empresa_id=app.empresa_atual());
GRANT SELECT,INSERT ON execucoes_rotas TO coleta_app;
ALTER TABLE coletas ADD COLUMN execucao_id uuid;
ALTER TABLE coletas ADD CONSTRAINT coleta_execucao FOREIGN KEY(empresa_id,execucao_id) REFERENCES execucoes_rotas(empresa_id,id);
CREATE UNIQUE INDEX coleta_parada_diaria ON coletas(empresa_id,execucao_id,cliente_id) WHERE execucao_id IS NOT NULL;
CREATE TABLE envios_motorista (
 empresa_id uuid NOT NULL REFERENCES empresas(id),
 id_local uuid NOT NULL,
 usuario_id uuid NOT NULL,
 coleta_id uuid NOT NULL,
 requisicao_hash text NOT NULL,
 PRIMARY KEY(empresa_id,id_local),
 FOREIGN KEY(empresa_id,usuario_id) REFERENCES usuarios(empresa_id,id),
 FOREIGN KEY(empresa_id,coleta_id) REFERENCES coletas(empresa_id,id)
);
ALTER TABLE envios_motorista ENABLE ROW LEVEL SECURITY;
ALTER TABLE envios_motorista FORCE ROW LEVEL SECURITY;
CREATE POLICY isolamento ON envios_motorista USING (empresa_id=app.empresa_atual()) WITH CHECK (empresa_id=app.empresa_atual());
GRANT SELECT,INSERT ON envios_motorista TO coleta_app;
COMMIT;
