"""V6.3: aplica ao texto a reanálise dos registros da bancada (31/10/2026).

- instante crítico só com quadros gerados depois do início da rodada (afetava a latência de H1b);
- "AEB desligado" = transição para OFF entre o instante crítico e o desfecho físico, sem os OFFs por
  alcance mínimo do lidar (d < 1 m) perto do contato e sem STANDBY a baixa velocidade;
- curva medida de disparo da supervisão por tamanho da lacuna e modelo de pares como limite superior.
Edita artigo_v6.md (seções 1 a 4) e build/secao5_v62.md (seção 5) no lugar.
"""
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ART = AQUI.parent / "artigo_v6.md"
SEC5 = AQUI / "secao5_v62.md"


def troca(path, pares):
    s = path.read_text(encoding="utf-8")
    for a, b in pares:
        assert a in s, f"{path.name}: não achei: {a[:70]}"
        s = s.replace(a, b)
    path.write_text(s, encoding="utf-8", newline="")


troca(ART, [
    # resumo
    ("contra 3 a 13 % com K-slack, que em troca acrescentou de 360 a 670 ms de latência.",
     "contra 3 a 13 % com K-slack, que em troca elevou a latência até o freio para 420 a 660 ms."),
    # métrica
    ("*AEB desligado:* rodada em que a ECU entrou em OFF depois do instante crítico.",
     "*AEB desligado:* rodada em que a ECU passou a OFF entre o instante crítico e o desfecho físico (menor "
     "distância real), detectado no estado publicado a cada 50 ms e no modo do comando de freio a cada 10 ms; "
     "não contam a queda para espera abaixo de 10 km/h nem o OFF por alcance mínimo do lidar (d < 1 m), que "
     "decorre do contato."),
    # resultados H1b
    ("Na bancada, processar pela ordem de chegada levou ao desligamento do AEB em 33 a 63 % das rodadas com "
     "apenas 5 % de quadros fora de ordem e em 97 a 100 % com 20 %, quando 12 das 30 rodadas colidiram em cada "
     "distância. O mecanismo é a supervisão de comunicação: quando dois ou três quadros consecutivos recebem o "
     "atraso extra, a ECU passa mais de 60 ms sem quadro, vai para OFF e, ao se recuperar, precisa de 0,8 s em "
     "alerta antes de frear; a latência até o freio passou a 1,2–4,3 s. Note-se que a idade média dos quadros "
     "não muda (100 ms); é o intervalo entre chegadas que ultrapassa a supervisão.",
     "Na bancada, processar pela ordem de chegada desligou o AEB antes do desfecho em 20 a 53 % das rodadas com "
     "apenas 5 % de quadros fora de ordem e em todas com 20 %, quando 12 das 30 rodadas colidiram em cada "
     "distância. O mecanismo é a supervisão de comunicação: quando dois ou mais quadros consecutivos recebem o "
     "atraso extra, a ECU fica 60 ms sem quadro, vai para OFF, solta o freio e, ao se recuperar, precisa de "
     "0,8 s em alerta antes de frear de novo. Com 20 % de desordem houve em média 3 a 4 episódios por rodada, "
     "quase sempre já durante a frenagem: a latência até o primeiro freio subiu pouco (de 240 para 470 a "
     "700 ms), mas a frenagem foi interrompida repetidas vezes. A idade média dos quadros não muda (100 ms); é o "
     "intervalo entre chegadas que ultrapassa a supervisão. Com 200 a 600 ms há um segundo caminho: um quadro "
     "antigo entregue no meio da frenagem traz a velocidade relativa de centenas de milissegundos antes, viola a "
     "verificação de plausibilidade do radar (salto acima de 2 m/s) e também leva a OFF."),
    ("O K-slack entrega um fluxo ordenado e quase contínuo, reduziu os desligamentos e as colisões (no máximo 4 "
     "de 30), mas fixou a latência entre 360 e 670 ms",
     "O K-slack entrega um fluxo ordenado e quase contínuo, reduziu os desligamentos (no máximo 12 de 30) e as "
     "colisões (no máximo 4 de 30), mas fixou a latência entre 300 e 670 ms"),
    # legenda e Tabela 3
    ("Figura 4. H1b: colisões (linha cheia) e desligamentos do AEB pela supervisão (pontilhada)",
     "Figura 4. H1b: colisões (linha cheia) e desligamentos do AEB antes do desfecho (pontilhada)"),
    ("Tabela 3. H1b com 20 % dos quadros fora de ordem, latência média de 100 ms (bancada SIL, 50 km/h, 30 "
     "rodadas por célula).",
     "Tabela 3. H1b com 20 % dos quadros fora de ordem, latência média de 100 ms (bancada SIL, 50 km/h, 30 "
     "rodadas por célula). Sem desordem, a latência até o freio foi de 180 a 260 ms."),
    ("| Atraso extra | Política | Latência até o freio (ms) | AEB desligado | Colisões (IC 95 %) | Dist. remanescente (m) |",
     "| Atraso extra | Política | Latência até o freio (ms) | AEB desligado (episódios por rodada) | Colisões (IC 95 %) | Dist. remanescente (m) |"),
    ("| 40–200 ms | chegada | 3229 | 29/30 |", "| 40–200 ms | chegada | 695 | 30/30 (3,1) |"),
    ("| 40–200 ms | marca d'água | 957 | 27/30 |", "| 40–200 ms | marca d'água | 706 | 29/30 (3,5) |"),
    ("| 40–200 ms | K-slack | 576 | 10/30 |", "| 40–200 ms | K-slack | 422 | 12/30 (0,6) |"),
    ("| 200–600 ms | chegada | 4318 | 30/30 |", "| 200–600 ms | chegada | 471 | 30/30 (3,3) |"),
    ("| 200–600 ms | marca d'água | 2311 | 30/30 |", "| 200–600 ms | marca d'água | 877 | 30/30 (4,3) |"),
    ("| 200–600 ms | K-slack | 657 | 1/30 |", "| 200–600 ms | K-slack | 657 | 2/30 (0,1) |"),
])

