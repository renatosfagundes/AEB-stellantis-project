**IMPACTO DE EVENTOS ATRASADOS E FORA DE ORDEM NA SEGURANÇA DE SISTEMAS AEB**

Renato Silva Fagundes · Ane Varoto · Leopoldo Yoshioka · Reginaldo Arakaki

*Escola Politécnica da Universidade de São Paulo*

**RESUMO**

Sistemas de frenagem autônoma de emergência (AEB) decidem a partir de eventos de percepção que precisam chegar a tempo e em ordem. Este artigo avalia como o atraso e a desordenação desses eventos, e a política usada para reordená-los, alteram a resposta de frenagem de uma ECU AEB e a confiabilidade de um monitor de Processamento de Eventos Complexos (CEP) usado para governança. A ECU é especificada por um modelo longitudinal com filtro de Kalman, máquina de estados por tempo para colisão (TTC), rampa de frenagem e supervisão de comunicação de 60 ms, e avaliada em dois experimentos no cenário Euro NCAP CCRs a 50 km/h: um modelo em Python e uma bancada software-in-the-loop (SIL) que executa o firmware C da ECU em Zephyr com dinâmica em Gazebo. Foram 900 rodadas válidas na bancada, auditadas contra a perturbação definida. O atraso se transfere para a latência de frenagem e, com 1 s, levou à colisão em 77 % das rodadas (23/30). A desordenação, mantida a latência média em 100 ms, levou a supervisão de comunicação a desligar o AEB: com 20 % dos quadros fora de ordem, 40 % das rodadas colidiram processando pela ordem de chegada e 53 a 60 % com marca d'água, contra 3 a 13 % com K-slack, que em troca acrescentou de 360 a 670 ms de latência. No monitor CEP, padrões baseados na ausência de eventos produziram até 17 % de alarmes falsos. Supervisão temporal e política de ordenação precisam, portanto, ser dimensionadas em conjunto.

**PALAVRAS-CHAVE**

Processamento de Eventos Complexos; frenagem autônoma de emergência; eventos fora de ordem; segurança funcional; software-in-the-loop; gêmeo digital.

# 1. INTRODUÇÃO

A frenagem autônoma de emergência (Autonomous Emergency Braking, AEB) precisa reconhecer uma situação de risco e frear enquanto ainda há distância para evitar ou mitigar a colisão. A decisão é formada a partir de eventos de percepção que trafegam pelo barramento do veículo e, em arquiteturas conectadas, por redes sem fio, sujeitas a atraso, desordem e perda. O AEB é requisito regulamentar para veículos novos \[1\], tem desempenho especificado por normas e protocolos de ensaio \[2, 3\] e reduz as colisões traseiras em campo \[4, 5\]. Uma detecção correta, mas tardia, também é uma falha de segurança: a ISO 26262 limita o tempo entre a falha e o estado seguro pelo intervalo de tolerância a falhas (FTTI), definido para cada item \[6\]. O Processamento de Eventos Complexos (CEP) correlaciona eventos simples para reconhecer padrões como "freio sem obstáculo confirmado" ou "risco sem reação" \[7, 8\], e trata a desordem por esperas limitadas, como pulsações, pontuação, K-slack e marcas d'água, que recuperam a ordem ao custo de latência \[9, 10, 11, 12, 13\]. Gêmeos digitais distribuídos entre o veículo e a nuvem usam esses padrões para governança, isto é, para gerar alertas, evidências e decisões de manutenção ou atualização \[14, 15, 16, 17\].

Os estudos de CEP quantificam o compromisso entre correção e latência sem relacioná-lo à consequência física de um sistema de segurança; a teoria de controle em rede trata o atraso no laço, mas não a desordem nem os mecanismos discretos de supervisão \[18, 19\]; e os estudos de AEB raramente tratam a ordem dos eventos. Este artigo responde à pergunta: **como o atraso, a desordenação e a política de ordenação dos eventos de percepção alteram a resposta de frenagem de uma ECU AEB e a confiabilidade de um monitor CEP de governança?** Duas hipóteses orientam a investigação. H1a: o aumento do atraso eleva a latência até o freio e reduz a distância remanescente ao alvo. H1b: o aumento da desordenação eleva os padrões perdidos, os alarmes falsos e as falhas de frenagem quando os eventos são processados pela ordem de chegada ou ultrapassam a tolerância de espera. As contribuições são (i) uma especificação do modelo AEB e de suas simplificações; (ii) um protocolo que isola atraso e desordem e audita a perturbação efetivamente aplicada; (iii) evidência, em modelo e em bancada com o firmware real, de que a supervisão de comunicação da ECU converte desordem em indisponibilidade da função.

