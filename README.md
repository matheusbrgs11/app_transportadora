# Coleta

Painel React e backend FastAPI/PostgreSQL para clientes, motoristas, rotas, coletas e histórico de várias transportadoras. Desenvolvimento local, sem Docker. Primeira implementação Android em `android/`, APK debug compilado, homologação em aparelho pendente; geocodificação pendente.

## Executar sem Docker

Na pasta do projeto:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
npm --prefix frontend ci
.venv/bin/python scripts/start.py
```

Abra **http://127.0.0.1:5173/** para usar o painel. Não abra `frontend/index.html` diretamente. O comando mantém o painel e a API funcionando enquanto o terminal estiver aberto. Não execute uma segunda instância nas mesmas portas.

O ambiente prepara um **banco de desenvolvimento separado** em `.local/postgres`, aplica migrações e cria uma empresa de desenvolvimento com administrador e senha aleatória. Não exige sudo e não altera o banco `coleta` do serviço PostgreSQL. Para executar somente a API, use `.venv/bin/python scripts/dev.py`.

Requisitos: Python 3.12+, PostgreSQL 17/PostGIS e Node.js 20.19+ ou 22.12+. Configure `PG_BIN` se necessário. O banco usa socket privado em `.local/socket`; painel e API escutam somente em `127.0.0.1`. Ctrl+C encerra os serviços iniciados pelo comando, preservando dados.

Credenciais: `.local/access.json`, com permissão restrita e ignorado pelo Git. No painel, informe `empresa_id` em **Código da empresa**, `usuario_login` em **Usuário** e `senha` em **Senha**. A sessão fica somente em memória; recarregar a página exige novo login.

Para desenvolvimento, a documentação interativa está em http://127.0.0.1:8000/docs. No Swagger:

1. Execute `POST /auth/login` com os três campos do arquivo.
2. Copie `access_token` em **Authorize** (somente o token).
3. Use clientes e importações. `POST /auth/logout` invalida a sessão.

O painel acessa a API pelo proxy `/api` do Vite, sem expor credenciais administrativas do banco.

## Implementado

- Login por empresa, senhas Argon2, token de uma hora e logout com revogação.
- Verificação de usuário e empresa ativos em cada chamada autenticada.
- Administradores criam usuários/importam clientes; administradores e operadores gerenciam clientes; motoristas não acessam essa gestão.
- Cadastro, edição, desativação, busca e paginação de clientes. Validação de CNPJ numérico/alfanumérico, UF, CEP e contrato.
- Prévia ODS/XLSX com erros por linha e duplicidades. Confirmação atômica de linhas válidas; repetir a confirmação não duplica clientes.
- Migrações com checksum, RLS e vínculos restritos à empresa. Atualizar endereço invalida localização confirmada.
- Painel com estados de carregamento/erro/vazio, busca e edição de clientes e prévia selecionável de importação.
- Cadastro/edição de motoristas e veículos, senha individual e bloqueio de veículo associado a outro motorista ativo.
- Montagem/edição de rotas com dias da semana, paradas ordenadas por arraste ou setas e janelas de atendimento opcionais.
- Proteção contra edição simultânea de rota. Cliente/motorista em rota ativa não pode ser desativado até remover/transferir/desativar a rota. A desativação preserva os cadastros.
- Registro de coleta agendada ou já realizada, com várias modalidades, quantidades confirmadas ou a conferir. Conclusão, cancelamento e não atendimento preservam eventos com responsável e data.
- Histórico por cliente, período, motorista, modalidade, origem, situação e conferência, com paginação e resumo por modalidade. Clientes inativos continuam consultáveis.
- Conferência de quantidade restrita ao administrador, com motivo obrigatório, valores anterior/novo, responsável e data. Atualizações concorrentes são rejeitadas por versão.

## Coletas e histórico

No painel, abra **Coletas** ou o botão **Histórico** na linha de um cliente. Use **Nova coleta** para agendar ou registrar uma visita já realizada. O horário de entrada é o do dispositivo; os filtros e a exibição usam o fuso da transportadora, indicado na tela.

Uma coleta pode ter PAC, SEDEX e outras modalidades no mesmo registro. Valores estimados e campos vazios ficam `a_conferir`; só os itens `confirmada` de coletas concluídas entram nos volumes confirmados. O resumo considera todos os resultados filtrados, não só a página atual. Uma visita multimodal conta em cada modalidade, sem duplicar o total de visitas.

Os registros novos guardam cópias de nome/CNPJ/endereço do cliente e nome do motorista, além dos nomes das modalidades. Alterações posteriores nos cadastros não reescrevem esses dados históricos. Registros legados sem cópia histórica usam os nomes atuais como fallback.

Endpoints:

- `GET /modalidades`: opções da empresa, inclusive inativas para consulta do passado.
- `POST /coletas`: exige identificador UUID em `id_local_dispositivo`, cliente/motorista ativos e lista `itens`. `agendada` exige `agendada_para`; `concluida` exige `concluida_em`. Datas precisam conter fuso. Realização futura além de cinco minutos de tolerância é rejeitada.
- `GET /coletas`: filtros `cliente_id`, `motorista_id`, `modalidade_id`, `data_inicio`, `data_fim`, `status`, `origem`, `quantidade_status`, `limit`, `offset`. Data final inclui o dia inteiro no fuso da empresa. A referência é realização para concluídas, agendamento para demais; criação é fallback legado.
- `GET /coletas/{id}`: itens, dados preservados, eventos e conferências.
- `PUT /coletas/{id}/status`: exige `versao`. Somente agendadas mudam para concluída/cancelada/não atendida. Conclusão exige realização e todos os itens; cancelamento/não atendimento exige motivo. Registros terminais não reabrem nesta versão.
- `PUT /coletas/{id}/itens/{item_id}/quantidade`: administrador informa versão, quantidade e motivo. Apenas coletas concluídas; confirma quantidade e grava auditoria na mesma transação.

Repetir o mesmo UUID e conteúdo em `POST /coletas` retorna a coleta existente (200), inclusive sob chamadas concorrentes. Conteúdo diferente com o mesmo UUID retorna 409. A primeira criação retorna 201. O painel mantém o UUID durante tentativas do formulário. Isso protege reenvios, mas não implementa uma fila offline Android. Mudanças de situação/conferência usam versão para impedir sobrescrita; após conflito, use **Atualizar detalhes**.

A origem `rota_fixa` é informada manualmente; ainda não há geração automática diária de coletas a partir das rotas. Não há captura de assinatura, exportação CSV/PDF ou reabertura de registros terminais nesta entrega. Operadores/administradores registram e consultam; motoristas terão seus endpoints próprios com o aplicativo Android.

## Consulta do motorista

`GET /motorista/rota-do-dia` usa a sessão normal de `/auth/login`, exige perfil motorista e cadastro de motorista ativo. Não recebe ID de motorista: a identidade vem do usuário autenticado. Administradores e operadores continuam usando os endpoints administrativos.

Retorna `data`, `fuso_horario`, dados básicos do próprio motorista/veículo, `rotas` com nome/versão/paradas ordenadas e `total_paradas`. As paradas incluem endereço, telefone e janela de atendimento. Somente rotas ativas atribuídas ao motorista e clientes ativos são retornados. Contrato, CNPJ e histórico de outros clientes não são enviados.

Sem parâmetro, o dia é calculado no fuso da transportadora. `?data=2026-09-07` permite consultar o planejamento recorrente para um dia específico. Essa consulta usa o cadastro **atual** das rotas; não representa o histórico de como uma rota estava organizada no passado. Dias sem rota retornam uma lista vazia. A consulta não gera coletas, não registra visitas e não implementa sincronização offline.

A primeira tela nativa e a fila local estão em [android/README.md](android/README.md), com APK debug compilado e teste em aparelho pendente. `GET /motorista/modalidades` fornece modalidades ativas. `POST /motorista/coletas` registra visitas concluídas da própria rota: exige UUID local, rota/versão, cliente, data com fuso, itens e observações opcionais. Confere atribuição, dia da semana e pertencimento do cliente; mudanças na rota geram conflito. A rota/versão fica preservada no evento de criação. Reenvio idêntico retorna 200; alteração de conteúdo com o mesmo UUID retorna 409. O endpoint não conclui agendamentos existentes: cria um registro de visita separado, sem gerar automaticamente coletas da rota. Testes verificam ordem/janelas, domingo, fuso na virada do dia, rotas inativas, ausência de gravações e isolamento entre motoristas/empresas.

## Importação

`POST /clientes/importacoes/previa`: upload multipart no campo `arquivo`. Retorna ID, erros por linha e prazo de uma hora. Ainda não cadastra clientes.

`POST /clientes/importacoes/{id}/confirmar`: JSON `{"linhas": [2, 3]}`. Usa somente os dados da prévia salva, da mesma empresa e administrador. Cada prévia aceita uma confirmação; para outras linhas, envie novo arquivo. Cadastro simultâneo com o mesmo CNPJ causa conflito e desfaz toda a confirmação.

Mapeamento: NOME, ENDERECO, NUMERO, COMPL, BAIRRO, CIDADE, ESTADO, CEP, TELEFONE, CGC. CGC equivale a CNPJ; colunas vazias são ignoradas. Também aceita CNPJ, COMPLEMENTO, UF, EMAIL/E-MAIL, NUMERO_CONTRATO e CONTRATO_STATUS.

- Uma aba, até 5.000 clientes, 40 colunas, 5 MB de arquivo e 30 MB de conteúdo descompactado.
- Fórmulas não são executadas; campos mapeados com fórmulas são rejeitados.
- CNPJ/CEP numéricos são rejeitados para não inventar zeros perdidos; use texto na origem.
- Contrato ausente significa `nao_informado`. Número informado implica `com_contrato` se a situação não foi enviada.
- CNPJ existente não é sobrescrito; use a edição do cliente.
- Geocodificação e expansão automática de abreviações não implementadas.
- Amostra ODS validada em memória: duas linhas válidas. Clientes reais não cadastrados no ambiente de desenvolvimento.

## Testar

```bash
.venv/bin/python -m pytest -q --tb=short
```

Os testes iniciam PostgreSQL temporário privado em `/tmp`, aplicam migrações, verificam a API com duas empresas e removem o cluster ao final. Não usam o serviço PostgreSQL nem o banco de desenvolvimento.

Última execução: 34 testes aprovados, com duas advertências de depreciação das bibliotecas de testes. Cobertura: isolamento entre empresas, perfis, autenticação, importação/rollback, veículos/rotas, registro de coletas, reenvio concorrente, estados, auditoria, preservação de dados históricos e limites de período/filtros por modalidade.

```bash
npm --prefix frontend run build
```

O build verifica TypeScript e gera `frontend/dist`. A checagem local verificou respostas HTTP do painel e chamadas autenticadas pelo proxy. Em 08/09/2026, a importação ODS também foi validada pelo navegador na empresa de demonstração: seleção de arquivo, prévia com três linhas válidas e uma com CNPJ inválido bloqueada, confirmação e exibição dos três novos clientes na listagem. O histórico de maio e a correção auditada de quantidade foram conferidos no painel em uma verificação anterior. Isso não equivale a uma revisão visual completa nem a um teste em celular Android.

## Banco do serviço e provisionamento

O usuário informou ter aplicado a 001 e o teste de isolamento ao banco `coleta` com sucesso. Esse banco não foi alterado durante a implementação do backend.

Para usá-lo, configure credencial sem superusuário/BYPASSRLS, membro de `coleta_app`. Migrações/provisionamento usam uma credencial administrativa separada em `ADMIN_DATABASE_URL`; a API usa `DATABASE_URL` e `JWT_SECRET`.

```bash
PYTHONPATH=backend .venv/bin/python -m coleta_api.cli migrate
PYTHONPATH=backend .venv/bin/python -m coleta_api.cli provision --nome 'Minha transportadora' --login admin
PYTHONPATH=backend .venv/bin/uvicorn coleta_api.main:create_app --factory --host 127.0.0.1 --port 8000
```

Se a 001 foi aplicada manualmente, após conferir a estrutura original, use `migrate --baseline-foundation` uma vez. Essa opção verifica tabelas/RLS e registra a 001 como aplicada; não compara integralmente uma instalação alterada. Não edite migrações já aplicadas.

A API recusa superusuário/BYPASSRLS, assume `coleta_app` e define a empresa na transação. No login, o ID da empresa seleciona onde conferir credenciais. Depois, a empresa vem do token verificado, nunca do corpo do cadastro.

## Operação e próximas fases

Piloto: quatro motoristas, três carros e uma moto, com Android próprio, sem limite fixo no sistema. Cada empresa tem modalidades próprias. O rastreamento deverá estar vinculado ao turno, com indicação visível e encerramento ao terminar o trabalho.

Faltam assinaturas, Android offline e execução pelo motorista, geração de coletas da rota do dia, exportações, geocodificação, rastreamento e chamados. As tabelas desses módulos não equivalem aos fluxos implementados. Nenhuma posição de motorista ou rota no mapa é simulada no painel.

Antes de publicar: HTTPS, recuperação de senha, backups, monitoramento, retenção/limpeza de prévias e sessões, limite de upload no proxy e limite de login compartilhado entre instâncias. O limitador atual é em memória, por IP, para uma instância de desenvolvimento.

Referências: [FastAPI autenticação](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/), [Psycopg transações](https://www.psycopg.org/psycopg3/docs/basic/transactions.html), [Receita Federal: dígitos do CNPJ](https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/cnpj/manual-dv-cnpj.pdf).

## Prévia visual do motorista

Abra http://127.0.0.1:5173/previa-motorista.html com o painel em execução, ou abra `frontend/public/previa-motorista.html` diretamente no navegador. A página é independente da API, usa apenas dados fictícios e permite simular login, registro de modalidades e envio pendente. Não é o APK executando: os controles nativos podem variar no Android. Os dados da prévia são descartados ao recarregar.

Desenvolvimento pausado a pedido do usuário após esta prévia. Próxima etapa: homologação do APK em aparelho ou emulador.
