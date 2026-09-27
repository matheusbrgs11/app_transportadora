BEGIN;
ALTER TABLE usuarios DROP CONSTRAINT usuarios_perfil_check;
ALTER TABLE usuarios ADD CONSTRAINT usuarios_perfil_check CHECK (perfil IN ('admin','operador','motorista','agendamento'));
COMMIT;