# 2. MODELO AEB E HIPÓTESES DE SIMPLIFICAÇÃO

O sistema estudado é a ECU AEB de um projeto acadêmico de referência \[20\], escrita em C99 para Zephyr e calibrada para os cenários Euro NCAP Car-to-Car \[3\]. A Figura 1 mostra o cenário e o caminho do sinal, com os pontos de perturbação e de medição.

![](C:/Users/rfagu/Estudo/dinamica_dt_aeb/resultados_tikz/fig_cenario.png){width="5.7in"}

Figura 1. Cenário CCRs (ego a 50 km/h, alvo parado) e caminho do sinal: percepção, canal com perturbação, política de ordenação, ECU e veículo; o monitor CEP recebe pelo mesmo canal as leituras e os comandos de freio.

**Dinâmica.** O movimento é longitudinal. Com distância livre d entre os para-choques e velocidade de aproximação v > 0, ḋ = −v, v̇ = −a, e TTC = d/v \[21\], definido apenas para v > 0,5 m/s; abaixo disso a ECU considera não haver aproximação. No modelo, o estado é integrado por Euler com passo de 10 ms e v é saturada em zero; na bancada, o Gazebo integra a 1 kHz um veículo com velocidade imposta (sem modelo de pneu), e o controlador do cenário aplica a desaceleração comandada. A distância inicial é de 95,5 m (alvo a 100 m menos 4,5 m de carroceria). Há colisão quando d ≤ 1 m com velocidade acima de 5 km/h; a rodada termina parada quando a velocidade cai abaixo do limiar, e a distância remanescente ao alvo é o valor de d nesse instante.

**Percepção e filtro.** Radar e lidar publicam a cada 20 ms a mesma distância medida com ruído gaussiano de desvio 0,25 m e a velocidade relativa; o modelo replica essa escolha da bancada. A ECU estima x = (d, v) com um filtro de Kalman de matriz de transição F = ((1, −Δt), (0, 1)), observações sequenciais de lidar e radar e covariâncias do firmware (Tabela 1). O filtro usa o instante de processamento, não o carimbo de origem: um quadro atrasado entra como se fosse atual, e um quadro mais antigo que chega depois de um mais novo faz a estimativa recuar. Um detector de variação abrupta declara falha após três leituras consecutivas com |Δd| > 10 m.

**Decisão e atuação.** A máquina de estados (Figura 2) eleva o nível de frenagem pelo TTC e por pisos de distância e reduz o nível somente após 0,2 s de histerese; antes de frear, exige 0,8 s em alerta. Cada nível pede uma desaceleração (2, 4 e 6 m/s²) que o controlador aplica com rampa de 1,67 % por ciclo de 10 ms, em que 100 % equivale a 10 m/s² (cerca de 16,7 m/s³). **Supervisão de comunicação:** se o quadro de percepção falta por 60 ms (seis ciclos), a ECU sinaliza falha, a máquina vai para OFF e o freio é liberado; no próximo quadro válido a falha cessa, mas a máquina recomeça em STANDBY e precisa passar de novo pelo alerta de 0,8 s.

![](C:/Users/rfagu/Estudo/dinamica_dt_aeb/resultados_tikz/fig_fsm.png){width="5.7in"}

Figura 2. Máquina de estados da ECU AEB, com a supervisão de comunicação que leva qualquer estado a OFF.

Tabela 1. Parâmetros do modelo e do firmware.

| Grupo | Parâmetro | Valor |
|---|---|---|
| Ciclo | ECU / percepção | 10 ms / 20 ms |
| Limiares de TTC | alerta, L1, L2, L3 | 4,0 / 3,0 / 2,2 / 1,8 s |
| Pisos de distância | L1, L2, L3; condição L3 | 20 / 10 / 5 m; v²/(2·6) ≥ d |
| Temporização | alerta mínimo; histerese de descida | 0,8 s; 0,2 s |
| Atuação | desaceleração L1, L2, L3; rampa | 2 / 4 / 6 m/s²; 16,7 m/s³ |
| Filtro | R lidar, R radar (d, v); Q (d, v) | 0,0025, 0,09, 0,01; 10⁻⁴, 10⁻⁵ |
| Falhas | variação abrupta; supervisão | 3 quadros com Δd > 10 m; 60 ms sem quadro |
| Percepção | ruído de distância | σ = 0,25 m |

