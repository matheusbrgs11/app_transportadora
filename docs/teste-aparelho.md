# APK pronto para iniciar testes funcionais

Esta entrega prepara testes, não declara homologação física nem produto comercial concluído.

## Pacotes

- Coleta Teste USB: .local/homologacao/coleta-teste-usb.apk. Identificador próprio, dados separados. HTTP permitido exclusivamente para 127.0.0.1; encaminhamento ADB para a API local. Servidor já preenchido no login.
- Coleta Homologação: .local/homologacao/coleta-homologacao.apk. HTTPS obrigatório; precisa de backend publicado. Informar URL da API, incluindo /api quando usado o proxy preparado.
- Ambos usam chave debug local para testes, sem depuração do aplicativo habilitada. Não são releases comerciais.

## Preparar sem conectar aparelho

Executar scripts/prepare-device-test.py com a API local ativa. Cria empresa isolada com motorista, cliente e rota fictícios para todos os dias. Pode ser repetido sem recriar cadastros; nunca usa a empresa operacional do piloto. As credenciais ficam exclusivamente em .local/acesso-aparelho.txt e .local/device-test.json, com permissão 0600 e fora do Git.

O endereço do cliente é fictício: não usar para navegação. Para validar Maps, cadastrar posteriormente um ponto de teste conhecido e consentido.

## Quando iniciar a homologação física

1. Configurar bloqueio por PIN/senha no Android. Ativar depuração USB e autorizar o computador.
2. Executar scripts/install-android-usb.sh. Não desinstala nem limpa dados, não concede permissões automaticamente; exige um aparelho autorizado ou serial explícito.
3. Abrir Coleta Teste USB e entrar como motorista usando o arquivo de acessos.
4. Confirmar rota do dia. Registrar coleta com modalidade/volume e rubrica ou justificativa; conferir no painel com administrador da mesma empresa fictícia.
5. Testar pendência offline removendo encaminhamento/cabo, salvar outro atendimento e reconectar. Recriar encaminhamento, enviar e verificar que há somente uma coleta no histórico. Para novo atendimento na mesma parada concluída, criar revisita pelo painel.
6. Abrir Turno e localização, conceder permissões e iniciar. Tela mostra estado do último envio e horário de confirmação (consultar Atualizar situação). Conferir horário/precisão no painel.
7. Encerrar turno online e offline; ao sincronizar manualmente, encerramentos pendentes também são enviados.
8. Testar bloqueio/reabertura, rubrica, teclado, fila, rejeições e troca de conta. Não apagar o app com pendências.

Cabo USB alimenta o aparelho: consumo de bateria e percurso na rua devem ser homologados com backend HTTPS remoto, sem cabo. O fluxo online depende do computador ligado enquanto usado o pacote USB.

## Recursos ainda pendentes

Chamados imprevistos com aceite/notificação, mapa integrado/geocodificação, administração/relatórios completos, infraestrutura Supabase/hospedagem, backup/restauração, limpeza agendada e release comercial assinado. Homologação real de localização/bateria e piloto continuam obrigatórios; consultar ROADMAP.md.
