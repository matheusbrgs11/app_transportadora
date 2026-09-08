BEGIN;
ALTER TABLE coletas ADD COLUMN versao integer NOT NULL DEFAULT 1;
ALTER TABLE coletas ADD COLUMN criado_por uuid;
ALTER TABLE coletas ADD CONSTRAINT coletas_autor FOREIGN KEY (empresa_id,criado_por) REFERENCES usuarios(empresa_id,id);
ALTER TABLE coletas ADD COLUMN dados_registro jsonb;
ALTER TABLE coletas ADD COLUMN requisicao_hash text;
ALTER TABLE coleta_itens ADD COLUMN modalidade_nome text;
UPDATE coleta_itens i SET modalidade_nome=m.nome FROM modalidades m
 WHERE m.id=i.modalidade_id AND m.empresa_id=i.empresa_id;
ALTER TABLE auditoria_quantidades ADD COLUMN status_anterior text;
ALTER TABLE auditoria_quantidades ADD COLUMN status_novo text;
ALTER TABLE auditoria_quantidades ADD COLUMN usuario_nome text;

CREATE TABLE coleta_eventos (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 empresa_id uuid NOT NULL REFERENCES empresas(id),
 coleta_id uuid NOT NULL,
 usuario_id uuid NOT NULL,
 usuario_nome text NOT NULL,
 status_anterior text,
 status_novo text NOT NULL,
 motivo text,
 dados jsonb NOT NULL DEFAULT '{}',
 criado_em timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY (empresa_id,coleta_id) REFERENCES coletas(empresa_id,id),
 FOREIGN KEY (empresa_id,usuario_id) REFERENCES usuarios(empresa_id,id)
);
ALTER TABLE coleta_eventos ENABLE ROW LEVEL SECURITY;
ALTER TABLE coleta_eventos FORCE ROW LEVEL SECURITY;
CREATE POLICY isolamento ON coleta_eventos USING (empresa_id=app.empresa_atual()) WITH CHECK (empresa_id=app.empresa_atual());
CREATE INDEX ON coleta_eventos(empresa_id,coleta_id,criado_em);
CREATE INDEX ON coletas(empresa_id,(coalesce(concluida_em,agendada_para,criado_em)),id);
GRANT SELECT,INSERT ON coleta_eventos TO coleta_app;
COMMIT;