**Monitor CEP de governança.** Um monitor recebe pelo mesmo canal as leituras e os comandos de freio e aplica dois padrões: "AEB sem reação" (TTC ≤ 3 s por mais de 0,2 s sem comando de freio conhecido, um padrão de ausência) e "frenagem fantasma" (comando de freio sem leitura com TTC ≤ 4 s nos 300 ms anteriores). O monitor observa e não atua no freio; um alarme "sem reação" é falso quando a ECU de fato freou em até 0,2 s.

**Diferenças entre o modelo e a bancada.** O modelo omite a dinâmica de corpo do Gazebo e a variabilidade de escalonamento da bancada; a bancada usa velocidade imposta e não modela atraso de atuador. Sem perturbação, o modelo para a 5,68 m do alvo e a bancada a 4,67 ± 1,02 m (30 rodadas): o modelo é, portanto, otimista em cerca de 1 m quanto à folga final, e seus valores absolutos de distância não devem ser extrapolados.

# 3. PROTOCOLO EXPERIMENTAL E MÉTRICAS

**Fatores.** H1a varia o atraso fixo do canal em 0, 25, 50, 100, 200, 400, 600, 800 e 1000 ms, mantidos ordem, jitter e perda. H1b mantém a latência média em 100 ms e acrescenta um atraso extra uniforme, de 40 a 200 ms ou de 200 a 600 ms, a 0, 5, 10 ou 20 % dos quadros, o que os faz chegar fora de ordem; o atraso-base é reduzido na mesma proporção (base = 100 ms − p × média do atraso extra), de modo que a latência média final permanece em 100 ms. Três políticas entregam os quadros à ECU e ao monitor: ordem de chegada; marca d'água de 150 ms a partir da geração, com descarte do que chega depois; e K-slack adaptativo, que espera pela maior defasagem já observada, libera também por tempo limite e descarta quadros mais antigos que o último liberado. A mesma implementação das políticas é usada no modelo e no relé da bancada.

**Experimento 2 (modelo).** Implementado em Python 3.12, com 30 sementes por célula a 40 e 50 km/h. As sementes variam o ruído de percepção e o sorteio dos quadros perturbados; a mesma semente reproduz exatamente a rodada, e a referência de cada semente é a rodada sem perturbação.

**Experimento 3 (bancada SIL).** A bancada executa o firmware da ECU em Zephyr (native_sim), o barramento CAN emulado por um relé TCP e a dinâmica em Gazebo/ROS 2 \[22, 23\]. O relé recebeu um estágio de perturbação nos quadros de percepção (0x100, 0x101 e 0x120) e registra para cada quadro o instante de entrada (t_in) e de saída (t_out). A perturbação é ativada antes do início de cada cenário. Uma rodada é aceita se (i) a percepção não interrompeu a publicação por mais de 100 ms nos 3 s que antecedem o instante crítico e (ii) a perturbação medida no registro corresponde à definida: atraso médio dentro de 15 ms, fração fora de ordem efetiva e entrega ordenada pelas políticas de reordenação. Rodadas reprovadas são repetidas, e um balanço a cada 20 rodadas interrompe a campanha se menos de 90 % estiverem conformes. Foram 900 rodadas aceitas (270 para H1a e 630 para H1b, 30 por célula, a 50 km/h). Com ordem de chegada, a latência média medida ficou entre 98 e 101 ms em todas as células e a fração efetivamente fora de ordem entre 5,0 e 19,7 %, próxima da definida, o que confirma o isolamento da desordenação.

**Métricas.** *Latência até o freio:* intervalo entre a entrada no canal do primeiro quadro com TTC ≤ 3 s e o primeiro comando de frenagem (nível ≥ L1); em H1a é apresentada como diferença em relação à média sem atraso. *Distância remanescente ao alvo:* valor de d na parada. *Colisão:* contagem e proporção, com intervalo de confiança de Wilson a 95 %. *AEB desligado:* rodada em que a ECU entrou em OFF depois do instante crítico. *Alarme falso do monitor:* conforme a Seção 2. *Margem no primeiro freio:* tempo, no instante do primeiro comando, até o último instante em que uma desaceleração imediata de 6 m/s² ainda pararia o veículo antes do alvo; como a ECU sobe por níveis e rampa, uma margem positiva não garante a parada. O prazo de 100 ms usado como referência é um parâmetro experimental e não um FTTI do item.

