# Ambiente de homologação sem Docker

Status: configuração preparada, **não publicada**. Usuário informou em 27/09/2026 que ainda não possui hospedagem nem domínio. Nenhuma contratação, recurso pago, DNS ou banco remoto foi criado.

## Estrutura prevista

Uma instância Linux com Python 3.12+, ambiente virtual, painel estático compilado e Caddy; banco PostgreSQL/PostGIS separado dos dados de desenvolvimento e produção. Supabase é a preferência do projeto, mas migrações/permissões precisam ser validadas em banco de homologação antes da instalação. A configuração não presume superusuário no Supabase.

O painel usa https://DOMINIO e o campo Servidor do APK usa **https://DOMINIO/api**. O proxy remove /api antes de encaminhar ao backend. A API escuta apenas 127.0.0.1:8001. Não publicar Vite nem o PostgreSQL privado em .local.

O mapa simultâneo no painel requer `VITE_GOOGLE_MAPS_JS_KEY` e `VITE_GOOGLE_MAPS_MAP_ID` durante o build do frontend. Crie uma chave de navegador restrita à Maps JavaScript API e ao domínio HTTPS do painel; configure limites e alertas de custo no Google Cloud. Essas variáveis são públicas no bundle do navegador, portanto não use nelas chaves de servidor. Sem a configuração, o painel mantém a lista de motoristas, horário/precisão e links individuais do Google Maps. O mapa só exibe posições classificadas como recentes pela API; validar os pinos no piloto antes de depender deles para despachos.

## Instalação após escolha da infraestrutura

1. Preparar usuário de serviço coleta e checkout em /srv/coleta, sem .local nem credenciais do desenvolvedor. Instalar dependências Python de requirements.lock e o pacote local com pip install --no-deps -e . em .venv. Compilar frontend com npm ci e npm run build. O usuário caddy precisa ler frontend/dist.
2. Em banco exclusivo de homologação, validar/aplicar migrações por coleta_api.cli com ADMIN_DATABASE_URL administrativo e provisionar empresa fictícia. Credencial administrativa serve apenas à manutenção e não fica no serviço.
3. Criar papel de conexão NOSUPERUSER NOBYPASSRLS e membro de coleta_app. Conferir TLS e certificados do provedor. Instalar environment.example como /etc/coleta/homologacao.env com valores reais, segredo exclusivo aleatório e permissão 0600. Não versionar.
4. Instalar coleta-homologacao.service em systemd. Conferir com systemd-analyze verify, recarregar configuração e iniciar somente após validação do banco.
   Instalar também coleta-manutencao.service/timer. O arquivo `/etc/coleta/manutencao.env` deve conter `ADMIN_DATABASE_URL` somente para enumerar empresas e `DATABASE_URL` com o usuário de execução/RLS. Permissões 0600, acesso apenas ao usuário de serviço. O timer encerra turnos expirados, apaga posições fora de turno e expira chamados ainda sem aceite a cada cinco minutos. Conferir `systemctl list-timers coleta-manutencao.timer` e os logs do serviço.
5. Instalar Caddy, definir COLETA_DOMAIN no ambiente do serviço Caddy, apontar DNS à instância e liberar 80/443. Manter 8001 e banco sem exposição pública. Copiar Caddyfile e executar caddy validate --config /etc/caddy/Caddyfile antes de recarregar. HTTPS exige domínio resolvendo corretamente e emissão de certificado válida.
6. Executar python3 scripts/check-homologacao.py https://DOMINIO. Depois testar login, isolamento entre duas empresas fictícias, rubrica e leitura/gravação do banco.
7. Instalar .local/homologacao/coleta-homologacao.apk no Android. Informar https://DOMINIO/api e credenciais de motorista fictício.

O serviço usa um worker porque o limitador de login atual é em memória. Sem log de acesso Uvicorn; não habilitar logs de corpos, tokens ou coordenadas. Este preparo não substitui backups/restauração, monitoramento, assinatura de produção e revisão de segurança da etapa 9.

