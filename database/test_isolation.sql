-- Executar como administrador em banco de desenvolvimento; dados revertidos.
\set ON_ERROR_STOP on
BEGIN;
INSERT INTO empresas(id,nome) VALUES
 ('11111111-1111-4111-8111-111111111111','Teste A'),
 ('22222222-2222-4222-8222-222222222222','Teste B');
INSERT INTO clientes(id,empresa_id,nome,cnpj,endereco,cidade,estado) VALUES
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','11111111-1111-4111-8111-111111111111','Cliente A','fixture','Rua A','Goiania','GO'),
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','22222222-2222-4222-8222-222222222222','Cliente B','fixture','Rua B','Goiania','GO');
SET LOCAL ROLE coleta_app;
SELECT set_config('app.empresa_id','',true);
DO $$ BEGIN
 IF EXISTS (SELECT FROM clientes) THEN RAISE EXCEPTION 'Sem contexto deve negar leitura'; END IF;
END $$;
SELECT set_config('app.empresa_id','11111111-1111-4111-8111-111111111111',true);
DO $$
DECLARE alteradas integer;
BEGIN
 IF (SELECT count(*) FROM clientes) <> 1 THEN RAISE EXCEPTION 'Empresa A deve ver um cliente'; END IF;
 IF EXISTS (SELECT FROM clientes WHERE empresa_id <> app.empresa_atual()) THEN RAISE EXCEPTION 'Vazamento entre empresas'; END IF;
 UPDATE clientes SET nome='Alterado' WHERE id='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
 GET DIAGNOSTICS alteradas = ROW_COUNT;
 IF alteradas <> 0 THEN RAISE EXCEPTION 'Alteracao cruzada permitida'; END IF;
 BEGIN
  INSERT INTO clientes(empresa_id,nome,cnpj,endereco,cidade,estado)
  VALUES ('22222222-2222-4222-8222-222222222222','Intruso','outro','Rua','Goiania','GO');
  RAISE EXCEPTION 'Insercao cruzada permitida';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  INSERT INTO coleta_itens(empresa_id,coleta_id,modalidade_id,quantidade,quantidade_status)
  VALUES ('11111111-1111-4111-8111-111111111111',gen_random_uuid(),gen_random_uuid(),NULL,'confirmada');
  RAISE EXCEPTION 'Quantidade confirmada vazia permitida';
 EXCEPTION WHEN check_violation THEN NULL;
 END;
END $$;
SELECT set_config('app.empresa_id','22222222-2222-4222-8222-222222222222',true);
DO $$ BEGIN
 IF (SELECT nome FROM clientes WHERE id='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb') IS DISTINCT FROM 'Cliente B' THEN
  RAISE EXCEPTION 'Cliente B alterado ou inacessivel';
 END IF;
END $$;
ROLLBACK;
\echo 'Testes de leitura, escrita e quantidade passaram; fixtures revertidas.'
