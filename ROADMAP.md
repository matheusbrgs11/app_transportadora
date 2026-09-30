# Plano de conclusão do Coleta — versão comercial inicial

Atualizado em 27/09/2026. Esta é a lista de referência solicitada pelo usuário para conduzir o projeto até a conclusão. Desenvolvimento retomado por solicitação do usuário em 26/09/2026. Priorizar testes automatizados leves e evidências resumidas.

## Como seguir este plano

Executar as etapas na ordem abaixo, respeitando dependências. Ao retomar, consultar este arquivo e iniciar pelo primeiro item pendente desbloqueado. Atualizar as caixas e registrar evidências, testes, limitações e data ao terminar cada entrega. Código escrito ou APK compilado, isoladamente, não comprovam um fluxo funcionando. Itens bloqueados continuam abertos, com motivo e próximo passo; avançar em tarefas independentes. Ao concluir cada entrega, enviar ao usuário: mudanças, evidências de validação e lista atualizada das pendências. Mudanças de escopo devem ser registradas aqui e alinhadas com o usuário. Não ampliar o escopo indefinidamente.

Conclusão significa uma primeira versão comercial multiempresa com os fluxos abaixo validados, operação em nuvem e piloto aprovado. Não significa encerrar manutenção ou garantir ausência de defeitos. Serviços pagos, domínio, canal de distribuição e decisões comerciais serão definidos antes da contratação; este plano não autoriza compras.

## Base existente (preservar e evoluir)

- [x] Backend FastAPI/PostgreSQL/PostGIS com isolamento de empresas e autenticação por perfil.
- [x] Painel de clientes, importação ODS/XLSX com prévia, motoristas/veículos e rotas fixas.
- [x] Histórico de coletas por cliente, filtros, modalidades e correções auditadas.
- [x] API restrita do motorista para rota do dia e registro com reenvio idempotente.
- [x] Código Android com cache/fila SQLite, registro de volumes e envio manual; APK debug compilado.
- [x] Prévia web fictícia e repositório GitHub com o trabalho.

Evidências já registradas: 34 testes de backend aprovados na última execução documentada, build web e APK debug compilados, importação pela interface conferida. Não foram repetidos nesta atualização de planejamento. Android ainda sem homologação em aparelho; sem nuvem operacional, rubrica, rastreamento ou chamados.

## 1. Homologar a base Android

- [ ] Configurar emulador sem exigir Android Studio, se houver virtualização e recursos; manter teste em aparelho real como requisito antes do piloto.
- [ ] Testar login de motorista, rota correta, registro de visita e aparecimento no painel/histórico.
- [ ] Conferir isolamento entre contas/empresas também no cache e na fila do aparelho.
- [ ] Testar tela pequena, teclado, acessibilidade, voltar, rotação, encerramento e reabertura; corrigir falhas e preservar rascunhos.
- [ ] Registrar procedimento de teste reproduzível e evidências.

Aceite: fluxo Android → API → painel funcionando; nenhuma perda de registro já salvo ou exposição entre contas nos cenários testados.

## 2. Unificar planejamento e execução das coletas

- [x] Criar execução diária da rota com cópia de paradas, motorista, ordem e janelas; preservar o planejamento histórico.
- [x] Exceções por data (feriado/pausa/dia extra), substituição por transferência dos atendimentos pendentes e revisitas explícitas na mesma execução.
- [x] Gerar atendimentos do dia uma única vez e vincular conclusão do motorista ao agendamento existente, evitando uma segunda coleta independente. Validado nos endpoints; integração visual Android ainda pendente.
- [x] Estados pendente/concluída/não atendida/cancelada nos perfis autorizados. Motorista conclui ou registra não atendimento; cancelamento fica com a operação, com motivo.
- [x] Progresso da execução no painel e no Android; histórico próprio do motorista de hoje/últimos sete dias, paginado. Atualização manual.
- [x] Transferência individual de atendimentos pendentes da rota, planejamento preservado, nova tentativa autorizada sem apagar a anterior e concorrência entre aparelhos com auditoria.

Homologação Android → API → painel ainda pendente (etapa 1).

