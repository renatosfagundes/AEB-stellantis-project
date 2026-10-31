"""Figuras da versão de 8 páginas: (1) cenário e caminho do sinal com pontos de perturbação e medição;
(2) máquina de estados da ECU; (3) H1a modelo × bancada; (4) H1b bancada (+ modelo com supervisão).
Rodar: py -3.12 figuras_v6.py  ->  resultados_v6/fig_*.png
"""
import csv
import statistics as st
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle, Polygon

AQUI = Path(__file__).resolve().parent
OUT = AQUI / "resultados_v6"
SIL = Path(r"C:\Users\rfagu\Estudo\AEB-stellantis-project\sil\experimentos\resultados")
MOD = AQUI / "resultados_h1"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8})
AZ, VM, VD, CZ, LR = "#2b5d8f", "#b03a2e", "#2e7d4f", "#555b66", "#b8741a"


def caixa(ax, x, y, w, h, txt, cor, fill="#ffffff", fs=7.2, bold=True):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", lw=1.2, ec=cor, fc=fill))
    ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=fs, color="#222", fontweight="bold" if bold else "normal", linespacing=1.15)


def seta(ax, a, b, cor=CZ, estilo="-", lw=1.2):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=10, lw=lw, color=cor, linestyle=estilo, shrinkA=1, shrinkB=1))


def fig_cenario():
    fig, ax = plt.subplots(figsize=(7.2, 3.3))
    ax.set_xlim(0, 14); ax.set_ylim(0, 6.6); ax.axis("off")
    # cena física
    ax.plot([0.3, 13.7], [5.0, 5.0], color="#999", lw=1)
    ax.add_patch(Rectangle((0.6, 5.05), 1.5, 0.6, fc="#dbe7f3", ec=AZ, lw=1.2)); ax.text(1.35, 5.35, "ego", ha="center", va="center", fontsize=7)
    ax.add_patch(Rectangle((11.4, 5.05), 1.5, 0.6, fc="#f3dede", ec=VM, lw=1.2)); ax.text(12.15, 5.35, "alvo\n(parado)", ha="center", va="center", fontsize=6.5)
    seta(ax, (2.2, 5.85), (3.4, 5.85), cor=AZ); ax.text(2.8, 6.0, "v (50 km/h)", ha="center", fontsize=7, color=AZ)
    ax.annotate("", xy=(11.35, 4.85), xytext=(2.15, 4.85), arrowprops=dict(arrowstyle="<->", color="#333", lw=0.9))
    ax.text(6.75, 4.6, "d = distância livre (95,5 m no início);  TTC = d / v", ha="center", fontsize=7)
    # cadeia
    y = 2.3
    caixa(ax, 0.2, y, 1.9, 1.0, "Percepção\nradar/lidar\n0x120 a 20 ms", VD, "#f3faf5")
    caixa(ax, 2.6, y, 2.2, 1.0, "Canal\n(relé CAN)\natraso / desordem", LR, "#fdf6ec")
    caixa(ax, 5.3, y, 2.0, 1.0, "Política\nchegada | WM |\nK-slack", LR, "#fdf6ec")
    caixa(ax, 7.8, y, 3.4, 1.0, "ECU AEB\nsupervisão 60 ms → Kalman →\nFSM (TTC, pisos) → rampa", AZ, "#eef4fa")
    caixa(ax, 11.7, y, 2.1, 1.0, "Freio /\nveículo\n(Gazebo)", AZ, "#eef4fa")
    for a, b in (((2.1, y + .5), (2.6, y + .5)), ((4.8, y + .5), (5.3, y + .5)), ((7.3, y + .5), (7.8, y + .5)), ((11.2, y + .5), (11.7, y + .5))):
        seta(ax, a, b)
    seta(ax, (12.75, y + 1.0), (12.75, 4.95), cor=AZ, estilo="--")
    caixa(ax, 5.3, 0.25, 4.0, 0.9, "Monitor CEP de governança\n\"AEB sem reação\" | \"frenagem fantasma\"", CZ, "#f4f4f6", fs=6.8)
    seta(ax, (6.3, y), (6.6, 1.15), cor=CZ, estilo="--")
    seta(ax, (9.5, y), (8.6, 1.15), cor=CZ, estilo="--")
    ax.text(9.65, 1.6, "comandos\nde freio", fontsize=6, color=CZ)
    # marcadores de medição
    for x, t in ((2.6, "t_in"), (5.3, "t_out"), (11.2, "t_freio")):
        ax.plot([x], [y + 1.12], marker="v", color=VM, ms=5)
        ax.text(x, y + 1.25, t, ha="center", fontsize=6.5, color=VM)
    ax.text(0.2, 1.65, "perturbação injetada\nentre t_in e t_out", fontsize=6.3, color=LR)
    fig.tight_layout(); fig.savefig(OUT / "fig_cenario.png", dpi=220)