troca(SEC5, [
    ("Com período de percepção T = 20 ms e supervisão S = 60 ms, um único quadro atrasado não produz lacuna: os "
     "quadros vizinhos chegam em seus instantes e o maior intervalo entre entregas é 2T = 40 ms. Dois quadros "
     "consecutivos atrasados produzem um intervalo de 3T = 60 ms, exatamente o limiar. Se a fração p de quadros "
     "perturbados for independente entre quadros, a probabilidade de ao menos um par consecutivo em N quadros é "
     "1 − (1 − p²)^N. Com N ≈ 350 quadros na aproximação, essa expressão dá 58 %, 97 % e 100 % para p = 5 %, "
     "10 % e 20 %; a bancada registrou 63 %, 97 % e 100 % de desligamentos com atraso extra de 200 a 600 ms "
     "(Figura 4b). Com atraso extra de 40 a 200 ms, o intervalo gerado pelo par fica no limiar de 60 ms e só "
     "parte dos casos o ultrapassa, o que explica as frações menores (33 %, 57 % e 97 %). Daí uma regra de "
     "projeto: a supervisão só tolera k quadros consecutivos atrasados se S > (k + 1) T.",
     "Com período de percepção T = 20 ms e supervisão S = 60 ms, um único quadro atrasado deixa entre entregas "
     "um intervalo de 2T = 40 ms, e dois consecutivos, de 3T = 60 ms. O firmware conta ciclos de 10 ms sem "
     "quadro e desliga no sexto, de modo que o limiar efetivo fica entre 50 e 60 ms. A bancada confirma essa "
     "fronteira: nas rodadas de H1b, lacunas de entrega abaixo de 50 ms levaram a OFF em 1 % dos casos "
     "(42/4088), de 50 a 60 ms em 50 % (166/330), de 60 a 70 ms em 78 % (307/395) e acima de 70 ms em 96 % "
     "(114/119). Se a fração p de quadros perturbados for independente entre quadros, a probabilidade de ao "
     "menos um par consecutivo em N quadros é 1 − (1 − p²)^N. Com N ≈ 230 quadros entre o instante crítico e o "
     "desfecho, a expressão dá 44 %, 90 % e 100 % para p = 5 %, 10 % e 20 %. É um limite superior: parte dos "
     "pares fica abaixo do limiar, e um quadro atrasado às vezes chega dentro da lacuna e a fecha. Com ordem de "
     "chegada, a bancada registrou 20 a 53 %, 63 a 67 % e 100 % (Figura 4). Daí uma regra de projeto: a "
     "supervisão só tolera k quadros consecutivos atrasados se S > (k + 1) T, com folga para a granularidade "
     "do contador."),
    ("Por isso a marca d'água produziu mais desligamentos e colisões do que a ordem de chegada (Tabela 3), apesar "
     "de entregar um fluxo ordenado.",
     "Por isso a marca d'água produziu mais episódios de desligamento e mais colisões do que a ordem de chegada "
     "(Tabela 3), apesar de entregar um fluxo ordenado. A ordem de chegada, por sua vez, entrega quadros velhos "
     "que podem violar a verificação de plausibilidade: a desordem que não engana a decisão engana o diagnóstico "
     "de sensor."),
    ("Em troca, a latência fixa de 360 a 670 ms recoloca o sistema na curva de H1a",
     "Em troca, a latência de 300 a 670 ms recoloca o sistema na curva de H1a"),
    ("Nas rodadas de 800 e 1000 ms a ECU entrou em OFF no fim da rodada em 23 e 26 casos, depois da parada ou "
     "do contato; a causa não foi isolada e esse indicador ficou fora da Tabela 2.",
     "Nas rodadas de 800 e 1000 ms a ECU entrou em OFF perto do fim em 23 e 26 casos: a distância recebida "
     "cruzou o alcance mínimo do lidar no firmware (1,0 m), em mediana 0,6 e 1,0 s depois da menor distância "
     "física, sem alterar o desfecho. Fora desses casos, H1a teve no máximo 3 de 30 desligamentos por nível, "
     "sem relação com o atraso, atribuídos a pausas de escalonamento da bancada."),
])
print("ok")
