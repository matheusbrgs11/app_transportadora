# Android — primeira implementação do motorista

Código nativo Kotlin, Android 8+ (API 26), com interface de componentes do sistema. **Ainda não compilado nem homologado em aparelho.** A máquina de desenvolvimento não possui Java, Gradle ou SDK Android. Esta entrega não é um APK pronto nem encerra a fase 3.

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

O script compila e executa lint; o APK esperado é `app/build/outputs/apk/debug/app-debug.apk`. Não há Gradle Wrapper incluído nesta versão; o script usa Gradle instalado no PATH.

Com telefone conectado por USB, depuração autorizada e platform-tools instalados:

```bash
adb reverse tcp:8000 tcp:8000
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Use `http://127.0.0.1:8000` como servidor no APK debug através desse encaminhamento USB. No emulador, use `http://10.0.2.2:8000`. O servidor local continua restrito ao computador; acesso direto pelo Wi-Fi ainda não foi configurado. Não use senha de administrador: crie um motorista pelo painel.

Reinicie o backend após atualizar o código para disponibilizar `/motorista/modalidades` e `/motorista/coletas`.

## Verificações pendentes no Android

Compilação/lint e teste no aparelho; perda de rede durante envio; encerramento do processo com pendências; troca de contas; resposta perdida após gravação no servidor; tela pequena/teclado; rotação durante formulário. Dados digitados e ainda não salvos não têm recuperação de rascunho.

Ainda faltam sincronização automática em segundo plano, login offline após reiniciar, assinatura, não atendimento/cancelamento, reconciliação de rota alterada, deduplicação de uma mesma parada entre aparelhos, rastreamento e notificações. Uma rota alterada antes do primeiro envio gera conflito; a fila mantém o registro para conferência da operação. Não há ferramenta de resolução desse conflito nesta primeira versão.