def fig_fsm():
    fig, ax = plt.subplots(figsize=(7.2, 2.5))
    ax.set_xlim(0, 14); ax.set_ylim(0.2, 4.9); ax.axis("off")
    pos = {"OFF": (0.9, 2.3), "STANDBY": (3.0, 2.3), "WARNING": (5.4, 2.3), "L1\n2 m/s²": (8.0, 3.4), "L2\n4 m/s²": (10.4, 3.4),
           "L3\n6 m/s²": (12.8, 3.4), "PÓS-\nFRENAGEM": (12.8, 0.9)}
    cores = {"OFF": VM, "STANDBY": CZ, "WARNING": LR}
    for k, (x, y) in pos.items():
        caixa(ax, x - 0.85, y - 0.45, 1.7, 0.9, k, cores.get(k, AZ), "#ffffff", fs=6.8)
    def s(a, b, txt, dy=0.12, cor=CZ, rad=0.0):
        (x1, y1), (x2, y2) = pos[a], pos[b]
        ax.add_patch(FancyArrowPatch((x1 + (0.85 if x2 > x1 else -0.85 if x2 < x1 else 0), y1), (x2 - (0.85 if x2 > x1 else -0.85 if x2 < x1 else 0), y2),
                                     arrowstyle="-|>", mutation_scale=9, lw=1.0, color=cor, connectionstyle=f"arc3,rad={rad}"))
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + dy, txt, ha="center", fontsize=6, color=cor)
    s("STANDBY", "WARNING", "")
    ax.text(4.2, 2.45, "TTC ≤ 4 s", ha="center", fontsize=6, color=CZ)
    s("WARNING", "L1\n2 m/s²", "", dy=0.0)
    ax.text(6.05, 3.55, "após ≥ 0,8 s:\nTTC ≤ 3 s\nou d ≤ 20 m", ha="center", fontsize=6, color=CZ)
    s("L1\n2 m/s²", "L2\n4 m/s²", "", dy=0.0)
    ax.text(9.2, 4.15, "TTC ≤ 2,2 s ou d ≤ 10 m", ha="center", fontsize=6, color=CZ)
    s("L2\n4 m/s²", "L3\n6 m/s²", "", dy=0.0)
    ax.text(11.6, 4.45, "TTC ≤ 1,8 s, d ≤ 5 m\nou v²/12 ≥ d", ha="center", fontsize=6, color=CZ)
    ax.add_patch(FancyArrowPatch((12.8, 2.95), (12.8, 1.35), arrowstyle="-|>", mutation_scale=9, lw=1.0, color=CZ))
    ax.text(13.0, 2.1, "v ≈ 0", fontsize=6, color=CZ)
    s("STANDBY", "OFF", "", cor=VM)
    ax.text(1.95, 3.25, "qualquer estado → OFF:\nsem 0x120 por 60 ms,\nfalha de sensor ou\nAEB desabilitado", fontsize=6, color=VM, ha="center")
    ax.text(1.95, 1.0, "OFF → STANDBY no\npróximo quadro válido", fontsize=6, color=VM, ha="center")
    ax.text(8.6, 1.2, "níveis sobem de imediato e só descem após\n0,2 s de histerese; rampa de 1,67 %/ciclo de 10 ms\n(100 % = 10 m/s²)", fontsize=6, color=AZ, ha="center")
    fig.tight_layout(); fig.savefig(OUT / "fig_fsm.png", dpi=220)


def ler(p):
    return list(csv.DictReader(open(p, encoding="utf-8", newline="")))


