**IMPACTO DE EVENTOS ATRASADOS E FORA DE ORDEM NA SEGURANÇA DE SISTEMAS AEB**

Renato Silva Fagundes · Ane Varoto · Leopoldo Yoshioka · Reginaldo Arakaki

*Escola Politécnica da Universidade de São Paulo*

**RESUMO**

Sistemas de frenagem autônoma de emergência (AEB) dependem de fluxos de eventos que precisam chegar em tempo e na sequência esperada para que situações críticas sejam reconhecidas antes que o prazo de segurança se esgote. A telemetria, entretanto, está sujeita a atraso, desordenação, perda e períodos de desconexão, condições que podem transformar uma detecção tecnicamente correta em uma decisão tardia ou impedir o reconhecimento do padrão. Este artigo investiga como essas instabilidades afetam a latência de detecção, a cobertura das regras, a formação de evidências auditáveis e o desfecho físico da frenagem. A avaliação tem duas partes. Na primeira, 360 rodadas comparam uma arquitetura em que os eventos são processados apenas na nuvem com uma arquitetura distribuída, na qual as regras sensíveis ao tempo são executadas localmente. O processamento local decidiu os cenários reativos em 5 a 15 ms, contra latência p95 entre 80 ms e 2,3 s na nuvem; sob 90 s de desconexão, preservou 100 % das detecções e das trilhas de auditoria, diante de 68 % e 94 %, e reduziu em 9,7 vezes o volume transmitido. Na segunda, atraso e desordenação são variados isoladamente na cadeia de decisão de uma ECU AEB calibrada, no cenário Euro NCAP CCRs. A latência de detecção acompanhou o atraso um a um, o prazo experimental de 100 ms foi ultrapassado a partir de 200 ms e todas as rodadas colidiram com 1 s de atraso. A desordenação isolada não degradou a decisão de frenagem, mas gerou até 33 % de alarmes falsos em padrões de governança baseados na ausência de eventos, e a reordenação por K-slack converteu a desordem em atraso, reduzindo a distância de parada de 4,9 m para 1,9 m. Os resultados mostram que a posição do processamento e a política de ordenação dos eventos determinam a capacidade de reconhecer situações críticas dentro do prazo.

**PALAVRAS-CHAVE**

Processamento de Eventos Complexos; sistemas AEB; eventos atrasados; eventos fora de ordem; segurança funcional; gêmeo digital; computação de borda; auditabilidade; arquitetura de sistemas; telemetria; governança digital.

# 1. INTRODUÇÃO

A frenagem autônoma de emergência (Autonomous Emergency Braking, AEB) precisa reconhecer uma situação de risco e acionar o freio enquanto ainda existe tempo para evitar ou mitigar a colisão. Essa decisão é formada a partir de eventos produzidos por sensores, unidades de controle e barramentos veiculares. Quando um evento chega tarde, fora da sequência esperada ou não chega, o sistema pode interpretar de modo incompleto uma situação que evolui em milissegundos. Portanto, o problema não se limita à exatidão da regra: uma detecção correta, mas tardia, também representa uma falha relevante para a segurança \[1\].

O Processamento de Eventos Complexos (Complex Event Processing, CEP) permite correlacionar sinais simples e reconhecer padrões como frenagem tardia, frenagem sem obstáculo confirmado, degradação de sensor ou atividade anômala no barramento \[6\]. Porém, em ambientes distribuídos, o instante em que o evento ocorre e o instante em que ele chega ao processador nem sempre coincidem. A rede pode acrescentar atraso, alterar a ordem de chegada, provocar retransmissões ou interromper o fluxo. Mecanismos como buffers, marcas d'água e reordenação recuperam parte da correção, mas introduzem espera e consomem uma parcela do tempo disponível \[7, 8\].

A literatura descreve mecanismos para tratar eventos fora de ordem e modelos de implantação de gêmeos digitais na borda e na nuvem. Ainda é limitada, contudo, a evidência que relaciona degradação temporal, reconhecimento de padrões críticos e consequência para a governança de sistemas AEB. A questão que este trabalho busca responder é a seguinte: **como o atraso e a desordenação dos eventos afetam a detecção de situações críticas e o cumprimento do prazo de segurança, e em que medida o processamento local reduz essa exposição sem comprometer análises de janela longa?**

Cinco hipóteses orientam a investigação. As duas primeiras tratam diretamente dos efeitos temporais sobre o processamento de eventos. H1a estabelece que o aumento do atraso de entrega eleva a latência de detecção e a probabilidade de ultrapassar o prazo adotado para a decisão. H1b propõe que o aumento da desordenação eleva a incidência de padrões perdidos e falsos positivos quando os eventos são processados pela ordem de chegada ou ultrapassam a tolerância de atraso. As demais hipóteses avaliam a resposta da arquitetura proposta a essas condições. H2 verifica se o processamento local preserva a cobertura das regras durante desconexões; H3 avalia se a formação local das evidências mantém a completude da trilha de auditoria; e H4 examina se o envio de eventos complexos e dados agregados reduz o volume de telemetria sem prejudicar as análises de janela longa.

O artigo está organizado de modo a conectar a fundamentação conceitual ao desenvolvimento da arquitetura e à sua avaliação experimental, culminando na análise dos resultados, das limitações e das contribuições da pesquisa.

# 2. FUNDAMENTAÇÃO E TRABALHOS RELACIONADOS

## 2.1 Processamento de eventos e sistemas AEB

