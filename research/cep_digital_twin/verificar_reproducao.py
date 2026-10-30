"""
Verificação independente dos resultados: roda os dois experimentos em modo rápido duas vezes,
confere que são bit a bit idênticos (determinismo) e checa as afirmações centrais do artigo.
Com --completo, usa as 20/30 sementes e compara com os CSV publicados em resultados/ e resultados_h1/.

Uso:  py -3.12 verificar_reproducao.py            (~1 min)
      py -3.12 verificar_reproducao.py --completo (~10 min)
Sai com código 0 se tudo passou; lista cada verificação.
"""
from __future__ import annotations

import csv
import hashlib
import io
import sys
from pathlib import Path
from statistics import mean

import experimento as E
import experimento_h1 as H

AQUI = Path(__file__).resolve().parent
completo = "--completo" in sys.argv
falhas = []


def check(nome, ok, detalhe=""):
    print(("OK   " if ok else "FALHA") + " " + nome + (f"  ({detalhe})" if detalhe else ""))
    if not ok:
        falhas.append(nome)


def csv_hash(linhas):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(linhas[0].keys()))
    w.writeheader()
    w.writerows(linhas)
    return hashlib.sha256(buf.getvalue().encode("utf-8")).hexdigest()


def ler_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- experimento principal (A0 x A1)
seeds = list(range(20)) if completo else list(range(3))
c1, r1 = E.executar(seeds)
c2, r2 = E.executar(seeds)
check("experimento principal é determinístico", csv_hash(c1) == csv_hash(c2) and csv_hash(r1) == csv_hash(r2))

reativos = {"Frenagem tardia (atraso de mensagem)", "Frenagem fantasma"}
a1 = [l for l in c1 if l["arquitetura"] == "A1_local+nuvem" and l["offline"] == "nenhum" and l["cenario"] in reativos]
a0 = [l for l in c1 if l["arquitetura"] == "A0_nuvem" and l["offline"] == "nenhum" and l["cenario"] in reativos]
check("A1 decide os reativos abaixo de 100 ms em todas as redes", all(l["lat_decisao"] is not None and l["lat_decisao"] < 0.1 for l in a1))
check("A0 ultrapassa 100 ms em rede média e ruim", all(l["lat_decisao"] is None or l["lat_decisao"] > 0.1 for l in a0 if l["rede"] != "boa"))
risco = [l for l in c1 if l["cenario"] in E.RISCO]
check("A1 detecta 100 % das falhas injetadas", all(l["detectado"] for l in risco if l["arquitetura"] == "A1_local+nuvem"))
a0_longo = [l for l in risco if l["arquitetura"] == "A0_nuvem" and l["offline"] == "longo"]
check("A0 perde falhas com offline longo", mean(l["detectado"] for l in a0_longo) < 1.0, f"{100 * mean(l['detectado'] for l in a0_longo):.0f}% detectadas")
vol = {arq: mean(l["bytes_nuvem"] for l in r1 if l["arquitetura"] == arq) for arq in E.ARQUITETURAS}
check("A1 envia menos de 1/5 do volume de A0", vol["A1_local+nuvem"] * 5 < vol["A0_nuvem"], f"{vol['A0_nuvem'] / vol['A1_local+nuvem']:.1f}x")
if completo:
    pub = ler_csv(AQUI / "resultados" / "por_cenario.csv")
    check("CSV publicado por_cenario.csv coincide com a reexecução", len(pub) == len(c1) and all(
        str(a[k]) == b[k] for a, b in zip(c1, pub) for k in ("arquitetura", "rede", "offline", "seed", "cenario", "detectado")))

# ---------------------------------------------------------------- complemento H1a / H1b
seeds_h = list(range(30)) if completo else list(range(3))
H.REFS.clear()
h1a_1 = H.plano_h1a(seeds_h)
H.REFS.clear()
h1a_2 = H.plano_h1a(seeds_h)
check("H1a é determinístico", csv_hash(h1a_1) == csv_hash(h1a_2))
for v0 in (40, 50):
    lat = {a: mean(l["lat_L1_ms"] for l in h1a_1 if l["v0_kmh"] == v0 and l["atraso_ms"] == a) for a in H.ATRASOS_MS}
    check(f"H1a {v0} km/h: latência de detecção cresce monotonicamente com o atraso", all(lat[a] <= lat[b] + 1e-6 for a, b in zip(H.ATRASOS_MS, H.ATRASOS_MS[1:])))
    dist = {a: mean(l["dist_parada_m"] for l in h1a_1 if l["v0_kmh"] == v0 and l["atraso_ms"] == a) for a in H.ATRASOS_MS}
    check(f"H1a {v0} km/h: distância de parada em 1000 ms é menor que sem atraso", dist[1000] < dist[0])
    col = [l["resultado"] for l in h1a_1 if l["v0_kmh"] == v0 and l["atraso_ms"] == 1000]
    check(f"H1a {v0} km/h: colisão em 100 % das rodadas com 1000 ms", all(r == "COLISAO" for r in col))
H.REFS.clear()
h1b = H.plano_h1b(seeds_h)
ks = [l for l in h1b if l["estrategia"] == "kslack" and l["dist_desordem"] == "200-600" and l["p_desordem"] > 0]
ch = [l for l in h1b if l["estrategia"] == "chegada" and l["dist_desordem"] == "200-600" and l["p_desordem"] > 0]
check("H1b: K-slack adiciona mais espera que a ordem de chegada", mean(l["espera_media_ms"] for l in ks) > mean(l["espera_media_ms"] for l in ch) + 100)
check("H1b: K-slack encurta a distância de parada em relação à ordem de chegada", mean(l["dist_parada_m"] for l in ks) < mean(l["dist_parada_m"] for l in ch))
if completo:
    pub = ler_csv(AQUI / "resultados_h1" / "h1a.csv")
    check("CSV publicado h1a.csv coincide com a reexecução", len(pub) == len(h1a_1) and all(
        str(a["dist_parada_m"]) == b["dist_parada_m"] for a, b in zip(h1a_1, pub)))

print()
print("TUDO OK" if not falhas else f"{len(falhas)} verificação(ões) falharam: " + "; ".join(falhas))
sys.exit(0 if not falhas else 1)
