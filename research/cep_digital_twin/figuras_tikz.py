"""Figuras do artigo em TikZ/pgfplots, no mesmo estilo do documento de projeto do AEB
(doc/task_c/task_c_design.tex): Computer Modern, caixas arredondadas em tons pastel, setas Stealth,
rótulos de sinais em fonte monoespaçada. Gera .tex standalone, compila com tectonic e rasteriza a 300 dpi.
Rodar: py -3.12 figuras_tikz.py   ->  resultados_tikz/fig_*.pdf e fig_*.png
"""
import csv
import statistics as st
import subprocess
import sys
from pathlib import Path

import fitz

AQUI = Path(__file__).resolve().parent
OUT = AQUI / "resultados_tikz"
SIL = Path(r"C:\Users\rfagu\Estudo\AEB-stellantis-project\sil\experimentos\resultados")
MOD = AQUI / "resultados_h1"
TECTONIC = r"C:\Users\rfagu\tools\tectonic\tectonic.exe"

PREAMBULO = r"""\documentclass[border=4pt]{standalone}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb}
\usepackage[table]{xcolor}
\usepackage{tikz}
\usetikzlibrary{positioning,fit,calc,arrows.meta,shapes.geometric,decorations.pathreplacing,backgrounds}
\usepackage{pgfplots}
\pgfplotsset{compat=1.17}
\definecolor{stellantis}{RGB}{26,58,92}
\definecolor{sectionblue}{RGB}{44,95,138}
\definecolor{ddbrown}{RGB}{180,100,30}
\definecolor{ddbrownlight}{RGB}{255,243,230}
\begin{document}
"""

ESTILOS = r"""
    mod/.style={rectangle, draw, rounded corners=4pt, minimum height=1.0cm, font=\small, align=center, inner sep=4pt},
    int/.style={mod, fill=blue!8, draw=sectionblue},
    exec/.style={mod, fill=purple!10, draw=purple!60!black},
    ext/.style={mod, fill=gray!10, draw=gray!50},
    pert/.style={mod, fill=ddbrownlight, draw=ddbrown},
    ini/.style={mod, fill=green!8, draw=green!50!black},
    arr/.style={-{Stealth[length=3mm, width=2.2mm]}, thick},
    darr/.style={-{Stealth[length=2.5mm, width=2mm]}, thick, dashed, gray!70!black},
    lbl/.style={font=\footnotesize\ttfamily},
    nota/.style={font=\footnotesize, align=center},"""


