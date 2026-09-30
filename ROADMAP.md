# Plano de conclusão do Coleta — versão comercial inicial

Atualizado em 30/09/2026. Esta é a lista de referência solicitada pelo usuário para conduzir o projeto até a conclusão. Desenvolvimento retomado por solicitação do usuário em 26/09/2026. Priorizar testes automatizados leves e evidências resumidas.

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

Evidências recentes estão no Registro de evolução. Android já foi testado no Samsung com coleta online/offline, assinatura, histórico, não atendimento e rastreamento por turno. Ainda faltam os cenários físicos indicados abaixo, nuvem operacional e chamados imprevistos.

## Ordem prática a partir de agora

As etapas 2, 4 e 8 estão implementadas. As etapas 1 e 3 dependem principalmente de testes adicionais no Android; as etapas 5 e parte da 6 dependem de um projeto Google Cloud; a 9 depende da escolha de hospedagem e do projeto Supabase. Essas dependências não impedem desenvolver os chamados imprevistos da etapa 7. A sequência de trabalho mais útil é: terminar o fluxo de chamados em código e teste local; repetir os cenários físicos de Android, offline e GPS; integrar e homologar mapas quando houver Google Cloud; colocar um ambiente de homologação na nuvem; executar o piloto e corrigir seus bloqueadores. Preparativos de segurança, automação e documentação da etapa 9 podem avançar em paralelo. Nenhuma compra ou ativação de serviço pago está autorizada por este plano.

Para cada etapa aberta, as caixas abaixo indicam o trabalho específico. O texto de abertura explica o resultado esperado, o modo de verificar e o que ainda depende do usuário ou de serviços externos. Uma etapa só será marcada como concluída quando o fluxo correspondente funcionar com evidência, não apenas porque o código foi escrito.

## 1. Homologar a base Android

**Resultado esperado:** um motorista consegue entrar, consultar sua rota, registrar atendimento com assinatura, reabrir o aplicativo e encontrar os dados corretos sem misturar contas. O fluxo principal já funcionou no Samsung; esta etapa agora cobre os cantos de uso que podem causar perda de rascunho ou confusão na tela.

**Como verificar:** executar um roteiro curto em aparelho real com duas contas/empresas fictícias, alternando login e conferindo cache e fila locais; repetir em tela menor ou com fonte ampliada, teclado aberto, botão Voltar, rotação, bloqueio e reabertura. Registrar para cada cenário o resultado no aparelho e, quando houver envio, a coleta correspondente na API/painel. Se o emulador continuar indisponível por falta de KVM, isso será documentado sem substituir o teste físico.

**Dependência:** aparelho Android disponível durante a sessão de testes. O desenvolvimento e os testes automatizados podem continuar sem o cabo.

- [ ] Configurar emulador sem exigir Android Studio, se houver virtualização e recursos; manter teste em aparelho real como requisito antes do piloto.
- [x] Testar login de motorista, rota correta, registro de visita e aparecimento no painel/histórico.
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

Fluxo Android → API → histórico validado no aparelho; demais cenários de homologação da etapa 1 continuam abertos.

Aceite: uma visita planejada tem identidade estável até o histórico; reenvios e aparelhos simultâneos não duplicam o atendimento; revisitas legítimas são explícitas.

## 3. Completar operação offline

**Resultado esperado:** uma coleta salva sem internet permanece no aparelho, indica claramente que aguarda envio e chega ao servidor uma única vez quando a conexão volta. Se houver conflito ou sessão inválida, o motorista vê o estado correto e a equipe consegue conferir o registro sem apagar o original.

**Como verificar:** além dos testes já aprovados de cabo removido, reinício, logout/login e reenvio, executar o roteiro restante com modo avião, conexão oscilante, atualização de APK preservando dados, relógio alterado e virada do dia. Conferir no banco o identificador da coleta e a ausência de duplicatas após cada repetição. Testar a sincronização automática com Wi-Fi ou dados móveis contra API HTTPS, pois o encaminhamento USB não representa uma rede Android normal para o JobScheduler.

**Dependência:** aparelho para os cenários locais; API HTTPS externa da etapa 9 para validar a sincronização automática em rede real.

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
- [x] Testes de PNG inválido/truncado, reenvio, isolamento, resposta perdida e rollback após gravar comprovante. Interoperabilidade PNG Android → validador API e assinatura física enviada e recuperada no teste Samsung.

Aceite: comprovante correto recuperável, sem imagem pública nem perda após confirmação local. Revisão jurídica do texto e uso do comprovante na etapa 9; não presumir validade jurídica apenas pela captura.

## 5. Localizar clientes e abrir navegação

