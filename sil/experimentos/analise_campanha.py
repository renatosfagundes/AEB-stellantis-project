"""Agrega os CSV da campanha SIL (resultados/h1a_*.csv, h1b_*.csv) em tabelas Markdown e figuras.
Uso: py -3.12 analise_campanha.py [--cenario ccrs_50]
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev, quantiles

AQUI = Path(__file__).resolve().parent
OUT = AQUI / "resultados"


def ler(path):
    with open(path, encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if r["resultado"] in ("PARADO", "COLISAO", "TIMEOUT_FIM")]


def fl(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def f1(xs, k=1):
    xs = [x for x in xs if x is not None]
    return f"{mean(xs):.{k}f}" if xs else "-"


def sd(xs):
    xs = [x for x in xs if x is not None]
    return f"{pstdev(xs):.1f}" if len(xs) > 1 else "-"


def p95(xs):
    xs = [x for x in xs if x is not None]
    return f"{quantiles(xs, n=20)[-1]:.0f}" if len(xs) >= 2 else "-"


def md_tabela(cab, linhas):
    out = ["| " + " | ".join(cab) + " |", "|" + "|".join("---" for _ in cab) + "|"]
    out += ["| " + " | ".join(str(c) for c in l) + " |" for l in linhas]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cenario", default="ccrs_50")
    a = ap.parse_args()
    md = [f"# Campanha SIL ({a.cenario})\n"]
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    h1a = OUT / f"h1a_{a.cenario}.csv"
    if h1a.exists():
        rs = ler(h1a)
        por = defaultdict(list)
        for r in rs:
            por[int(float(r["delay_ms"]))].append(r)
        base = por.get(0, [])
        lat0 = mean(fl(r["lat_brake_ms"]) for r in base if fl(r["lat_brake_ms"]) is not None) if base else 0.0
        md.append(f"## H1a: atraso isolado ({len(rs)} rodadas válidas; latência relativa à média das rodadas sem atraso, {lat0:.0f} ms)\n")
        linhas, xs, lat_m, dist_m, col_m = [], [], [], [], []
        for d in sorted(por):
            ls = por[d]
            lat = [fl(r["lat_brake_ms"]) - lat0 for r in ls if fl(r["lat_brake_ms"]) is not None]
            col = [r for r in ls if r["resultado"] == "COLISAO"]
            gap = [fl(r["gap_final_m"]) for r in ls if r["resultado"] == "PARADO"]
            linhas.append([d, len(ls), f1(lat, 0), sd(lat), p95(lat), f"{100 * mean(x > 100 for x in lat):.0f}%" if lat else "-",
                           f1(gap, 2), f"{100 * len(col) / len(ls):.0f}%", f1([fl(r['v_final_kmh']) for r in col], 1) if col else "-",
                           f1([fl(r["lacunas_60ms"]) for r in ls], 1), f"{100 * mean(fl(r['ecu_off']) or 0 for r in ls):.0f}%"])
            xs.append(d); lat_m.append(mean(lat) if lat else float("nan")); dist_m.append(mean(gap) if gap else 0.0); col_m.append(100 * len(col) / len(ls))
        md.append(md_tabela(["Atraso (ms)", "n", "Latência de frenagem (ms)", "σ", "p95", "Excede 100 ms", "Dist. parada (m)", "Colisões",
                             "v impacto (km/h)", "Lacunas > 60 ms", "ECU OFF"], linhas))
        fig, axs = plt.subplots(1, 3, figsize=(10.5, 3.3))
        axs[0].plot(xs, lat_m, "o-", color="#b03a2e"); axs[0].axhline(100, color="#888", ls="--", lw=1); axs[0].set_ylabel("latência adicional de frenagem (ms)")
        axs[1].plot(xs, dist_m, "o-", color="#b03a2e"); axs[1].set_ylabel("distância de parada (m)")
        axs[2].plot(xs, col_m, "o-", color="#b03a2e"); axs[2].set_ylabel("colisões (%)"); axs[2].set_ylim(-3, 103)
        for ax in axs:
            ax.set_xlabel("atraso da telemetria (ms)"); ax.grid(alpha=.3)
        fig.suptitle(f"SIL, {a.cenario}: atraso isolado (H1a)", fontsize=10); fig.tight_layout()
        fig.savefig(OUT / f"fig_sil_h1a_{a.cenario}.png", dpi=160)

    h1b = OUT / f"h1b_{a.cenario}.csv"
    if h1b.exists():
        rs = ler(h1b)
        md.append(f"\n\n## H1b: desordenação isolada ({len(rs)} rodadas válidas; latência média {100} ms)\n")
        for dist in ("40-200", "200-600"):
            md.append(f"\n### Distância da desordenação {dist} ms\n")
            linhas = []
            for p in (0.0, 0.05, 0.10, 0.20):
                for pol in ("arrival", "watermark", "kslack"):
                    ls = [r for r in rs if float(r["p_disorder"]) == p and r["policy"] == pol and (r["disorder"] == dist or p == 0.0)]
                    if not ls:
                        continue
                    col = [r for r in ls if r["resultado"] == "COLISAO"]
                    gap = [fl(r["gap_final_m"]) for r in ls if r["resultado"] == "PARADO"]
                    linhas.append([f"{100 * p:.0f}%", pol, len(ls), f1([fl(r["lat_brake_ms"]) for r in ls], 0),
                                   f1([fl(r["descartados"]) for r in ls], 1), f1([fl(r["lacunas_60ms"]) for r in ls], 1),
                                   f"{100 * mean(fl(r['ecu_off']) or 0 for r in ls):.0f}%", f1(gap, 2), f"{100 * len(col) / len(ls):.0f}%",
                                   f1([fl(r['v_final_kmh']) for r in col], 1) if col else "-"])
            md.append(md_tabela(["Fora de ordem", "Política", "n", "Latência de frenagem (ms)", "Descartados", "Lacunas > 60 ms", "ECU OFF",
                                 "Dist. parada (m)", "Colisões", "v impacto (km/h)"], linhas))
    texto = "\n".join(md) + "\n"
    (OUT / f"resumo_sil_{a.cenario}.md").write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    main()
