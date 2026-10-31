"""Diagnóstico dos desligamentos (OFF) da ECU a partir dos logs do relé. Reproduz os números do artigo:

1. Curva de disparo da supervisão (H1b): para cada intervalo entre entregas consecutivas de 0x120 dentro da
   janela instante crítico -> desfecho, com a ECU em alerta ou frenagem antes dele, verifica se o modo do
   comando 0x080 caiu para 0 durante o intervalo (ou até 15 ms depois). Agrupa por tamanho do intervalo.
2. OFF por alcance mínimo do lidar (H1a, 800 e 1000 ms): quanto tempo depois da menor distância física
   ele ocorre (mediana), e em quantas rodadas antes dela.

Uso: py -3.12 diagnostico_off.py
"""
import bisect
import collections
import csv
import statistics as st

import campanha_cep as c

FAIXAS = [(0, 50), (50, 60), (60, 70), (70, 10_000)]


def eventos(run_id):
    """Lê o log e devolve t_ttc3, t_desfecho, entregas de 0x120, modos de 0x080 e estados de 0x200."""
    cap = {}
    orig = c.desligamentos

    def espia(t_ttc3, entregas, vegos, saidas_ecu, t_desfecho=None):
        cap.update(t3=t_ttc3, tf=t_desfecho, ent=sorted(entregas), ecu=sorted(saidas_ecu))
        return orig(t_ttc3, entregas, vegos, saidas_ecu, t_desfecho)

    c.desligamentos = espia
    try:
        c.analisar_log(c.LOG_DIR / f"{run_id}.csv")
    finally:
        c.desligamentos = orig
    return cap


def curva_disparo():
    cont = collections.defaultdict(lambda: [0, 0])
    rows = [r for r in csv.DictReader(open(c.OUT / "h1b_ccrs_50.csv", encoding="utf-8")) if float(r["p_disorder"]) > 0]
    for r in rows:
        ev = eventos(r["run_id"])
        t3, tf = ev.get("t3"), ev.get("tf")
        if t3 is None or tf is None:
            continue
        ts = [e[0] for e in ev["ent"]]
        m80 = [(t, v) for t, k, v in ev["ecu"] if k == "080"]
        tm = [t for t, _ in m80]
        for a, b in zip(ts, ts[1:]):
            if not (t3 <= a and b <= tf):
                continue
            g = 1000 * (b - a)
            if g < 40:
                continue
            fx = next(f for f in FAIXAS if f[0] <= g < f[1])
            i = bisect.bisect_right(tm, a) - 1
            if i < 0 or m80[i][1] < 1:
                continue
            caiu = any(v == 0 for t, v in m80[i + 1:] if t <= b + 0.015)
            cont[fx][0] += 1
            cont[fx][1] += int(caiu)
    print("Curva de disparo (H1b, intervalos >= 40 ms com a ECU em alerta ou frenagem):")
    for f in FAIXAS:
        n, k = cont[f]
        rot = f"{f[0]}-{f[1]} ms" if f[1] < 10_000 else f">= {f[0]} ms"
        if f[0] == 0:
            rot = "40-50 ms"
        print(f"  {rot:>10}: {k}/{n} = {100 * k / n:.0f} %" if n else f"  {rot}: sem casos")


def off_alcance_h1a():
    rows = [r for r in csv.DictReader(open(c.OUT / "h1a_ccrs_50.csv", encoding="utf-8"))
            if r["delay_ms"] in ("800", "1000")]
    por = collections.defaultdict(list)
    for r in rows:
        path = c.LOG_DIR / f"{r['run_id']}.csv"
        t0, fis, ent, ecu = None, [], [], []
        with open(path, encoding="utf-8") as f:
            next(f)
            for line in f:
                p = line.rstrip("\n").split(",")
                cid, data, t = int(p[2]), bytes.fromhex(p[4]), float(p[0])
                if cid == 0x120:
                    d = c.u(data, 0, 16) * 0.01
                    if t0 is None:
                        if d < 60:
                            continue
                        t0 = t
                    if t >= t0:
                        fis.append((t - t0, d))
                    if p[1] and p[5] == "0":
                        ent.append((float(p[1]) - t0, d))
                elif cid == 0x200 and t0 is not None:
                    ecu.append((t - t0, c.u(data, 0, 8)))
        fis.sort(); ent.sort()
        # menor distância física antes do reset
        t_min, d_min, d_ant = None, None, None
        for t, d in fis:
            if d_ant is not None and d > d_ant + 20:
                break
            if d_min is None or d < d_min:
                d_min, t_min = d, t
            d_ant = d
        # primeiro OFF com distância entregue < 1 m nos 100 ms anteriores
        ts = [e[0] for e in ent]
        for t, est in ecu:
            if est != 0 or t < float(r["t_ttc3"]):
                continue
            i = bisect.bisect_right(ts, t) - 1
            j = bisect.bisect_left(ts, t - 0.1)
            if any(e[1] < c.LIDAR_DIST_MIN_M for e in ent[j:i + 1]):
                por[r["delay_ms"]].append(t - t_min)
                break
    print("OFF por alcance mínimo do lidar em H1a (instante do OFF menos instante da menor distância física):")
    for k, v in sorted(por.items(), key=lambda x: int(x[0])):
        print(f"  {k} ms: {len(v)} rodadas, mediana {st.median(v):.2f} s, antes da menor distância: {sum(x < 0 for x in v)}")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    curva_disparo()
    off_alcance_h1a()
