# Android — primeira implementação do motorista

Código nativo Kotlin, Android 8+ (API 26), com interface de componentes do sistema. **APK debug compilado; homologação em aparelho pendente.** Java 17, Gradle 8.11.1 e SDK 35 foram configurados localmente em `.local/toolchains`, fora do Git. A compilação não encerra a fase 3.

## Fluxo implementado no código

- Login com servidor, empresa, usuário e senha; apenas perfil motorista.
- Consulta da rota de hoje com paradas ordenadas, endereço, telefone e janela de atendimento.
- Cache da rota e modalidades em SQLite privado. A tela informa a data e impede novas visitas usando um planejamento de outro dia.
- Seleção de várias modalidades e quantidade inteira; campo vazio significa `a_conferir`.
- Cada visita recebe um UUID e é gravada primeiro em SQLite. Somente a confirmação HTTP marca o registro como enviado. Falha de rede ou rejeição preserva o conteúdo original e mostra o erro.
- Envio após salvar e botão para tentar novamente. Cache e fila separados por servidor, empresa e usuário.
- Sessão somente em memória; não armazena senha/token. Reiniciar o processo exige novo login online. Após autenticar na mesma conta, os registros pendentes reaparecem. A sessão expirada exige novo login para enviar.
- Backup Android desativado. Versão principal exige HTTPS; apenas debug permite HTTP para desenvolvimento.

## Compilar sem Android Studio

Requisitos fixados: JDK 17, Gradle 8.11.1, SDK `platforms;android-35` e `build-tools;35.0.0`. Android Gradle Plugin 8.9.2 e Kotlin 2.1.20 estão fixados nos arquivos do projeto. Consulte a [compatibilidade oficial do AGP](https://developer.android.com/build/releases/agp-8-9-0-release-notes).

Instale as ferramentas de linha de comando oficiais, configure `ANDROID_HOME` e o PATH de Java/Gradle e execute:

```bash
./build-debug.sh
```

Na máquina configurada, o script carrega automaticamente `scripts/android-env.sh`. Em outra máquina, instale as ferramentas e configure o ambiente. O script compila e executa lint; o APK esperado é `app/build/outputs/apk/debug/app-debug.apk`. Não há Gradle Wrapper incluído nesta versão; o script usa Gradle instalado no PATH.

Com telefone conectado por USB, depuração autorizada e platform-tools instalados:

```bash
adb reverse tcp:8000 tcp:8000
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Use `http://127.0.0.1:8000` como servidor no APK debug através desse encaminhamento USB. No emulador, use `http://10.0.2.2:8000`. O servidor local continua restrito ao computador; acesso direto pelo Wi-Fi ainda não foi configurado. Não use senha de administrador: crie um motorista pelo painel.

Reinicie o backend após atualizar o código para disponibilizar `/motorista/modalidades` e `/motorista/coletas`.

## Verificações pendentes no Android

Teste no aparelho; perda de rede durante envio; encerramento do processo com pendências; troca de contas; resposta perdida após gravação no servidor; tela pequena/teclado; rotação durante formulário. Rascunhos de volumes e observações agora são persistidos por conta e atendimento; rascunhos da versão anterior continuam recuperáveis na primeira tentativa. Podem ser recuperados após novo login ao abrir a mesma parada; não são enviados até salvar a coleta.

Ainda faltam sincronização automática em segundo plano, login offline após reiniciar, assinatura, ferramenta de resolução dos conflitos, rastreamento e notificações. Nas novas execuções, o planejamento é preservado mesmo que a rota recorrente mude. Filas antigas sem coleta_id podem exigir conferência operacional, mantendo os registros. Não há ferramenta de resolução desse conflito nesta primeira versão.


## Testes econômicos sem emulador completo

Execute `../scripts/test-android.sh` a partir desta pasta. Robolectric simula APIs Android na JVM; não exige KVM. Gradle usa no máximo dois workers e os testes um processo com heap de 1 GB. Primeira execução baixa dependências; próximas reutilizam cache.

Em 26/09/2026, 8 testes passaram na API 28, com APK recompilado e lint executado. Os testes cobrem armazenamento SQLite, isolamento, migração, confirmação de envio e recuperação de falhas. Não equivalem a homologação visual, GPS, bateria, sincronização automática ou Android → API real → painel.

Conflitos 403/404/409/422 preservam o registro como `conflict` e deixam os demais seguirem. O botão de envio tenta novamente os registros não confirmados; falhas de rede e autenticação interrompem o lote sem excluir dados. Uma resposta sem confirmação válida não marca a coleta como enviada.

Ao atualizar a rota, o app prepara os atendimentos diários e recebe IDs estáveis. O registro envia `coleta_id` e conclui a mesma coleta exibida no painel. Visitas finalizadas no servidor aparecem sem botão de nova coleta após atualização. Exige backend com migração 006.

## Operação diária — 26/09/2026

- A rota mostra tentativa e progresso no servidor. O progresso pode estar desatualizado enquanto offline; registros salvos localmente são indicados separadamente.
- Não atendimento exige motivo, não aceita volumes e é salvo na mesma fila SQLite antes do envio. Na API, `concluida_em` transporta o instante da ocorrência por compatibilidade do payload; a coleta não recebe data de conclusão e o instante fica no evento auditado.
- Revisitas têm outro `coleta_id`, evitando que a primeira tentativa esconda o botão da próxima. Só a operação pode criá-las.
- Atendimentos transferidos aparecem ao atualizar a rota. Um envio do motorista anterior recusado com 404 é preservado como conflito; os demais continuam.
- Histórico próprio de hoje ou dos últimos sete dias consultado online, com paginação de 50 registros. Ele não substitui a fila local nem inclui envios ainda não aceitos.
- Cancelamento continua exclusivo do painel administrativo. Não há reabertura destrutiva do registro anterior.

Teste de tela Robolectric: primeira tentativa concluída, revisita disponível, preenchimento do motivo e gravação offline pela interface. Ainda não é validação ponta a ponta com servidor real ou homologação em aparelho.

Validação final desta entrega: 12 testes Robolectric aprovados (11 de armazenamento/sincronização e 1 de tela), APK debug e lint aprovados. Backend correspondente: 43 testes de integração aprovados.
