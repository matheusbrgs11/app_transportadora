# Rastreamento por turno

O motorista abre **Turno e localização**, autoriza localização/notificações e inicia a captura. Requer login com acesso lembrado e bloqueio do aparelho. A notificação permite encerrar. Intervalos disponíveis: 30/60/120/300 segundos, sujeitos aos provedores e restrições Android.

O painel consulta a cada 15 segundos enquanto visível. Mostra horário da captura, precisão, posição antiga após 120 segundos e indisponibilidade da conexão. O link abre a última coordenada no Google Maps. Mapa incorporado simultâneo permanece pendente.

## Retenção e limites

- Apenas última posição por motorista, sem histórico de percurso nem fila local de GPS.
- Turno expira em 12 horas. Captura exige sessão válida; encerramento/logout interrompem o serviço. Processo terminado pelo Android não reinicia automaticamente.
- Sem rede, encerrar para a captura imediatamente. O encerramento no servidor aguarda sincronização com sessão válida; a posição anterior envelhece até confirmação ou expiração.
- Posição apagada ao encerrar no servidor. Turnos expirados são limpos no próximo acesso aos endpoints de consulta/início. Limpeza periódica independente de acessos ainda precisa ser configurada em produção.
- Início exige rede. Existe um turno por motorista, inclusive entre aparelhos.
- Precisão acima de 1.000 metros é recusada. Intervalos maiores que 120 segundos podem mostrar posição antiga entre envios.
- Revogação no servidor é detectada no próximo envio; offline, vale expiração local.

## Homologação pendente

Testar Android físico, inclusive 14+: início visível, tela desligada, economia de bateria, permissões aproximada/precisa/revogadas, perda de rede/GPS, encerramento pela notificação, troca de conta, reinício/force-stop e consumo por turno. Robolectric e compilação não validam GPS, Doze ou consumo real.
