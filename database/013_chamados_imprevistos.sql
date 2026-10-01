BEGIN;
CREATE TABLE chamados_imprevistos (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 empresa_id uuid NOT NULL REFERENCES empresas(id),
 coleta_id uuid NOT NULL,
 motorista_id uuid NOT NULL,
 estado text NOT NULL DEFAULT 'enviado' CHECK (estado IN ('enviado','aceito','recusado','expirado','concluido','nao_atendido','cancelado')),
 prioridade text NOT NULL CHECK (prioridade IN ('normal','urgente')),
 prazo timestamptz NOT NULL,
 requisicao_hash text NOT NULL,
 versao integer NOT NULL DEFAULT 1,
 criado_em timestamptz NOT NULL DEFAULT now(),
 respondido_em timestamptz,
 atualizado_em timestamptz NOT NULL DEFAULT now(),
 UNIQUE(empresa_id,id), UNIQUE(empresa_id,coleta_id),
 FOREIGN KEY(empresa_id,coleta_id) REFERENCES coletas(empresa_id,id),
 FOREIGN KEY(empresa_id,motorista_id) REFERENCES motoristas(empresa_id,id)
);
CREATE INDEX chamados_motorista_estado ON chamados_imprevistos(empresa_id,motorista_id,estado,prazo);
ALTER TABLE chamados_imprevistos ENABLE ROW LEVEL SECURITY;
ALTER TABLE chamados_imprevistos FORCE ROW LEVEL SECURITY;
CREATE POLICY isolamento ON chamados_imprevistos USING (empresa_id=app.empresa_atual()) WITH CHECK (empresa_id=app.empresa_atual());
GRANT SELECT,INSERT,UPDATE ON chamados_imprevistos TO coleta_app;
GRANT DELETE ON sessoes,importacoes TO coleta_app;
COMMIT;