**Resultado esperado:** o gestor identifica no mapa os clientes com localização confirmada, encontra endereços sem ponto confiável e o motorista abre o destino correto no Google Maps. Endereços ambíguos devem ir para conferência humana antes de virar coordenadas usadas na operação.

**Como executar e verificar:** criar um projeto Google Cloud com cobrança e limites sob controle da empresa, restringir as chaves aos serviços e origens necessários e habilitar somente as APIs escolhidas. Implementar geocodificação sob demanda ou no cadastro, apresentar candidatos e permitir correção. Conferir uma amostra de endereços reais do piloto comparando endereço, pino e destino aberto no Android. Medir chamadas/custos e documentar as regras de armazenamento do provedor antes de guardar resultados.

**Dependência:** o usuário ainda não possui projeto Google Cloud. A navegação por link já funciona sem chave; geocodificação e mapa incorporado ficam bloqueados até haver projeto e configuração de cobrança. Não comprar ou ativar serviços por conta própria.

- [ ] Configurar projeto Google Cloud, chaves restritas, quotas, medição e alertas de custo. Usuário informou em 27/09/2026 que ainda não possui projeto. Nenhuma conta, API paga ou cobrança foi criada/ativada.
- [x] Cadastro/correção/remoção manual de pontos fornecidos pelo cliente ou GPS em campo, com versão, motivo e auditoria. Alterar endereço invalida o ponto; execuções já emitidas preservam seu snapshot.
- [ ] Geocodificar automaticamente e tratar candidatos ambíguos/inexistentes. Depende da configuração e política de armazenamento do provedor.
- [ ] Respeitar condições de armazenamento e uso do provedor escolhido.
- [ ] Homologar mapa incorporado no painel. Lista ordenada e links de cada trecho já funcionam; Maps Embed opcional está preparado, mas sem chave/projeto e sem validação real. Ainda não há visão simultânea de todos os pontos.
- [x] Abrir Google Maps no Android com ponto confirmado ou endereço mediante aviso; fallback para navegador, sem exigir chave e sem transmitir nome/CNPJ/telefone. Homologação em aparelho ainda pendente.

Aceite: endereços do piloto conferidos e navegação para o destino esperado; sem prometer otimização automática de rotas nesta versão.

## 6. Rastreamento durante o turno

**Resultado esperado:** durante um turno ativo, o operador vê a última posição de cada motorista, com horário e precisão, e sabe distinguir posição recente de posição antiga. Fora do turno não deve haver captura nem coordenada visível. O teste anterior confirmou envio e encerramento em aparelho; ainda falta medir comportamento por tempo maior e em condições adversas.

**Como verificar:** fazer um percurso real controlado com tela acesa e bloqueada, registrar horário inicial/final, bateria e frequência das atualizações; repetir com economia de bateria, permissão retirada, GPS sem sinal e aplicativo em segundo plano. Confirmar que a posição some após encerrar o turno e que turnos expirados são limpos por tarefa agendada, sem depender de uma visita ao painel. Com Google Cloud configurado, exibir os motoristas simultaneamente no mapa e comparar pinos, horários e links de navegação.

**Dependência:** aparelho em percurso real e, para o mapa incorporado, projeto Google Cloud. A política de retenção de localização precisa ser aprovada antes da produção; a implementação do job pode ser preparada sem contratar infraestrutura.

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

**Resultado esperado:** quando um cliente pede coleta fora da rota fixa, a pessoa de agendamento cria um chamado, escolhe ou confirma um motorista e acompanha cada estado até a conclusão ou não atendimento. O motorista recebe o chamado no Android, pode aceitar ou recusar com motivo e o resultado entra no mesmo histórico de coletas, sem duplicar visita.

**Como executar:** primeiro modelar chamado, estados, prazo e eventos auditados no backend; depois construir a tela de criação/despacho no painel e a caixa de chamados no Android. A sugestão inicial de motorista pode usar disponibilidade, tipo de veículo e distância aproximada a partir de uma posição recente, informando quando a posição estiver velha ou ausente. Cálculo de trajeto com Google Maps fica opcional até a etapa 5. Uma notificação apenas alerta: o painel só mostrará recebimento ou aceite após confirmação do aplicativo. Implementar expiração, recusa, reatribuição e bloqueio de edição concorrente.

**Como verificar:** simular dois operadores, dois motoristas e um aparelho offline; despachar, receber, aceitar ou recusar, reatribuir e concluir. Conferir eventos e responsável final no histórico, incluindo reenvio idempotente após falha de rede. Repetir no aparelho e na API HTTPS quando a etapa 9 disponibilizar o servidor externo.