Aceite: uma visita planejada tem identidade estável até o histórico; reenvios e aparelhos simultâneos não duplicam o atendimento; revisitas legítimas são explícitas.

## 3. Completar operação offline

- [x] Planejamento, rascunhos e fila em SQLite privado, migração v1→v2, backup desativado e falhas de gravação sinalizadas. Sessão persistida usa AES-GCM/Android Keystore e requer bloqueio do aparelho. Validado com testes leves; homologação física continua pendente.
- [x] Política de sessão de motorista de até 12 horas; renovação por novo login, logout local imediato e revogação no servidor quando online. Reabrir exige credencial do Android; reinício do aparelho, expiração ou alteração relevante do relógio exigem login online. Revogação remota é conhecida na próxima requisição autenticada.
- [x] JobScheduler com rede obrigatória, tentativa imediata, repetição exponencial e verificação periódica. Sessão lembrada em aparelho com bloqueio é necessária; envio manual permanece disponível. Horário real depende do Android e deve ser homologado em aparelho.
- [x] Pendente/enviando/enviado/conflito/em conferência/conferido; recuperação de envio interrompido, retentativa explícita e conferência no painel com autor/motivo e vínculo opcional à coleta, preservando o payload original.
- [x] Impedir que um registro recusado bloqueie todos os demais envios. Validado para conflitos; autenticação/rede continuam interrompendo o envio e preservando a fila.
- [ ] Testar modo avião, resposta perdida, rede oscilante, reinício, atualização do app, relógio incorreto, virada do dia e logout com pendências.

Aceite: registros salvos sobrevivem aos cenários de falha, voltam ao servidor sem duplicação e têm estado compreensível para motorista e operação.

## 4. Implementar rubrica e comprovante

- [x] Captura da rubrica com dedo, nome, horário e limpar/refazer no Android; testada com gestos e rasterização nativa simulada.
- [x] Novo formulário Android exige rubrica com nome ou ausência/recusa justificada. API mantém compatibilidade com filas antigas sem comprovante; painel identifica registros sem comprovante.
- [x] Rascunho de traços/metadados e imagem PNG confirmada preservados no SQLite; imagem e coleta viajam no mesmo payload imutável da fila.
- [x] PNG privado no PostgreSQL com RLS, limite de 128 KB/1024×512, estrutura/CRC/descompressão limitada validados e gravação atômica com coleta. Comprovante append-only por coleta.
- [x] Consulta administrativa autenticada, rubrica/justificativa e download HTML autocontido para impressão/salvar PDF pelo navegador. Snapshot original e hash preservados; imagens não são copiadas para eventos.
- [x] Testes de PNG inválido/truncado, reenvio, isolamento, resposta perdida e rollback após gravar comprovante. Interoperabilidade PNG Android → validador API conferida. Homologação física permanece na etapa 1.

Aceite: comprovante correto recuperável, sem imagem pública nem perda após confirmação local. Revisão jurídica do texto e uso do comprovante na etapa 9; não presumir validade jurídica apenas pela captura.

## 5. Localizar clientes e abrir navegação

- [ ] Configurar projeto Google Cloud, chaves restritas, quotas, medição e alertas de custo. Usuário informou em 27/09/2026 que ainda não possui projeto. Nenhuma conta, API paga ou cobrança foi criada/ativada.
- [x] Cadastro/correção/remoção manual de pontos fornecidos pelo cliente ou GPS em campo, com versão, motivo e auditoria. Alterar endereço invalida o ponto; execuções já emitidas preservam seu snapshot.
- [ ] Geocodificar automaticamente e tratar candidatos ambíguos/inexistentes. Depende da configuração e política de armazenamento do provedor.
- [ ] Respeitar condições de armazenamento e uso do provedor escolhido.
- [ ] Homologar mapa incorporado no painel. Lista ordenada e links de cada trecho já funcionam; Maps Embed opcional está preparado, mas sem chave/projeto e sem validação real. Ainda não há visão simultânea de todos os pontos.
- [x] Abrir Google Maps no Android com ponto confirmado ou endereço mediante aviso; fallback para navegador, sem exigir chave e sem transmitir nome/CNPJ/telefone. Homologação em aparelho ainda pendente.

