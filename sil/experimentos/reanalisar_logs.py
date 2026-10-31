"""Reprocessa os logs do relé já gravados com a análise atual de campanha_cep.analisar_log.

Motivo (31/10/2026): na versão anterior, o instante crítico (TTC <= 3 s) podia ser tirado de um quadro
gerado ANTES do início da rodada (ego parado perto do alvo anterior) e entregue depois, por causa do
atraso extra de H1b. Isso afetava t_ttc3, lat_brake_ms, a janela do critério de validade (trava_pre_ms)
e o indicador ecu_off. Além disso, ecu_off passou a separar o OFF por supervisão de comunicação do OFF
por alcance mínimo do lidar perto do contato (ecu_off_alcance).

Colunas físicas (resultado, gap_final_m, v_final_kmh) vêm do simulador e não mudam. A configuração da
rodada e a conformidade (atraso e desordem medidos) também não dependem do instante crítico.

Uso: py -3.12 reanalisar_logs.py resultados/h1a_ccrs_50.csv resultados/h1b_ccrs_50.csv
O CSV original é preservado como <nome>_v1.csv (só na primeira execução) e o corrigido o substitui.
"""
import csv
import shutil
import sys
from pathlib import Path

from campanha_cep import CAMPOS, LOG_DIR, TRAVA_MAX_MS, analisar_log

AQUI = Path(__file__).resolve().parent
DERIVADAS = ["t_inicio", "t_ttc3", "t_ttc1p8", "t_brake", "t_L2", "t_L3", "frames_percepcao", "frames_entregues",
             "descartados", "lacunas_60ms", "ecu_off", "ecu_off_alcance", "standby_baixa_vel", "n_off", "off_lacuna", "off_salto",
             "off_sem_causa", "max_mode", "trava_pre_ms",
             "atraso_medido_ms", "fora_ordem_medido"]


def reprocessar(arq):
    arq = (AQUI / arq).resolve()
    v1 = arq.with_name(arq.stem + "_v1.csv")
    if not v1.exists():
        shutil.copy(arq, v1)
    rows = list(csv.DictReader(open(v1, encoding="utf-8", newline="")))
    mud = dict(validade=[], ttc=0, off=0, sem_log=0)
    novas = []
    for r in rows:
        path = LOG_DIR / f"{r['run_id']}.csv"
        if not path.exists():
            mud["sem_log"] += 1
            novas.append(r)
            continue
        an = analisar_log(path)
        n = dict(r)
        for k in DERIVADAS:
            n[k] = an.get(k)
        if an["t_brake"] is not None and an["t_ttc3"] is not None:
            n["lat_brake_ms"] = round((an["t_brake"] - an["t_ttc3"]) * 1000, 1)
        else:
            n["lat_brake_ms"] = None
        tr = an.get("trava_pre_ms")
        n["valida"] = int(tr is not None and tr <= TRAVA_MAX_MS and r["resultado"] in ("PARADO", "COLISAO"))
        if str(n["valida"]) != r["valida"]:
            mud["validade"].append((r["run_id"], r["valida"], n["valida"], tr))
        if r["t_ttc3"] and an["t_ttc3"] is not None and abs(float(r["t_ttc3"]) - an["t_ttc3"]) > 0.05:
            mud["ttc"] += 1
        if r["ecu_off"] != str(an["ecu_off"]):
            mud["off"] += 1
        novas.append(n)
    with open(arq, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for n in novas:
            w.writerow({k: n.get(k) for k in CAMPOS})
    print(f"{arq.name}: {len(rows)} rodadas; t_ttc3 mudou em {mud['ttc']}; ecu_off mudou em {mud['off']}; "
          f"validade mudou em {len(mud['validade'])}; sem log {mud['sem_log']}")
    for rid, a, b, tr in mud["validade"]:
        print(f"   validade {rid}: {a} -> {b} (trava_pre {tr} ms)")


if __name__ == "__main__":
    for a in sys.argv[1:]:
        reprocessar(a)