Um evento representa uma mudança observável no sistema, como a identificação de um obstáculo, a atualização da velocidade relativa ou a emissão de um comando de frenagem. Isoladamente, esses registros têm significado limitado. O CEP combina sequência, ausência, frequência e proximidade temporal para reconhecer uma situação de maior relevância \[6\]. No AEB, por exemplo, a relação entre a identificação do alvo, o cálculo do tempo para a colisão e o acionamento do freio forma um padrão crítico. O valor do processamento está, portanto, na interpretação conjunta dos eventos e no momento em que essa interpretação se torna disponível.

## 2.2 Atraso, desordenação e prazo de segurança

Sistemas distribuídos distinguem o tempo do evento, registrado na origem, do tempo de processamento, observado quando o evento chega ao motor CEP. A diferença entre esses instantes varia com a rede, as filas e as retransmissões. Como consequência, eventos posteriores podem chegar antes de eventos anteriores. Marcas d'água e limites de tolerância permitem aguardar os registros atrasados, mas criam um compromisso entre correção e latência \[7, 8\]. Em uma função associada à segurança, esse compromisso precisa respeitar o tempo disponível para detectar e controlar a condição perigosa. A ISO 26262 denomina esse intervalo de Fault Tolerant Time Interval (FTTI), cujo valor depende da análise de segurança do item \[1\]. Neste estudo, o limite de 100 ms é um parâmetro experimental e não deve ser interpretado como um FTTI universal para sistemas AEB.

## 2.3 Gêmeo digital, borda e governança

O gêmeo digital associa o sistema físico, sua representação virtual e o fluxo que mantém ambos sincronizados \[4, 5\]. Neste trabalho, ele organiza o estado observado, as regras CEP e as evidências produzidas por cada decisão. A computação de borda aproxima parte desse processamento da origem e reduz a dependência da rede \[10, 11, 12\]. A nuvem, por sua vez, conserva a visão histórica e permite comparar veículos e períodos. A combinação das duas camadas é especialmente relevante para a governança: decisões rápidas podem ser tomadas localmente, enquanto tendências, atualizações e auditorias permanecem apoiadas por uma visão consolidada.

## 2.4 Lacuna de pesquisa

Os estudos de CEP explicam como tratar eventos atrasados e fora de ordem \[7, 8\], enquanto os trabalhos sobre gêmeos digitais e borda discutem alternativas de implantação \[5, 9\]. Em geral, essas linhas não conectam o comportamento temporal do fluxo à detecção de situações críticas em AEB e às evidências necessárias para governar o sistema. A lacuna investigada é a ausência de uma avaliação que associe atraso, desordenação, latência de decisão, padrões perdidos, auditabilidade e desfecho físico, comparando o processamento centralizado com a execução local das regras mais sensíveis ao tempo.

# 3. MÉTODO DE PESQUISA

A pesquisa combina visão arquitetural e experimento controlado. Primeiro foram identificados os eventos, atores, decisões e evidências do sistema AEB. Em seguida, esses elementos foram convertidos em requisitos e regras CEP. Por fim, as hipóteses foram avaliadas em dois experimentos complementares. O Experimento 1 compara duas arquiteturas sob condições combinadas de rede e conectividade. O Experimento 2 isola o atraso e a desordenação na cadeia de decisão do AEB e mede o desfecho físico. A Tabela 1 relaciona as hipóteses às métricas e aos critérios utilizados.

Tabela 1. Hipóteses, métricas e critérios de análise.

| Hip. | Afirmação | Métrica | Critério | Exp. |
|---|---|---|---|---|
| H1a | O aumento do atraso de entrega eleva a latência de detecção e pode ultrapassar o prazo experimental. | latência de detecção; excedência de 100 ms; distância de parada; colisão | crescimento monotônico com o atraso; excedência e perda de margem | 1 e 2 |
| H1b | A desordenação e a chegada tardia aumentam padrões perdidos e falsos positivos. | níveis de frenagem perdidos; alarmes falsos; espera e descarte da política | aumento com a fração de eventos fora de ordem | 1 e 2 |
| H2 | O processamento local preserva a cobertura das regras durante desconexões. | proporção das falhas detectadas | A1 = 100 % sob offline longo | 1 |
| H3 | A formação local da evidência preserva a trilha de auditoria. | trilhas completas; tempo até a evidência | A1 = 100 % sob offline longo | 1 |
| H4 | Eventos complexos e agregados reduzem o volume sem prejudicar regras de janela longa. | bytes; mensagens; latência da degradação lenta | A1 ≤ 1/5 do volume; diferença ≤ 2 s | 1 |

**Experimento 1 (arquiteturas).** Combina duas arquiteturas, três perfis de rede e três condições de conectividade. A linha de base (A0) envia os eventos à nuvem antes de executar as regras. A proposta (A1) processa localmente as regras sensíveis ao tempo e encaminha à nuvem eventos complexos, evidências e indicadores agregados. Os perfis de rede representam condições boa (50 ms ± 10 ms, sem perda), média (150 ms ± 40 ms, 2 % de perda) e ruim (400 ms ± 120 ms, 10 % de perda). As janelas sem conectividade são inexistente, curta (30 s) e longa (90 s). Cada combinação foi repetida com 20 sementes, totalizando 360 rodadas de 240 s. A mesma semente gera o mesmo fluxo para A0 e A1, permitindo comparação pareada. Para evitar uma comparação artificialmente favorável à proposta, A0 utiliza reordenação por *timestamp* com limite de atraso igual à média acrescida de três vezes o *jitter*, procedimento compatível com o uso de marcas d'água em motores de fluxo \[8\], e as duas arquiteturas dispõem do mesmo buffer de retenção e reenvio, com 128 KB.