# 4. RESULTADOS

## 4.1 Atraso isolado (H1a)

No modelo, a latência até o primeiro nível de frenagem acompanhou o atraso injetado, com a quantização do período de percepção de 20 ms (25 ms de atraso resultaram em 30 ms de latência). A Figura 3 e a Tabela 2 comparam modelo e bancada. Na bancada, a latência adicional cresce com o atraso e, a partir de 400 ms, fica de 50 a 80 ms abaixo dele, porque perto do alvo os pisos de distância antecipam a subida dos níveis; até 100 ms, o efeito se confunde com a variabilidade da própria bancada (desvio de 94 ms sem perturbação). A distância remanescente cai de 4,7 m sem atraso para 0,39 m com 800 ms, e com 1000 ms 23 de 30 rodadas colidiram, a 7,4 km/h em média. No modelo, a margem no primeiro freio caiu de 1,85 s para 0,85 s com 1000 ms e todas as rodadas colidiram, embora a margem ainda fosse positiva: a margem supõe 6 m/s² imediatos, enquanto a ECU começa em 2 m/s² e sobe por rampa. Os pontos testados delimitam a transição para a colisão entre 800 e 1000 ms, sem estimar um limiar exato. O ponto não monotônico entre 100 e 200 ms decorre da permanência mínima em alerta: conforme o instante em que o limiar é cruzado, o atraso recai ou não sobre essa espera. H1a é confirmada no modelo e na bancada.

![](C:/Users/rfagu/Estudo/dinamica_dt_aeb/resultados_tikz/fig_h1a.png){width="5.7in"}

Figura 3. H1a: latência adicional até o freio, distância remanescente ao alvo e colisões em função do atraso, no modelo e na bancada (média ± desvio, 30 rodadas por ponto, 50 km/h).

Tabela 2. H1a na bancada SIL (50 km/h, 30 rodadas por nível).

| Atraso (ms) | Latência adicional (ms) | Distância remanescente (m) | Colisões (IC 95 %) |
|---:|---:|---:|---:|
| 0 | 0 ± 94 | 4,67 ± 1,02 | 0/30 (0–11 %) |
| 200 | 199 ± 77 | 4,58 ± 1,54 | 0/30 (0–11 %) |
| 400 | 352 ± 35 | 3,86 ± 1,09 | 1/30 (1–17 %) |
| 600 | 548 ± 56 | 2,30 ± 0,76 | 0/30 (0–11 %) |
| 800 | 728 ± 15 | 0,39 ± 0,36 | 0/30 (0–11 %) |
| 1000 | 924 ± 14 | 0,06 ± 0,09 | 23/30 (59–88 %) |

## 4.2 Desordenação isolada (H1b)

A Figura 4 resume a bancada para as três políticas e as duas distâncias de desordenação, e o modelo para a distância maior; a Tabela 3 detalha a condição de 20 %. Na bancada, processar pela ordem de chegada levou ao desligamento do AEB em 33 a 63 % das rodadas com apenas 5 % de quadros fora de ordem e em 97 a 100 % com 20 %, quando 12 das 30 rodadas colidiram em cada distância. O mecanismo é a supervisão de comunicação: quando dois ou três quadros consecutivos recebem o atraso extra, a ECU passa mais de 60 ms sem quadro, vai para OFF e, ao se recuperar, precisa de 0,8 s em alerta antes de frear; a latência até o freio passou a 1,2–4,3 s. Note-se que a idade média dos quadros não muda (100 ms); é o intervalo entre chegadas que ultrapassa a supervisão. A marca d'água não evitou o efeito: os quadros que chegam depois da tolerância são descartados e abrem lacunas, e com 20 % de desordem 16 e 18 de 30 rodadas colidiram. O K-slack entrega um fluxo ordenado e quase contínuo, reduziu os desligamentos e as colisões (no máximo 4 de 30), mas fixou a latência entre 360 e 670 ms e, com atraso extra de 200 a 600 ms, deixou o veículo a cerca de 2 m do alvo mesmo com pouca desordem.

