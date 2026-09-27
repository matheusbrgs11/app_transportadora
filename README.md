# Coleta

Plano de execução até a primeira versão comercial: [ROADMAP.md](ROADMAP.md). Consultar e atualizar esse checklist a cada retomada e entrega.

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

Rotas podem gerar atendimentos diários no botão **Preparar atendimentos de hoje** ou ao atualizar a rota no Android. A geração é solicitada pelo usuário/app, não por um agendador em segundo plano. Coletas avulsas cadastradas manualmente continuam separadas e não são vinculadas por aproximação de cliente/data. Não há captura de assinatura, exportação CSV/PDF ou reabertura de registros terminais nesta entrega. Operadores/administradores registram e consultam; motoristas usam os endpoints próprios descritos abaixo.

## Consulta do motorista

`GET /motorista/rota-do-dia` usa a sessão normal de `/auth/login`, exige perfil motorista e cadastro de motorista ativo. Não recebe ID de motorista: a identidade vem do usuário autenticado. Administradores e operadores continuam usando os endpoints administrativos.

Retorna `data`, `fuso_horario`, dados básicos do próprio motorista/veículo, `rotas` com nome/versão/paradas ordenadas e `total_paradas`. As paradas incluem endereço, telefone e janela de atendimento. Somente rotas ativas atribuídas ao motorista e clientes ativos são retornados. Contrato, CNPJ e histórico de outros clientes não são enviados.

Sem parâmetro, o dia é calculado no fuso da transportadora. `?data=2026-09-07` permite consultar o planejamento recorrente para um dia específico. Essa consulta usa o cadastro **atual** das rotas; não representa o histórico de como uma rota estava organizada no passado. Dias sem rota retornam uma lista vazia. A consulta não gera coletas, não registra visitas e não implementa sincronização offline.

A primeira tela nativa e a fila local estão em [android/README.md](android/README.md), com APK debug compilado e teste em aparelho pendente. `GET /motorista/modalidades` fornece modalidades ativas. `POST /motorista/coletas` registra visitas concluídas da própria rota: exige UUID local, rota/versão, cliente, data com fuso, itens e observações opcionais. Confere atribuição, dia da semana e pertencimento do cliente; mudanças na rota geram conflito. A rota/versão fica preservada no evento de criação. Reenvio idêntico retorna 200; alteração de conteúdo com o mesmo UUID retorna 409. O aplicativo atualizado envia `coleta_id` para concluir o agendamento gerado na execução diária. O formato legado sem esse campo só é aceito quando não há execução diária na rota/data; conflitos exigem conferência, sem descarte da fila. Testes verificam ordem/janelas, domingo, fuso na virada do dia, rotas inativas, ausência de gravações e isolamento entre motoristas/empresas.

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

Última execução: 40 testes aprovados, com duas advertências de depreciação das bibliotecas de testes. Cobertura: isolamento entre empresas, perfis, autenticação, importação/rollback, veículos/rotas, registro de coletas, reenvio concorrente, estados, auditoria, preservação de dados históricos e limites de período/filtros por modalidade.

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

Faltam homologação Android em aparelho, exportações gerais do histórico, geocodificação, mapa simultâneo da frota e chamados. O rastreamento por turno está implementado e aguarda homologação física. Rubrica, comprovante e operação offline estão implementados e aguardam homologação física. As tabelas desses módulos não equivalem aos fluxos implementados. Nenhuma posição de motorista ou rota no mapa é simulada no painel.

Antes de publicar: HTTPS, recuperação de senha, backups, monitoramento, retenção/limpeza de prévias e sessões, limite de upload no proxy e limite de login compartilhado entre instâncias. O limitador atual é em memória, por IP, para uma instância de desenvolvimento.