**Experimento 2 (atraso e desordenação isolados).** Reproduz a cadeia percepção → telemetria → ordenação → ECU → veículo no cenário Euro NCAP CCRs (alvo parado a 100 m, aproximação a 40 e 50 km/h) e perturba uma variável de cada vez. Para H1a, a ordem, o *jitter* e a perda são mantidos constantes e o atraso fixo assume 0, 25, 50, 100, 200, 400, 600, 800 e 1000 ms. Para H1b, a latência média é mantida em 100 ms, sem perda, e 0 %, 5 %, 10 % ou 20 % dos eventos recebem um atraso extra de 40 a 200 ms ou de 200 a 600 ms, o que os faz chegar fora de ordem. Três políticas de processamento são comparadas: ordem de chegada, marca d'água de tolerância fixa (150 ms, com descarte do que chega depois) e K-slack adaptativo (espera igual ao maior atraso relativo já observado). Cada célula tem 30 repetições. A referência de cada repetição é a rodada da mesma semente sem atraso e em ordem.

**Métricas.** No Experimento 1: latência entre o início da ocorrência e a decisão e seu percentil 95; proporção de padrões detectados; falsos positivos; completude e tempo de disponibilização da evidência; volume transmitido; descartes no buffer. No Experimento 2: latência de detecção do primeiro e do segundo nível de frenagem em relação à referência; fração das rodadas acima de 100 ms; margem temporal no primeiro comando de freio (tempo restante até o último instante em que 6 m/s² ainda evitaria a colisão); níveis de frenagem perdidos; liberações espúrias do freio; espera e descartes da política de ordenação; colisão, velocidade de impacto e distância de parada. No Experimento 2, um monitor CEP de governança recebe pelo mesmo canal as leituras e os comandos de freio e aplica dois padrões: "AEB sem reação" (tempo para colisão ≤ 3 s por mais de 0,2 s sem comando de freio conhecido, um padrão de ausência) e "frenagem fantasma" (comando de freio sem leitura de risco nos 300 ms anteriores). Um alarme de "sem reação" é falso quando a ECU de fato freou em até 0,2 s. Os dois experimentos são determinísticos e acompanhados de um procedimento de verificação que os reexecuta e confere as afirmações centrais deste artigo.

# 4. REQUISITOS DE GOVERNANÇA E ARQUITETURA

## 4.1 Atores, políticas e decisões

A governança envolve engenharia de segurança funcional, operações de cibersegurança, engenharia de software e manutenção. Essas áreas precisam compreender o que ocorreu, por que uma regra foi acionada e quais evidências sustentam uma ação de atualização, isolamento, manutenção ou *recall*. O motorista participa do sistema e seu comportamento pode orientar a calibração de alertas, embora não seja o responsável pelas decisões de governança. A Tabela 2 reúne os cenários considerados, os eventos correlacionados e a decisão apoiada por cada padrão.

Tabela 2. Cenários de governança apoiados pelo gêmeo digital no sistema AEB.

| Cenário | Tipo | Padrão CEP (eventos simples → complexo) | Parâmetros | Decisão da gestão |
|---|---|---|---|---|
| Saúde da rede de mensagens | Operação normal | A cada 10 s: p95 da latência, média da carga, soma das perdas, comparados ao nominal | latência, carga do barramento, mensagens perdidas, alive counter | painel de KPIs e evidência de conformidade; linha de base dos riscos |
| Comportamento do motorista | Operação normal | alerta seguido de freio do motorista → tempo de reação | tempo de reação, alertas por dia, desativações do AEB | calibração do alerta e melhoria da HMI |
| Degradação do sensor | Risco preventivo | erros crescendo na janela de 10 s, ou > 30 % das leituras radar/lidar divergindo > 15 % | erros/h, divergência radar × lidar, desalinhamento | agenda manutenção ou recalibração |
| Degradação do barramento | Risco preventivo | média da carga > 70 % ou > 5 mensagens perdidas em 10 s | carga, perdas, error frames, bus-off | inspeção elétrica, revisão da matriz CAN |
| Ataque cibernético | Risco preventivo | ≥ 5 mensagens em 1 s com ID desconhecido ou MAC inválido | falhas de autenticação, IDs inesperados, frequência anômala | aciona o VSOC, isola a ECU |
| Frenagem fantasma | Risco reativo | freio do AEB sem obstáculo confirmado pelo lidar nos 300 ms anteriores | desaceleração sem alvo, confiança da detecção, local e hora | análise de incidente; correção via OTA |
| Frenagem tardia | Risco reativo | comando de freio com latência sensor → atuador > 100 ms | timestamps, latência, TTC, velocidade relativa, DTC | causa raiz; OTA ou recall |

## 4.2 Requisitos e atributos de qualidade

Os requisitos da Tabela 3 derivam dos cenários e das referências normativas. Eles combinam quatro necessidades: executar políticas sobre o fluxo de eventos, conservar uma trilha reconstituível, responder dentro do prazo e continuar operando durante falhas de conectividade. A arquitetura deve, portanto, equilibrar desempenho temporal, tolerância a falhas e auditabilidade.

Tabela 3. Requisitos de governança e atributos de qualidade.

| ID | Requisito | Risco | Mecanismo | Métrica |
|---|---|---|---|---|
| RG1 | Políticas executáveis sobre o fluxo de eventos | Decisão fora da política; falha não reconhecida | Motor CEP com as regras da Tabela 2, na borda e na nuvem | Cobertura: fração das falhas injetadas detectadas |
| RG2 | Trilha auditável de cada decisão | Decisão não rastreável | Evento complexo + snapshot + agregados em repositório imutável | Completude da trilha; tempo até a evidência |
| RQ1 | Baixa latência de decisão nos cenários reativos | Ação tardia (prazo de segurança) | Processamento na borda, sem atravessar a rede | p95 do tempo falha → decisão (limite experimental de 100 ms) |
| RQ2 | Operar sem conectividade | Perda de detecção e de evidência em túneis e áreas sem cobertura | Gêmeo local autônomo; store-and-forward; snapshot local | Detecção e completude durante a janela offline |