def compilar(nome, corpo):
    OUT.mkdir(exist_ok=True)
    tex = OUT / f"{nome}.tex"
    tex.write_text(PREAMBULO + corpo + "\n\\end{document}\n", encoding="utf-8")
    r = subprocess.run([TECTONIC, "--chatter", "minimal", str(tex)], cwd=OUT, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit(f"falhou: {nome}")
    pdf = fitz.open(OUT / f"{nome}.pdf")
    pdf[0].get_pixmap(dpi=300).save(OUT / f"{nome}.png")
    print("ok", nome)


# ------------------------------------------------------------------ Figura 1: cenário e caminho do sinal
def fig_cenario():
    corpo = r"""
\begin{tikzpicture}[""" + ESTILOS + r"""
    carro/.style={rectangle, draw, rounded corners=2pt, minimum width=1.5cm, minimum height=0.6cm, font=\footnotesize},
]
% ---- cena
\draw[gray!60, thick] (-0.3,0) -- (14.6,0);
\node[carro, fill=blue!8, draw=sectionblue, anchor=south west] (ego) at (0,0.05) {ego};
\node[carro, fill=red!8, draw=red!60!black, anchor=south east] (alvo) at (14.3,0.05) {alvo parado};
\draw[arr, sectionblue] ($(ego.north east)+(0.15,0.15)$) -- ++(1.4,0) node[right, font=\footnotesize, sectionblue] {$v$ = 50 km/h};
\draw[<->, >={Stealth[length=2mm]}] ($(ego.south east)+(0,-0.35)$) -- ($(alvo.south west)+(0,-0.35)$)
     node[midway, below, font=\footnotesize] {$d$: distância livre (95{,}5 m no início) \quad $\mathrm{TTC} = d/v$};
% ---- caminho do sinal
\begin{scope}[yshift=-3.0cm]
\node[ini, minimum width=2.2cm] (perc) at (1.1,0) {Percepção\\radar / lidar};
\node[pert, minimum width=2.4cm, right=1.0cm of perc] (canal) {Canal (relé CAN)\\atraso | desordem};
\node[pert, minimum width=2.4cm, right=0.9cm of canal] (pol) {Política\\chegada | WM | K-slack};
\node[exec, minimum width=3.0cm, right=0.9cm of pol] (ecu) {\textbf{ECU AEB}\\supervisão 60 ms\\Kalman $\to$ FSM $\to$ rampa};
\node[int, minimum width=1.6cm, right=0.9cm of ecu] (frei) {Freio /\\veículo};
\draw[arr] (perc) -- node[lbl, above] {0x120} node[lbl, below] {20 ms} (canal);
\draw[arr] (canal) -- (pol);
\draw[arr] (pol) -- (ecu);
\draw[arr] (ecu) -- node[lbl, above] {0x080} (frei);
\draw[arr, sectionblue] (frei.north) -- ++(0,1.25) node[right, nota, sectionblue] {desaceleração};
\node[ext, minimum width=5.6cm, below=1.0cm of $(pol)!0.5!(ecu)$] (mon) {Monitor CEP de governança\\``AEB sem reação'' \,|\, ``frenagem fantasma''};
\draw[darr] (pol.south) -- node[nota, right, pos=0.45] {leituras} (pol.south |- mon.north);
\draw[darr] (ecu.south) -- node[nota, right, pos=0.45] {comandos de freio} (ecu.south |- mon.north);
% marcadores de medição
\foreach \n/\l in {canal/t_{\mathrm{in}}, pol/t_{\mathrm{out}}}
  { \node[font=\footnotesize, red!60!black, above=1pt of \n.north west] {$\blacktriangledown\, \l$}; }
\node[font=\footnotesize, red!60!black, above=1pt of ecu.north east, anchor=south east] {$t_{\mathrm{freio}}\,\blacktriangledown$};
\draw[decorate, decoration={brace, amplitude=5pt, mirror}, ddbrown] ($(canal.south west)+(0,-0.1)$) -- ($(canal.south east)+(0,-0.1)$)
   node[midway, below=6pt, nota, ddbrown] {perturbação injetada};
\end{scope}
\end{tikzpicture}"""
    compilar("fig_cenario", corpo)


# ------------------------------------------------------------------ Figura 2: máquina de estados
def fig_fsm():
    corpo = r"""
\begin{tikzpicture}[""" + ESTILOS + r"""
    st/.style={rectangle, draw, rounded corners=4pt, minimum width=2.0cm, minimum height=0.9cm, font=\small, align=center},
    sb/.style={st, fill=blue!8, draw=sectionblue},
    sw/.style={st, fill=orange!10, draw=orange!60!black},
    so/.style={st, fill=red!8, draw=red!60!black},
    sl/.style={st, fill=purple!10, draw=purple!60!black},
    t/.style={font=\footnotesize, align=center},
]
% linha superior: estados sem frenagem; linha inferior: níveis de frenagem
\node[so] (off) at (0,0) {OFF};
\node[sb] (stb) at (4.0,0) {STANDBY};
\node[sw] (war) at (8.0,0) {WARNING\\(alerta)};
\node[sb] (pb) at (16.4,0) {PÓS-\\FRENAGEM};
\node[sl] (l1) at (8.0,-2.8) {L1\\2 m/s$^2$};
\node[sl] (l2) at (11.8,-2.8) {L2\\4 m/s$^2$};
\node[sl] (l3) at (16.4,-2.8) {L3\\6 m/s$^2$};
\draw[arr] (stb) -- node[t, above] {TTC $\le$ 4 s} (war);
\draw[arr] (war) -- node[t, right, xshift=1mm] {após $\ge$ 0{,}8 s em alerta:\\TTC $\le$ 3 s ou $d \le$ 20 m} (l1);
\draw[arr] (l1) -- node[t, above] {TTC $\le$ 2{,}2 s\\ou $d \le$ 10 m} (l2);
\draw[arr] (l2) -- node[t, above] {TTC $\le$ 1{,}8 s, $d\le$ 5 m\\ou $v^2/12 \ge d$} (l3);
\draw[arr] (l3) -- node[t, right] {$v \approx 0$} (pb);
\draw[arr] ([yshift=2mm]off.east) -- node[t, above] {quadro válido} ([yshift=2mm]stb.west);
\draw[arr, red!60!black] ([yshift=-2mm]stb.west) -- ([yshift=-2mm]off.east);
\draw[arr, red!60!black] (l1.west) -- (off.south |- l1.west) node[t, below, pos=0.5, xshift=4.0cm, red!60!black, align=center] {} -- (off.south);
\node[t, red!60!black, align=left, anchor=north west] at (0.3,-1.05)
   {qualquer estado $\to$ OFF:\\sem quadro de percepção por 60 ms,\\falha de sensor ou AEB desabilitado};
\node[t, sectionblue, align=center, anchor=north] at (12.2,-3.45)
   {níveis sobem de imediato e só descem após 0{,}2 s de histerese;\\rampa de 1{,}67\,\%/ciclo de 10 ms (100\,\% = 10 m/s$^2$)};
\end{tikzpicture}"""
    compilar("fig_fsm", corpo)


# ------------------------------------------------------------------ dados
def ler(p):
    return list(csv.DictReader(open(p, encoding="utf-8", newline="")))


def coords(xs, ys, es=None):
    if es is None:
        return " ".join(f"({x},{y:.2f})" for x, y in zip(xs, ys))
    return " ".join(f"({x},{y:.2f}) +- (0,{e:.2f})" for x, y, e in zip(xs, ys, es))


EIXO = r"""/pgf/number format/use comma, /pgf/number format/1000 sep={}, width=5.4cm, height=4.4cm, grid=major, grid style={gray!20}, tick label style={font=\footnotesize},
label style={font=\footnotesize}, legend style={font=\scriptsize, draw=gray!40, fill=white, fill opacity=0.9, text opacity=1},
xlabel={atraso injetado (ms)}, xtick={0,200,400,600,800,1000}"""


def fig_h1a():
    sil, mod = ler(SIL / "h1a_ccrs_50.csv"), ler(MOD / "h1a.csv")
    ds = [0, 25, 50, 100, 200, 400, 600, 800, 1000]
    base = st.mean(float(r["lat_brake_ms"]) for r in sil if float(r["delay_ms"]) == 0)
    sel_s = lambda d: [r for r in sil if float(r["delay_ms"]) == d]
    sel_m = lambda d: [r for r in mod if r["v0_kmh"] == "50" and float(r["atraso_ms"]) == d]
    lm = [st.mean(float(r["lat_L1_ms"]) for r in sel_m(d)) for d in ds]
    ls = [st.mean(float(r["lat_brake_ms"]) - base for r in sel_s(d)) for d in ds]
    es = [st.pstdev(float(r["lat_brake_ms"]) for r in sel_s(d)) for d in ds]
    gm = [st.mean(float(r["dist_parada_m"]) for r in sel_m(d)) for d in ds]
    gs = [st.mean(float(r["gap_final_m"]) for r in sel_s(d)) for d in ds]
    eg = [st.pstdev(float(r["gap_final_m"]) for r in sel_s(d)) for d in ds]
    cm = [100 * st.mean(r["resultado"] == "COLISAO" for r in sel_m(d)) for d in ds]
    cs = [100 * st.mean(r["resultado"] == "COLISAO" for r in sel_s(d)) for d in ds]
    estilo_m = r"color=gray!70!black, mark=o, mark size=1.6pt, thick"
    estilo_s = r"color=sectionblue, mark=square*, mark size=1.5pt, thick, error bars/.cd, y dir=both, y explicit, error bar style={sectionblue!70}"
    corpo = r"""
\begin{tikzpicture}
\begin{axis}[""" + EIXO + r""", name=a, ylabel={latência adicional até o freio (ms)}, ymin=-150, ymax=1100,
  legend pos=north west, title={\footnotesize (a) latência}]
\addplot[gray!50, dotted, domain=0:1000, forget plot] {x};
\addplot[""" + estilo_m + r"""] coordinates {""" + coords(ds, lm) + r"""}; \addlegendentry{modelo}
\addplot[""" + estilo_s + r"""] coordinates {""" + coords(ds, ls, es) + r"""}; \addlegendentry{bancada SIL}
\end{axis}
\begin{axis}[""" + EIXO + r""", at={(a.east)}, anchor=west, xshift=1.3cm, name=b, ylabel={distância remanescente ao alvo (m)},
  ymin=-0.3, ymax=6.6, legend pos=south west, title={\footnotesize (b) distância remanescente}]
\addplot[""" + estilo_m + r"""] coordinates {""" + coords(ds, gm) + r"""}; \addlegendentry{modelo}
\addplot[""" + estilo_s + r"""] coordinates {""" + coords(ds, gs, eg) + r"""}; \addlegendentry{bancada SIL}
\end{axis}
\begin{axis}[""" + EIXO + r""", at={(b.east)}, anchor=west, xshift=1.3cm, ylabel={colisões (\% de 30 rodadas)},
  ymin=-5, ymax=105, legend pos=north west, title={\footnotesize (c) colisões}]
\addplot[""" + estilo_m + r"""] coordinates {""" + coords(ds, cm) + r"""}; \addlegendentry{modelo}
\addplot[color=sectionblue, mark=square*, mark size=1.5pt, thick] coordinates {""" + coords(ds, cs) + r"""}; \addlegendentry{bancada SIL}
\end{axis}
\end{tikzpicture}"""
    compilar("fig_h1a", corpo)


def fig_h1b():
    sil, mod = ler(SIL / "h1b_ccrs_50.csv"), ler(MOD / "h1b.csv")
    ps = [0, 5, 10, 20]
    pols = (("arrival", "chegada", "chegada", "gray!70!black", "o"),
            ("watermark", "watermark", "marca d'água", "ddbrown", "square*"),
            ("kslack", "kslack", "K-slack", "sectionblue", "triangle*"))
    def sil_sel(dist, p, pol):
        return [r for r in sil if abs(float(r["p_disorder"]) - p / 100) < 1e-9 and r["policy"] == pol and (r["disorder"] == dist or p == 0)]
    def mod_sel(p, est):
        return [r for r in mod if r["v0_kmh"] == "50" and r["dist_desordem"] == "200-600" and abs(float(r["p_desordem"]) - p / 100) < 1e-9 and r["estrategia"] == est]
    eixo = EIXO.replace("xlabel={atraso injetado (ms)}, xtick={0,200,400,600,800,1000}", "xlabel={quadros fora de ordem (\\%)}, xtick={0,5,10,20}")
    def painel(nome, extra, titulo, linhas, legenda):
        out = r"\begin{axis}[" + eixo + ", " + extra + r", ymin=-5, ymax=105, title={\footnotesize " + titulo + "}"
        out += (", legend columns=3, legend cell align=left, legend style={at={(1.72,-0.36)}, anchor=north, /tikz/every even column/.append style={column sep=8pt}}" if legenda else "") + "]\n"
        return out + linhas + r"\end{axis}" + "\n"
    blocos = []
    for i, (dist, titulo) in enumerate((("40-200", "(a) bancada, +40 a 200 ms"), ("200-600", "(b) bancada, +200 a 600 ms"))):
        linhas = ""
        for pol, _, nome, cor, mk in pols:
            col = [100 * st.mean(r["resultado"] == "COLISAO" for r in sil_sel(dist, p, pol)) for p in ps]
            off = [100 * st.mean(int(r["ecu_off"]) for r in sil_sel(dist, p, pol)) for p in ps]
            linhas += rf"\addplot[color={cor}, mark={mk}, mark size=1.6pt, thick] coordinates {{{coords(ps, col)}}};"
            linhas += (rf"\addlegendentry{{{nome}: colisões}}" if i == 0 else "") + "\n"
            linhas += rf"\addplot[color={cor}, mark={mk}, mark size=1.2pt, densely dashed, mark options={{solid}}] coordinates {{{coords(ps, off)}}};"
            linhas += (rf"\addlegendentry{{{nome}: AEB desligado}}" if i == 0 else "") + "\n"
        extra = ("name=a, ylabel={\\% das rodadas (n = 30)}" if i == 0 else "at={(a.east)}, anchor=west, xshift=0.7cm, name=b, yticklabels={}")
        blocos.append(painel(dist, extra, titulo, linhas, i == 0))
    linhas = ""
    for _, est, nome, cor, mk in pols:
        col = [100 * st.mean(r["resultado"] == "COLISAO" for r in mod_sel(p, est)) for p in ps]
        linhas += rf"\addplot[color={cor}, mark={mk}, mark size=1.6pt, thick] coordinates {{{coords(ps, col)}}};" + "\n"
    blocos.append(r"\begin{axis}[" + eixo + r", at={(b.east)}, anchor=west, xshift=0.7cm, yticklabels={}, ymin=-5, ymax=105, title={\footnotesize (c) modelo, +200 a 600 ms (colisões)}]" + "\n" + linhas + r"\end{axis}" + "\n")
    corpo = "\\begin{tikzpicture}\n" + "".join(blocos) + "\\end{tikzpicture}"
    compilar("fig_h1b", corpo)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    alvo = sys.argv[1:] or ["cenario", "fsm", "h1a", "h1b"]
    for a in alvo:
        globals()["fig_" + a]()