Referências: [FastAPI autenticação](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/), [Psycopg transações](https://www.psycopg.org/psycopg3/docs/basic/transactions.html), [Receita Federal: dígitos do CNPJ](https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/cnpj/manual-dv-cnpj.pdf).

## Prévia visual do motorista

Abra http://127.0.0.1:5173/previa-motorista.html com o painel em execução, ou abra `frontend/public/previa-motorista.html` diretamente no navegador. A página é independente da API, usa apenas dados fictícios e permite simular login, registro de modalidades e envio pendente. Não é o APK executando: os controles nativos podem variar no Android. Os dados da prévia são descartados ao recarregar.

Desenvolvimento retomado em 26/09/2026. Progresso e pendências em ROADMAP.md.


## Execução diária unificada

`POST /rotas/{rota_id}/execucoes?data=AAAA-MM-DD` prepara o dia para a operação; sem data usa hoje no fuso da empresa. `POST /motorista/rota-do-dia/preparar` prepara as rotas do motorista e retorna as execuções do dia, incluindo `coleta_id`, situação e versão de cada atendimento. O Android usa este endpoint ao atualizar. A consulta GET antiga continua sendo apenas uma prévia do planejamento recorrente atual, sem gravar dados.

Cada rota/data possui uma execução imutável com motorista, versão, endereços, ordem e janelas. Repetir a preparação devolve a mesma execução. O agendamento usa o início da janela ou 08:00 no fuso da empresa quando não há janela. As modalidades ficam a informar até a coleta; o painel também pode informá-las na conclusão.

A conclusão pelo motorista mantém o ID do agendamento, acrescenta volumes e evento de auditoria. Reenvio idêntico é confirmado; outro aparelho tentando concluir uma visita já finalizada recebe 409. Atualizar a rota mostra o estado atual do servidor. Alterações no planejamento recorrente só afetam novas execuções; atendimentos pendentes podem ser transferidos individualmente, e feriados/dias extras e revisitas são tratados na operação diária.

Compatibilidade: visitas antigas já registradas em uma rota/data bloqueiam nova geração nessa combinação para exigir conferência operacional. Registros antigos e filas existentes não são apagados. Não há conversão automática desses registros nem associação automática de agendamentos avulsos. Aplicar migração 006 antes de usar o APK atualizado (o servidor de desenvolvimento aplica migrações ao iniciar).

## Operação diária: exceções, transferências e revisitas

No painel, abra **Rotas → Acompanhar operação do dia**. Escolha a data, consulte o andamento e prepare os atendimentos. **Atualizar andamento** consulta os estados atuais; não há atualização automática nesta entrega.

Antes de emitir o dia, uma exceção pode suspender a operação (feriado/pausa) ou autorizar atendimento extra. Não há importação automática de calendário. Depois de emitir, use as ações individuais; a exceção não pode apagar uma execução existente. Alterações de exceção ficam em eventos append-only com usuário/data/motivo.

Transferências exigem atendimento pendente, motorista ativo, versão atual e motivo. O ID é preservado e o evento registra os responsáveis anterior e novo. Não altera a escala recorrente. O novo motorista recebe o atendimento ao atualizar; a fila antiga do anterior é preservada como conflito se enviada após a transferência.

Uma revisita é uma nova tentativa na **mesma data e execução**, autorizada pela operação após a anterior ser finalizada, com motivo e vínculo com a tentativa anterior. Repetir a mesma solicitação não duplica. Uma tentativa só tem uma sucessora; novas revisitas partem da tentativa mais recente. Para outro dia, prepare a execução correspondente. Registros anteriores nunca são reabertos ou apagados.

O histórico administrativo expõe `tentativa` e `revisita_de`, e preserva eventos das intervenções. O motorista consulta apenas os próprios atendimentos por dia/semana, com paginação e sem dados comerciais dos clientes. O resumo inclui todas as tentativas, não clientes únicos.

Endpoints adicionais: `GET /rotas/{id}/execucoes?data=...`, `PUT /rotas/{id}/excecoes/{data}`, `POST /coletas/{id}/transferir`, `POST /coletas/{id}/revisitas` e `GET /motorista/historico`. O OpenAPI local documenta os campos. Migração 006 aplicada pelo iniciador local; nenhuma migração em Supabase foi executada.

## Operação offline e conferências

O Android pode lembrar a sessão do motorista por até 12 horas, protegida pelo Android Keystore e pelo bloqueio do aparelho. A fila envia automaticamente quando o sistema disponibiliza rede/execução, com retentativas progressivas; o botão manual continua disponível. Reabrir o app permite desbloqueio offline; reiniciar o aparelho ou expirar a sessão exige novo login. Confira política e limitações em `android/README.md`.

Em **Coletas → Conferências offline**, a operação consulta registros recusados enviados pelo motorista e registra a decisão sem sobrescrever o original. É possível vincular uma coleta do mesmo cliente. A decisão, usuário e horário ficam armazenados; conferências encerradas continuam consultáveis. Encerrar a conferência não conclui nem corrige uma coleta automaticamente. O motorista consulta a resposta na tela de registros salvos.

Migração 007 cria a fila de conferências com isolamento por empresa e impede atualização do payload pelo papel da API. Endpoints: `POST /motorista/conflitos`, `GET /motorista/conflitos/{id_local}`, `GET /conflitos` e `POST /conflitos/{id}/resolver`. O iniciador local aplica a migração; nenhum banco Supabase foi alterado.

## Rubrica e comprovantes

Em **Coletas → Detalhes → Comprovante**, usuários administrativos podem consultar a rubrica ou justificativa de ausência/recusa e baixar um HTML autocontido para imprimir ou salvar como PDF pelo navegador. O documento preserva os dados da coleta no momento da captura; correções posteriores de volumes permanecem no histórico, sem reescrever o comprovante.

A migração 008 guarda PNG e metadados privadamente no próprio PostgreSQL, usando RLS por empresa e permissões de inserção/leitura sem edição do comprovante. Isso permite uma única transação para coleta + comprovante, sem serviço externo de arquivos nesta etapa. Antes da produção, dimensionar banco/backup/retenção no Supabase conforme a etapa 9. Nenhum dado foi enviado à nuvem.

A API valida PNG RGB/RGBA de 8 bits, não entrelaçado, até 128 KB e 1024×512, com CRC e descompressão limitada. Imagens não entram nos eventos de auditoria. O endpoint `GET /coletas/{id}/comprovante` exige autenticação administrativa, isola empresas e retorna `Cache-Control: no-store`. O hash SHA-256 cobre metadados, snapshot serializado e PNG; não representa validação da identidade de quem desenhou. Revisão do texto/uso do comprovante continua prevista na etapa 9.

A política do novo Android exige rubrica com nome ou exceção justificada. A API mantém filas antigas e cadastros administrativos sem comprovante por compatibilidade, exibindo essa ausência explicitamente. Não adiciona rubricas retroativas. Os envios antigos preservam o mesmo hash de idempotência.

## Localização e navegação — 27/09/2026

Em **Clientes → Localização**, informe coordenadas fornecidas pelo cliente ou obtidas por GPS em campo, confira o destino no link do Google Maps e registre fonte/motivo. A gravação exige a versão atual: se o endereço ou ponto mudou, reabra o formulário. Alterações de endereço apagam a confirmação de localização. Alterações apenas de contato não a invalidam. Remoção/correção e invalidação geram eventos privados por empresa.

Em **Rotas → Destinos no mapa**, consulte a sequência e abra cada trecho no Google Maps. A primeira parada parte da origem escolhida no Maps; demais trechos vão da parada anterior à selecionada. Nenhuma parada é descartada para caber em limites de waypoints. Essa tela mostra o planejamento recorrente atual, não a execução histórica. Sem geocodificação automática, endereços podem retornar resultados ambíguos e precisam ser conferidos.

O Android inclui **Abrir destino no Google Maps** em cada atendimento. Pontos confirmados usam latitude/longitude; nos demais casos há aviso e pesquisa por endereço. Google Maps recebe apenas destino/endereço e parâmetros de navegação, sem nome, CNPJ, telefone ou credenciais. Sem o aplicativo Maps, tenta abrir no navegador. Rotas já emitidas e caches antigos mantêm seus dados; corrigir um ponto cadastral vale para próximas execuções. Confira os pontos do piloto antes de emitir o dia.

As URLs oficiais funcionam sem chave. A navegação é solicitada em modo de condução; não há roteirização especializada para caminhão/moto, otimização da ordem, envio de localização do motorista ou rastreamento nesta entrega. A disponibilidade da navegação offline depende do Google Maps e dos mapas baixados no aparelho.

### Google Cloud: pendências e configuração futura

O usuário informou que ainda não tem projeto Google Cloud. Não criamos projeto, ativamos faturamento nem efetuamos geocodificação. Não coletamos ou armazenamos resultados da API Google; somente pontos próprios informados pela operação. As políticas de armazenamento da geocodificação precisam ser revisadas antes de sua integração.

Foi preparado **Maps Embed API** opcional para mostrar cliente/trecho selecionado no painel. Sem chave, permanecem links externos; nada é carregado em iframe. Para habilitar posteriormente:

1. Criar/configurar projeto Google Cloud e verificar os requisitos de faturamento, orçamento e APIs na documentação oficial.
2. Habilitar Maps Embed API; usar chave exclusiva de navegador, restrita a essa API e aos referenciadores HTTP do ambiente (desenvolvimento: `http://127.0.0.1:5173/*`; produção: apenas domínio HTTPS próprio).
3. Copiar `frontend/.env.example` para `frontend/.env.local`, definir `VITE_GOOGLE_MAPS_EMBED_KEY` e reiniciar o Vite ou reconstruir o painel. A chave de navegador aparece no cliente por definição; nunca utilizar chave de servidor com acesso a outras APIs.
4. Validar mapa real, restrições, quotas/medição aplicáveis e alertas antes do piloto. O mapa incorporado desta entrega é por cliente/trecho; uma visão simultânea de todos os pontos ainda não foi implementada.

Geocodificação não está habilitada: uma chave de Embed não a implementa nem autoriza chamadas a outros serviços. Nenhuma chave deve ser enviada pelo chat ou versionada no Git.

Fontes: [Maps URLs](https://developers.google.com/maps/documentation/urls/get-started), [configuração do Embed](https://developers.google.com/maps/documentation/embed/get-api-key), [modos de mapa](https://developers.google.com/maps/documentation/embed/embedding-map).


## Homologação Android e HTTPS

O pacote de preparação está em [deploy/homologacao](deploy/homologacao/README.md). Execute scripts/package-homologacao.sh para gerar .local/homologacao/coleta-homologacao.apk e build.json. Instalação separada do app atual, assinatura somente de teste e acesso HTTPS obrigatório. Ainda não existe URL pública: hospedagem/domínio e banco de homologação precisam ser definidos e validados. Não utilizar dados reais antes dos controles da etapa 9.