# 5. ARQUITETURA PROPOSTA

## 5.1 Contexto, componentes e implantação

A Figura 1 apresenta o sistema como uma cadeia que liga o mundo físico à governança. Sensores e unidades de controle produzem eventos no veículo; o gêmeo local mantém o estado recente e executa as regras que não podem esperar pela rede; o gêmeo em nuvem consolida históricos, compara ocorrências e preserva evidências. A gestão recebe alertas e indicadores e pode devolver regras, limiares, atualizações ou ações de manutenção. A mesma figura mostra a alocação das regras CEP entre as duas camadas e o que atravessa a rede celular em cada sentido.

![](C:\Users\rfagu\Downloads\WhatsApp Image 2026-10-30 at 12.10.12.jpeg){width="6.3in"}

Figura 1. Contexto, componentes e implantação borda-nuvem: mundo real, gêmeo local, gêmeo em nuvem e governança.

O modelo de classes da Figura 2 representa essa integração. Eventos simples atualizam o estado observado e alimentam regras CEP. Quando uma combinação relevante é reconhecida, o sistema produz um evento complexo associado a um cenário de governança. As regras podem ser executadas localmente ou na nuvem, conforme a escala de tempo e a quantidade de dados requerida. A decisão permanece ligada à evidência que a originou, composta pelo evento complexo, pelo recorte temporal dos eventos simples e pelos indicadores do período.

![](C:\Users\rfagu\AppData\Local\Temp\claude\c--Users-rfagu-Estudo\ea1b3a81-fea8-4657-be1b-6371be5e76e3\scratchpad\v3_media/media/image2.png){width="6.0in"}

Figura 2. Modelo de classes reduzido: veículo, os dois gêmeos, motor CEP, evento complexo e gestão.

## 5.2 Fluxo de eventos e estado do Digital Twin

O fluxo começa quando uma mensagem do barramento é convertida em evento com origem, conteúdo e *timestamp*. As regras correlacionam esses registros em janelas temporais, sequências ou padrões de ausência. O estado mantém as últimas leituras e o histórico necessário para interpretar o contexto. Quando o padrão é reconhecido, o sistema registra a decisão, preserva a evidência e comunica a ocorrência à gestão. Um evento produzido localmente pode ser reutilizado na nuvem para correlações de maior alcance, como a recorrência da mesma anomalia em diferentes veículos. Assim, a borda responde à urgência e a nuvem amplia o contexto.

## 5.3 Controles de governança

A arquitetura adota controles para que a distribuição do processamento não reduza a governança. Regras e limiares enviados ao veículo devem ser autenticados e rastreáveis. O componente local observa o barramento, mas não substitui a ECU responsável pela frenagem, preservando a separação da função de segurança. Cada decisão mantém vínculo com os eventos e indicadores que a sustentam. Os dados enviados à nuvem são limitados ao necessário para análise e auditoria, e o padrão que originou cada alerta permanece explícito para engenheiros e auditores.

## 5.4 Critério de alocação borda-nuvem

A alocação das regras considera urgência e abrangência. Permanecem no veículo os padrões que exigem resposta em milissegundos ou dependem de grande volume de eventos recentes, como frenagem tardia, frenagem fantasma, ataque ao barramento e degradação rápida da comunicação. A nuvem recebe análises que dependem de períodos longos ou da comparação entre veículos, como tendências de sensor e comportamento do motorista. Durante uma desconexão, o resultado local e sua evidência são retidos e transmitidos quando a comunicação retorna. Os resultados do Experimento 2 acrescentam um terceiro critério: padrões que dependem da ordem ou da ausência de eventos devem ser executados onde o fluxo chega íntegro.

# 6. IMPLEMENTAÇÃO E ESTUDO DE CASO

O estudo de caso reproduz o fluxo de eventos de um sistema AEB e aplica as regras descritas na Tabela 2. O ambiente experimental gera leituras de radar e lidar, mensagens do barramento, alertas e comandos de frenagem. Também injeta situações controladas de frenagem tardia, frenagem sem obstáculo confirmado, degradação de sensor, degradação do barramento e atividade suspeita. O estado do sistema e as decisões são registrados com *timestamps*, permitindo reconstruir a sequência observada pelo processador.

A Figura 3 resume o Experimento 1. O gerador produz 240 s de eventos e registra a verdade de referência. O módulo de rede acrescenta atraso, *jitter*, perda, retransmissão e janelas sem conectividade. Em A0, o fluxo bruto atravessa a rede e é reorganizado antes da execução das regras na nuvem. Em A1, quatro regras sensíveis ao tempo são executadas localmente; a nuvem recebe o evento complexo, um recorte de evidências e indicadores agregados. As saídas incluem decisões por cenário, latência, cobertura, falsos positivos, volume transmitido e descartes. O código foi implementado em Python 3.12 e gera os dados e as figuras de maneira determinística.

![](C:/Users/rfagu/Estudo/dinamica_dt_aeb/resultados/fig_pipeline.png){width="5.4in"}

Figura 3. Blocos do simulador do Experimento 1: gerador, rede, as duas arquiteturas, medição e saídas.

A Figura 4 apresenta uma rodada com rede média e desconexão longa. Na linha de base, uma degradação do barramento ocorrida durante a interrupção não foi reconhecida porque parte dos eventos se perdeu no buffer; a degradação do sensor foi percebida somente após o retorno da rede. Na arquitetura proposta, as decisões locais foram produzidas durante a desconexão e comunicadas posteriormente. O exemplo evidencia a diferença entre o momento da detecção e o momento em que a gestão recebe a informação.

