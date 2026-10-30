"""Figuras de como o simulador funciona: pipeline do experimento e linha do tempo de uma rodada.
Rodar: py -3.12 figuras_simulador.py -> resultados/fig_pipeline.png, resultados/fig_linha_tempo.png
"""
import random
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

import experimento as X

OUT = Path(__file__).resolve().parent / "resultados"
plt.rcParams["font.family"] = "DejaVu Sans"
CINZA, AZUL, VERDE, VERM, LAR = "#555b66", "#2b5d8f", "#2e7d4f", "#b03a2e", "#b8741a"


def caixa(ax, x, y, w, h, titulo, linhas=(), cor=CINZA, fs=7.6, fill="#ffffff", passo=0.3):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", lw=1.3, ec=cor, fc=fill))
    ax.text(x + w / 2, y + h - 0.16, titulo, ha="center", va="top", fontsize=fs + 0.8, fontweight="bold", color=cor)
    for i, l in enumerate(linhas):
        ax.text(x + 0.14, y + h - 0.5 - i * passo, l, ha="left", va="top", fontsize=fs, color="#222")


def seta(ax, a, b, cor=CINZA, estilo="-", txt="", dy=0.14, fs=7):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=11, lw=1.2, color=cor, linestyle=estilo, shrinkA=2, shrinkB=2))
    if txt:
        ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + dy, txt, ha="center", va="bottom", fontsize=fs, color=cor,
                bbox=dict(fc="white", ec="none", pad=0.8))


def pipeline():
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    ax.set_xlim(0, 13); ax.set_ylim(0, 8.6); ax.axis("off")
    caixa(ax, 0.3, 5.3, 3.2, 3.0, "Gerador (semente)",
          ["240 s a 20 Hz: radar, lidar,", "mensagem CAN, barramento,", "motorista", "Injeta 6 falhas em instantes", "sorteados", "→ eventos + verdade de ref."],
          cor=VERDE, fill="#f3faf5")
    caixa(ax, 0.3, 0.6, 3.2, 3.6, "Rede (perfil × offline)",
          ["atraso gaussiano + jitter", "perda com reenvio QoS 1", "janela offline sorteada", "buffer 128 KB (descarta", "o mais antigo), dreno", "50 KB/s ao reconectar"],
          cor=LAR, fill="#fdf6ec")
    # A0
    caixa(ax, 4.6, 5.3, 3.9, 3.0, "A0: gêmeo só na nuvem",
          ["eventos brutos (64 B) → rede", "reordenação por timestamp", "(limite L = atraso + 3·jitter)", "7 regras CEP sobre brutos", "evidência: brutos em ±3 s"],
          cor=CINZA, fill="#f4f4f6")
    # A1
    caixa(ax, 4.6, 0.6, 3.9, 3.6, "A1: gêmeo local + nuvem",
          ["borda: 4 regras rápidas (5 ms)", "→ evento complexo (256 B),", "   snapshot ±3 s (32 B/ev),", "   agregado de 1 s (96 B)", "rede → nuvem: 3 regras de", "janela longa sobre agregados"],
          cor=AZUL, fill="#eef4fa")
    caixa(ax, 9.6, 3.0, 3.1, 3.6, "Medição por falha",
          ["detectado?", "latência de decisão", "latência até a gestão", "completude da trilha", "tempo até a evidência", "+ falsos positivos, bytes,", "   descartes, KPI"],
          cor=VERM, fill="#fbf1ef")
    caixa(ax, 9.6, 0.6, 3.1, 1.7, "Saídas",
          ["por_cenario.csv, por_rodada.csv", "resumo.md, figuras"], cor=VERM, fill="#fbf1ef")
    seta(ax, (3.5, 6.8), (4.6, 6.8), cor=VERDE, txt="eventos")
    seta(ax, (3.5, 6.4), (4.6, 2.4), cor=VERDE)
    seta(ax, (3.5, 2.4), (4.6, 6.2), cor=LAR)
    seta(ax, (3.5, 2.0), (4.6, 2.0), cor=LAR, txt="rede")
    seta(ax, (8.5, 6.8), (9.6, 5.6), cor=CINZA, txt="decisões", dy=0.2)
    seta(ax, (8.5, 2.4), (9.6, 3.8), cor=AZUL, txt="decisões", dy=-0.5)
    seta(ax, (11.15, 3.0), (11.15, 2.3), cor=VERM)
    seta(ax, (1.9, 5.3), (1.9, 4.2), cor=VERDE, estilo="--", txt="")
    ax.text(2.05, 4.75, "verdade de\nreferência", fontsize=7, color=VERDE, va="center")
    ax.text(6.5, 4.75, "mesma semente, mesmos eventos: comparação pareada", fontsize=7.2, color="#333", ha="center", va="center", style="italic")
    ax.text(6.5, 0.2, "Plano fatorial: 2 arquiteturas × 3 redes × 3 janelas offline × 20 sementes = 360 rodadas", fontsize=7.4, color="#333", ha="center")
    fig.tight_layout()
    fig.savefig(OUT / "fig_pipeline.png", dpi=170)


