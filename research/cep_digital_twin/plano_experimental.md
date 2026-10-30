# Plano experimental: Gêmeo Digital local + nuvem para a governança do AEB

Este documento explica o que o experimento testa, por quê, como ele é construído e como cada
resultado entra no artigo. Os números ficam em `resultados/resumo.md` (gerado por
`experimento.py`); aqui está o raciocínio.

## 1. Pergunta de pesquisa

Num sistema AEB conectado, a governança precisa de duas coisas que puxam em direções opostas:
reagir em milissegundos a uma falha na troca de mensagens (frenagem tardia, frenagem fantasma,
ataque) e manter uma trilha auditável completa para decidir OTA, manutenção ou recall. Um gêmeo
digital só na nuvem recebe tudo pela rede celular e sofre com atraso, perda e desconexão. A
pergunta:

> Particionar o gêmeo digital em uma instância local (na ECU hospedeira) e uma na nuvem reduz a
> latência de decisão e preserva a cobertura de políticas e a trilha de auditoria sob rede
> degradada e janelas offline, sem perder a detecção dos cenários de janela longa?

## 2. Teorias que viraram hipóteses

Cada "teoria" da dinâmica virou uma hipótese com métrica, critério e requisito do artigo.

| Hipótese | O que afirmamos | Métrica | Critério de aceitação | Requisito |
|---|---|---|---|---|
| H1 | A decisão dos cenários reativos na borda não depende da rede; na nuvem ela cresce com o atraso | p95 do tempo entre a falha e a decisão | A1 abaixo de 100 ms em todas as redes; A0 acima em rede média e ruim | RQ1 baixa latência |
| H2 | Sob offline, a borda mantém a cobertura das políticas; a nuvem perde as falhas que caem na janela ou que o buffer descarta | fração das falhas injetadas que geraram o evento complexo esperado | A1 = 100 %; A0 < 100 % com offline longo | RG1 políticas executáveis |
| H3 | A borda grava o snapshot localmente e entrega depois; a nuvem só reconstrói se todos os brutos chegaram | fração de decisões com trilha completa; tempo até a evidência estar disponível | A1 = 100 % de trilhas completas, inclusive com offline longo; A0 < 100 % | RG2 trilha auditável |
| H4 | Mandar eventos complexos, snapshots e agregados em vez do fluxo bruto reduz o volume em uma ordem de grandeza, e isso não atrasa a detecção dos cenários de janela longa | bytes enviados por rodada; latência de detecção da degradação do sensor | A1 ≤ 1/5 do volume de A0; diferença de latência na degradação ≤ 2 s | atributo de qualidade (custo) |

A tabela de requisitos do artigo (seção 4.2) sai daqui: RG1, RG2, RQ1 e um RQ2 novo, "operar sem
conectividade", cujo mecanismo é o DT local com store-and-forward.

## 3. Desenho do experimento

Fatorial completo, com repetição:

| Fator | Níveis | Por que |
|---|---|---|
| Arquitetura | A0 só nuvem (linha de base); A1 local + nuvem (proposta) | é a variável de interesse |
| Rede celular | boa (50 ms ± 10, 0 % perda); média (150 ms ± 40, 2 %); ruim (400 ms ± 120, 10 %) | cobre de 5G urbano a 4G congestionado |
| Janela offline | nenhuma; curta (30 s); longa (90 s) | túnel, garagem, área rural |
| Repetições | 20 sementes; cada semente muda os instantes das falhas e o ruído | média, p95 e variação entre rodadas |

São 2 × 3 × 3 × 20 = 360 rodadas de 240 s simulados. A mesma semente gera o mesmo fluxo de
eventos para A0 e A1, então a comparação entre arquiteturas é pareada.

**Linha de base justa.** A nuvem de A0 não é ingênua: ela reordena os eventos por timestamp com
um limite de atraso tolerado L = atraso + 3·jitter (suposto conhecido), como fazem os motores CEP
com marca d'água. Evento que chega depois de L é processado fora de ordem. O gateway de A0 tem o
mesmo buffer store-and-forward que A1 (128 KB) para os períodos offline. Sem isso, os resultados
ficariam a favor da proposta por um motivo errado.

## 4. Modelo de simulação

**Veículo.** Radar e lidar a 20 Hz, mensagem CAN do radar a cada ciclo (latência nominal ~40 ms,
alive counter, MAC), estado do barramento a 1 Hz, alertas da HMI e freio do motorista.

**Falhas injetadas (verdade de referência).** Em cada rodada, uma de cada, em instantes sorteados
e sem sobreposição:

| Cenário | Como é injetado | Tipo |
|---|---|---|
| Frenagem tardia | comando de freio chega com 180 ms (limite 100 ms) | risco reativo, borda |
| Frenagem fantasma | radar vê alvo a 8 m, lidar vê 80 m, AEB freia | risco reativo, borda |
| Ataque cibernético | rajada de 12 mensagens com ID desconhecido e MAC inválido | risco preventivo, borda |
| Degradação do barramento | 15 s com carga > 80 % e perdas crescentes | risco preventivo, borda |
| Degradação do sensor | 30 s em que o radar diverge do lidar cada vez mais, com erros em frequência crescente | risco preventivo, nuvem |
| Comportamento do motorista | dois alertas, reação de 0,9 s e de 2,2 s | operação normal, nuvem |