![](C:/Users/rfagu/Estudo/dinamica_dt_aeb/resultados/fig_linha_tempo.png){width="5.4in"}

Figura 4. Linha do tempo de uma rodada: falhas injetadas, janela offline e instantes de decisão em A0 e A1.

Durante a implementação, a linha de base foi ajustada para incluir reordenação por *timestamp*. Sem esse recurso, a chegada tardia do evento do lidar provocava perdas de padrão mesmo em condições favoráveis, o que tornaria a comparação pouco representativa. Também foi corrigida uma perda de pares radar/lidar na agregação por segundo. Esses ajustes asseguram que os resultados expressem o efeito da arquitetura e da degradação temporal, e não deficiências evitáveis da implementação.

O Experimento 2 reproduz a ECU com a calibração do firmware do projeto AEB de referência \[15\]: limiares de tempo para colisão de 4,0, 3,0, 2,2 e 1,8 s para alerta e para os três níveis de frenagem; pisos de distância de 20, 10 e 5 m; permanência mínima de 0,8 s em alerta antes de frear; histerese de 0,2 s para reduzir o nível; desacelerações de 2, 4 e 6 m/s² com rampa limitada; filtro de Kalman de dois estados; detector de variação abrupta que desliga o AEB após três leituras inconsistentes; e ciclo de 10 ms. A percepção publica distância e velocidade relativa a cada 20 ms com ruído gaussiano de 0,25 m. Sem atraso, o modelo para o veículo a 6,99 m do alvo a 40 km/h e a 5,68 m a 50 km/h, contra 5,3 m e 4,7 m registrados na bancada SIL do mesmo projeto. A diferença está dentro da variação da própria bancada entre execuções e não afeta as comparações, que são pareadas por semente.

# 7. RESULTADOS E DISCUSSÃO

## 7.1 Efeito do atraso sobre a decisão (H1a)

No Experimento 1, a Tabela 4 e a Figura 5 mostram que o processamento local reconheceu a frenagem tardia em 5 ms e a frenagem fantasma em 15 ms, independentemente do perfil da rede. Na linha de base, a latência média passou de 80 a 90 ms em rede boa para 280 a 313 ms em rede média e 880 a 957 ms em rede ruim. No percentil 95, a decisão alcançou 1,1 s na rede média e 2,3 s na rede ruim. O limite de 100 ms, parâmetro experimental deste estudo e não um FTTI normativo, foi ultrapassado já na rede média.

Tabela 4. Latência de decisão nos cenários reativos, sem janela offline (ms; 20 sementes).

| Cenário | Rede | A0 média | A0 p95 | A1 média | A1 p95 | Até a gestão p95 (A1) |
|---|---|---:|---:|---:|---:|---:|
| Frenagem tardia | boa | 80 | 80 | 5 | 5 | 70 |
| Frenagem tardia | média | 313 | 1083 | 5 | 5 | 1123 |
| Frenagem tardia | ruim | 957 | 2343 | 5 | 5 | 1535 |
| Frenagem fantasma | boa | 90 | 90 | 15 | 15 | 91 |
| Frenagem fantasma | média | 280 | 280 | 15 | 15 | 226 |
| Frenagem fantasma | ruim | 880 | 2296 | 15 | 15 | 2480 |
| Ataque cibernético | boa | 280 | 280 | 205 | 205 | 273 |
| Ataque cibernético | média | 475 | 520 | 205 | 205 | 438 |
| Ataque cibernético | ruim | 987 | 1105 | 205 | 205 | 1632 |

![](C:\Users\rfagu\AppData\Local\Temp\claude\c--Users-rfagu-Estudo\ea1b3a81-fea8-4657-be1b-6371be5e76e3\scratchpad\v3_media/media/image6.png){width="4.0in"}

Figura 5. Latência de decisão (p95) de frenagem tardia e fantasma por perfil de rede, sem offline; escala logarítmica.

O Experimento 2 isola o atraso e acrescenta o desfecho físico (Tabela 5 e Figura 6). A latência de detecção do primeiro nível de frenagem foi igual ao atraso injetado em todos os níveis e nas duas velocidades, porque a ECU decide sobre o quadro mais recente que recebeu e esse quadro é tão antigo quanto a telemetria. O limite de 100 ms foi ultrapassado em todas as rodadas a partir de 200 ms. A margem no primeiro comando de freio caiu 1 s para cada segundo de atraso, e a distância de parada a 50 km/h caiu de 5,68 m para 0,31 m entre 0 e 800 ms. Com 1000 ms, todas as rodadas colidiram, a 8,4 km/h (40 km/h) e 15,9 km/h (50 km/h). Entre 200 e 800 ms o padrão continua sendo reconhecido e o freio continua sendo acionado, mas a margem é consumida: é a região em que a detecção é correta e a decisão já é tardia. Correção lógica e oportunidade temporal são, portanto, propriedades distintas.

Tabela 5. Experimento 2, H1a: atraso isolado (30 sementes por célula; ordem, *jitter* e perda constantes).

| Atraso (ms) | Latência de detecção (ms) | Excede 100 ms | Margem no 1º freio, 50 km/h (s) | Dist. de parada 40 km/h (m) | Dist. de parada 50 km/h (m) | Colisões |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 0 % | 1,85 | 6,99 | 5,68 | 0 % |
| 25 | 30 | 0 % | 1,82 | 6,88 | 5,45 | 0 % |
| 50 | 50 | 0 % | 1,80 | 6,79 | 5,27 | 0 % |
| 100 | 100 | 0 % | 1,75 | 6,58 | 4,91 | 0 % |
| 200 | 200 | 100 % | 1,65 | 6,05 | 5,04 | 0 % |
| 400 | 400 | 100 % | 1,45 | 4,74 | 3,97 | 0 % |
| 600 | 600 | 100 % | 1,25 | 3,19 | 2,29 | 0 % |
| 800 | 800 | 100 % | 1,05 | 1,43 | 0,31 | 0 % |
| 1000 | 1000 | 100 % | 0,85 | colisão | colisão | 100 % |

