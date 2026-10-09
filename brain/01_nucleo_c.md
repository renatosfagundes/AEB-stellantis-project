# 01 — Núcleo C (perception, decision, execution, integration)

Fonte: leitura completa de `include/*.h` e `src/**/*.c`. Linhas citadas são de v2.0.0.

## Tipos (`include/aeb_types.h`)

| Struct | Campos (unidade) |
|---|---|
| `perception_output_t` | `distance` [0.5,300] m, `v_ego` m/s, `v_rel` m/s (>0 = aproximando), `confidence` [0,1], `fault_flag` **bitmask** (comentário "0/1" é enganoso) |
| `ttc_output_t` | `ttc` [0,10] s, `d_brake` m, `is_closing` |
| `fsm_output_t` | `fsm_state` 0..6, `decel_target` m/s², `brake_active`, `alert_level` (FSM só gera 0..2), `warn_timer`, `state_timer` |
| `pid_output_t` | `brake_pct` [0,100], `brake_bar` = pct/10 |
| `alert_output_t` | `alert_type` (0 NONE,1 VIS,2 AUD,3 BOTH), `alert_active`, `buzzer_cmd` 0..4 |
| `driver_input_t` | `brake_pedal`, `accel_pedal`, `steering_angle` (graus), `aeb_enabled` |
| `raw_sensor_input_t` | `radar_d`, `radar_vr`, `lidar_d`, `v_ego`, `can_timeout`, `fi` (fault injection V&V) |

Fault bits: `AEB_FAULT_LIDAR=0x01`, `AEB_FAULT_RADAR=0x02`, `AEB_FAULT_CAN_TO=0x80` (0x80 também sinaliza `v_ego` não-finito).

## Constantes (`include/aeb_config.h`)

| Grupo | Valores |
|---|---|
| Tempo | `AEB_CYCLE_TIME_MS=10`, `AEB_DT=0.01` |
| TTC | `TTC_WARNING=4.0`, `TTC_BRAKE_L1=3.0`, `L2=2.2`, `L3=1.8`, `TTC_MAX=10.0`, `V_REL_MIN=0.5 m/s` |
| Pisos de distância | `D_FLOOR_L1=20`, `L2=10`, `L3=5` m |
| Faixa | `V_EGO_MIN=2.78` (10 km/h), `V_EGO_MAX=16.67 m/s` (60 km/h), `V_STOP_THRESHOLD=0.01` |
| Decel | `DECEL_L1=2`, `L2=4`, `L3=6 m/s²`, `POST_BRAKE_DECEL=5` (hold ≈50%) |
| Timing | `HYSTERESIS_TIME=0.2`, `WARNING_MIN_TIME=0.8`, `POST_BRAKE_HOLD=2.0` |
| PI | `PID_KP=10`, `PID_KI=0.05`, `PID_INTEG_MAX=50%`, saída [0,100]%, `MAX_JERK=10 m/s³` |
| Falha sensor | `SENSOR_FAULT_CYCLES=3`, `DIST_ROC_LIMIT=10 m/ciclo`, `VEL_ROC_LIMIT=2 m/s/ciclo`, `STEERING_OVERRIDE_DEG=5` |
| Faixas sensor | radar 0.5–200 m, lidar 1.0–100 m, `MAX_REL_VEL=50 m/s` |
| Kalman | R_lidar 0.0025, R_radar_d 0.09, R_radar_v 0.01; Q_d 1e-4, Q_v 1e-5; P0 1.0/0.25 |
| Saída | distância clampada [0.5, 300] m |
| CAN/UDS | 500 kbit/s, TX 50 ms, RX timeout 60 ms; DIDs F100/F101/F102, RID 0x0301 (módulos usam nomes próprios) |

## Perception (`src/perception/aeb_perception.c`)

- **Detectores de falha** (Simulink chart_26/33): frame "ruim" se não-finito, fora de faixa, ou |Δd|>10 m (e radar |Δvr|>2 m/s) vs. baseline. 3 ciclos ruins consecutivos (30 ms) → falha.
- **Latch**: baseline (`prev_d`, `prev_vr`) só atualiza com frame bom. Se o alvo "pulou" >10 m (ou v_rel >2 m/s) durante a falha, todo frame seguinte falha o ROC → **latch permanente até `perception_init()`** (só no power-on). Não há re-seed nem timeout. Frames fora de faixa (ex. d=0) não viram baseline — o 1º frame real é aceito sem ROC.
- **Fusão**: Kalman 2 estados x=[d, v_rel], F=[[1,−dt],[0,1]]; update lidar (H=[1 0]) depois radar (H=I₂). Lidar domina distância (R 36× menor). Semeado no 1º radar finito (inclusive 0 → saída clampada 0.5). README chama de "weighted fusion" — é Kalman.
- **Confiança**: 1.0/0.7/0.5/0 × max(0, 1−tr(P)/2). **Ninguém usa** downstream.
- `can_timeout` → `fault_flag=0x83`, mantém estado Kalman (sem predição), confiança 0.