def fig_h1a():
    sil, mod = ler(SIL / "h1a_ccrs_50.csv"), ler(MOD / "h1a.csv")
    ds = [0, 25, 50, 100, 200, 400, 600, 800, 1000]
    base = st.mean(float(r["lat_brake_ms"]) for r in sil if float(r["delay_ms"]) == 0)
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.3))
    ls_m = [st.mean(float(r["lat_L1_ms"]) for r in mod if r["v0_kmh"] == "50" and float(r["atraso_ms"]) == d) for d in ds]
    ls_s = [st.mean(float(r["lat_brake_ms"]) - base for r in sil if float(r["delay_ms"]) == d) for d in ds]
    ss_s = [st.pstdev(float(r["lat_brake_ms"]) for r in sil if float(r["delay_ms"]) == d) for d in ds]
    axs[0].plot(ds, ls_m, "o-", color=CZ, ms=3, label="modelo")
    axs[0].errorbar(ds, ls_s, yerr=ss_s, fmt="s-", color=AZ, ms=3, capsize=2, label="bancada SIL")
    axs[0].plot([0, 1000], [0, 1000], ":", color="#999", lw=0.8)
    axs[0].set_xlabel("atraso injetado (ms)"); axs[0].set_ylabel("latência adicional\naté o freio (ms)")
    def gap(rows, chave_d, chave_gap, chave_res, d, v=None):
        g = [float(r[chave_gap]) for r in rows if float(r[chave_d]) == d and (v is None or r["v0_kmh"] == v)]
        return st.mean(g), (st.pstdev(g) if len(g) > 1 else 0)
    gm = [gap(mod, "atraso_ms", "dist_parada_m", "resultado", d, "50")[0] for d in ds]
    gs = [gap(sil, "delay_ms", "gap_final_m", "resultado", d) for d in ds]
    axs[1].plot(ds, gm, "o-", color=CZ, ms=3, label="modelo")
    axs[1].errorbar(ds, [g[0] for g in gs], yerr=[g[1] for g in gs], fmt="s-", color=AZ, ms=3, capsize=2, label="bancada SIL")
    axs[1].set_xlabel("atraso injetado (ms)"); axs[1].set_ylabel("distância remanescente\nao alvo (m)")
    cm = [100 * st.mean(r["resultado"] == "COLISAO" for r in mod if r["v0_kmh"] == "50" and float(r["atraso_ms"]) == d) for d in ds]
    cs = [100 * st.mean(r["resultado"] == "COLISAO" for r in sil if float(r["delay_ms"]) == d) for d in ds]
    axs[2].plot(ds, cm, "o-", color=CZ, ms=3, label="modelo")
    axs[2].plot(ds, cs, "s-", color=AZ, ms=3, label="bancada SIL")
    axs[2].set_xlabel("atraso injetado (ms)"); axs[2].set_ylabel("colisões (%)"); axs[2].set_ylim(-4, 104)
    for ax in axs:
        ax.grid(alpha=.3); ax.legend(fontsize=6.5)
    fig.tight_layout(); fig.savefig(OUT / "fig_h1a.png", dpi=220)


def fig_h1b():
    sil = ler(SIL / "h1b_ccrs_50.csv")
    mod = ler(MOD / "h1b.csv")
    ps = [0.0, 0.05, 0.10, 0.20]
    pols = (("arrival", "chegada", CZ, "o"), ("watermark", "marca d'água", LR, "s"), ("kslack", "K-slack", AZ, "^"))
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.4))
    for j, (dist, ttl) in enumerate((("40-200", "bancada: +40 a 200 ms"), ("200-600", "bancada: +200 a 600 ms"))):
        for pol, nome, cor, mk in pols:
            ys = [100 * st.mean(r["resultado"] == "COLISAO" for r in sil if float(r["p_disorder"]) == p and r["policy"] == pol and (r["disorder"] == dist or p == 0)) for p in ps]
            off = [100 * st.mean(int(r["ecu_off"]) for r in sil if float(r["p_disorder"]) == p and r["policy"] == pol and (r["disorder"] == dist or p == 0)) for p in ps]
            axs[j].plot([100 * p for p in ps], ys, mk + "-", color=cor, ms=3.5, label=f"{nome}: colisões")
            axs[j].plot([100 * p for p in ps], off, mk + ":", color=cor, ms=2.5, alpha=.7, label=f"{nome}: AEB desligado")
        axs[j].set_title(ttl, fontsize=7.5); axs[j].set_xlabel("quadros fora de ordem (%)"); axs[j].set_ylim(-4, 104)
        axs[j].set_ylabel("% das rodadas (n = 30)"); axs[j].grid(alpha=.3)
    axs[0].legend(fontsize=5.6, loc="upper left")
    for pol, nome, cor, mk in pols:
        ys = [100 * st.mean(r["resultado"] == "COLISAO" for r in mod if r["v0_kmh"] == "50" and r["dist_desordem"] == "200-600" and float(r["p_desordem"]) == p and r["estrategia"] == {"arrival": "chegada", "watermark": "watermark", "kslack": "kslack"}[pol]) for p in ps]
        off = [100 * st.mean(int(r["desligamentos"]) > 0 for r in mod if r["v0_kmh"] == "50" and r["dist_desordem"] == "200-600" and float(r["p_desordem"]) == p and r["estrategia"] == {"arrival": "chegada", "watermark": "watermark", "kslack": "kslack"}[pol]) for p in ps]
        axs[2].plot([100 * p for p in ps], ys, mk + "-", color=cor, ms=3.5, label=f"{nome}: colisões")
    axs[2].legend(fontsize=5.6, loc="upper left")
    axs[2].set_title("modelo: +200 a 600 ms", fontsize=7.5); axs[2].set_xlabel("quadros fora de ordem (%)")
    axs[2].set_ylim(-4, 104); axs[2].grid(alpha=.3)
    fig.tight_layout(); fig.savefig(OUT / "fig_h1b.png", dpi=220)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    fig_cenario(); fig_fsm()
    if (MOD / "h1a.csv").exists():
        fig_h1a(); fig_h1b()
    print("ok")