![](C:\Users\rfagu\Estudo\dinamica_dt_aeb\resultados_h1\fig_h1a.png){width="6.3in"}

Figura 6. Experimento 2, H1a: latência de detecção, distância de parada e colisões em função do atraso da telemetria.

Dois efeitos secundários merecem registro. A distância de parada cai menos do que o produto velocidade × atraso porque, mais perto do alvo, a ECU escala os níveis de frenagem mais depressa pelos pisos de distância. E a partir de 400 ms, a 50 km/h, ocorre uma liberação antecipada do freio por rodada, porque a estimativa de distância da ECU fica atrasada em relação ao veículo real. O ponto não monotônico entre 100 e 200 ms a 50 km/h decorre da permanência mínima de 0,8 s em alerta: conforme o instante em que o limiar é cruzado, o atraso adicional recai ou não sobre essa espera.

Os resultados também confirmam H4. A redução do fluxo transmitido influenciou a resiliência. A1 enviou 95 KB e 256 mensagens por rodada, enquanto A0 enviou 917 KB e 14 674 mensagens, diferença de 9,7 vezes em bytes e 57 vezes em mensagens. Com menor pressão sobre o buffer, A1 atravessou 90 s de desconexão sem descartar registros. A análise de degradação lenta do sensor sofreu aproximadamente 1 s de atraso adicional por utilizar agregados de 1 s, permanecendo dentro do critério definido. O achado indica que nem toda regra precisa consumir o fluxo bruto: para fenômenos de evolução lenta, a agregação reduz a telemetria sem perda relevante de oportunidade.

Tabela 6. Volume, descartes, falsos positivos e detecção da degradação do sensor (rede média).

| Offline | Arq. | KB / rodada | Msgs / rodada | Descartes no buffer | Falsos positivos / rodada | Degradação do sensor: detecção / latência |
|---|---|---:|---:|---:|---:|---|
| nenhum | A0 | 917 | 14 674 | 0 | 0,10 | 100 % / 16,7 s |
| nenhum | A1 | 95 | 256 | 0 | 0,10 | 100 % / 17,7 s |
| curto | A0 | 917 | 14 674 | 0 | 0,65 | 100 % / 21,6 s |
| curto | A1 | 95 | 256 | 0 | 0,10 | 100 % / 22,0 s |
| longo | A0 | 917 | 14 674 | 3 459 | 0,75 | 70 % / 26,9 s |
| longo | A1 | 95 | 256 | 0 | 0,25 | 100 % / 45,9 s |

## 7.2 Efeito da desordenação e da desconexão (H1b, H2 e H3)

No Experimento 1, os resultados da Tabela 7 e da Figura 7 confirmam H2. Sem desconexão, a reordenação da linha de base foi suficiente para detectar todas as falhas. Após 30 s sem comunicação, a cobertura caiu para 95 % na frenagem fantasma e 90 % no ataque. Com 90 s, apenas 68 % dos cinco cenários de risco foram reconhecidos. As perdas ocorreram principalmente quando os eventos foram descartados ou retornaram em rajadas, tarde e fora da sequência exigida pelas janelas das regras. Nessas condições, os falsos positivos da linha de base aumentaram de 0,10 para até 0,90 por rodada. A1 manteve 100 % das detecções, pois as regras críticas observaram localmente o fluxo íntegro.

Tabela 7. Detecção das falhas de risco por janela offline (rede média). Entre parênteses, a detecção das falhas ocorridas dentro da janela e seu número.

| Cenário | A0, offline curto | A0, offline longo | A1, qualquer offline |
|---|---|---|---|
| Frenagem tardia | 100 % (100 %, n = 5) | 65 % (30 %, n = 10) | 100 % (100 %) |
| Frenagem fantasma | 95 % (0 %, n = 1) | 60 % (0 %, n = 8) | 100 % (100 %) |
| Ataque cibernético | 90 % (60 %, n = 5) | 75 % (44 %, n = 9) | 100 % (100 %) |
| Degradação do barramento | 100 % (100 %, n = 3) | 70 % (40 %, n = 10) | 100 % (100 %) |
| Degradação do sensor | 100 % (100 %, n = 3) | 70 % (73 %, n = 11) | 100 % (100 %) |

![](C:\Users\rfagu\AppData\Local\Temp\claude\c--Users-rfagu-Estudo\ea1b3a81-fea8-4657-be1b-6371be5e76e3\scratchpad\v3_media/media/image7.png){width="4.0in"}

Figura 7. Falhas de risco detectadas por janela offline, rede média, cinco cenários agregados.

A preservação da evidência, avaliada em H3, acompanha esse resultado. A1 manteve completas todas as trilhas de auditoria, pois o recorte temporal foi formado localmente e permaneceu no buffer até a reconexão. Em A0, 94 % das trilhas ficaram completas sob desconexão longa. O tempo de disponibilização precisa ser interpretado em conjunto com a completude: em A1, o percentil 95 chegou a 77 s porque a evidência foi entregue após a volta da rede; em A0, o valor de 19 s considera apenas os casos que permaneceram completos. Portanto, receber rapidamente uma evidência parcial não equivale a conservar uma trilha capaz de reconstituir a decisão. As regras de janela longa (saúde da rede e comportamento do motorista) foram reconhecidas em todas as condições pelas duas arquiteturas.

