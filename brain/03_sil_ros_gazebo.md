# 03 — SIL (ROS 2 Humble + Gazebo Classic 11 + Zephyr, Docker Compose)

## Containers (`sil/docker-compose.yml`)

| Serviço | Imagem | Portas | Papel |
|---|---|---|---|
| canbus | python:3.11-slim | — (não publicada) | Relay TCP CAN em IP fixo **10.99.0.10** (rede 10.99.0.0/24) |
| gazebo | Dockerfile.gazebo (osrf/ros:humble-desktop) | 6080 noVNC | Xvfb :1 + x11vnc + websockify; `ros2 launch aeb_gazebo aeb_scenario.launch.py scenario:=ccrs_40` |
| aeb-ecu | Dockerfile.zephyr (multi-stage, contexto = raiz do repo) | — | `/app/build/zephyr/zephyr.exe` compilado do `src/` do repo |
| api | Dockerfile.api | 8000 | FastAPI; monta `/var/run/docker.sock` para reiniciar a ECU |
| dashboard | nginx:alpine | 3000 | UI estática; proxy `/api/` e `/novnc/` |

- Ordem: canbus (healthy) → gazebo (healthy = `ros2 topic list`, **fraco**: passa antes do mundo carregar) → ecu, api → dashboard.
- Volume `live-data` em `/tmp` (gazebo, api). Pacote `aeb_gazebo` é COPY no build → mudou código ROS, rebuild.
- CI (`sil.yml`) não builda gazebo nem roda cenário.

## Grafo ROS 2

| Tópico | Tipo | Pub → Sub |
|---|---|---|
| `/aeb/ego/cmd_vel`, `/aeb/target/cmd_vel` | Twist | scenario_controller → planar_move |
| `/aeb/ego/odom`, `/aeb/target/odom` | Odometry | planar_move → controller, perception |
| `/aeb/restart` | String (nome do cenário) | api → controller |
| `/aeb/stop` | Float64 | api → controller |
| `/aeb/driver_aeb_enable` | Int32 | api → perception |
| `/aeb/scenario_status` | String | controller → ninguém |
| `/aeb/scan` | LaserScan | gazebo → ninguém (só custo) |

Serviços: `/aeb/set_entity_state` (teleporte), `/reset_world`. Msgs custom `Aeb*.msg` geradas mas não usadas no Docker.

Mundo (`worlds/aeb_highway.world`): ODE 1 kHz, RTF 1.0; ego hatchback 1500 kg em (0,−1.85), alvo SUV 2000 kg em (100,−1.85); ambos com `planar_move` (velocidade imposta, sem dinâmica de pneu).

## scenario_controller.py

- CAN RX: 0x080 → `brake_pct = pressure/0.1`; 0x200 → nome do estado. **Freio: `decel = pct/100 × 10 m/s²`** (100% = 10 m/s²; L1 20% → 2 m/s²).
- Início: 1º odom → espera 5 s → teleporte (se gap≠100) → +2 s → roda. Ego vai de 0 ao cruzeiro **num degrau** (sem rampa).
- Distância = `target_x − ego_x − 4.5` (ground truth).
- Fim: d≤1 e v>5 km/h → COLLISION; d≤1 e v≤5 → STOPPED; `v_cmd<0.15` após 2 s → STOPPED; SETTLED (CCRm); 60 s → TIMEOUT.
- Telemetria `/tmp/aeb_live.json` ~10 Hz (escrita não atômica; TTC = d/(v_ego−v_alvo)).
- `/aeb/restart <nome>`: recarrega preset só se o nome estiver no dict local `SCENARIOS`; sempre teleporta.

## perception_node.py

- TX 0x100 (10 ms), 0x101 (10 ms), 0x120 (20 ms), após 1º odom.
- Sensores: radar 0.5–260 m, lidar 0.3–200 m, ruído σ=0.25 igual nos dois (ou `CAN_SIL_NOISE=1` → radar 0.25 / lidar 0.05). `noise_sigma_v` declarado e não usado (v_rel sem ruído).
- Fusão local 0.3·radar+0.7·lidar (ou lidar se diferença >5 m) → envia **uma** distância no 0x120; a ECU usa essa mesma distância como radar e lidar.
- 0x101: AEB_Enable = `/aeb/driver_aeb_enable` (default 1); pedais sempre 0.