## TTC (`src/decision/aeb_ttc.c`)

- `ttc = d / v_rel` se d>0 e v_rel>0.5, clamp 10; senão 10 (inclui NaN).
- `d_brake = v_ego² / (2·6)` (usa velocidade do ego, não relativa): 40 km/h → 10.3 m; 50 → 16.1 m.

## FSM (`src/decision/aeb_fsm.c`)

`evaluate_desired_state` (primeiro que casar): não aproximando → STANDBY; `d_brake ≥ d` → L3; d≤5 → L3; d≤10 → L2; d≤20 → L1; TTC≤1.8 → L3; ≤2.2 → L2; ≤3.0 → L1; ≤4.0 → WARNING; senão STANDBY.

`fsm_step` por prioridade:
1. Guards (dt inválido/NULL → retorna). `aeb_enabled` só vale se ==1U. Estado >6 → STANDBY.
2. **P1** `fault_flag≠0` ou AEB desabilitado → **OFF** (zera tudo). Qualquer falha de um sensor = OFF (sem modo degradado).
3. **P2** override (freio pedal ou |volante|>5°), exceto em POST_BRAKE → STANDBY. Sem latch.
4. **P3** fora de 10–60 km/h: (a) v<0.01 e estado≥L1 → POST_BRAKE (timer=0); (b) não freando → STANDBY; (c) freando em baixa velocidade → segue (brake hold pelos pisos); POST_BRAKE com v<0.01 → segue para P4 (timer de hold corre).
5. **P4** transições: POST_BRAKE sai após 2 s ou acelerador; WARNING sobe para o nível desejado só após 0.8 s (pode pular direto p/ L3), desce após 0.2 s; BRAKE sobe imediato, desce após 0.2 s **direto ao desejado** (pode pular níveis); STANDBY/OFF → WARNING obrigatório antes de frear.
6. Saídas: `decel_target` L1/L2/L3 = 2/4/6, POST_BRAKE = 5 (≈50%), demais 0; `alert_level` WARNING/L1=1, L2/L3=2.

## PID (`src/execution/aeb_pid.c`)

- Ativo só em {L1,L2,L3,POST_BRAKE} com entradas finitas e `decel_target>0`; senão reseta.
- `P=10·e`, integral `+=0.05·e·dt` clamp [0,50], saída [0,100], jerk limit 1.667 %/ciclo (subida 0→60% em 0.36 s); liberação instantânea.
- No core, `a_ego=0.0` fixo → **malha aberta**: L1≈20%, L2≈40%, L3≈60%. Mapeamento P (6 m/s²→60%) inconsistente com jerk (100%=6 m/s²).

## Alert (`src/execution/aeb_alert.c`)

| Estado | tipo | buzzer |
|---|---|---|
| OFF/STANDBY/POST_BRAKE | NONE | SILENT |
| WARNING | BOTH | SINGLE(1) |
| L1 | BOTH | DOUBLE(2) |
| L2 | BOTH | FAST_PULSE(4) |
| L3 | BOTH | CONTINUOUS(3) |

`override_detect()` é calculado no core mas não usado (FSM recalcula).

## Core (`src/integration/aeb_core.c`)

- `aeb_core_init`: memset, init de módulos, `can_init`, `uds_init`, `driver.aeb_enabled=1` (sobrescrito a cada step por `CAN 0x101 AND uds.aeb_enabled` → AEB OFF até chegar 0x101; UDS 0x0301=0 desliga).
- `aeb_core_step` sem NULL check; ordem na tabela do CLAUDE.md. Códigos de retorno de TX ignorados. `crc_error` e `actuator_fault` fixos em 0.
- Driver de ciclo SIL: `sil/zephyr_aeb/src/main.c` — `usleep(10000)` relativo (deriva), `radar_d = lidar_d = target_distance` (mesmo sinal para os dois sensores), `fi=0`.