**Dependência:** não exige Google Cloud para o fluxo básico. Notificação remota e teste fora do cabo dependem da infraestrutura externa; o fluxo local pode ser desenvolvido agora.

- [ ] Criar chamado no painel com cliente, modalidade/volume esperado, prioridade e observações.
- [ ] Sugerir motoristas por posição recente, disponibilidade, veículo e proximidade; calcular trajeto quando necessário.
- [ ] Despachar para o motorista escolhido e enviar notificação.
- [ ] Implementar recebimento, aceite/recusa com motivo, expiração, reatribuição e conclusão.
- [ ] Integrar à lista de atendimentos e histórico como chamado imprevisto, sem duplicação.
- [ ] Tratar motorista offline, posição antiga, notificações desativadas e dois operadores editando juntos.

Aceite: chamado sai do painel, é recebido pelo motorista e termina no histórico com responsável e eventos; envio de notificação não é tratado como confirmação de recebimento.

## 8. Finalizar gestão e relatórios

- [x] Gestão de usuários/perfis, recuperação e troca de senha, bloqueio de acesso e encerramento de sessões.
  - [x] Painel do administrador lista/cria acessos administrativos, bloqueia/reativa, redefine senhas e revoga sessões; troca da própria senha exige a senha atual e também revoga sessões. Motoristas seguem na aba própria.
  - [x] Recuperação independente do administrador por oito códigos de uso único gerados com senha atual, exibidos apenas uma vez. Sem código guardado, o administrador redefine a senha; após recuperação/troca, códigos antigos são invalidados.
- [x] Gestão da própria empresa, fuso e modalidades pelo painel; onboarding de outra empresa por CLI privada sem SQL manual.
- [x] Exportar histórico filtrado em CSV e PDF, com linha/resumo de totais, limite explícito e proteção contra fórmulas em CSV.
- [x] Resumo operacional de agendadas, concluídas, não atendidas, itens a conferir e chamados registrados.
- [x] Padronizar erros, estados vazios, confirmações e acessibilidade básica das telas administrativas: tratamento compartilhado da API, diálogo de bloqueio, foco de modal, atalhos/labels, alvos de toque, contraste da ação principal e largura compacta. Homologação com leitor de tela e usuários reais permanece no piloto.

Aceite: administrador da empresa executa a rotina sem intervenção técnica no banco; exportações correspondem aos filtros e permissões.

## 9. Nuvem, segurança e operação

**Resultado esperado:** painel e API ficam acessíveis por HTTPS sem computador ou cabo, com banco segregado por empresa, segredos protegidos, backup restaurável, monitoramento e procedimento de publicação/reversão. Esta etapa transforma o protótipo local em ambiente de homologação e depois em operação de produção; não é só apontar um domínio.

**Sequência de trabalho:** definir região, capacidade, orçamento e hospedagem da API/painel; identificar o projeto Supabase de homologação; testar migrações, PostGIS, papéis, RLS e conexão TLS nesse projeto; publicar homologação com domínio/HTTPS; fazer smoke de login, coleta, assinatura, rastreamento e exportação por rede móvel. Em seguida preparar produção separada, backup/restauração, retenção, limites, logs/alertas e resposta a incidentes. Por fim automatizar testes, builds e migrações, criar chave de assinatura Android protegida e gerar uma versão release reproduzível.

**Como verificar:** um celular fora da rede do computador acessa a API HTTPS; dados de uma empresa não aparecem em outra; uma cópia de backup restaura os registros esperados em ambiente isolado; uma versão nova pode ser publicada e revertida sem perder a fila do motorista. Registrar tempo de indisponibilidade e comportamento com carga próxima aos quatro motoristas iniciais, deixando margem para outras empresas.

**Dependência:** projeto Supabase identificado e hospedagem/domínio definidos pelo usuário antes da publicação. Custos e serviços pagos serão apresentados para decisão antes da contratação. Revisão dos textos e práticas de privacidade, especialmente localização e assinatura, deve ocorrer antes de usar dados reais.

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

**Resultado esperado:** uma transportadora real usa a solução com quatro motoristas (três carros e uma moto) durante um período combinado, sem perda ou duplicação crítica de coletas. O gestor consegue planejar, acompanhar, corrigir, consultar histórico e exportar; o motorista consegue trabalhar com conexão normal e falhas temporárias.