![](C:/Users/rfagu/Estudo/dinamica_dt_aeb/resultados_tikz/fig_h1b.png){width="5.7in"}

Figura 4. H1b: colisões (linha cheia) e desligamentos do AEB pela supervisão (pontilhada) em função da fração de quadros fora de ordem, por política, na bancada (30 rodadas por ponto); à direita, colisões no modelo com supervisão.

Tabela 3. H1b com 20 % dos quadros fora de ordem, latência média de 100 ms (bancada SIL, 50 km/h, 30 rodadas por célula).

| Atraso extra | Política | Latência até o freio (ms) | AEB desligado | Colisões (IC 95 %) | Dist. remanescente (m) |
|---|---|---:|---:|---:|---:|
| 40–200 ms | chegada | 3229 | 29/30 | 12/30 (25–58 %) | 1,42 |
| 40–200 ms | marca d'água | 957 | 27/30 | 16/30 (36–70 %) | 0,97 |
| 40–200 ms | K-slack | 576 | 10/30 | 4/30 (5–30 %) | 3,14 |
| 200–600 ms | chegada | 4318 | 30/30 | 12/30 (25–58 %) | 1,09 |
| 200–600 ms | marca d'água | 2311 | 30/30 | 18/30 (42–75 %) | 1,03 |
| 200–600 ms | K-slack | 657 | 1/30 | 1/30 (1–17 %) | 1,88 |

Sem a supervisão de comunicação, o modelo indicava que a desordem era inócua para a frenagem: a histerese de 0,2 s absorve o recuo da estimativa causado por um quadro antigo, e o quadro seguinte a restaura. Com a supervisão incluída e a mesma implementação de K-slack da bancada, o modelo reproduz a direção observada: com 20 % de desordem, 23 a 27 % de colisões pela ordem de chegada, 23 a 50 % com marca d'água e 0 a 3 % com K-slack. As magnitudes menores no modelo são coerentes com sua folga final cerca de 1 m maior.

No monitor CEP do modelo, o padrão "sem reação", que depende da ausência do comando de freio, produziu alarmes falsos em até 10 % das rodadas pela ordem de chegada e até 17 % com marca d'água, porque o comando de freio chegou depois das leituras que deveria explicar; com K-slack, os alarmes deixaram de ser falsos, mas passaram a refletir a demora real que a própria espera introduziu. O padrão "frenagem fantasma", apoiado em leituras redundantes, não produziu alarmes falsos. H1b é confirmada por dois caminhos: nos padrões de governança baseados em ausência ou sequência e, com a ECU real, na própria decisão de frenagem.

# 5. DISCUSSÃO

## 5.1 Três mecanismos e um modelo simples para o desligamento

Os resultados separam três efeitos que a literatura de fluxos de eventos costuma tratar sob o mesmo rótulo de "qualidade temporal". O primeiro é o **atraso**, que consome a margem de forma contínua e previsível: a latência até o freio cresce com o atraso injetado e a distância remanescente cai de forma quase linear a partir de 200 ms (Figura 3). É o efeito clássico dos sistemas de controle em rede, em que o atraso no laço reduz o desempenho e, acima de um limite, a estabilidade \[18, 19\]; aqui ele aparece como perda de distância, e o ponto em que a frenagem deixa de evitar a colisão fica entre 800 e 1000 ms para esta calibração e velocidade.

O segundo é a **desordenação**, que não engana a lógica de decisão, mas aciona o mecanismo de supervisão. A lógica de limiar com histerese tolera um quadro antigo porque o quadro seguinte, 20 ms depois, restaura a estimativa; já a supervisão conta ciclos sem quadro. Com período de percepção T = 20 ms e supervisão S = 60 ms, um único quadro atrasado não produz lacuna: os quadros vizinhos chegam em seus instantes e o maior intervalo entre entregas é 2T = 40 ms. Dois quadros consecutivos atrasados produzem um intervalo de 3T = 60 ms, exatamente o limiar. Se a fração p de quadros perturbados for independente entre quadros, a probabilidade de ao menos um par consecutivo em N quadros é 1 − (1 − p²)^N. Com N ≈ 350 quadros na aproximação, essa expressão dá 58 %, 97 % e 100 % para p = 5 %, 10 % e 20 %; a bancada registrou 63 %, 97 % e 100 % de desligamentos com atraso extra de 200 a 600 ms (Figura 4b). Com atraso extra de 40 a 200 ms, o intervalo gerado pelo par fica no limiar de 60 ms e só parte dos casos o ultrapassa, o que explica as frações menores (33 %, 57 % e 97 %). Daí uma regra de projeto: a supervisão só tolera k quadros consecutivos atrasados se S > (k + 1) T. Com S = 60 ms e T = 20 ms, k = 1; bastaria S = 80 ms para tolerar pares, ao custo de 20 ms a mais na detecção de uma perda real de sensor.

