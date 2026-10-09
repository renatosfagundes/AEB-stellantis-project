# 02 — Comunicação: CAN, UDS, HAL, Zephyr

**Não existe arquivo `.dbc`** no repo (citado em comentários como `aeb_system.dbc`). O layout vive em `src/communication/aeb_can.c` e espelhado em `sil/aeb_gazebo/src/can_codec.py`.

Regras: Intel little-endian, bit LSB-first; físico = raw·fator + offset; raw unsigned. 500 kbit/s nominal (ignorado pelos HALs).

## Frames

| ID | Nome | Dir | Período | DLC | Sinais |
|---|---|---|---|---|---|
| 0x080 | BrakeCmd | ECU→ | 10 ms | 4 | BrakeRequest b0; BrakePressure b1-15 ×0.1 bar (=pct/10); BrakeMode b16-18 (OFF/STBY=0,WARN=1,L1=2,L2=3,L3=4,PB=5); AliveCounter b24-27; CRC-4 b28-31 (init 0x0F, poly 0x3, bytes 0..2) |
| 0x200 | FSMState | ECU→ | 50 ms | 4 | FSMState b0-7; AlertLevel b8-15; BrakeActive b16-23; TTCThreshold b24-31 ×0.1 s |
| 0x300 | Alert | ECU→ | 10 ms (header diz event-driven) | 2 | AlertType b0-7; AlertActive b8; BuzzerCmd b9-11 |
| 0x100 | EgoVehicle | →ECU | 10 ms | 8 | Speed b0-15 ×0.01 m/s; LongAccel b16-31 ×0.001 −32; YawRate b32-47 ×0.01 −327.68; Steering b48-63 ×0.1 −3276.8 |
| 0x101 | DriverInput | →ECU | 10 ms | 4 | BrakePedal b0-7 %; AccelPedal b8-15 %; **AEB_Enable b16**; DriverOverride b17 (não usado) |
| 0x120 | RadarTarget | →ECU | 20 ms | 8 | Distance b0-15 ×0.01 m; RelSpeed b16-31 ×0.01 −327.68 (>0 aproximando); TTC b32-47 ×0.001 (ignorado); Confidence b48-55 (ignorado) |
| 0x7DF | UDS req | →ECU | evento | ≥4 | byte0 SID, 1-2 DID/RID, 3 valor (sem PCI ISO-TP) |
| 0x7E8 | UDS resp | ECU→ | evento | 8 | resp SID, DID echo, data1..5 |

- C vs Python: layouts idênticos; arredondamento difere (C +0.5 truncado; Python `round()` bancário); overflow de campo **envolve silenciosamente** nos dois lados; Python não verifica alive/CRC.
- Sinais decodificados e não usados: ttc_radar, confidence, long_accel (core passa `a_ego=0`), yaw, driver_override.

## Timeouts / E2E

- Só **0x120** é supervisionado: miss counter por ciclo, timeout em ≥6 ciclos (60 ms). Recupera no próximo 0x120 válido. 0x100/0x101 ficam stale para sempre.
- Timeout → `fault_flag |= 0x80` → FSM OFF + DTC C1001 latched.
- E2E só no TX 0x080; nenhum receptor verifica. DTCs C1004 (CRC) e C1006 (atuador) nunca setam (entradas fixas em 0).

## UDS (`src/communication/aeb_uds.c`, `sil/docker/api/uds_client.py`)

| SID | Serviço | Resposta |
|---|---|---|
| 0x22 | ReadDataByIdentifier | 0x62 + DID + dados |
| 0x14 | ClearDiagnosticInformation | 0x54 (limpa 3 DTCs; ignora group) |
| 0x31 | RoutineControl (sem sub-função) | 0x71 + RID + novo estado |
| outro | — | `7F SID 11`; SID 0x00 gera frame todo-zero |

- DIDs: **F100** TTC uint16 ×100 LE; **F101** estado FSM uint8; **F102** "brake pressure" = na verdade `brake_pct ×10` (%). NRC 0x31 para fora de faixa/desconhecido.
- RID **0x0301**: 0 desabilita, 1 habilita → `uds.aeb_enabled`, combinado com o bit 16 do 0x101 (`AND`) no core. Vale até o próximo power-on (restart da ECU volta para 1).
- DTCs C1001/C1004/C1006 latched sem debounce; não há 0x19 (não dá para ler DTCs pelo barramento). Sem sessões (0x10), TesterPresent, SecurityAccess. **Não conforme ISO 14229/15765** (é single-frame simplificado).

## HAL

- Interface (`stubs/can_hal.h`, duplicada em `sil/zephyr_aeb/src/can_hal.h`): `can_hal_init`, `can_hal_add_rx_filter`, `can_hal_send`; RX é push via `can_rx_process()`.
- Stub host: buffer TX de 32 frames (depois disso send falha → `can_hal_test_reset()`), 8 filtros, `force_init_fail`/`force_send_fail`.
- Zephyr (`can_hal_zephyr.c`): socket POSIX, 30 tentativas de conexão, **`inet_pton` só IPv4 literal** (por isso canbus = 10.99.0.10), pthread RX → ring SPSC 128 (drop silencioso se cheio, `volatile` sem barreiras), drenado no main loop. **Sem reconexão**. `extern can_rx_process(void*)` com protótipo divergente (UB/MISRA).

## Protocolo TCP (relay `sil/docker/canbus/can_tcp_server.py`)

16 bytes fixos por frame: `[0-3] ID uint32 LE | [4] DLC | [5-7] pad | [8-15] dados`. Relay faz broadcast para **todos os outros** clientes (sem eco, sem filtro, sem arbitragem, sem timestamp). Log a cada 100 frames.

## App Zephyr (`sil/zephyr_aeb/`)

- Zephyr v3.6.0, `native_sim`, base `ghcr.io/zephyrproject-rtos/ci:v0.26.13`; prj.conf: 1000 ticks/s, LOG nível 3, PTHREAD_IPC, CBPRINTF_FP.
- Log a cada 50 ciclos: `c= st= ttc= brk= d= v= flt= to=` → ciclo, estado FSM, TTC, freio %, distância fundida, `v` do 0x100 (m/s), `fault_flag` decimal (1 lidar, 2 radar, 128 CAN_TO; 131 = todos), timeout (defasado 1 ciclo).
- Diagnóstico rápido: `flt=2` = só radar (ROC de velocidade); `flt=3` = distância/faixa (ambos); `≥128` = timeout CAN.