## Backup e restauração

`scripts/backup-db.py --directory /CAMINHO/PRIVADO` cria um dump customizado e confere sua estrutura. Execute com a `.venv` do projeto e `ADMIN_DATABASE_URL` somente em ambiente administrativo; a URL não aparece nos argumentos do `pg_dump`. O diretório deve existir com permissão 0700, estar em volume criptografado e fora do checkout/servidor principal. O script produz um manifesto SHA-256. `scripts/verify-backup.py ARQUIVO.dump` restaura em PostgreSQL temporário separado, conta as tabelas essenciais e verifica RLS; exige PostgreSQL/PostGIS locais. Um teste local de restauração foi aprovado, mas o procedimento precisa ser repetido com o banco remoto escolhido e armazenamento externo. Definir frequência, retenção, responsável, tempo de recuperação e perda máxima aceitável antes do piloto.

## Assinatura comercial

O código aceita chave de assinatura Android em variáveis de ambiente, fora do Git. `scripts/package-release.sh` exige `COLETA_KEYSTORE_FILE`, `COLETA_KEYSTORE_PASSWORD`, `COLETA_KEY_ALIAS` e `COLETA_KEY_PASSWORD`; compila, testa, executa lint e verifica a assinatura. A chave inicial foi criada em `.local/release/coleta-release.p12`, com configuração em `.local/release/signing.env` e permissões 0600. **Guarde duas cópias protegidas desses arquivos fora do computador antes de distribuir o APK**: perder a chave impede atualizar instalações comerciais com o mesmo identificador. `COLETA_VERSION_CODE` deve aumentar em toda atualização; `COLETA_VERSION_NAME` é o nome visível. A APK comercial usa HTTPS obrigatório e só deve ser distribuída quando o endereço da API estiver publicado e os testes físicos estiverem aprovados.

## APK de testes

Execute scripts/package-homologacao.sh. A variante staging tem identificador br.com.coleta.motorista.homologacao, nome Coleta Homologação, dados separados, não é depurável e rejeita HTTP. Usa assinatura debug local **somente para testes**; não é release comercial. Outra máquina pode usar chave diferente e impedir atualização por cima. Não desinstalar app com registros pendentes sem antes sincronizar/conferir.

build.json registra hash SHA-256, commit base e existência de alterações locais. APK e relatório não incluem credenciais nem URL fixa.

## Evidência de campo

Para cada aparelho, registrar modelo, Android, versão/hash APK, data, operador e configurações de bateria/localização. Usar dados fictícios e registrar somente resultado/horário, sem coordenadas pessoais em relatórios compartilhados.

- Login, carregar rota, salvar coleta/rubrica offline, reabrir, recuperar rede e confirmar envio único.
- Iniciar turno com permissão precisa e aproximada; comparar ponto conhecido com precisão exibida.
- Percurso com tela apagada e app em segundo plano; painel deve atualizar ou indicar posição antiga.
- Retirar/restaurar internet e GPS; não aceitar leitura antiga como atual.
- Revogar permissão; encerrar pela notificação, pelo app e por logout. Confirmar ausência de novas capturas e limpeza no servidor quando conectado.
- Encerrar offline, reconectar e confirmar encerramento; reiniciar/force-stop não pode reiniciar captura automaticamente.
- Comparar bateria antes/depois em períodos semelhantes com/sem rastreamento, anotando duração, sinal, uso do Maps e economia de bateria. Combinar meta de consumo com a transportadora após a primeira medição.
- Repetir nos quatro aparelhos do piloto. Falhas são corrigidas e retestadas; compilação não equivale a aprovação física.

## Referências de configuração

[Caddy: HTTPS automático](https://caddyserver.com/docs/automatic-https)
[Caddy: proxy e frontend no mesmo domínio](https://caddyserver.com/docs/caddyfile/patterns)