**Rede.** Atraso gaussiano, perda com reenvio QoS 1 (timeout 1 s, 3 tentativas), janela offline
em instante sorteado. Durante o offline, o gateway guarda as mensagens num buffer de 128 KB e
descarta as mais antigas quando enche; ao voltar, drena a 50 KB/s.

**A0, só nuvem.** Cada evento bruto (64 B) vai pela rede. A nuvem reordena, roda as sete regras e
guarda os brutos; a evidência de uma decisão é o conjunto de brutos em ±3 s em volta dela.

**A1, local + nuvem.** A ECU hospedeira roda as quatro regras rápidas sobre o barramento, com 5 ms
de processamento. Para cada evento complexo ela manda à nuvem o evento (256 B) e, 3 s depois, o
snapshot de ±3 s em formato compacto (32 B por evento). A cada 1 s manda um agregado de 96 B
(p95 da latência, carga, perdas, erros do sensor, pares radar/lidar e quantos divergem). A nuvem
roda as três regras de janela longa sobre os agregados. A evidência de uma decisão local é o
snapshot; a de uma decisão na nuvem são os dez agregados anteriores.

**Regras CEP.** As mesmas da tabela da dinâmica, com os mesmos limiares, em `simulacao_cep.py`.
A versão sobre agregados das três regras da nuvem está em `experimento.py`
(`NuvemAgregada`).

## 5. Métricas (definição operacional)

| Métrica | Como é medida | Vai para |
|---|---|---|
| Detecção | existe evento complexo do cenário certo entre t₀ − 0,5 s e t₁ + 15 s | H2, RG1, seção 7.2 |
| Latência de decisão | instante da decisão (borda ou nuvem) − t₀ da falha; média e p95 | H1, RQ1, seção 7.1 |
| Latência até a Gestão | chegada do evento complexo à nuvem − t₀ | H1, seção 7.1 |
| Completude da trilha | fração da evidência que chegou ao repositório; e fração de decisões com 100 % | H3, RG2, seção 7.2 |
| Tempo até a evidência | instante em que a evidência fica completa − t₀ | H3, RG2, seção 7.2 |
| Falsos positivos | eventos complexos de risco fora de qualquer janela de falha | H2, seção 7.3 |
| Volume | bytes e mensagens enviados ao longo da rodada | H4, seção 7.1 |
| Descartes no buffer | mensagens perdidas por buffer cheio durante o offline | H2/H3, seção 7.2 |
| Cobertura de KPI | janelas de 10 s de saúde da rede entregues à Gestão / esperadas | operação normal, seção 7.2 |

## 6. Procedimento reprodutível

```
py -3.12 experimento.py          # 20 sementes, cerca de 2 min
py -3.12 experimento.py --rapido # 3 sementes, para conferir
```

Saídas em `resultados/`: `por_cenario.csv` (uma linha por rodada × cenário), `por_rodada.csv`,
`resumo.md` (tabelas das hipóteses) e `fig_latencia.png`, `fig_deteccao.png`,
`fig_evidencia.png`, `fig_volume.png`. Todos os parâmetros estão no dicionário `CFG` e nos
limiares `P` de `simulacao_cep.py`.

## 7. Ameaças à validade (e o que fazer com elas)

- **Modelo de rede simplificado.** Atraso gaussiano e perda independente. Vale como primeiro
  estudo; o passo seguinte é usar traços reais de rede celular (ou os dados de telemetria da
  frota, se o grupo tiver acesso).
- **Regras simples.** As regras CEP são as da dinâmica, não um motor comercial. O que se mede é
  o efeito da arquitetura, não a qualidade das regras.
- **Sensores sintéticos.** O radar e o lidar são sorteados, não vêm de um cenário físico. O SIL do
  AEB resolve isso: substituir o gerador de eventos pela saída do SIL e manter o resto.
- **Cenário de sensor com regras diferentes.** A0 usa a regra sobre brutos e A1 a regra sobre
  agregados. A diferença medida (~1 s) é o custo da agregação por segundo, e é o que H4 quer
  mostrar.
- **Parâmetros de volume.** 64 B por evento bruto, 32 B por evento no snapshot, 96 B por agregado
  são estimativas; o ganho de H4 depende deles e por isso ficam explícitos.
- **Tamanho do buffer.** 128 KB foi escolhido para que o offline curto caiba e o longo não. Vale
  dizer no artigo que o resultado de H2/H3 com offline longo depende dessa escolha.

## 8. Mapa resultado → seção do artigo

| Seção do modelo | O que entra |
|---|---|
| 3 Método | seções 3, 4, 5 e 7 deste plano |
| 4.2 Requisitos | RG1, RG2, RQ1, RQ2 ligados a H2, H3, H1 e à janela offline |
| 5.4 Implantação edge/cloud | critério de alocação (reação em ms e volume → borda; janela longa e frota → nuvem) |
| 6 Implementação | descrição de `simulacao_cep.py` e `experimento.py`, parâmetros, procedimento |
| 7.1 Desempenho e resiliência | tabela H1, figura de latência, tabela H4 de volume |
| 7.2 Governança e auditabilidade | tabelas H2 e H3, figuras de detecção e de evidência |
| 7.3 Comparação e limitações | linha de base justa, ameaças à validade |
| 8 Conclusão | resposta à pergunta: qual hipótese se confirmou e com que margem |
