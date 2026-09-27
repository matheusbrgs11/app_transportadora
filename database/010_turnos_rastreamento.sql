BEGIN;
CREATE TABLE turnos_motorista (
 id uuid NOT NULL, empresa_id uuid NOT NULL REFERENCES empresas(id), motorista_id uuid NOT NULL,
 iniciado_em timestamptz NOT NULL DEFAULT now(), expira_em timestamptz NOT NULL DEFAULT now()+interval '12 hours',
 encerrado_em timestamptz, PRIMARY KEY(empresa_id,id),
 FOREIGN KEY(empresa_id,motorista_id) REFERENCES motoristas(empresa_id,id)
);
CREATE UNIQUE INDEX turno_ativo ON turnos_motorista(empresa_id,motorista_id) WHERE encerrado_em IS NULL;
ALTER TABLE turnos_motorista ENABLE ROW LEVEL SECURITY;
ALTER TABLE turnos_motorista FORCE ROW LEVEL SECURITY;
CREATE POLICY isolamento ON turnos_motorista USING(empresa_id=app.empresa_atual()) WITH CHECK(empresa_id=app.empresa_atual());
GRANT SELECT,INSERT,UPDATE ON turnos_motorista TO coleta_app;
ALTER TABLE posicoes_motorista ADD COLUMN turno_id uuid;
ALTER TABLE posicoes_motorista ADD CONSTRAINT posicao_turno FOREIGN KEY(empresa_id,turno_id) REFERENCES turnos_motorista(empresa_id,id);
GRANT DELETE ON posicoes_motorista TO coleta_app;
COMMIT;