O terceiro efeito é o da **política de ordenação**, que desloca o problema em vez de resolvê-lo. A marca d'água descarta o que chega depois da tolerância; na ordem de chegada, o quadro atrasado ainda é entregue e reinicia o contador da supervisão, enquanto na marca d'água ele desaparece e a lacuna se prolonga. Por isso a marca d'água produziu mais desligamentos e colisões do que a ordem de chegada (Tabela 3), apesar de entregar um fluxo ordenado. O K-slack preserva a continuidade porque segura todos os quadros por um tempo próximo ao maior atraso observado e os libera em sequência: o intervalo entre entregas volta a ser T, e a supervisão não dispara. Em troca, a latência fixa de 360 a 670 ms recoloca o sistema na curva de H1a: a distância remanescente de 1,9 a 2,3 m com K-slack (Tabela 3) coincide com a observada para atrasos fixos de 600 ms (2,3 m, Tabela 2).

## 5.2 Implicações de projeto

Três recomendações seguem dos mecanismos. Primeira, **supervisão temporal e política de ordenação devem ser dimensionadas em conjunto**, com a distância típica de desordenação do canal como entrada: o tempo de supervisão define quantos quadros consecutivos podem atrasar, e a política define se o quadro atrasado ainda alimenta a supervisão (ordem de chegada), some (marca d'água) ou é retido junto com os demais (K-slack). Segunda, para a decisão de frenagem, **a alimentação deve vir do barramento local, sem reordenação**: nenhuma das políticas melhorou a frenagem em relação à ordem de chegada sem cobrar em latência, e a arquitetura que mantém a ECU ligada ao barramento e leva à nuvem apenas eventos complexos evita o problema na origem. Esse é o critério de alocação das arquiteturas de gêmeo digital na borda \[16, 17\]; em um experimento anterior do grupo com um gêmeo digital simulado (360 rodadas), as regras no veículo decidiram em 5 a 15 ms, contra p95 de até 2,3 s na nuvem, e mantiveram a detecção durante 90 s sem conectividade. Terceira, nos **monitores de governança, os padrões de ausência precisam de semântica de tempo de evento e de proteção do evento crítico**: o comando de freio não pode ser descartado por uma marca d'água, e a janela de ausência deve ser avaliada no tempo de origem, com tolerância de atraso explícita, como fazem os modelos de fluxo com marcas d'água e pontuação \[12, 9, 10\]. Sem isso, o monitor produziu até 17 % de alarmes falsos e, com K-slack, alarmes verdadeiros causados pela própria espera.

Do ponto de vista da segurança funcional, o desligamento por supervisão é o comportamento previsto pelo firmware para perda de sensor \[6\]; o que o experimento mostra é que a desordenação do canal, sem perda, aciona o mesmo caminho. É uma limitação de desempenho do tipo que a ISO 21448 denomina condição de disparo \[24\], e a análise de segurança do item deveria incluir a distribuição de atraso do canal entre os cenários avaliados. O limite de 100 ms deste estudo é um parâmetro experimental: um prazo real derivaria do FTTI do item e da margem no primeiro freio, que foi de 1,85 s sem atraso e cai 1 s por segundo de atraso.

## 5.3 Relação com a literatura

O compromisso entre esperar pela ordem e agir a tempo é conhecido no processamento de fluxos: folga K e pulsações de tempo \[9\], pontuação \[10\], marcas de progresso \[11\], marca d'água como ajuste entre correção, latência e custo \[12\] e espera adaptativa para sensores de alta taxa \[13\]. Esses trabalhos medem correção lógica e latência de processamento; este artigo acrescenta a consequência física e o mecanismo de supervisão, que converte a latência de uma política em distância perdida e a lacuna de outra em indisponibilidade. Do lado automotivo, a análise de tempo de resposta em CAN \[25\] e a proteção fim a fim \[26\] tratam a entrega no prazo dentro do barramento, não a travessia de um canal externo com desordem; os estudos de eficácia do AEB em campo \[4, 5\] não variam a qualidade do fluxo de eventos. A validação em SIL segue a recomendação de exercitar em simulação condições raras em campo \[27\].

## 5.4 Ameaças à validade

*Construto.* A latência é medida na entrada do relé e no comando de freio emitido pela ECU, não nos tempos internos da ECU; a margem no primeiro freio supõe desaceleração imediata de 6 m/s² e por isso é um limite superior. *Interna.* A bancada tem variabilidade própria (desvio de 94 ms na latência sem perturbação); o critério de validade e a auditoria de conformidade controlam essa fonte, e a perturbação medida coincidiu com a definida em todas as células. Nas rodadas de 800 e 1000 ms a ECU entrou em OFF no fim da rodada em 23 e 26 casos, depois da parada ou do contato; a causa não foi isolada e esse indicador ficou fora da Tabela 2. *Externa.* Um cenário, uma velocidade, velocidade imposta sem modelo de pneu nem atraso de atuador, ruído gaussiano idêntico nos dois sensores, uma tolerância de marca d'água e um K-slack com liberação por tempo limite; o modelo é otimista em cerca de 1 m na folga final. *Conclusão.* Trinta rodadas por célula dão intervalos de Wilson de 11 a 33 pontos percentuais \[28\]; ausência de colisão em 30 rodadas não demonstra probabilidade nula, e diferenças de poucas rodadas entre políticas não devem ser lidas como efeito. Os próximos passos são outras velocidades e cenários Euro NCAP (CCRm e CCRb), para testar a regra S > (k + 1) T, a variação conjunta de supervisão e tolerância de ordenação, um filtro que use o carimbo de origem dos quadros e distribuições de atraso medidas em redes celulares. O código do modelo, do relé e da campanha com auditoria e os registros de cada rodada estão disponíveis como material suplementar e serão identificados por repositório e versão na versão final.

# 6. CONCLUSÃO

O atraso dos eventos de percepção se transfere para a latência de frenagem e, com 1 s, levou à colisão na maioria das rodadas. A desordenação, com a latência média constante, não engana a lógica de decisão, mas faz a supervisão de comunicação da ECU desligar o AEB, com colisões em até 60 % das rodadas na bancada com o firmware real; o K-slack evita a maior parte delas ao custo de centenas de milissegundos. No monitor de governança, padrões baseados em ausência de eventos produzem alarmes falsos sob desordem. A contribuição é mostrar, com um modelo especificado e uma bancada auditada, que a segurança temporal de um AEB depende não só da regra, mas da interação entre política de ordenação e mecanismos de supervisão.

# REFERÊNCIAS

\[1\] UNECE. UN Regulation No. 152 -- Uniform provisions concerning the approval of motor vehicles with regard to the Advanced Emergency Braking System (AEBS) for M1 and N1 vehicles. Geneva, 2020.

\[2\] ISO. ISO 22839:2013, Intelligent transport systems -- Forward vehicle collision mitigation systems -- Operation, performance, and verification requirements. Geneva, 2013.

\[3\] Euro NCAP. Test Protocol -- AEB Car-to-Car systems. Leuven: European New Car Assessment Programme, 2023.

\[4\] Cicchino, J. B. Effectiveness of forward collision warning and autonomous emergency braking systems in reducing front-to-rear crash rates. Accident Analysis & Prevention, v. 99, p. 142-152, 2017.

\[5\] Fildes, B. et al. Effectiveness of low speed autonomous emergency braking in real-world rear-end crashes. Accident Analysis & Prevention, v. 81, p. 24-29, 2015.

\[6\] ISO. ISO 26262:2018, Road vehicles -- Functional safety. Geneva: ISO, 2018.

\[7\] Luckham, D. The Power of Events: An Introduction to Complex Event Processing in Distributed Enterprise Systems. Boston: Addison-Wesley, 2002.

\[8\] Cugola, G.; Margara, A. Processing flows of information: from data stream to complex event processing. ACM Computing Surveys, v. 44, n. 3, art. 15, 2012.

\[9\] Srivastava, U.; Widom, J. Flexible time management in data stream systems. In: ACM Symposium on Principles of Database Systems (PODS). Paris, 2004. p. 263-274.

\[10\] Tucker, P. A.; Maier, D.; Sheard, T.; Fegaras, L. Exploiting punctuation semantics in continuous data streams. IEEE Transactions on Knowledge and Data Engineering, v. 15, n. 3, p. 555-568, 2003.

\[11\] Li, J.; Tufte, K.; Shkapenyuk, V.; Papadimos, V.; Johnson, T.; Maier, D. Out-of-order processing: a new architecture for high-performance stream systems. Proceedings of the VLDB Endowment, v. 1, n. 1, p. 274-288, 2008.

\[12\] Akidau, T. et al. The Dataflow Model: a practical approach to balancing correctness, latency, and cost in massive-scale, unbounded, out-of-order data processing. Proceedings of the VLDB Endowment, v. 8, n. 12, p. 1792-1803, 2015.

\[13\] Mutschler, C.; Philippsen, M. Distributed low-latency out-of-order event processing for high data rate sensor streams. In: IEEE International Parallel and Distributed Processing Symposium (IPDPS). Boston, 2013. p. 1133-1144.

\[14\] Grieves, M.; Vickers, J. Digital Twin: Mitigating unpredictable, undesirable emergent behavior in complex systems. In: Transdisciplinary Perspectives on Complex Systems. Cham: Springer, 2017. p. 85-113.

\[15\] Tao, F.; Zhang, H.; Liu, A.; Nee, A. Y. C. Digital Twin in industry: state-of-the-art. IEEE Transactions on Industrial Informatics, v. 15, n. 4, p. 2405-2415, 2019.

\[16\] Minerva, R.; Lee, G. M.; Crespi, N. Digital Twin in the IoT context: a survey on technical features, scenarios, and architectural models. Proceedings of the IEEE, v. 108, n. 10, p. 1785-1824, 2020.

\[17\] Shi, W.; Cao, J.; Zhang, Q.; Li, Y.; Xu, L. Edge computing: vision and challenges. IEEE Internet of Things Journal, v. 3, n. 5, p. 637-646, 2016.

\[18\] Zhang, W.; Branicky, M. S.; Phillips, S. M. Stability of networked control systems. IEEE Control Systems Magazine, v. 21, n. 1, p. 84-99, 2001.

\[19\] Hespanha, J. P.; Naghshtabrizi, P.; Xu, Y. A survey of recent results in networked control systems. Proceedings of the IEEE, v. 95, n. 1, p. 138-162, 2007.

\[20\] AEB Stellantis Project. Bancada SIL de frenagem autônoma de emergência com ECU virtual Zephyr, CAN emulado e Gazebo/ROS 2. UFPE/Stellantis, 2026.

\[21\] Lee, D. N. A theory of visual control of braking based on information about time-to-collision. Perception, v. 5, n. 4, p. 437-459, 1976.

\[22\] Koenig, N.; Howard, A. Design and use paradigms for Gazebo, an open-source multi-robot simulator. In: IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS). Sendai, 2004. p. 2149-2154.

\[23\] Macenski, S.; Foote, T.; Gerkey, B.; Lalancette, C.; Woodall, W. Robot Operating System 2: design, architecture, and uses in the wild. Science Robotics, v. 7, n. 66, 2022.

\[24\] ISO. ISO 21448:2022, Road vehicles -- Safety of the intended functionality. Geneva, 2022.

\[25\] Davis, R. I.; Burns, A.; Bril, R. J.; Lukkien, J. J. Controller Area Network (CAN) schedulability analysis: refuted, revisited and revised. Real-Time Systems, v. 35, n. 3, p. 239-272, 2007.

\[26\] AUTOSAR. Specification of SW-C End-to-End Communication Protection Library. AUTOSAR Classic Platform, release R22-11, 2022.

\[27\] Koopman, P.; Wagner, M. Challenges in autonomous vehicle testing and validation. SAE International Journal of Transportation Safety, v. 4, n. 1, p. 15-24, 2016.

\[28\] Brown, L. D.; Cai, T. T.; DasGupta, A. Interval estimation for a binomial proportion. Statistical Science, v. 16, n. 2, p. 101-133, 2001.
