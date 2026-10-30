"""
Campanha SIL: atraso (H1a) e desordenação (H1b) isolados na telemetria percepção -> ECU.

Para cada rodada: grava a configuração de perturbação em docker/canbus/perturb.json (o relé lê sem
reiniciar), dispara o cenário pela API (POST /scenarios/start), acompanha /live até o fim, lê o log do
relé (docker/canbus/logs/<run_id>.csv) e grava uma linha no CSV da campanha.

Uso:
  py -3.12 campanha_cep.py --smoke                      # 1 rodada sem perturbação
  py -3.12 campanha_cep.py --plano h1a --reps 30        # atraso 0..1000 ms, ccrs_50
  py -3.12 campanha_cep.py --plano h1b --reps 30        # desordem 0..20 %, 2 distâncias, 3 políticas
  py -3.12 campanha_cep.py --plano h1a --reps 30 --cenario ccrs_40
Retoma de onde parou: rodadas já presentes no CSV não são repetidas.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import struct
import sys
import time
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CANBUS = AQUI.parent / "docker" / "canbus"
CFG_PATH = CANBUS / "perturb.json"
LOG_DIR = CANBUS / "logs"
OUT = AQUI / "resultados"
API = "http://localhost:8000"

ATRASOS_MS = (0, 25, 50, 100, 200, 400, 600, 800, 1000)
LAT_MEDIA_H1B = 100
DISTANCIAS = {"40-200": [40, 200], "200-600": [200, 600]}
POLITICAS = ("arrival", "watermark", "kslack")
FRACOES = (0.0, 0.05, 0.10, 0.20)

CAMPOS = ["campanha", "cenario", "rep", "run_id", "delay_ms", "p_disorder", "disorder", "policy", "seed", "resultado",
          "gap_final_m", "v_final_kmh", "t_inicio", "t_ttc3", "t_ttc1p8", "t_brake", "t_L2", "t_L3", "lat_brake_ms",
          "frames_percepcao", "frames_entregues", "descartados", "lacunas_60ms", "ecu_off", "max_mode", "dur_s", "erro"]


# ---------------------------------------------------------------- API
def http(method, path, body=None, timeout=20):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def live():
    try:
        return http("GET", "/live", timeout=5)
    except Exception:
        return None


def set_cfg(cfg):
    CFG_PATH.write_text(json.dumps(cfg), encoding="utf-8")
    time.sleep(0.6)   # o relé relê a cada 0,2 s


# ---------------------------------------------------------------- decodificação do log do relé
def u(data, start, length):
    r = 0
    for i in range(length):
        b = start + i
        r |= ((data[b // 8] >> (b % 8)) & 1) << i
    return r


def analisar_log(path):
    """Extrai do log do relé os instantes de interesse e contadores. Tempos relativos ao 1º frame 0x120."""
    res = dict(t_inicio=None, t_ttc3=None, t_ttc1p8=None, t_brake=None, t_L2=None, t_L3=None, frames_percepcao=0,
               frames_entregues=0, descartados=0, lacunas_60ms=0, ecu_off=0, max_mode=0)
    if not path.exists():
        return res
    t0, ult_out, v_ego = None, None, None
    with open(path, encoding="utf-8") as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").split(",")
            if len(p) < 6:
                continue
            t_in = float(p[0])
            t_out = float(p[1]) if p[1] else None
            cid, data, dropped = int(p[2]), bytes.fromhex(p[4]), p[5] == "1"
            if cid == 0x100:
                v_ego = u(data, 0, 16) * 0.01
            elif cid == 0x120:
                if t0 is None:
                    t0 = t_in
                res["frames_percepcao"] += 1
                if dropped:
                    res["descartados"] += 1
                else:
                    res["frames_entregues"] += 1
                    if ult_out is not None and t_out - ult_out > 0.06:
                        res["lacunas_60ms"] += 1
                    ult_out = t_out
                d = u(data, 0, 16) * 0.01
                vr = u(data, 16, 16) * 0.01 - 327.68
                v = vr if vr >= 0.5 else (v_ego or 0)
                if d < 95 and v >= 0.5:
                    ttc = d / v
                    if res["t_ttc3"] is None and ttc <= 3.0:
                        res["t_ttc3"] = t_in - t0
                    if res["t_ttc1p8"] is None and ttc <= 1.8:
                        res["t_ttc1p8"] = t_in - t0
            elif cid == 0x080 and t0 is not None:
                mode = u(data, 16, 3)
                res["max_mode"] = max(res["max_mode"], mode)
                if mode >= 2 and res["t_brake"] is None:
                    res["t_brake"] = t_in - t0
                if mode >= 3 and res["t_L2"] is None:
                    res["t_L2"] = t_in - t0
                if mode >= 4 and res["t_L3"] is None:
                    res["t_L3"] = t_in - t0
            elif cid == 0x200 and t0 is not None:
                if u(data, 0, 8) == 0 and res["t_ttc3"] is not None:
                    res["ecu_off"] = 1
    res["t_inicio"] = 0.0 if t0 is not None else None
    return res


# ---------------------------------------------------------------- uma rodada
def rodar(campanha, cenario, rep, cfg, timeout_inicio=60, timeout_fim=90):
    run_id = cfg["run_id"]
    linha = dict(campanha=campanha, cenario=cenario, rep=rep, run_id=run_id, delay_ms=cfg.get("delay_ms", 0),
                 p_disorder=cfg.get("p_disorder", 0.0), disorder="-".join(str(x) for x in cfg.get("disorder_ms", [0, 0])),
                 policy=cfg.get("policy", "arrival"), seed=cfg.get("seed", 1), erro="")
    t_run0 = time.time()
    set_cfg(dict(cfg, run_id=""))                     # sem log durante o reset, para não poluir
    try:
        http("POST", "/scenarios/start", {"scenario": cenario}, timeout=60)
    except Exception as e:
        linha.update(resultado="ERRO_API", erro=str(e)[:80])
        return linha
    set_cfg(cfg)                                      # liga o log e a perturbação para esta rodada
    # espera começar (live.time > 0)
    t_espera = time.time()
    while True:
        lv = live()
        if lv and lv.get("time", 0) > 0.3:
            break
        if time.time() - t_espera > timeout_inicio:
            linha.update(resultado="NAO_INICIOU", erro="live.time não avançou")
            set_cfg(dict(cfg, run_id=""))
            return linha
        time.sleep(0.05)
    # espera terminar (live.time volta a 0.0 no ramo 'ended')
    ultimo = lv
    t_espera = time.time()
    while True:
        lv = live()
        if lv:
            if lv.get("time", 0) == 0.0:
                break
            ultimo = lv
        if time.time() - t_espera > timeout_fim:
            linha.update(resultado="TIMEOUT_FIM")
            break
        time.sleep(0.05)
    fim = lv or ultimo
    time.sleep(0.3)
    set_cfg(dict(cfg, run_id=""))                     # fecha o log
    gap, v = fim.get("distance", 0.0), fim.get("speed_kmh", 0.0)
    if "resultado" not in linha:
        linha["resultado"] = "COLISAO" if (gap <= 1.0 and v > 5.0) else "PARADO"
    linha.update(gap_final_m=gap, v_final_kmh=v, dur_s=round(time.time() - t_run0, 1))
    an = analisar_log(LOG_DIR / f"{run_id}.csv")
    linha.update(an)
    if an["t_brake"] is not None and an["t_ttc3"] is not None:
        linha["lat_brake_ms"] = round((an["t_brake"] - an["t_ttc3"]) * 1000, 1)
    else:
        linha["lat_brake_ms"] = None
    return linha


# ---------------------------------------------------------------- planos
def plano(nome, cenario, reps):
    if nome == "smoke":
        yield dict(run_id=f"smoke_{cenario}", delay_ms=0, seed=1), 0
        return
    if nome == "h1a":
        for rep in range(reps):
            for d in ATRASOS_MS:
                yield dict(run_id=f"h1a_{cenario}_d{d:04d}_r{rep:02d}", delay_ms=d, seed=100 + rep), rep
    elif nome == "h1b":
        for rep in range(reps):
            for dnome, dist in DISTANCIAS.items():
                for p in FRACOES:
                    base = LAT_MEDIA_H1B - p * (dist[0] + dist[1]) / 2
                    for pol in POLITICAS:
                        if p == 0.0 and dnome != "40-200":
                            continue    # 0 % é igual nas duas distâncias
                        yield dict(run_id=f"h1b_{cenario}_{dnome}_p{int(p*100):02d}_{pol}_r{rep:02d}", delay_ms=base,
                                   p_disorder=p, disorder_ms=dist, policy=pol, watermark_ms=150, seed=200 + rep), rep
    else:
        raise SystemExit(f"plano desconhecido: {nome}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plano", default="smoke")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--reps", type=int, default=30)
    ap.add_argument("--cenario", default="ccrs_50")
    a = ap.parse_args()
    nome = "smoke" if a.smoke else a.plano
    OUT.mkdir(exist_ok=True)
    saida = OUT / f"{nome}_{a.cenario}.csv"
    feitos = set()
    if saida.exists():
        with open(saida, encoding="utf-8", newline="") as f:
            feitos = {r["run_id"] for r in csv.DictReader(f)}
    novo = not saida.exists()
    with open(saida, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if novo:
            w.writeheader()
        for cfg, rep in plano(nome, a.cenario, a.reps):
            if cfg["run_id"] in feitos:
                continue
            linha = rodar(nome, a.cenario, rep, cfg)
            w.writerow({k: linha.get(k) for k in CAMPOS})
            f.flush()
            print(f"{linha['run_id']}: {linha['resultado']} gap={linha.get('gap_final_m')} v={linha.get('v_final_kmh')} "
                  f"lat={linha.get('lat_brake_ms')} ms desc={linha.get('descartados')} lac60={linha.get('lacunas_60ms')} "
                  f"off={linha.get('ecu_off')} ({linha.get('dur_s')} s)", flush=True)
            if linha["resultado"] in ("ERRO_API", "NAO_INICIOU"):
                time.sleep(5)
    set_cfg(dict(run_id="", delay_ms=0))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
