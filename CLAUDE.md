# AEB Stellantis Project — Brain (índice)

Sistema acadêmico de **Autonomous Emergency Braking** (residência UFPE/CIn + Stellantis), release **v2.0.0** (`main` @ 5cf8eba). C99/MISRA C:2012, orientado a ISO 26262, validado em **SIL** (Zephyr `native_sim` + Gazebo Classic 11 + ROS 2 Humble, Docker). Autores: Eryca, Jéssica, Lourenço, **Renato Fagundes** (autor do módulo CAN, cross-validator do UDS), Rian.

> Detalhes em [brain/](brain/). Este arquivo é o mapa; leia o arquivo de detalhe antes de mexer numa área.
> Brain criado em 2026-09-26 a partir de leitura completa do código + execução real do SIL. Ao mudar o código, atualize o arquivo correspondente.

| Arquivo | Conteúdo |
|---|---|
| [brain/01_nucleo_c.md](brain/01_nucleo_c.md) | Tipos, TODAS as constantes de `aeb_config.h`, perception (Kalman, ROC), TTC, FSM (prioridades/transições), PID, alert, `aeb_core_step` |
| [brain/02_comunicacao_can_uds.md](brain/02_comunicacao_can_uds.md) | Tabela de frames CAN (bits/escala), timeouts, E2E, UDS (SIDs/DIDs/RIDs/DTCs), HAL, protocolo TCP de 16 bytes, app Zephyr |
| [brain/03_sil_ros_gazebo.md](brain/03_sil_ros_gazebo.md) | Containers, grafo ROS 2, scenario_controller, perception_node, cenários, API, dashboard, como adicionar cenário |
| [brain/04_build_testes_vv_ci.md](brain/04_build_testes_vv_ci.md) | Makefile, harness de testes, V&V por módulo (MC/DC, fault injection, memória, MISRA), CI, convenções git, catálogo de requisitos |
| [brain/05_achados_bugs_gaps.md](brain/05_achados_bugs_gaps.md) | **Bugs e inconsistências confirmados** (POST_BRAKE, UDS enable sem efeito, drift de cenários, latch ROC…) — insumo de pesquisa |

## Arquitetura em 1 minuto

```
perception_node (Gazebo, ROS2) --0x100/0x101/0x120--> canbus relay TCP :29536 --> aeb-ecu (Zephyr native_sim, 10 ms)
                                                                                     perception -> ttc -> fsm -> pid -> alert -> uds
scenario_controller (Gazebo) <--0x080 BrakeCmd / 0x200 FSMState / 0x300 Alert-------- aeb-ecu
scenario_controller -> /tmp/aeb_live.json -> api :8000 /live -> nginx dashboard :3000 (polling 100 ms)
```

- Pipeline por ciclo (10 ms): `can_check_timeout → driver inputs (CAN) → perception_step → ttc_process → fsm_step → pid_brake_step → alert_map → uds_monitor_faults → UDS req/resp → TX 0x080(10ms) 0x200(50ms) 0x300(10ms)` ([src/integration/aeb_core.c](src/integration/aeb_core.c)).
- FSM 7 estados: `OFF=0 STANDBY=1 WARNING=2 BRAKE_L1=3 BRAKE_L2=4 BRAKE_L3=5 POST_BRAKE=6`. TTC 4.0/3.0/2.2/1.8 s; decel 2/4/6 m/s²; pisos de distância 20/10/5 m; faixa 10–60 km/h; WARNING ≥0.8 s antes de frear; debounce de descida 0.2 s.

## Rodar (Windows + Docker Desktop — testado)

```bash
cd sil
docker compose up -d            # 1ª vez: docker compose build (~15-20 min)
# http://localhost:3000 dashboard | :6080/vnc.html Gazebo | :8000/docs API
curl -X POST localhost:8000/scenarios/start -H "Content-Type: application/json" -d '{"scenario":"ccrs_40"}'
docker compose logs --no-log-prefix aeb-ecu | grep flt=   # log ECU a cada 500 ms
docker compose down
```

- **Sempre dê Start** (dashboard ou API) antes de avaliar: o auto-run do boot colide porque a ECU trava em falha de radar (ROC de velocidade, `flt=2`) quando o ego salta 0→cruzeiro. `/scenarios/start` reinicia o container da ECU e limpa o latch. Resultado verificado (branch `fix/sil-fsm-findings`): ccrs_40 para a **6.4 m**, FSM `STANDBY→WARNING→L1→L2→L1→L2→POST_BRAKE (51% de freio, 2 s)→STANDBY`.
- Repo local configurado com `core.autocrlf=false` / `core.eol=lf` (CRLF quebra scripts nos containers).
- Testes C no host precisam de Linux: `docker build -t aeb-vv -f docker/Dockerfile.vv .` e `docker run --rm -v "${PWD}:/work" -w /work aeb-vv make test` (ver brain/04).

## Mapa do repositório

| Caminho | O quê |
|---|---|
| `include/` | Contratos: `aeb_types.h`, `aeb_config.h` (calibração), headers por módulo |
| `src/perception/` `src/decision/` `src/execution/` `src/communication/` `src/integration/` | Módulos C (perception; ttc+fsm; pid+alert; can+uds; core) |
| `stubs/` | HAL CAN de host (buffer TX 32, fault injection) + stub Zephyr |
| `tests/` | 19 suites standalone (`test_<m>.c`, `_fault`, `_mcdc`, `_struct`, smoke, integration) |
| `tools/sim_manual.c` | Simulador interativo de terminal (`make sim_manual`) |
| `sil/` | Stack SIL Docker (ver brain/03); `sil/zephyr_aeb/` app Zephyr |
| `reports/` | Evidências V&V por módulo + `reports/sil/` (runs CCR) |
| `.github/workflows/` | `ci.yml`, `vv-<módulo>.yml` (gates ≥95% MC/DC etc.), `sil.yml`, `publish-index.yml` |

## Convenções

- Conventional Commits `type(scope): subject`; PRs para `development` com template; release `development → main` + tag.
- Código: C99, `-Wall -Wextra -Wpedantic` sem warnings, tipos de largura fixa, `@requirement FR-xxx` em cada função, single-exit/NULL guards (MISRA). Calibração só em `aeb_config.h` (apesar de a FSM ainda ter literais — ver brain/05).
- Requisitos do "SRS v2.0" (documento fora do repo): FR-PER, FR-DEC, FR-FSM, FR-BRK, FR-ALR, FR-CAN, FR-UDS, FR-COD, NFR-* (catálogo em brain/04).

## Uso como bancada de pesquisa

O SIL é usado como bancada experimental para estudos de V2X e de processamento de eventos (atraso, desordem e perda de mensagens). Os achados do [brain/05](brain/05_achados_bugs_gaps.md) que envolvem tempo, ordem e frescor de eventos são ameaças à validade desses experimentos e devem ser declarados ou corrigidos antes de coletar dados.