Aceite: endereços do piloto conferidos e navegação para o destino esperado; sem prometer otimização automática de rotas nesta versão.

## 6. Rastreamento durante o turno

- [x] Implementar início/fim de turno, permissões, explicação ao motorista e serviço Android com notificação de rastreamento.
- [x] Implementar captura em serviço foreground e envio com intervalos de 30/60/120/300 segundos; falhas descartam posições antigas. Consumo de bateria e comportamento real do Android ainda dependem de homologação.
- [x] Validar precisão/horário e impedir que posição atrasada substitua uma mais recente.
- [x] Painel com última posição, horário, precisão, estado de conexão e link para Google Maps.
- [ ] Mapa incorporado com múltiplos motoristas e homologação com Google Cloud.
- [x] Interromper captura ao encerrar/sair; guardar encerramento offline para retentativa. API rejeita posições de turnos encerrados/expirados e mantém somente a última posição.
- [ ] Aprovar retenção e automatizar limpeza periódica em produção: atualmente a posição é apagada ao encerrar no servidor ou no próximo acesso ao rastreamento após expiração de 12 horas; não existe limpeza agendada.
- [ ] Testar aparelhos reais, economia de bateria, permissão revogada, falta de sinal e app em segundo plano.

Aceite: operação identifica localização e sua atualidade; não há rastreamento fora do turno no fluxo definido; consumo validado no piloto.

## 7. Chamados imprevistos

- [ ] Criar chamado no painel com cliente, modalidade/volume esperado, prioridade e observações.
- [ ] Sugerir motoristas por posição recente, disponibilidade, veículo e proximidade; calcular trajeto quando necessário.
- [ ] Despachar para o motorista escolhido e enviar notificação.
- [ ] Implementar recebimento, aceite/recusa com motivo, expiração, reatribuição e conclusão.
- [ ] Integrar à lista de atendimentos e histórico como chamado imprevisto, sem duplicação.
- [ ] Tratar motorista offline, posição antiga, notificações desativadas e dois operadores editando juntos.

Aceite: chamado sai do painel, é recebido pelo motorista e termina no histórico com responsável e eventos; envio de notificação não é tratado como confirmação de recebimento.

## 8. Finalizar gestão e relatórios

- [ ] Gestão de usuários/perfis, recuperação e troca de senha, bloqueio de acesso e encerramento de sessões.
- [ ] Gestão de empresas, fuso e modalidades próprias; onboarding sem editar diretamente o banco.
- [ ] Exportar histórico filtrado em CSV e PDF, com conferência de totais e proteção contra fórmulas em CSV.
- [ ] Resumo operacional de pendências, concluídas, não atendidas, volumes a conferir e chamados.
- [ ] Padronizar erros, estados vazios, confirmações e acessibilidade das telas.

Aceite: administrador da empresa executa a rotina sem intervenção técnica no banco; exportações correspondem aos filtros e permissões.

## 9. Nuvem, segurança e operação

- [ ] Definir capacidade inicial, orçamento, região e requisitos de disponibilidade; aprovar custos. Preferência do usuário: Supabase para PostgreSQL. Projeto ainda não identificado; hospedagem da API/painel ainda precisa ser definida.
- [ ] Validar migrações, PostGIS, papéis/permissões, conexão TLS/pooler e isolamento no Supabase de homologação antes de usar produção. Não presumir compatibilidade de superusuário nem expor tabelas operacionais pela Data API.
- [ ] Preparar homologação e produção separadas: API, painel, PostgreSQL/PostGIS e arquivos privados, com domínio/HTTPS.
- [ ] Gerenciar segredos e permissões mínimas; aplicar limites de login/upload, logs sem credenciais e limpeza de sessões/prévias.
- [ ] Validar isolamento de empresas em todos os módulos, arquivos, exports e tarefas em segundo plano.
- [ ] Definir retenção, descarte, acesso aos dados, termos e privacidade com revisão adequada, incluindo localização e assinatura.
- [ ] Automatizar backups do banco/arquivos e comprovar restauração; definir prazo de recuperação e perda máxima aceitável.
- [ ] Monitorar erros, indisponibilidade, fila e custos; testar alertas e documentar atendimento a incidentes.
- [ ] Automatizar testes/builds e publicação; adicionar Gradle Wrapper, gestão segura da chave de assinatura, migrações e reversão de versão.
- [ ] Gerar release Android assinado, definir distribuição e atualização, verificando requisitos vigentes do canal escolhido.
- [ ] Testar carga representativa e crescimento de dados; revisar dependências e corrigir vulnerabilidades relevantes.