def linha_tempo(seed=3, perfil="media", off="longo"):
    ev, gt = X.gerar(seed, X.CFG["duracao"])
    rng = lambda: random.Random(X.semente_rede(seed, perfil, off))
    r0, r1 = X.Rede(rng(), perfil, X.OFFLINE[off], X.CFG["duracao"]), X.Rede(rng(), perfil, X.OFFLINE[off], X.CFG["duracao"])
    d0, d1 = X.rodar_A0(ev, r0), X.rodar_A1(ev, r1)
    cen = X.CENARIOS_GT
    cores = dict(zip(cen, ["#b03a2e", "#d4502b", "#7b3fa0", "#b8741a", "#2e7d4f", "#2b5d8f"]))
    rot = {"Frenagem tardia (atraso de mensagem)": "Frenagem tardia", "Saúde da rede de mensagens": "Saúde da rede"}

    fig, ax = plt.subplots(figsize=(7.4, 3.5))
    linhas = ["Falhas injetadas", "A0: decisões (nuvem)", "A1: decisões (borda ●, nuvem ○)"]
    ys = {l: 2 - i for i, l in enumerate(linhas)}
    if r0.off:
        ax.axvspan(r0.off[0], r0.off[1], color="#dddddd", alpha=0.8, lw=0)
        ax.text((r0.off[0] + r0.off[1]) / 2, 2.45, f"offline {X.OFFLINE[off]} s", ha="center", fontsize=7.5, color="#444")
    for c in cen:
        t0, t1 = gt[c]
        y = ys["Falhas injetadas"]
        if t1 > t0:
            ax.plot([t0, t1], [y, y], color=cores[c], lw=6, solid_capstyle="butt", alpha=0.85, label=rot.get(c, c))
        else:
            ax.plot(t0, y, marker="v", color=cores[c], ms=8, ls="none", label=rot.get(c, c))
    ax.legend(fontsize=6.3, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.22), frameon=False, handlelength=1.6)
    for decis, lab in ((d0, "A0: decisões (nuvem)"), (d1, "A1: decisões (borda ●, nuvem ○)")):
        for d in decis:
            if d["cenario"] == "Saúde da rede de mensagens":
                continue
            mk = "o"
            fill = cores.get(d["cenario"], "#333") if d.get("local", False) or lab.startswith("A0") else "white"
            ax.plot(d["t_decisao"], ys[lab], marker=mk, ms=6, mfc=fill, mec=cores.get(d["cenario"], "#333"), ls="none", mew=1.3)
    ax.set_yticks(list(ys.values()), list(ys.keys()), fontsize=7.5)
    ax.set_ylim(-0.6, 2.9); ax.set_xlim(0, X.CFG["duracao"])
    ax.set_xlabel("tempo simulado (s)", fontsize=8)
    ax.tick_params(axis="x", labelsize=7.5)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", alpha=.25)
    fig.tight_layout()
    fig.savefig(OUT / "fig_linha_tempo.png", dpi=170)
    return seed, perfil, off, r0.off


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    pipeline()
    print(linha_tempo())
