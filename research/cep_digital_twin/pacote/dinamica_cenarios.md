# Dinâmica 1: cenários em que o DT apoia a Governança (grupo 4, AEB)

Tema do grupo: troca de mensagens no sistema AEB de veículo de passeio.

## Tabela de cenários

| Cenário | N/R | Descrição | Parâmetros considerados | Decisão da Gestão |
|---|---|---|---|---|
| Saúde da rede de mensagens | Operação normal | Espelha em tempo real a comunicação entre as ECUs (AEB, radar, lidar, câmera, freio, central) e verifica se está no comportamento nominal | latência, perda de mensagens, carga do barramento, alive counter, período das mensagens cíclicas | painel de KPIs; evidência de conformidade; linha de base dos riscos |
| Comportamento do motorista | Operação normal | Mede a frequência de alertas e como o motorista reage a eles | tempo de reação ao alerta, % de frenagens do motorista após o alerta, alertas por dia, desativações do AEB | calibração do alerta e melhoria da HMI |
| Degradação do sensor | Risco preventivo | Erros crescendo ou radar divergindo do lidar | erros/hora, tempo ligado, divergência radar × lidar, desalinhamento | agenda manutenção / recalibração |
| Degradação do barramento | Risco preventivo | Barramento instável, mensagens pouco confiáveis | carga/hora, variação de perdas/hora, jitter, período entre mensagens, error frames, bus-off | inspeção elétrica; revisão da matriz CAN |
| Ataque cibernético / injeção | Risco preventivo | Spoofing ou replay de mensagens CAN capazes de acionar ou desativar o AEB | falhas de autenticação, IDs estranhos, frequência anômala | aciona VSOC; isola ECU |
| Frenagem fantasma | Risco reativo | AEB freia sem obstáculo real (erro de percepção ou de comunicação) | desaceleração sem alvo confirmado, confiança da detecção, concordância radar × lidar × câmera, GPS, horário | análise de incidente; correção via OTA |
| Frenagem tardia (falso negativo) | Risco reativo | Mensagem atrasada/perdida e o AEB não freia ou freia tarde | timestamps, latência sensor → freio, TTC, velocidade relativa, DTC | causa raiz; OTA ou recall |
| Simulação what-if de condições extremas | Risco preventivo | Combinações ainda não vistas em campo (chuva, noite, barramento sobrecarregado, sensor fora) | visibilidade, atrito, carga do barramento, modo degradado, ASIL | plano de riscos (FMEA/HARA) |

## Não-risco (operação normal) monitorado pelo DT

Desempenho nominal da comunicação (linha de base); estatísticas de uso do AEB; comportamento do
motorista; rastreabilidade de versões e configuração (UN R156); evidência de conformidade (Euro NCAP,
auditoria); planejamento de capacidade da rede; custo de telemetria. O não-risco fornece a linha de
base, e o desvio dela dispara os cenários de risco.

## Divisão entre DT local e DT nuvem

| | DT local (ECU hospedeira) | DT nuvem |
|---|---|---|
| Papel | espelho de um veículo em tempo real | espelho da frota e do histórico |
| Escala de tempo | ms a segundos | horas a meses |
| Sem rede? | funciona | não precisa estar sempre conectado |
| Regras | frenagem tardia, frenagem fantasma, ataque, degradação do barramento | degradação do sensor, saúde da rede, comportamento do motorista |
| Saída | evento complexo + snapshot (±3 s) + agregados | painel, comparação de frota, what-if, validação de OTA, regras/limiares para a borda |

Critério: fica na borda o que precisa reagir em ms ou gera dado demais para enviar bruto; vai para a
nuvem o que depende de janela longa ou de comparar veículos.

## Pontos levados ao professor e à Ane

1. Em qual ECU roda o DT local: recomendação de uma ECU separada da ECU do AEB (freedom from
   interference, ISO 26262); se for a do AEB, vira requisito explícito.
2. O DT local observa, não comanda o freio.
3. Sem rede, o DT local bufferiza e envia quando a conexão volta.
4. A nuvem devolve regras e limiares ao DT local via OTA, fechando o ciclo.