**Como executar e medir:** importar e conferir a base real, validar veículos/rotas e treinar gestor, agendamento e motoristas; realizar uma operação completa online e offline com assinatura, GPS e chamado imprevisto. Durante o piloto, registrar falhas, tempo de sincronização, bateria, chamadas de suporte, duplicações e acertos de endereço. Corrigir bloqueadores, repetir os cenários afetados e obter aceite explícito da transportadora para os fluxos críticos. Em paralelo, fechar preço, implantação, limites, suporte, retenção, cancelamento e cobrança; cadastrar uma segunda empresa para comprovar a operação multiempresa.

**Dependência:** etapas funcionais e de nuvem aprovadas, dados e participantes reais autorizados. A publicação estável só ocorre após aceite do piloto, restauração de backup demonstrada e responsáveis por suporte/manutenção definidos.

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

- 30/09/2026: reinício completo do Samsung validado. O aplicativo solicitou novo login, conforme a política; após restabelecer USB e autenticar, usuário confirmou que rota e registros anteriores permaneciam disponíveis.

- 30/09/2026: persistência de coleta pendente após logout/login validada no Samsung. O usuário registrou a coleta sem conexão, saiu e entrou novamente no aplicativo e confirmou o registro como pendente. Após restabelecer o encaminhamento USB, acionou o envio manual e confirmou o status `enviado`. Permanece pendente testar interrupção durante a transmissão e sincronização automática em segundo plano/Doze.

- 30/09/2026: interrupção de envio validada no Samsung. Uma revisita fictícia foi concluída sem conexão e mantida em fila; após iniciar o envio, o cabo foi removido imediatamente e o registro continuou pendente. Ao restabelecer USB e reenviar uma única vez, o aplicativo exibiu `enviado`. A API confirmou uma revisita concluída e uma única ocorrência para a coleta de origem, sem duplicidade.

- 30/09/2026: caminho de sincronização em segundo plano validado no Samsung. O JobScheduler manteve os trabalhos persistentes; como o encaminhamento ADB não é uma rede Android validada, a execução automática por restrição de conectividade não pode ser homologada via USB. Com a tela bloqueada, foi disparada a tarefa já agendada pelo sistema, que processou um registro pendente; API e aplicativo confirmaram `enviado`. Adicionado diagnóstico sem dados sensíveis para falhas/execuções da tarefa. Falta homologar o disparo autônomo por Wi-Fi/dados móveis contra API HTTPS externa e sob Doze real.

- 30/09/2026: interface do motorista reorganizada para avaliação física. Navegação inferior fixa com Coletas, Clientes, Histórico e Mais; turno no topo da tela principal, paradas em cartões com ação de coleta destacada, clientes com endereço/navegação, formulário em três etapas visuais e histórico de hoje, sete dias ou seis meses com cliente, dia da semana e data. Fluxos de armazenamento, envio, assinatura e rastreamento preservados. Testes unitários Android, montagem da APK USB e lint aprovados; APK instalada como atualização sem apagar dados. A usabilidade visual e os toques nas abas ainda precisam de avaliação no aparelho pelo usuário.

- 30/09/2026: identidade visual do painel gestor aplicada ao Android: azul petróleo, laranja nas ações, fundo cinza claro, cartões brancos e ícones lineares nas quatro abas. Prévia web do motorista atualizada para representar a navegação atual e servir de demonstração visual sem aparelho. APK USB gerada, testes Android e lint aprovados; frontend compilado e prévia local disponível em `/previa-motorista.html`. Instalação desta atualização no celular aguarda reconexão do cabo.

- 30/09/2026: teste físico da nova tela encontrou indicador de turno desatualizado. API confirmou turno ativo e serviço Android em primeiro plano, mas o cartão dependia de uma variável do serviço que podia chegar após a renderização. O cartão agora mostra turno em andamento a partir do estado local ativo e oferece retomada de localização quando o serviço não estiver executando. Regressão Android adicionada; 30 testes e APK USB aprovados, atualização instalada sem limpar dados. A atualização da APK interrompe o serviço ativo; confirmar no aparelho o estado exibido e concluir/retomar turno no próximo teste.

- 30/09/2026: no retorno do teste, usuário confirmou o cartão `Finalizar turno` e `Retomar localização`. Consulta Android posterior encontrou o serviço de rastreamento em primeiro plano, mas a tela havia sido desenhada antes de o serviço sinalizar inicialização; API confirmou turno ativo, ainda sem posição recente neste teste. O cartão passa a mostrar `Ver situação da localização` durante turno aberto, evitando ação de retomada baseada em estado visual transitório. Testes Android e APK USB aprovados; instalar somente após encerrar o turno ativo para não interromper a captura durante a avaliação.

