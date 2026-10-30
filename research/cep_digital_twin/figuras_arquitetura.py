"""Figuras 1 e 2 do artigo (contexto/componentes e implantação borda-nuvem), em matplotlib.
Rodar: py -3.12 figuras_arquitetura.py  ->  resultados/fig_arquitetura.png, resultados/fig_implantacao.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent / "resultados"
plt.rcParams["font.family"] = "DejaVu Sans"
CINZA, AZUL, VERDE, VERM = "#555b66", "#2b5d8f", "#2e7d4f", "#b03a2e"


def caixa(ax, x, y, w, h, titulo, linhas=(), cor=CINZA, fs=8, fill="#ffffff", passo=0.36):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.15", lw=1.4, ec=cor, fc=fill))
    ax.text(x + w / 2, y + h - 0.22, titulo, ha="center", va="top", fontsize=fs + 1, fontweight="bold", color=cor)
    for i, l in enumerate(linhas):
        ax.text(x + 0.2, y + h - 0.62 - i * passo, l, ha="left", va="top", fontsize=fs, color="#222")


def seta(ax, a, b, cor=CINZA, estilo="-"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=12, lw=1.3, color=cor, linestyle=estilo,
                                 shrinkA=2, shrinkB=2))


def rotulo(ax, x, y, texto, cor=CINZA, ha="center", va="center", fs=7.5):
    ax.text(x, y, texto, ha=ha, va=va, fontsize=fs, color=cor, linespacing=1.1)


def fig1():
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    ax.set_xlim(0, 13); ax.set_ylim(0, 8); ax.axis("off")
    caixa(ax, 0.3, 0.4, 3.7, 7.2, "Mundo real (veículo)",
          ["Radar, lidar, câmera (20 Hz)", "ECU AEB  →  ECU Freio", "Barramento CAN / CAN-FD", "Motorista e HMI",
           "ECU hospedeira do DT local", "Gateway de telemetria", "(store-and-forward)"], cor=VERDE, fill="#f3faf5")
    caixa(ax, 5.2, 4.6, 3.0, 3.0, "DT local",
          ["Espelho de 1 veículo", "4 regras CEP rápidas", "Snapshot ±3 s", "Agregados de 1 s"], cor=AZUL, fill="#eef4fa")
    caixa(ax, 9.6, 4.6, 3.1, 3.0, "DT nuvem",
          ["Espelho da frota", "3 regras de janela longa", "Histórico e tendência", "Repositório de evidência"], cor=AZUL, fill="#eef4fa")
    caixa(ax, 5.2, 0.4, 7.5, 2.9, "Gestão / Governança",
          ["Cenários: operação normal, risco preventivo, risco reativo", "Decisão: OTA, manutenção, recall, resposta a incidente",
           "Evidência: evento complexo + snapshot + agregados"], cor=VERM, fill="#fbf1ef")
    # veículo -> DT local
    seta(ax, (4.0, 6.1), (5.2, 6.1), cor=VERDE)
    rotulo(ax, 4.6, 6.35, "eventos\nsimples", cor=VERDE, va="bottom")
    # DT local <-> DT nuvem
    seta(ax, (8.2, 6.7), (9.6, 6.7), cor=AZUL)
    rotulo(ax, 8.9, 6.95, "complexos,\nsnapshots,\nagregados", cor=AZUL, va="bottom")
    seta(ax, (9.6, 5.2), (8.2, 5.2), cor=AZUL, estilo="--")
    rotulo(ax, 8.9, 4.95, "regras e\nlimiares", cor=AZUL, va="top")
    # DTs -> Gestão
    seta(ax, (6.7, 4.6), (6.7, 3.3), cor=AZUL)
    rotulo(ax, 6.85, 3.95, "decisão local\n(registro, alarme)", cor=AZUL, ha="left")
    seta(ax, (11.1, 4.6), (11.1, 3.3), cor=VERM)
    rotulo(ax, 10.95, 3.95, "painel e\nalertas", cor=VERM, ha="right")
    # Gestão -> veículo
    seta(ax, (5.2, 1.3), (4.0, 1.3), cor=VERM)
    rotulo(ax, 4.6, 1.55, "ação", cor=VERM, va="bottom")
    fig.tight_layout()
    fig.savefig(OUT / "fig_arquitetura.png", dpi=170)


def fig2():
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    ax.set_xlim(0, 13); ax.set_ylim(0, 6.8); ax.axis("off")
    caixa(ax, 0.3, 0.4, 5.4, 6.1, "BORDA (ECU hospedeira, no veículo)",
          ["Reação em milissegundos", "Funciona sem rede", "", "Regras CEP sobre o barramento:", "  • Frenagem tardia (latência > 100 ms)",
           "  • Frenagem fantasma (freio sem alvo)", "  • Ataque cibernético (ID / MAC)", "  • Degradação do barramento", "",
           "Saída: evento complexo (256 B),", "snapshot ±3 s (32 B/evento),", "agregado de 1 s (96 B)"],
          cor=AZUL, fill="#eef4fa", passo=0.4)
    caixa(ax, 7.3, 0.4, 5.4, 6.1, "NUVEM (frota, histórico)",
          ["Janelas de segundos a meses", "Compara veículos da frota", "", "Regras CEP sobre agregados:", "  • Saúde da rede (KPI de 10 s)",
           "  • Degradação do sensor (tendência)", "  • Comportamento do motorista", "", "Governança: painel, trilha de",
           "auditoria, what-if, validação de OTA", "Retorno: regras e limiares"],
          cor=AZUL, fill="#eef4fa", passo=0.4)
    seta(ax, (5.7, 3.9), (7.3, 3.9), cor=CINZA)
    rotulo(ax, 6.5, 4.15, "rede celular\n(atraso, perda,\noffline)", va="bottom")
    seta(ax, (7.3, 2.4), (5.7, 2.4), cor=CINZA, estilo="--")
    rotulo(ax, 6.5, 2.15, "OTA de\nregras", va="top")
    fig.tight_layout()
    fig.savefig(OUT / "fig_implantacao.png", dpi=170)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    fig1()
    fig2()
    print("ok")