Aceite: operação funciona sem computador do desenvolvedor, restauração comprovada, acessos segregados e procedimento reproduzível de publicação/recuperação. Preparativos desta etapa podem ocorrer em paralelo; deve estar pronta antes do piloto com dados reais.

## 10. Piloto e lançamento comercial

- [ ] Preparar uma empresa real, base validada, quatro motoristas (três carros e uma moto) e treinamento.
- [ ] Rodar teste ponta a ponta online/offline, rubrica, rastreamento, chamados, histórico e exportação.
- [ ] Acompanhar período de piloto acordado; medir falhas, duplicações, tempo de sincronização, bateria e tempo de suporte.
- [ ] Corrigir bloqueadores e obter aceite da transportadora sobre os fluxos críticos.
- [ ] Validar preço, implantação, limites de uso, suporte, retenção e cancelamento; proposta anterior de preços é hipótese, não decisão fechada.
- [ ] Definir cobrança e acompanhamento de pagamentos (processo manual é aceitável no início), sem perda indevida de dados ao suspender conta.
- [ ] Documentar onboarding, ajuda ao motorista, suporte e plano de atualização; cadastrar segunda empresa para validar operação comercial multiempresa.
- [ ] Publicar versão estável e registrar checklist final e responsáveis pela manutenção.

Aceite final: todos os itens necessários acima concluídos com evidência, piloto aprovado, sem defeitos críticos conhecidos, backups recuperáveis e suporte/custos definidos. Teste em emulador não substitui homologação de GPS/bateria em aparelho real.

## Fora desta versão

iOS, otimização automática avançada, emissão fiscal/CT-e/MDF-e, integrações ERP/TMS específicas, marca própria por cliente e análises avançadas. Só entram mediante nova definição de escopo; não bloqueiam a conclusão acordada.

## Registro de evolução

- 26/09/2026: plano criado após revisão do README e documentação Android. Próxima entrega: etapa 1; projeto ainda pausado. Pendência externa principal: emulador ou aparelho disponível para teste, e aparelho real antes do piloto.

- 26/09/2026: retomada. `/dev/kvm` indisponível; adotado Robolectric para testes de SQLite/fila sem emulador completo. Isso não conclui homologação visual, GPS/bateria ou teste ponta a ponta em aparelho.

- 26/09/2026: 8 testes Android Robolectric aprovados (API 28), APK debug recompilado e lint executado. Validados cache/fila entre contas, persistência ao reabrir banco, conflito sem bloquear demais visitas, resposta perdida, sessão expirada, confirmação inválida, rascunho e migração SQLite v1→v2. Etapa 1 segue aberta: sem execução ponta a ponta em aparelho/emulador completo.

- 26/09/2026: migração 005 e execução diária entregues. 40 testes backend aprovados, incluindo concorrência na preparação/conclusão, snapshots, compatibilidade e isolamento. Painel prepara o dia e conclui atendimentos sem modalidades prévias. Android atualizado para usar coleta_id. A etapa 2 permanece aberta para exceções, transferência, revisita, progresso/histórico próprio e homologação.

- 26/09/2026: usuário informou conta Supabase e pediu lista restante a cada entrega. Supabase adotado como destino preferido do banco, sujeito à validação técnica; aguardando identificação do projeto. Nenhum recurso em nuvem foi criado ou migrado.

- 26/09/2026: concluído o passo solicitado de operação diária (etapa 2 deste plano): exceções por data auditadas, transferência de pendentes, revisitas encadeadas, não atendimento offline, progresso e histórico próprio diário/semanal. Migração 006 aplicada no banco privado local. Validação: 43 testes backend, 12 testes Robolectric (incluindo tela de revisita/não atendimento), build web, APK debug e lint aprovados. Mantidos pendentes homologação real, resolução assistida de conflitos e demais etapas. Próxima implementação: completar operação offline (etapa 3); homologação física da etapa 1 continua necessária.

