# Ambiente de homologação sem Docker

Status: configuração preparada, **não publicada**. Usuário informou em 27/09/2026 que ainda não possui hospedagem nem domínio. Nenhuma contratação, recurso pago, DNS ou banco remoto foi criado.

## Estrutura prevista

Uma instância Linux com Python 3.12+, ambiente virtual, painel estático compilado e Caddy; banco PostgreSQL/PostGIS separado dos dados de desenvolvimento e produção. Supabase é a preferência do projeto, mas migrações/permissões precisam ser validadas em banco de homologação antes da instalação. A configuração não presume superusuário no Supabase.

O painel usa https://DOMINIO e o campo Servidor do APK usa **https://DOMINIO/api**. O proxy remove /api antes de encaminhar ao backend. A API escuta apenas 127.0.0.1:8001. Não publicar Vite nem o PostgreSQL privado em .local.

## Instalação após escolha da infraestrutura

1. Preparar usuário de serviço coleta e checkout em /srv/coleta, sem .local nem credenciais do desenvolvedor. Instalar dependências Python de requirements.lock e o pacote local com pip install --no-deps -e . em .venv. Compilar frontend com npm ci e npm run build. O usuário caddy precisa ler frontend/dist.
2. Em banco exclusivo de homologação, validar/aplicar migrações por coleta_api.cli com ADMIN_DATABASE_URL administrativo e provisionar empresa fictícia. Credencial administrativa serve apenas à manutenção e não fica no serviço.
3. Criar papel de conexão NOSUPERUSER NOBYPASSRLS e membro de coleta_app. Conferir TLS e certificados do provedor. Instalar environment.example como /etc/coleta/homologacao.env com valores reais, segredo exclusivo aleatório e permissão 0600. Não versionar.
4. Instalar coleta-homologacao.service em systemd. Conferir com systemd-analyze verify, recarregar configuração e iniciar somente após validação do banco.
5. Instalar Caddy, definir COLETA_DOMAIN no ambiente do serviço Caddy, apontar DNS à instância e liberar 80/443. Manter 8001 e banco sem exposição pública. Copiar Caddyfile e executar caddy validate --config /etc/caddy/Caddyfile antes de recarregar. HTTPS exige domínio resolvendo corretamente e emissão de certificado válida.
6. Executar python3 scripts/check-homologacao.py https://DOMINIO. Depois testar login, isolamento entre duas empresas fictícias, rubrica e leitura/gravação do banco.
7. Instalar .local/homologacao/coleta-homologacao.apk no Android. Informar https://DOMINIO/api e credenciais de motorista fictício.

O serviço usa um worker porque o limitador de login atual é em memória. Sem log de acesso Uvicorn; não habilitar logs de corpos, tokens ou coordenadas. Este preparo não substitui backups/restauração, monitoramento, limpeza periódica, assinatura de produção e revisão de segurança da etapa 9.

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