O Experimento 2 isola a desordenação, e a resposta a H1b depende do tipo de padrão (Tabela 8 e Figura 8). Na decisão de frenagem da ECU, processar na ordem de chegada não produziu nível de frenagem perdido nem colisão em nenhuma célula, mesmo com 20 % dos eventos fora de ordem e atrasos extras de até 600 ms; a distância de parada ficou a menos de 0,4 m da rodada ordenada. A razão é estrutural: um quadro antigo faz a estimativa de distância recuar, mas a ECU só reduz o nível depois de 0,2 s de histerese, e o quadro seguinte, 20 ms depois, restaura a estimativa. Para um padrão de limiar com histerese, H1b não se confirma.

Nos padrões de governança do monitor CEP, o resultado é o oposto. O padrão "AEB sem reação", que depende da ausência de um evento dentro de uma janela, gerou alarmes falsos em 3 % a 33 % das rodadas quando processado na ordem de chegada, porque o comando de freio chegou depois das leituras que ele deveria explicar. A marca d'água não eliminou o problema (3 % a 20 %) e, em uma rodada, descartou o próprio comando de freio. O padrão "frenagem fantasma" não gerou alarme falso, porque se apoia em leituras redundantes, quinze por janela. Para padrões de ausência e de sequência, H1b se confirma.

Tabela 8. Experimento 2, H1b: desordenação isolada a 50 km/h, latência média de 100 ms, atraso extra de 200 a 600 ms (30 sementes por célula).

| Fora de ordem | Política | Espera adicional (ms) | Descartados / rodada | Latência de detecção (ms) | Dist. de parada (m) | Liberações antecipadas | Alarmes falsos "sem reação" |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0 % | chegada | 0 | 0 | 100 | 4,91 | 0,00 | 0 % |
| 0 % | marca d'água | 50 | 0 | 150 | 4,99 | 0,00 | 0 % |
| 5 % | chegada | 0 | 0 | 97 | 5,10 | 0,03 | 10 % |
| 5 % | marca d'água | 70 | 21 | 150 | 5,04 | 0,00 | 7 % |
| 5 % | K-slack | 482 | 0 | 640 | 1,91 | 1,00 | 0 % |
| 10 % | chegada | 0 | 0 | 73 | 5,29 | 0,00 | 7 % |
| 10 % | marca d'água | 90 | 43 | 150 | 5,19 | 0,00 | 3 % |
| 10 % | K-slack | 485 | 0 | 632 | 1,99 | 1,00 | 0 % |
| 20 % | chegada | 0 | 0 | 61 | 5,31 | 0,00 | 7 % |
| 20 % | marca d'água | 130 | 81 | 150 | 5,37 | 0,00 | 20 % |
| 20 % | K-slack | 467 | 0 | 600 | 2,31 | 1,00 | 0 % |

![](C:\Users\rfagu\Estudo\dinamica_dt_aeb\resultados_h1\fig_h1b_200-600.png){width="6.3in"}

Figura 8. Experimento 2, H1b: alarmes do monitor, liberações antecipadas, espera adicional e distância de parada por política de ordenação.

As políticas de correção têm custo próprio. A marca d'água acrescentou de 50 a 130 ms de espera e descartou de 4 % a 19 % dos quadros, sem efeito sobre o desfecho físico. O K-slack adaptativo, que ajusta a espera ao maior atraso observado, acrescentou cerca de 480 ms; a latência de detecção subiu para 600 a 640 ms, a distância de parada caiu de 4,91 m para 1,9 a 2,3 m e houve uma liberação antecipada do freio por rodada. Não houve colisão na velocidade testada, mas a margem foi quase toda consumida. Nesse caso o monitor emitiu o alarme "sem reação" em praticamente todas as rodadas, e nenhum deles é falso: a ECU de fato demorou mais de 0,2 s para frear, por causa da própria política de ordenação. Corrigir a ordem comprando tempo devolve o sistema à curva de H1a.

## 7.3 Discussão integrada e limitações