- 26/09/2026: entrega de operação offline: sessão lembrada de até 12 horas, AES-GCM/Keystore e desbloqueio Android; JobScheduler com rede/backoff e recuperação de envios interrompidos; conflitos com retentativa explícita, conferência auditada no painel e resposta ao motorista. Migração 007 aplicada apenas no banco local. Validação: 46 testes backend e 20 testes Android Robolectric aprovados, incluindo concorrência manual/background, criptografia com chave de teste, política de expiração/relógio/reinício, configuração do agendador e tela na virada do dia. Build web, APK e lint aprovados. Corrigida compatibilidade Closeable do SQLiteOpenHelper em Android antigo. Etapa 3 ainda requer homologação física de rede/Doze/force-stop/Keystore/desbloqueio e fluxo ponta a ponta. Próxima implementação independente: rubrica e comprovante (etapa 4).

- 26/09/2026: rubrica e comprovantes implementados (migração 008). Novo formulário exige assinatura ou exceção justificada; rascunho e imagem preservados offline. PostgreSQL guarda PNG privado atomicamente com a coleta; painel consulta e exporta HTML imprimível com snapshot original. Compatibilidade de reenvio de filas antigas preservada. Validação: 50 testes backend, 23 testes Android (incluindo rasterização nativa simulada), build web, APK e lint aprovados; PNG produzido pelo Android aceito pelo validador real da API. Sem homologação física nem publicação em nuvem. Próxima implementação: localizar clientes e navegação (etapa 5).

- 27/09/2026: localização manual e navegação entregues (migração 009). Pontos versionados/auditados, invalidação por alteração do endereço, snapshots preservados, links por trecho no painel e navegação Android. Google Maps Embed preparado como opção de ambiente, sem carregar mapa ou chamar APIs quando não configurado. Usuário ainda sem projeto Google Cloud; geocodificação e mapa incorporado permanecem pendentes. Validação desta entrega: 52 testes backend, 25 testes Android, build web, APK e lint (evidências nos relatórios locais). Conferência de endereços reais, Google Cloud e homologação física seguem abertas.


- 27/09/2026: rastreamento por turno implementado (migração 010), isolamento por empresa/motorista, início idempotente, encerramento e descarte da última posição, expiração em 12 horas e rejeição de posições atrasadas. Android usa serviço foreground iniciado pelo motorista, permissões de localização/notificação, sessão protegida e intervalos configuráveis. Painel consulta a cada 15 segundos e sinaliza dados antigos/indisponibilidade. Sem histórico de percurso nem simulação apresentada como posição real. Validação: 54 testes backend e 27 testes Android aprovados, build web, APK debug e lint aprovados. Migração 010 aplicada no banco local e endpoint autenticado conferido via HTTP. Pendentes aparelhos reais, mapa incorporado, limpeza agendada e política de retenção aprovada.


- 27/09/2026: preparo de homologação sem Docker em deploy/homologacao: serviço API local à máquina, proxy HTTPS/painel estático e roteiro de instalação/teste. Usuário informou não ter hospedagem/domínio; nenhuma infraestrutura foi contratada/publicada. Variante Android staging separada (Coleta Homologação), HTTPS obrigatório, sem depuração, assinada com chave debug apenas para testes. APK/lint aprovados; manifesto e assinatura verificados. Scripts de empacotamento/hash e verificação HTTPS adicionados. Caddy/systemd no servidor e acesso HTTPS externo ainda não validados. Próximos passos externos: escolher hospedagem/domínio, identificar projeto Supabase de homologação e disponibilizar Android físico. Chamados imprevistos seguem como próxima implementação funcional independente.


- 27/09/2026: usuário disponibilizou Android e preferiu concluir preparo do APK antes de conectar. Variante USB isolada criada, HTTP limitado ao loopback e servidor preenchido; instalador não apaga dados/concede permissões. Preparada empresa fictícia local com motorista, cliente e rota diária, acessos privados fora do Git. Melhoradas mensagens de rede/API e situação de envio GPS; sincronização manual também envia encerramentos pendentes. Homologação física ainda não iniciada. Procedimento em docs/teste-aparelho.md.


