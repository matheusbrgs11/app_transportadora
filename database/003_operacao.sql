BEGIN;
ALTER TABLE rotas ADD COLUMN versao integer NOT NULL DEFAULT 1;
ALTER TABLE rota_paradas ADD COLUMN janela_inicio time;
ALTER TABLE rota_paradas ADD COLUMN janela_fim time;
ALTER TABLE rota_paradas ADD CONSTRAINT janela_valida CHECK (
 (janela_inicio IS NULL AND janela_fim IS NULL) OR
 (janela_inicio IS NOT NULL AND janela_fim IS NOT NULL AND janela_inicio < janela_fim));
CREATE UNIQUE INDEX motorista_veiculo_ativo ON motoristas(empresa_id,veiculo_id)
 WHERE ativo AND veiculo_id IS NOT NULL;
GRANT DELETE ON rota_paradas TO coleta_app;
COMMIT;
