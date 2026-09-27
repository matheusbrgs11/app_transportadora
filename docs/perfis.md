# Perfis do painel

## Administrador

Mantém Rastreamento, Clientes, Motoristas, Rotas fixas e Coletas. Gerencia cadastro, alteração, importação, localização e desativação de clientes. O sistema preserva o histórico por desativação; esta alteração não introduz exclusão definitiva.

Na parte inferior do menu, **Criar acesso de agendamento** cadastra nome, usuário e senha de pelo menos 12 caracteres. O perfil é definido como agendamento pelo formulário, sem seletor de administrador. Só administradores podem criar usuários na API.

## Agendamento de coletas

Entra no mesmo painel com código da empresa e credenciais próprias. Abre inicialmente Coletas e vê apenas Rastreamento, Motoristas, Rotas fixas e Coletas.

Pode consultar a frota e sua última posição, organizar rotas e usar os fluxos operacionais de coletas. Consulta e seleciona clientes existentes nos formulários; não tem aba Clientes. Não pode criar, alterar, importar, desativar clientes ou alterar sua localização, nem gerenciar usuários ou cadastro de motoristas. Esses bloqueios são verificados pela API, independentemente do menu.

Pedidos recebidos por WhatsApp são inseridos manualmente pelo funcionário. Não foi implementada integração com WhatsApp. A integração completa de chamados imprevistos/aceite/notificação continua na etapa 7; organizar rota fixa não é o mesmo que despachar um chamado imediato ao motorista.

## Compatibilidade

O perfil antigo operador continua válido, mas também perde a gestão cadastral de clientes: conforme a regra solicitada, somente admin pode modificar esse cadastro. A consulta de clientes continua disponível à equipe para agendamento. Perfil motorista permanece exclusivo do Android.

Migração 011 amplia a restrição de perfil no banco sem alterar usuários existentes. Nenhuma pessoa recebe novo acesso automaticamente. O administrador deve criar suas contas de agendamento pelo painel.