- 27/09/2026: revisão pré-instalação: 29 testes Android aprovados, incluindo recusa de redirecionamento sem encaminhar credencial e resposta HTTP inválida. Conta motorista e preparação da rota fictícia verificadas contra API local; reexecução preserva os cadastros. Usuário pediu desenvolvimento antes de conectar, portanto nenhuma instalação, concessão de permissão ou captura GPS física foi executada.


- 27/09/2026: perfil agendamento adicionado (migração 011), com Rastreamento/Motoristas/Rotas fixas/Coletas, abertura inicial em Coletas e criação de acesso pelo administrador. Cadastro, atualização, importação, localização e desativação de clientes restritos a admin na API; operador legado também segue essa regra. Consulta de clientes preservada para seleção em rotas/coletas. Gestão ampla de usuários, recuperação e bloqueio de acessos continuam pendentes na etapa 8. Não inclui integração WhatsApp nem despacho de chamados imprevistos.

Validação do perfil agendamento: 55 testes backend aprovados, build web aprovado, migração 011 aplicada no banco local e smoke autenticado local aprovado. Nenhum APK precisou ser alterado nesta entrega.

- Correção durante teste físico: erro 401 no login agora informa empresa/usuário/senha incorretos, em vez de sessão expirada; preserva formulário para corrigir os dados. Erros 401 de sessão autenticada mantêm o fluxo de novo login.

- Homologação física Samsung: identificado crash ao abrir histórico por Instant.parse rejeitar data ISO com offset -03:00 no Android. Leitura centralizada via OffsetDateTime, aplicada também à expiração de turno, datas da fila e rubrica; teste de regressão cobre UTC, offsets, frações e virada de data no fuso local.

- 29/09/2026: teste físico offline no Samsung confirmado pelo usuário: coleta salva como pendente sem cabo, conexão USB restabelecida e envio manual confirmado. Conferência autenticada na API: exatamente uma coleta no dia, mesmo ID agendado, status concluída, três modalidades e comprovante com assinatura PNG e hash presentes. Valida este cenário; não encerra testes de interrupção durante envio, reinício/Doze, GPS/bateria ou piloto. Mensagem de falha de envio após salvar offline ainda precisa distinguir claramente salvamento local bem-sucedido de indisponibilidade de rede.

- 29/09/2026: após ajuste dos relógios, usuário confirmou período de tela bloqueada no Samsung. API registrou posição às 11:23:56 -03:00, recebida às 11:24:14, posterior à referência 11:20:01. Na conferência às 11:24:31, posição recente (35 s), precisão estimada 8 m. Evidência de atualização durante o período informado, não de entrega contínua de todos os pontos (somente última posição é retida). Encerramento, percurso real e bateria ainda pendentes.

- 29/09/2026: encerramento online de turno validado no Samsung: após ação do usuário, API retornou fora_turno, sem turno ativo nem coordenadas/horário de posição; consulta ADB não encontrou TrackingService ativo. Testes físicos confirmados até aqui: coleta online/offline com assinatura, envio sem duplicação no cenário testado, posição atualizada durante tela bloqueada e encerramento online. Permanecem percurso/bateria, encerramento offline, interrupções/reinício e demais cenários do piloto.

- 30/09/2026: encerramento offline de turno validado no Samsung: sem cabo, o aplicativo interrompeu a captura e apresentou “encerramento aguardando conexão”. Após reconectar e executar “Enviar registros salvos”, a API passou a retornar `fora_turno`, sem turno ativo nem coordenadas. O cenário exige sincronização manual nesta validação; teste de execução automática pelo Android continua pendente.

- 30/09/2026: recuperação após encerramento forçado do processo validada no Samsung. O aplicativo foi encerrado e reaberto por ADB sem limpar dados; usuário confirmou a tela de desbloqueio por credencial do aparelho e retorno correto à rota salva. Reinício completo do aparelho ainda em validação, pois a política exige login online depois da reinicialização.
