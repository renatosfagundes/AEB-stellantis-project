# Experimentos de eventos atrasados e fora de ordem na bancada SIL

Campanha H1a / H1b do artigo *Impacto de eventos atrasados e fora de ordem na segurança de sistemas AEB*
(Fagundes, Varoto, Arakaki; PCS5039, Poli-USP), executada na bancada SIL deste repositório.

## Como funciona

O relé TCP CAN (`docker/canbus/can_tcp_server.py`) ganhou um estágio de perturbação configurável em
tempo de execução por `docker/canbus/perturb.json` (o diretório é um bind mount, então o host altera o
arquivo entre rodadas sem reiniciar contêineres). Só os frames percepção → ECU (0x100, 0x101, 0x120)
são perturbados; os frames da ECU (0x080, 0x200, 0x300) passam direto. O relé grava cada frame em
`docker/canbus/logs/<run_id>.csv` com os instantes de entrada e de saída.

```
percepção ──► relé: [atraso + jitter + desordem + perda] ──► [política: chegada | watermark | K-slack] ──► ECU
ECU ──► relé ──► scenario_controller (sem perturbação)
```

`campanha_cep.py` escreve a configuração, dispara o cenário pela API (`POST /scenarios/start`),
acompanha `/live` até o fim, lê o log do relé e grava uma linha por rodada em `resultados/<plano>_<cenario>.csv`
(retoma de onde parou). `analise_campanha.py` agrega em tabelas e figuras. `teste_relay.py` testa o
relé sem Docker.

## Rodar

```
cd sil
docker compose up -d                      # 1ª vez: docker compose build (~15-20 min)
cd experimentos
py -3.12 teste_relay.py                   # teste do relé (sem Docker)
py -3.12 campanha_cep.py --smoke          # 1 rodada sem perturbação (ccrs_50)
py -3.12 campanha_cep.py --plano h1a --reps 30
py -3.12 campanha_cep.py --plano h1b --reps 30
py -3.12 analise_campanha.py
```

## Métricas por rodada

`resultado` (PARADO / COLISAO), `gap_final_m`, `v_final_kmh` (velocidade de impacto quando colide),
`t_ttc3` (1ª leitura 0x120 com TTC ≤ 3 s, na entrada do relé), `t_brake` (1º 0x080 com modo ≥ L1),
`lat_brake_ms` = `t_brake − t_ttc3` (comparar com a média das rodadas sem atraso), `t_L2`, `t_L3`,
`descartados` (frames rejeitados pela política), `lacunas_60ms` (intervalos > 60 ms entre entregas de
0x120 à ECU: risco do timeout de supervisão do firmware, que desliga o AEB), `ecu_off` (FSM em OFF
observada após o TTC crítico), `max_mode`.

## Planos

- **H1a** (atraso isolado): atraso fixo 0, 25, 50, 100, 200, 400, 600, 800, 1000 ms; ordem, jitter e perda
  constantes; 30 repetições (sementes 100..129) por nível.
- **H1b** (desordenação isolada): latência média 100 ms; 0, 5, 10, 20 % de frames com atraso extra uniforme
  de 40–200 ms ou 200–600 ms; políticas ordem de chegada, watermark (150 ms) e K-slack adaptativo; 30 repetições.

Os mesmos protocolos foram executados antes em simulação pura (`research/cep_digital_twin/experimento_h1.py`),
o que permite comparar modelo e bancada.
