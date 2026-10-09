# 04 — Build, testes, V&V, CI, convenções

## Toolchain

- `make build|test|misra`: gcc C99 + make + libm (+ cppcheck com addon MISRA).
- `make vv-*`: **gcc-14/gcov-14** (nomes fixos; `-fcondition-coverage` = MC/DC nativo), gcovr ≥8.0 (Decision e PID+Alert; `venv/bin/gcovr` auto-detectado), lcov/genhtml 2.0, cppcheck 2.13 + `cppcheck-htmlreport`, valgrind, ASan/UBSan, python3, bc.
- **Windows**: nada roda nativo. Usar `docker/Dockerfile.vv` (Ubuntu 24.04 + gcc-14 etc.):
  ```
  docker build -t aeb-vv -f docker/Dockerfile.vv .
  docker run --rm -v "${PWD}:/work" -w /work aeb-vv make test
  ```
  Faltam na imagem: `cppcheck-htmlreport`, `bc`, `git`, gcovr≥8 (criar venv no repo) → `html-*` falha.

## Targets

| Target | Faz |
|---|---|
| `build` | compila 8 módulos + stub (gate zero-warning) |
| `test` | `test_smoke test_can test_perception test_decision test_pid test_alert test_uds test_integration` (não inclui `_fault/_mcdc/_struct`) |
| `sim_manual` | simulador interativo (`tools/sim_manual.c`) |
| `misra` | cppcheck MISRA em todos os fontes (não falha) |
| `mcdc-<m>` / `fault-<m>` / `memory-<m>` / `misra-<m>` / `html-<m>` / `vv-<m>` | por módulo `uds`, `decision`, `pid-alert`, `perception`, `can` → `reports/vv_<m>/` |

## Harness de testes

Sem framework: cada `tests/*.c` tem `main()` e macros próprias; exit 0 = pass. Sufixos: nenhum = requisitos; `_fault` = injeção de falhas (cross-validator); `_mcdc`/`_struct` = cobertura complementar; `smoke`; `integration` (via `aeb_core_step`, 8 casos). 19 arquivos, ~8.3k linhas.

Categorias de fault injection: **A** valores inválidos (NaN/Inf/NULL), **B** extremos numéricos, **C** corrupção de estado/SEU, **D** persistência/toggling, **E** timing (fora do escopo unitário → SIL).

Adicionar teste: `tests/test_x.c` → `SRC_X_TEST` + regra no Makefile → `TEST_BINS` → `.gitignore`/`clean` → (V&V) receitas do módulo + `paths:` do workflow `vv-<m>.yml`. Para HTML de fault, imprimir `[NN] nome ... PASS|FAIL` e `Results: N / M passed`.

## V&V por módulo (ISO 26262-6 ASIL-D como referência)

| Módulo | Autor → cross-validator | Cobertura (último snapshot) | Fault injection |
|---|---|---|---|
| UDS | Rian → **Renato** | 100% linhas/branches | 3 bugs (NaN, 2 SEU) corrigidos PR #94; gate 18/18 |
| Decision | Lourenço → Eryca | 97.7% L / 96.8% B / 96.6% MC/DC | 4 bugs corrigidos PR #107/#111; gate 32/32 |
| Perception | Eryca → Jéssica | ≥95% (gate) | 3 bugs corrigidos PR #93 (UBSan não pega NaN) |
| PID+Alert | Jéssica → Rian | 100/100 | 2 bugs PID (NaN, SEU blacklist); **gate não-bloqueante** no main |
| CAN | **Renato** → mphumapo2014 | ~99% L / 95.9% B / 95.2% cond | 1 UB (float→uint) corrigido PR #102 |

Evidências em `reports/` são snapshots de épocas diferentes (alguns pré-correção). Relatórios PDF consolidados ficam fora do repo.

## CI (`.github/workflows/`)

- `ci.yml`: push/PR em development/main → build, test, misra (misra não bloqueia).
- `vv-<m>.yml` (path-filtered): 4 gates bloqueantes — cobertura stmt/branch/MC/DC ≥95%, memória limpa, MISRA 0 (com desvios aceitos: 8.7/15.5 decision, 15.5 perception, 2.3/2.4 pid-alert, 10.6/14.4/2.5 can), fault injection 100%. Publica em GitHub Pages `vv_<m>/<branch>/`.
- `sil.yml`: compose config, hadolint, build api/canbridge, zephyr só até `zephyr-setup`, ruff, shellcheck.
- `publish-index.yml`: `docs/index.html` → gh-pages. Site: https://erycaaf.github.io/AEB-stellantis-project/
- Em `origin/development` (não no main): `publish-vv-reports.yml` agregado.

## Git

- `main` = releases (v1.0.0 2026-04-10, v2.0.0 2026-05-06); `development` = integração.
- Branches `feat/ fix/ test/ tests/ ci/ docs/ chore/`. Conventional Commits (fix 72, test 31, feat 29, docs 28, ci 28…).
- PR template: resumo, tipo, áreas AEB, requisitos impactados, artefatos, evidência (CCRs/CCRm/CCRb, back-to-back).

## Catálogo de requisitos (SRS v2.0, externo)

- **FR-PER-001..008** fusão/confiança, entradas do motorista, detecção de falha (006/007).
- **FR-DEC-001** TTC (só aproximando, clamp 10) · **002** d_brake=v²/(2·6) · **003/004** limiares e pisos · **005** piso de frenagem prioritário · **006/007** override freio/volante>5° · **008** 10–60 km/h · **010** debounce 0.2 s · **011** STANDBY passa por WARNING. (009 não referenciado.)
- **FR-FSM-001** inicia STANDBY · **002/003** desabilitado→OFF · **004** escalonamento · **005/006** POST_BRAKE.
- **FR-BRK-001** sem saltos >2 m/s²/ciclo · **002** PI anti-windup (erro <0.5 m/s² em 500 ms) · **003** ≥5 m/s² · **004** jerk ≤10 m/s³ · **005** hold ≥2 s após parar · **006** libera em 1 ciclo com acelerador · **007** saída [0,100]%.
- **FR-ALR-001/002** alerta visual/sonoro em 1 ciclo · **003** alerta ≥800 ms antes de frear · **004** sem alerta em OFF/STANDBY/POST_BRAKE.
- **FR-CAN-001..004** TX/RX/encoding/500k · **FR-UDS-001..005** 0x22, DTCs, 0x14, 0x31/0x0301, 0x7DF/0x7E8 · **FR-COD-001..003** correspondência com Simulink (`AEB_Integration.slx`, fora do repo).
- NFR: COD-005/006/007, PERF-001 (10 ms), POR-001..003, SAF-004/005/ROB/NULL, MEM-001, MIS-001, VAL-001/005.
