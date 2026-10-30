"""Resumo do plano reduzido (resultados/rapido_<cenario>.csv): só rodadas válidas.
Uso: py -3.12 analise_rapido.py [--cenario ccrs_50]
"""
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev

AQUI = Path(__file__).resolve().parent
OUT = AQUI / "resultados"


def fl(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def f(xs, k=0):
    xs = [x for x in xs if x is not None]
    return f"{mean(xs):.{k}f}" if xs else "-"


def sd(xs, k=0):
    xs = [x for x in xs if x is not None]
    return f"{pstdev(xs):.{k}f}" if len(xs) > 1 else "-"


def tab(cab, linhas):
    return "\n".join(["| " + " | ".join(cab) + " |", "|" + "|".join("---" for _ in cab) + "|"] +
                     ["| " + " | ".join(str(c) for c in l) + " |" for l in linhas])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cenario", default="ccrs_50")
    a = ap.parse_args()
    rs = list(csv.DictReader(open(OUT / f"rapido_{a.cenario}.csv", encoding="utf-8", newline="")))
    val = [r for r in rs if r.get("valida") == "1"]
    md = [f"# SIL, plano reduzido ({a.cenario}): {len(val)} rodadas válidas de {len(rs)}\n",
          "Válida = percepção sem trava > 100 ms nos 3 s antes do TTC crítico (entrada do relé).\n"]
    h1a = defaultdict(list)
    for r in val:
        if r["run_id"].startswith("rap_h1a"):
            h1a[int(float(r["delay_ms"]))].append(r)
    linhas = []
    for d in sorted(h1a):
        ls = h1a[d]
        col = [r for r in ls if r["resultado"] == "COLISAO"]
        lat = [fl(r["lat_brake_ms"]) for r in ls]
        linhas.append([d, len(ls), f(lat), sd(lat), f"{100 * mean((x or 0) > 100 for x in lat):.0f}%",
                       f([fl(r["gap_final_m"]) for r in ls if r["resultado"] == "PARADO"], 2),
                       f"{len(col)}/{len(ls)}", f([fl(r["v_final_kmh"]) for r in col], 1) if col else "-",
                       f"{sum(int(r['ecu_off'] or 0) for r in ls)}/{len(ls)}"])
    md.append("## H1a: atraso isolado\n")
    md.append(tab(["Atraso (ms)", "n", "TTC crítico → freio (ms)", "σ", "> 100 ms", "Dist. parada (m)", "Colisões", "v impacto (km/h)", "ECU OFF"], linhas))
    h1b = defaultdict(list)
    for r in val:
        if r["run_id"].startswith("rap_h1b"):
            h1b[r["policy"]].append(r)
    linhas = []
    for pol in ("arrival", "watermark", "kslack"):
        ls = h1b.get(pol, [])
        if not ls:
            continue
        col = [r for r in ls if r["resultado"] == "COLISAO"]
        linhas.append([pol, len(ls), f([fl(r["lat_brake_ms"]) for r in ls]), f([fl(r["descartados"]) for r in ls], 1),
                       f([fl(r["lacunas_60ms"]) for r in ls], 1), f"{sum(int(r['ecu_off'] or 0) for r in ls)}/{len(ls)}",
                       f([fl(r["gap_final_m"]) for r in ls if r["resultado"] == "PARADO"], 2), f"{len(col)}/{len(ls)}",
                       f([fl(r["v_final_kmh"]) for r in col], 1) if col else "-"])
    md.append("\n\n## H1b: 20 % fora de ordem (+200 a 600 ms), latência média 100 ms\n")
    md.append(tab(["Política", "n", "TTC crítico → freio (ms)", "Descartados", "Lacunas > 60 ms à ECU", "ECU OFF", "Dist. parada (m)", "Colisões", "v impacto (km/h)"], linhas))
    txt = "\n".join(md) + "\n"
    (OUT / f"resumo_rapido_{a.cenario}.md").write_text(txt, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