Os resultados confirmam H1a com desfecho físico: o atraso da telemetria se transfere integralmente para a latência de decisão, ultrapassa o limite experimental a partir de 200 ms, consome a margem de segurança e leva à colisão em 1 s. H1b foi refinada: a desordenação isolada não degrada a decisão de frenagem, protegida pela histerese e pela taxa de atualização, mas degrada os padrões de governança que dependem da ausência ou da sequência de eventos; e as políticas que restauram a ordem cobram em tempo (K-slack) ou em eventos descartados (marca d'água), sendo a primeira a mais danosa porque reinsere o atraso de H1a no caminho crítico. H2, H3 e H4 foram confirmadas no Experimento 1. Para a arquitetura, o conjunto reforça o critério de alocação: a decisão de frenagem deve permanecer na ECU, sem política de reordenação, e os padrões de governança sensíveis à ordem devem ser executados onde o fluxo chega íntegro ou, na nuvem, com tolerância limitada e com o comando de freio protegido contra descarte.

Esses achados devem ser lidos à luz de cinco limitações. Primeiro, atraso gaussiano e perda independente simplificam o comportamento de redes reais. Segundo, o buffer de 128 KB influencia a quantidade de eventos descartados durante desconexões longas. Terceiro, os tamanhos atribuídos às mensagens são estimativas. Quarto, no Experimento 2 o veículo é cinemático e o ruído de percepção é gaussiano; apenas duas velocidades e um cenário Euro NCAP foram usados, e a marca d'água foi testada com uma única tolerância. Quinto, o modelo da ECU para o veículo de 1 a 1,7 m antes da bancada SIL, o que torna conservadores os valores absolutos de distância de parada.

## 7.4 Validação na bancada SIL

Os protocolos de H1a e H1b estão sendo repetidos na bancada SIL do projeto de referência \[15\], que executa o código C da ECU em Zephyr, com barramento CAN emulado e dinâmica veicular em Gazebo/ROS 2. O relé do barramento recebeu um estágio de perturbação que atrasa, desordena e reordena (por ordem de chegada, marca d'água ou K-slack) os quadros de percepção antes de entregá-los à ECU, e registra os instantes de entrada e saída de cada quadro. O plano compreende H1a completo (nove níveis de atraso, 30 repetições, CCRs a 50 km/h) e H1b reduzido (atraso extra de 200 a 600 ms, quatro frações de desordem, três políticas, 10 repetições). Além de confirmar o limiar de colisão e a robustez da decisão à desordem com a dinâmica do Gazebo, a bancada expõe um efeito que a simulação não modela: a ECU supervisiona a chegada do quadro de percepção e desliga o AEB se ele faltar por 60 ms, de modo que descartes e esperas longas podem desativar a função.

# 8. CONCLUSÃO

Este artigo investigou como eventos atrasados e fora de ordem afetam a detecção de situações críticas em um sistema AEB. No Experimento 1, o processamento na nuvem apresentou latências p95 de até 2,3 s à medida que a rede se degradou, enquanto o processamento local manteve decisões de 5 a 15 ms para os cenários reativos; sob desconexão longa, a cobertura da linha de base caiu para 68 % e a completude das trilhas para 94 %, ao passo que a arquitetura distribuída preservou ambas em 100 % e transmitiu 9,7 vezes menos dados. No Experimento 2, o atraso isolado se transferiu integralmente para a decisão e levou à colisão com 1 s, e a desordenação isolada mostrou efeitos distintos conforme o padrão: inócua para a decisão de frenagem, mas geradora de alarmes falsos nos padrões de governança baseados em ausência de eventos, enquanto a reordenação por K-slack converteu desordem em atraso e consumiu a margem de segurança.

A principal contribuição é relacionar propriedades temporais do fluxo, reconhecimento de padrões, governança e desfecho físico em uma mesma avaliação arquitetural, e derivar dela um critério de alocação: decisões de segurança na borda, sem reordenação; padrões de governança sensíveis à ordem onde o fluxo chega íntegro; análises de janela longa na nuvem, sobre agregados. A validação na bancada SIL, em andamento, deverá confirmar o limiar de atraso a partir do qual uma detecção ainda correta deixa de evitar a colisão e verificar como a supervisão de tempo da própria ECU interage com as políticas de ordenação.

# REFERÊNCIAS

\[1\] ISO. ISO 26262:2018, Road vehicles -- Functional safety. Geneva: International Organization for Standardization, 2018.

\[2\] UNECE. UN Regulation No. 155 -- Uniform provisions concerning the approval of vehicles with regards to cyber security and cyber security management system. Geneva: United Nations Economic Commission for Europe, 2021.

\[3\] UNECE. UN Regulation No. 156 -- Uniform provisions concerning the approval of vehicles with regards to software update and software updates management system. Geneva: United Nations Economic Commission for Europe, 2021.

\[4\] Grieves, M.; Vickers, J. Digital Twin: Mitigating unpredictable, undesirable emergent behavior in complex systems. In: Kahlen, F.-J.; Flumerfelt, S.; Alves, A. (eds.). Transdisciplinary Perspectives on Complex Systems. Cham: Springer, 2017. p. 85-113.

\[5\] Tao, F.; Zhang, H.; Liu, A.; Nee, A. Y. C. Digital Twin in industry: state-of-the-art. IEEE Transactions on Industrial Informatics, v. 15, n. 4, p. 2405-2415, 2019.

\[6\] Cugola, G.; Margara, A. Processing flows of information: from data stream to complex event processing. ACM Computing Surveys, v. 44, n. 3, art. 15, 2012.

\[7\] Li, J.; Tufte, K.; Shkapenyuk, V.; Papadimos, V.; Johnson, T.; Maier, D. Out-of-order processing: a new architecture for high-performance stream systems. Proceedings of the VLDB Endowment, v. 1, n. 1, p. 274-288, 2008.

\[8\] Akidau, T. et al. The Dataflow Model: a practical approach to balancing correctness, latency, and cost in massive-scale, unbounded, out-of-order data processing. Proceedings of the VLDB Endowment, v. 8, n. 12, p. 1792-1803, 2015.

\[9\] Minerva, R.; Lee, G. M.; Crespi, N. Digital Twin in the IoT context: a survey on technical features, scenarios, and architectural models. Proceedings of the IEEE, v. 108, n. 10, p. 1785-1824, 2020.

\[10\] Shi, W.; Cao, J.; Zhang, Q.; Li, Y.; Xu, L. Edge computing: vision and challenges. IEEE Internet of Things Journal, v. 3, n. 5, p. 637-646, 2016.

\[11\] Bonomi, F.; Milito, R.; Zhu, J.; Addepalli, S. Fog computing and its role in the Internet of Things. In: Proceedings of the First Edition of the MCC Workshop on Mobile Cloud Computing. New York: ACM, 2012. p. 13-16.

\[12\] Satyanarayanan, M. The emergence of edge computing. Computer, v. 50, n. 1, p. 30-39, 2017.

\[13\] ISO/IEC. ISO/IEC 25010:2011, Systems and software engineering -- Systems and software Quality Requirements and Evaluation (SQuaRE) -- System and software quality models. Geneva, 2011.

\[14\] Euro NCAP. Test Protocol -- AEB Car-to-Car systems. Leuven: European New Car Assessment Programme, 2023.

\[15\] AEB Stellantis Project. Bancada SIL de frenagem autônoma de emergência com ECU virtual Zephyr, CAN emulado e Gazebo/ROS 2. UFPE/Stellantis. Disponível em: https://github.com/erycaaf/AEB-stellantis-project.