## Cenários (`config/scenarios.yaml` é a fonte da API/dashboard)

| id | ego | alvo | gap | decel | critério |
|---|---|---|---|---|---|
| ccrs_20/30/40/50 | 20–50 | 0 | 100 | — | v_impact < 5 km/h |
| ccrs_50_no_aeb | 50 | 0 | 100 | — | controle (AEB off) |
| ccrm | 50 | 20 | 50 | — | Δv ≥ 20 km/h |
| ccrb_d2/d6_g12/g40 | 50 | 50 | 12/40 | −2/−6 após 2 s | v_impact < 15 km/h |
| uds_diagnostic | 0 | 0 | 100 | — | n/a |

**Drift (corrigido no branch `fix/sil-fsm-findings`)**: `ccrs_50_no_aeb` e `uds_diagnostic` faltavam no dict do `scenario_controller.py` e o controller mantinha o preset anterior. Ainda há corrida: após um run `no_aeb`, o perception segue mandando AEB desligado até a API republicar o enable (CLI ROS lenta).

Resultados de referência (`reports/sil/`): ccrs_20 10.1 m, ccrs_30 8.2, ccrs_40 5.3, ccrs_50 4.7, ccrm sem colisão, ccrb_d2_g40 1.4 m — **ccrb_d6_g40 colide a 19.7 km/h**. g12 não reportado (ECU fica offline ~2–3.5 s após Start → arriscado).

## API (`sil/docker/api/scenario_api.py`)

| Método | Rota | Efeito |
|---|---|---|
| GET | /scenarios | lista do yaml (carregado no import) |
| POST | /scenarios/start `{"scenario":id}` | `/reset_world` → `/aeb/restart id` → **restart container aeb-ecu** (docker SDK) → publica `driver_aeb_enable` (+ UDS 0x0301 se `disable_aeb`) |
| POST | /scenarios/stop, /scenarios/restart | stop / reset+restart ECU |
| GET | /status, /live | status da API; conteúdo de aeb_live.json |
| GET/POST | /uds/health, /uds/read_did/{did}, /uds/snapshot, /uds/clear_dtc, /uds/routine_control | UDS via `uds_client.py` |

Chamadas ROS via CLI `ros2` (segundos por chamada). Testes: `cd sil/docker/api && python -m pytest tests/test_uds_client.py` (15 casos, fora do CI).

## Dashboard

Polling `/api/live` a cada 100 ms (sem websocket). Alertas derivados do estado FSM (não do 0x300). Overlay de resultado só mostra STOPPED (colisão nunca aparece). iframe VNC aponta direto a `localhost:6080` (só funciona no host Docker). Toggle UDS é cosmético.

## Legado (não usado no Docker)

`aeb_node.py` (FSM Python), `aeb_controller_node.cpp` (não compila: inclui `aeb_main.h` inexistente), `dashboard_overlay.py` (PyQt5), `target_vehicle_controller.py`, `run.sh`, `launcher.sh`, `aeb_with_dashboard`/`ccr*.launch.py` (wrappers), `models/*/model.sdf` (mundo define veículos inline), `docker/canbridge/*`.

## Adicionar cenário

1. `config/scenarios.yaml` (API/dashboard; reiniciar api).
2. **`src/scenario_controller.py` `SCENARIOS`** (obrigatório, senão mantém preset antigo).
3. `launch/aeb_scenario.launch.py` `SCENARIOS` + descrição do arg.
4. `docker compose up --build` (gazebo copia o pacote).
Limites: gap ≲104.5 m (lidar max 100 m na ECU), ego 10–60 km/h para a FSM agir, |v_rel| ≤ 50 m/s.