- 30/09/2026: durante a verificação da nova interface, o cabo USB deixou de ser detectado e o app informou servidor inacessível. O registro de coleta permaneceu `enviado` e a API confirmou `concluida`. O encerramento de turno ficou pendente enquanto o aparelho estava sem encaminhamento; após reconectar e usar `Enviar registros salvos`, a API retornou sem turno ativo nem posição. A APK com o botão `Ver situação da localização` foi então instalada com sucesso, preservando os dados. Ainda falta conferir visualmente essa versão e testar uma nova posição GPS real.

- 30/09/2026: novo turno no Samsung mostrou captura ativa e erro transitório `posição recusada pelo servidor (422)`. API confirmou depois posição recente aceita no mesmo turno; relógio do aparelho estava cerca de 11 segundos atrás do computador. O Android agora ignora leituras cuja captura preceda o início do turno, evitando a recusa inicial de uma posição guardada pelo provedor. Regressão e APK USB passaram; instalar a atualização após encerrar o turno de GPS atual, então repetir a abertura e o envio de posição.

- 30/09/2026: usuário confirmou `Último envio confirmado pelo servidor` no turno físico e o encerrou pelo aplicativo. API retornou sem turno ativo; a APK USB com a correção de leitura GPS anterior ao início foi instalada sem limpar dados e o encaminhamento USB restabelecido. A aceitação da posição confirma transmissão real neste turno; a prevenção do erro 422 ainda requer repetição em um novo turno com a APK atualizada.

- 30/09/2026: repetição com a APK corrigida: ao iniciar novo turno, o app exibiu `Aguardando uma nova leitura de localização` em vez de tentar enviar a leitura anterior. O serviço foreground permaneceu ativo; em seguida a API registrou posição recente, capturada após o início do turno. A confirmação visual do último envio e o encerramento deste novo turno ainda dependem da ação no aparelho.

- 30/09/2026: usuário confirmou a indicação de envio GPS no aparelho e finalizou o turno após a repetição com a APK corrigida. A API retornou sem turno ativo. Abertura, aceitação de nova posição e encerramento foram validados nesta versão; a duração e bateria em percurso real continuam pendentes.

- 30/09/2026: regressão da interface offline validada no Samsung. Nova revisita fictícia foi concluída sem cabo, apareceu como `Pendente` em Registros do aparelho e mudou para `Enviado` após reconectar e usar Mais → Enviar registros salvos. A API confirmou atendimento concluído, uma única revisita para a coleta de origem, um item de modalidade e comprovante do tipo assinatura com imagem PNG e hash presentes. O fluxo visual de Clientes e Histórico foi confirmado pelo usuário; ainda falta percurso real e bateria.

- 30/09/2026: fluxo físico de não atendimento da nova interface confirmado pelo usuário no histórico. A API registrou `nao_atendida` uma única vez; motivo preservado no evento auditado. Revisão detectou que o botão `Últimos 6 meses` consultava uma API limitada a 31 dias; limite ampliado para 184 dias inclusivos, teste de fronteira aprovado e consulta autenticada no servidor reiniciado retornou atendimentos com nome do cliente. A APK não precisou de alteração nesta correção.

- 30/09/2026: gestão de acessos administrativos entregue no painel. O administrador lista/cria/bloqueia/reativa usuários, redefine senhas e encerra sessões; cada usuário administrativo pode trocar a própria senha informando a atual. Tentativas de bloquear a própria conta ou alterar contas de outra empresa são recusadas. Validação: 57 testes backend, build frontend e smoke HTTP local de login/listagem aprovados. API local reiniciada; o painel segue disponível em `http://127.0.0.1:5173/`. Não houve alteração no APK nesta entrega. Permanecem recuperação sem administrador, gestão de empresa/modalidades, relatórios e os demais itens abertos.

- 30/09/2026: concluídos os três ajustes administrativos solicitados. Nome/fuso e modalidades gerenciáveis por administrador; recuperação autônoma por códigos de uso único; CSV/PDF filtrados com totais e proteção CSV; Visão do dia; melhorias de foco, teclado, estados e contraste. Migração 012 aplicada no banco local; provisionamento de empresa por CLI documentado em `docs/gestao-relatorios.md`. Validação: 61 testes backend completos, build do painel, smoke HTTP local de seis endpoints, renderização e leitura de PDF curto, multipágina e com 50 modalidades e inspeção da tela de recuperação em 360 px. APK Android não mudou. Restam as etapas 1/3/5/6/7/9/10 e testes físicos do piloto, sem considerar estes três ajustes pendentes.

- 30/09/2026: etapas abertas do roteiro detalhadas com resultado esperado, execução/verificação e dependências. A ordem prática destaca o que pode ser desenvolvido agora e o que depende de testes no Android, Google Cloud ou hospedagem.
