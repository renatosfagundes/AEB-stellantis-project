# 05 — Achados: bugs, inconsistências e limitações

Legenda: ✅ **corrigido no branch `fix/sil-fsm-findings`** · **[código]** confirmado lendo o código · **[execução]** observado rodando o SIL em 2026-09-26 · **[inferência]** deduzido, não testado.

## Segurança funcional / comportamento

1. ✅ **POST_BRAKE não expirava com o carro parado** [código `aeb_fsm.c:254-265`]. Com v<0.01, a prioridade 3(a) dispara todo ciclo (`current_state >= FSM_BRAKE_L1` inclui POST_BRAKE=6), zera o timer e retorna antes da P4 → os 2 s e o acelerador nunca atuam. Testes usam v=5 m/s em POST_BRAKE e mascaram o problema.
2. ✅ **POST_BRAKE aplicava 0% de freio** [código]. Agora a FSM pede `POST_BRAKE_DECEL` = 5 m/s² (≈50% com o PI em malha aberta), conforme o README do Gazebo; verificado no SIL (51%). O README principal ainda fala em −6 m/s².
3. **OFF pode "grudar" após a falha limpar** [código `aeb_fsm.c:367-389`]: sem ameaça, OFF permanece OFF (README diz OFF→STANDBY).
4. **Latch da falha do radar/lidar** [código + execução]. Baseline ROC só atualiza com frame bom; salto >10 m ou Δv_rel >2 m/s trava a falha até power-on. No boot do SIL o ego salta 0→11 m/s em um degrau → `flt=2` (ROC de velocidade, só radar) → FSM OFF → **auto-run ccrs_40 colide a 40 km/h**. Workaround da API: reiniciar o container da ECU a cada Start.
5. **Qualquer falha de um sensor = OFF** (sem modo degradado) [código]. No SIL, lidar=radar=mesma distância → alvo >100 m gera falha de lidar.
6. **Pisos de distância escalam, não só seguram** [código]: 20 m aproximando a 0.6 m/s (TTC 33 s) pede L1; `d_brake ≥ d` usa v_ego (seguir a 50 km/h com gap <16 m → L3).
7. **Desescalonamento pula níveis** (L3→STANDBY após 0.2 s) e o debounce não é estritamente consecutivo [código].
8. **PID em malha aberta** (`a_ego=0`); liberação sem limite de jerk [código].
9. **ccrb_d6_g40 colide a 19.7 km/h** [reports/sil] — L3 entra tarde (sintonia da FSM).

## Comunicação / diagnóstico

10. ✅ **UDS RoutineControl 0x0301 não desabilitava o AEB** [código]: escreve `uds.aeb_enabled`, ninguém lê. Agora `driver.aeb_enabled = CAN 0x101 AND uds.aeb_enabled`; o toggle do dashboard passa a ter efeito (até o próximo restart da ECU).
11. **AEB fica OFF até chegar o 1º frame 0x101** (`aeb_enabled` sobrescrito com 0 do memset) [código].
12. Só 0x120 tem timeout; 0x100/0x101 podem ficar stale indefinidamente [código].
13. Alive counter/CRC só no TX 0x080 e ninguém verifica; DTC C1004/C1006 impossíveis [código].
14. UDS não conforme ISO 14229/15765 (sem ISO-TP, sessões, 0x19; F102 retorna % e não bar) [código].
15. ECU sem reconexão TCP; ring RX sem barreiras de memória; protótipo `can_rx_process` divergente [código].
16. Timing por `usleep` relativo (deriva) — NFR-PERF-001 aproximado [código].

## SIL / ferramentas

17. ✅ **Drift de cenários**: `ccrs_50_no_aeb` e `uds_diagnostic` ausentes do `scenario_controller.py` → mantém o preset anterior [código + execução: run "no_aeb" a 11.1 m/s = 40 km/h].
18. Healthcheck do gazebo fraco (passa antes do mundo carregar) [código].
19. Timers `create_timer(2.0, …)` nunca cancelados → restarts podem iniciar antes do teleporte [código/inferência].
20. ECU offline ~2–3.5 s após Start (restart) → cenários g12 arriscados [inferência].
21. ✅ (só o TTC) TTC da telemetria usava v_ego (errado p/ CCRm/CCRb); JSON não atômico; colisão nunca aparece no dashboard [código].
22. Freio no simulador: 100% = 10 m/s², veículos com `planar_move` (velocidade imposta, sem pneu/atraso de atuador) [código].

## Calibração / documentação

23. ✅ Macros `D_FLOOR_*`, `HYSTERESIS_TIME`, `WARNING_MIN_TIME`, `POST_BRAKE_HOLD` não usadas (literais na FSM) — contraria NFR-POR-002.
24. README: "weighted fusion" (é Kalman), POST_BRAKE −6 m/s², OFF→STANDBY, descida passo a passo — divergem do código.
25. Sem `.dbc`; SRS e modelo Simulink fora do repo.

## Por que isso importa para experimentos

Os itens 4, 5, 12, 13 e 20 são **problemas de tempo/ordem/frescor de eventos** e de **supervisão de degradação**: em experimentos que injetam atraso, desordem ou perda no barramento, eles disparam timeout/latch e levam a FSM a OFF, mascarando o efeito que se quer medir.
