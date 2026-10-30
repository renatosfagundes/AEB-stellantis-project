"""
Experimento controlado: Gêmeo Digital só na nuvem (A0, linha de base) versus
Gêmeo Digital local + nuvem (A1, arquitetura proposta) para a governança do AEB.

Para cada combinação de fatores (arquitetura x perfil de rede x janela offline)
roda N repetições com sementes diferentes, injeta as falhas da tabela de cenários
em instantes aleatórios e mede, por cenário:

  detectado        a falha gerou o evento complexo esperado?
  lat_decisao      tempo entre a falha e a decisão (onde ela é tomada)
  lat_gestao       tempo entre a falha e a chegada do evento complexo à Gestão (nuvem)
  evid_completude  fração da evidência (snapshot/agregados) que chegou ao repositório de auditoria
  t_evidencia      tempo entre a falha e a evidência completa estar disponível

e, por rodada: falsos positivos, volume enviado à nuvem, mensagens descartadas no
buffer e cobertura dos KPIs de saúde da rede.

Rodar:  py -3.12 experimento.py            (20 sementes, ~2 min)
        py -3.12 experimento.py --rapido   (3 sementes, para testar)
Saídas em resultados/: por_cenario.csv, por_rodada.csv, resumo.md, fig_*.png
Só usa biblioteca padrão + matplotlib para as figuras.
"""
from __future__ import annotations

import bisect
import csv
import random
import sys
from collections import defaultdict, deque
from pathlib import Path
from statistics import mean, quantiles

import simulacao_cep as base
from simulacao_cep import Evento, EventoComplexo, P

AQUI = Path(__file__).resolve().parent
OUT = AQUI / "resultados"

# ---------------------------------------------------------------- fatores
REDES = {  # rede celular entre o veículo e a nuvem
    "boa":   dict(delay_ms=50,  jitter_ms=10,  perda=0.00),
    "media": dict(delay_ms=150, jitter_ms=40,  perda=0.02),
    "ruim":  dict(delay_ms=400, jitter_ms=120, perda=0.10),
}
# A nuvem (A0) reordena os eventos por timestamp: segura cada evento até t + L (L = atraso + 3 jitter,
# suposto conhecido). Evento que chega depois disso é "atrasado" e é processado fora de ordem.
def lateness(perfil):
    p = REDES[perfil]
    return (p["delay_ms"] + 3 * p["jitter_ms"]) / 1000
OFFLINE = {"nenhum": 0, "curto": 30, "longo": 90}   # segundos sem conectividade (túnel, garagem)
ARQUITETURAS = ("A0_nuvem", "A1_local+nuvem")

CFG = dict(
    duracao=240.0,          # s de condução simulada por rodada
    hz=20,                  # taxa dos sensores
    proc_borda_s=0.005,     # tempo de processamento na ECU hospedeira
    snapshot_s=3.0,         # snapshot cobre [t-3, t+3] em volta do evento complexo
    buffer_bytes=128 * 1024,  # store-and-forward do gateway durante offline
    dreno_bytes_s=50_000,   # vazão ao esvaziar o buffer quando a rede volta
    qos_timeout_s=1.0,      # QoS 1: reenvio após timeout
    qos_tentativas=3,
    bytes=dict(bruto=64, complexo=256, agregado=96, snapshot_por_evento=32),
)
B = CFG["bytes"]

LOCAIS = {"Frenagem tardia (atraso de mensagem)", "Frenagem fantasma", "Ataque cibernético", "Degradação do barramento"}
RISCO = LOCAIS | {"Degradação do sensor"}
CENARIOS_GT = ["Frenagem tardia (atraso de mensagem)", "Frenagem fantasma", "Ataque cibernético",
               "Degradação do barramento", "Degradação do sensor", "Comportamento do motorista"]


# ---------------------------------------------------------------- gerador com verdade de referência
def gerar(seed: int, duracao: float):
    """Fluxo de eventos simples do veículo + instantes reais de cada falha injetada."""
    rng = random.Random(seed)
    passo = 1 / CFG["hz"]
    snap = lambda x: round(x / passo) * passo
    slots = [20 + 34 * i + rng.uniform(0, 6) for i in range(6)]
    rng.shuffle(slots)
    t_tard, t_fant, t_atq, t_bus, t_sens, t_mot = (snap(s) for s in slots)
    gt = {
        "Frenagem tardia (atraso de mensagem)": (t_tard, t_tard),
        "Frenagem fantasma": (t_fant, t_fant),
        "Ataque cibernético": (t_atq, t_atq),
        "Degradação do barramento": (t_bus, t_bus + 15),
        "Degradação do sensor": (t_sens, t_sens + 30),
        "Comportamento do motorista": (t_mot + 0.9, t_mot + 0.9),
    }
    ev, t, alive = [], 0.0, 0
    while t < duracao:
        dist = 30 + 3 * rng.random()
        desvio = 0.0 if not t_sens <= t < t_sens + 30 else (t - t_sens) / 30 * 0.4
        radar = dist * (1 + rng.choice([-1, 1]) * desvio * rng.random())
        ev.append(Evento(t, "deteccao", "radar", {"dist": radar}))
        ev.append(Evento(t + 0.001, "can_msg", "radar", {"id": 0x101, "alive": alive % 16, "mac_ok": True, "lat_ms": rng.gauss(40, 8)}))
        ev.append(Evento(t + 0.002, "deteccao", "lidar", {"dist": dist}))
        alive += 1
        t += passo
    for k in range(1, 15):
        ev.append(Evento(t_sens + 30 * (1 - 1 / k), "erro_sensor", "radar", {"codigo": "U0235"}))
    for s in range(int(duracao)):
        over = t_bus <= s < t_bus + 15
        carga = 45 + rng.random() * 5 + (35 if over else 0)
        perdidas = int(rng.random() < 0.1) + (int(s - t_bus) + 1 if over else 0)
        ev.append(Evento(float(s), "bus_status", "gateway", {"carga": carga, "perdidas": perdidas}))
    for ta, reacao in [(t_mot, 0.9), (t_mot + 15, 2.2)]:
        ev.append(Evento(ta, "alerta", "hmi"))
        ev.append(Evento(ta + reacao, "freio_motorista", "pedal"))
    ev.append(Evento(t_fant + 0.003, "deteccao", "radar", {"dist": 8.0}))
    ev.append(Evento(t_fant + 0.004, "deteccao", "lidar", {"dist": 80.0}))
    ev.append(Evento(t_fant + 0.010, "freio_aeb", "ecu_aeb", {"decel": 6.0, "lat_ms": 45}))
    for i in range(12):
        ev.append(Evento(t_atq + i * 0.05, "can_msg", "desconhecida", {"id": 0x7FF, "alive": 0, "mac_ok": False, "lat_ms": 1}))
    ev.append(Evento(t_tard, "freio_aeb", "ecu_aeb", {"decel": 8.0, "lat_ms": 180}))
    ev.sort(key=lambda e: e.t)
    return ev, gt


# ---------------------------------------------------------------- rede veículo -> nuvem
class Rede:
    """Atraso + jitter + perda (QoS 1 com reenvio) + janela offline com store-and-forward limitado."""

    def __init__(self, rng: random.Random, perfil: str, offline_s: float, duracao: float):
        self.rng, self.p, self.perfil = rng, REDES[perfil], perfil
        self.off = None
        if offline_s:
            a = rng.uniform(40, duracao - offline_s - 30)
            self.off = (a, a + offline_s)
        self.msgs = self.bytes = self.descartados = self.perdidas = 0

    def _transmitir(self, t):
        for _ in range(CFG["qos_tentativas"]):
            d = max(0.005, self.rng.gauss(self.p["delay_ms"], self.p["jitter_ms"]) / 1000)
            if self.rng.random() >= self.p["perda"]:
                return t + d
            t += CFG["qos_timeout_s"]
        return None

    def _drenar(self, buf):
        t0, acc, res = self.off[1], 0, []
        for _, nb, pl in buf:
            acc += nb
            ta = self._transmitir(t0 + acc / CFG["dreno_bytes_s"])
            if ta is None:
                self.perdidas += 1
            else:
                res.append((ta, pl))
        return res

    def entregar(self, msgs):
        """msgs: [(t_envio, bytes, payload)] em ordem de envio -> [(t_chegada, payload)] em ordem de chegada."""
        out, buf, buf_bytes = [], deque(), 0
        for t, nb, pl in msgs:
            self.msgs += 1
            self.bytes += nb
            if self.off and self.off[0] <= t < self.off[1]:
                buf.append((t, nb, pl))
                buf_bytes += nb
                while buf_bytes > CFG["buffer_bytes"]:       # buffer cheio: descarta o mais antigo
                    _, b, _ = buf.popleft()
                    buf_bytes -= b
                    self.descartados += 1
                continue
            if buf and t >= self.off[1]:
                out.extend(self._drenar(buf))
                buf.clear()
                buf_bytes = 0
            ta = self._transmitir(t)
            if ta is None:
                self.perdidas += 1
            else:
                out.append((ta, pl))
        if buf:
            out.extend(self._drenar(buf))
        out.sort(key=lambda x: x[0])
        return out


# ---------------------------------------------------------------- regras da nuvem sobre agregados (A1)
class Agregador:
    """Na borda: resume cada segundo do fluxo bruto num pacote pequeno para a nuvem."""

    def __init__(self):
        self.sec, self.ult_radar = 0, None
        self._zera()

    def _zera(self):
        self.lats, self.cargas, self.perdidas, self.erros, self.pares, self.diverg = [], [], 0, 0, 0, 0

    def alimentar(self, e: Evento, saida: list):
        while e.t >= self.sec + 1:
            self.fechar(saida)
        if e.tipo == "can_msg" and e.dados["mac_ok"]:
            self.lats.append(e.dados["lat_ms"])
        elif e.tipo == "bus_status":
            self.cargas.append(e.dados["carga"])
            self.perdidas += e.dados["perdidas"]
        elif e.tipo == "erro_sensor":
            self.erros += 1
        elif e.tipo == "deteccao" and e.origem == "radar":
            self.ult_radar = e.dados["dist"]
        elif e.tipo == "deteccao" and e.origem == "lidar" and self.ult_radar:
            self.pares += 1
            self.diverg += abs(self.ult_radar - e.dados["dist"]) / e.dados["dist"] > P["divergencia_max"]

    def fechar(self, saida: list):
        p95 = quantiles(self.lats, n=20)[-1] if len(self.lats) >= 2 else (self.lats[0] if self.lats else 0.0)
        pl = dict(sec=self.sec, lat_p95=p95, carga=mean(self.cargas) if self.cargas else 0.0, perdidas=self.perdidas,
                  erros=self.erros, pares=self.pares, diverg=self.diverg)
        saida.append((self.sec + 1 + CFG["proc_borda_s"], B["agregado"], ("agregado", pl)))
        self.sec += 1
        self._zera()


class NuvemAgregada:
    """Na nuvem (A1): as mesmas três regras de janela longa, agora sobre os agregados de 1 s."""

    def __init__(self):
        self.janela, self.kpi, self.kpi_fim = deque(), [], 10
        self.ant_erros, self.ult_disp_sensor = 0, -999
        self.motorista = base.ComportamentoMotorista()
        self.secs_recebidos = set()

    def receber_evento(self, e: Evento):
        return self.motorista.avaliar(e, None)

    def receber_agregado(self, pl: dict):
        out = []
        self.secs_recebidos.add(pl["sec"])
        self.janela.append(pl)
        while self.janela and self.janela[0]["sec"] < pl["sec"] - 9:
            self.janela.popleft()
        self.kpi.append(pl)
        if pl["sec"] + 1 > self.kpi_fim:
            p95 = max(x["lat_p95"] for x in self.kpi)
            carga, perdas = mean(x["carga"] for x in self.kpi), sum(x["perdidas"] for x in self.kpi)
            ok = p95 <= P["latencia_max_ms"] and carga <= P["carga_bus_max"] and perdas <= P["perda_max_janela"]
            out.append(EventoComplexo(self.kpi_fim, "Saúde da rede de mensagens",
                                      f"lat p95={p95:.0f} ms, carga={carga:.0f}%, perdidas={perdas} -> {'CONFORME' if ok else 'FORA DO NOMINAL'}"))
            self.kpi, self.kpi_fim = [], self.kpi_fim + 10
        erros = sum(x["erros"] for x in self.janela)
        rec = list(self.janela)[-2:]
        pares, div = sum(x["pares"] for x in rec), sum(x["diverg"] for x in rec)
        frac = div / pares if pares else 0.0
        crescendo = erros >= P["erros_sensor_min"] and erros > self.ant_erros
        self.ant_erros = erros
        if (crescendo or (pares >= 40 and frac > P["divergencia_frac"])) and pl["sec"] - self.ult_disp_sensor >= 10:
            self.ult_disp_sensor = pl["sec"]
            out.append(EventoComplexo(pl["sec"] + 1, "Degradação do sensor",
                                      f"{erros} erros em 10 s (crescendo={crescendo}), {frac:.0%} divergem"))
        return out


# ---------------------------------------------------------------- arquiteturas
def _janela(ts_ordenados, lo, hi):
    return bisect.bisect_left(ts_ordenados, lo), bisect.bisect_right(ts_ordenados, hi)


def rodar_A0(ev, rede: Rede):
    """Linha de base: todo evento bruto vai pela rede; a nuvem roda as 7 regras e guarda os brutos."""
    chegadas = rede.entregar([(e.t, B["bruto"], e) for e in ev])
    L = lateness(rede.perfil)
    # buffer de reordenação: libera em ordem de timestamp; o atrasado (chegou depois de t+L) sai na hora
    fila = sorted(((max(ta, e.t + L), e.t, e) for ta, e in chegadas), key=lambda x: (x[0], x[1]))
    dt = base.GemeoDigital([base.SaudeRede(), base.ComportamentoMotorista(), base.DegradacaoSensor(),
                            base.DegradacaoBarramento(), base.AtaqueCibernetico(), base.FrenagemFantasma(), base.FrenagemTardia()])
    decis = []
    for ta, _, e in fila:
        n0 = len(dt.disparos)
        dt.receber(e)
        for ec in dt.disparos[n0:]:
            decis.append(dict(cenario=ec.cenario, t_evento=ec.t, t_decisao=ta, t_gestao=ta, local=False))
    # evidência = eventos brutos da janela do snapshot que chegaram à nuvem
    ger_ts = [e.t for e in ev]
    cheg = sorted((e.t, ta) for ta, e in chegadas)
    cheg_ts = [c[0] for c in cheg]
    S = CFG["snapshot_s"]
    for d in decis:
        a, b = _janela(ger_ts, d["t_evento"] - S, d["t_evento"] + S)
        c, e_ = _janela(cheg_ts, d["t_evento"] - S, d["t_evento"] + S)
        n_ger, chegaram = max(1, b - a), [cheg[i][1] for i in range(c, e_)]
        d["evid_completude"] = min(1.0, len(chegaram) / n_ger)
        d["t_evidencia"] = max(chegaram) if d["evid_completude"] >= 1.0 else None
    return decis


def rodar_A1(ev, rede: Rede):
    """Proposta: DT local roda as 4 regras rápidas na ECU; manda à nuvem só complexos, snapshots e agregados."""
    borda = base.GemeoDigital([base.DegradacaoBarramento(), base.AtaqueCibernetico(), base.FrenagemFantasma(), base.FrenagemTardia()])
    agg, saida, decis = Agregador(), [], []
    ger_ts = [e.t for e in ev]
    S, proc = CFG["snapshot_s"], CFG["proc_borda_s"]
    for e in ev:
        n0 = len(borda.disparos)
        borda.receber(e)
        for ec in borda.disparos[n0:]:
            d = dict(cenario=ec.cenario, t_evento=ec.t, t_decisao=e.t + proc, t_gestao=None, local=True,
                     evid_completude=0.0, t_evidencia=None)
            decis.append(d)
            saida.append((e.t + proc, B["complexo"], ("complexo", d)))
            a, b = _janela(ger_ts, ec.t - S, ec.t + S)
            saida.append((ec.t + S + proc, (b - a) * B["snapshot_por_evento"], ("snapshot", d)))
        agg.alimentar(e, saida)
        if e.tipo in ("alerta", "freio_motorista"):
            saida.append((e.t + proc, B["bruto"], ("evento", e)))
    agg.fechar(saida)
    saida.sort(key=lambda x: x[0])
    nuvem = NuvemAgregada()
    cheg_agg = {}
    for ta, (tipo, pl) in rede.entregar(saida):
        if tipo == "complexo":
            pl["t_gestao"] = ta
        elif tipo == "snapshot":
            pl["evid_completude"], pl["t_evidencia"] = 1.0, ta
        else:
            novos = nuvem.receber_agregado(pl) if tipo == "agregado" else nuvem.receber_evento(pl)
            if tipo == "agregado":
                cheg_agg[pl["sec"]] = ta
            for ec in novos:
                decis.append(dict(cenario=ec.cenario, t_evento=ec.t, t_decisao=ta, t_gestao=ta, local=False, _sec=int(ec.t)))
    for d in decis:
        if d["local"]:
            continue
        secs = [cheg_agg.get(s) for s in range(d["_sec"] - 10, d["_sec"])]
        ok = [s for s in secs if s is not None]
        d["evid_completude"] = len(ok) / 10
        d["t_evidencia"] = max(ok) if len(ok) == 10 else None
    return decis


# ---------------------------------------------------------------- métricas de uma rodada
def medir(decis, gt, rede: Rede, duracao: float):
    linhas, usados = [], set()
    for cen in CENARIOS_GT:
        t0, t1 = gt[cen]
        cand = [d for d in decis if d["cenario"] == cen and t0 - 0.5 <= d["t_evento"] <= t1 + 15]
        cand.sort(key=lambda d: d["t_decisao"])
        d = cand[0] if cand else None
        for x in cand:
            usados.add(id(x))
        linhas.append(dict(
            cenario=cen,
            falha_no_offline=bool(rede.off and rede.off[0] <= t0 < rede.off[1]),
            detectado=int(d is not None),
            lat_decisao=(d["t_decisao"] - t0) if d else None,
            lat_gestao=(d["t_gestao"] - t0) if d and d["t_gestao"] is not None else None,
            evid_completude=d["evid_completude"] if d else 0.0,
            t_evidencia=(d["t_evidencia"] - t0) if d and d["t_evidencia"] is not None else None,
        ))
    fp = sum(1 for d in decis if d["cenario"] in RISCO and id(d) not in usados)
    kpi = sum(1 for d in decis if d["cenario"] == "Saúde da rede de mensagens" and d["t_gestao"] is not None)
    rodada = dict(falsos_positivos=fp, msgs_nuvem=rede.msgs, bytes_nuvem=rede.bytes, descartados_buffer=rede.descartados,
                  perdidas_rede=rede.perdidas, kpi_cobertura=kpi / (int(duracao / 10) - 1))
    return linhas, rodada


# ---------------------------------------------------------------- execução do plano fatorial
def semente_rede(seed, perfil, off_nome):
    """Semente determinística da rede (hash() de string muda a cada processo; não serve)."""
    return seed * 1000 + list(REDES).index(perfil) * 10 + list(OFFLINE).index(off_nome)


def executar(seeds):
    por_cen, por_rod = [], []
    total = len(ARQUITETURAS) * len(REDES) * len(OFFLINE) * len(seeds)
    n = 0
    for seed in seeds:
        ev, gt = gerar(seed, CFG["duracao"])
        for perfil in REDES:
            for off_nome, off_s in OFFLINE.items():
                for arq in ARQUITETURAS:
                    rede = Rede(random.Random(semente_rede(seed, perfil, off_nome)), perfil, off_s, CFG["duracao"])
                    decis = rodar_A0(ev, rede) if arq == "A0_nuvem" else rodar_A1(ev, rede)
                    linhas, rodada = medir(decis, gt, rede, CFG["duracao"])
                    chave = dict(arquitetura=arq, rede=perfil, offline=off_nome, seed=seed)
                    por_cen += [{**chave, **l} for l in linhas]
                    por_rod.append({**chave, **rodada})
                    n += 1
                    if n % 36 == 0:
                        print(f"  {n}/{total} rodadas", file=sys.stderr)
    return por_cen, por_rod


def gravar_csv(path, linhas):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)


# ---------------------------------------------------------------- resumo e figuras
def p95(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return xs[0] if xs else float("nan")
    return quantiles(xs, n=20)[-1]


def md_tabela(cab, linhas):
    out = ["| " + " | ".join(cab) + " |", "|" + "|".join("---" for _ in cab) + "|"]
    out += ["| " + " | ".join(str(c) for c in l) + " |" for l in linhas]
    return "\n".join(out)


def resumir(por_cen, por_rod):
    g = defaultdict(list)
    for l in por_cen:
        g[(l["arquitetura"], l["rede"], l["offline"], l["cenario"])].append(l)
    r = defaultdict(list)
    for l in por_rod:
        r[(l["arquitetura"], l["rede"], l["offline"])].append(l)
    nseeds = len({l["seed"] for l in por_rod})
    md = [f"# Resumo do experimento ({nseeds} sementes por célula, {CFG['duracao']:.0f} s por rodada)\n"]

    # H1: latência de decisão, cenários reativos, sem offline
    md.append("## H1 (RQ1): latência de decisão nos cenários reativos, sem janela offline\n")
    linhas = []
    for cen in ["Frenagem tardia (atraso de mensagem)", "Frenagem fantasma", "Ataque cibernético"]:
        for perfil in REDES:
            for arq in ARQUITETURAS:
                ls = g[(arq, perfil, "nenhum", cen)]
                lat = [l["lat_decisao"] for l in ls if l["lat_decisao"] is not None]
                lg = [l["lat_gestao"] for l in ls if l["lat_gestao"] is not None]
                linhas.append([cen, perfil, arq, f"{100 * mean(l['detectado'] for l in ls):.0f}%",
                               f"{1000 * mean(lat):.0f}" if lat else "-", f"{1000 * p95(lat):.0f}" if lat else "-",
                               f"{1000 * p95(lg):.0f}" if lg else "-"])
    md.append(md_tabela(["Cenário", "Rede", "Arquitetura", "Detecção", "Decisão média (ms)", "Decisão p95 (ms)", "Até a Gestão p95 (ms)"], linhas))

    # H2: detecção com offline
    md.append("\n\n## H2 (RG1): taxa de detecção das falhas de risco por janela offline (rede media)\n")
    linhas = []
    for cen in [c for c in CENARIOS_GT if c in RISCO]:
        for off in OFFLINE:
            row = [cen, off]
            for arq in ARQUITETURAS:
                ls = g[(arq, "media", off, cen)]
                dentro = [l for l in ls if l["falha_no_offline"]]
                row.append(f"{100 * mean(l['detectado'] for l in ls):.0f}%" + (f" (na janela: {100 * mean(l['detectado'] for l in dentro):.0f}%, n={len(dentro)})" if dentro else ""))
            linhas.append(row)
    md.append(md_tabela(["Cenário", "Offline", *ARQUITETURAS], linhas))

    # H3: trilha auditável
    md.append("\n\n## H3 (RG2): completude da trilha e tempo até a evidência (rede media, cenários decididos na borda)\n")
    linhas = []
    for off in OFFLINE:
        for arq in ARQUITETURAS:
            ls = [l for c in LOCAIS for l in g[(arq, "media", off, c)] if l["detectado"]]
            comp = [l["evid_completude"] for l in ls]
            te = [l["t_evidencia"] for l in ls if l["t_evidencia"] is not None]
            linhas.append([off, arq, f"{100 * mean(comp):.1f}%" if comp else "-",
                           f"{100 * mean(c >= 1.0 for c in comp):.0f}%" if comp else "-",
                           f"{mean(te):.1f}" if te else "-", f"{p95(te):.1f}" if te else "-"])
    md.append(md_tabela(["Offline", "Arquitetura", "Completude média", "Decisões com trilha completa", "Evidência média (s)", "Evidência p95 (s)"], linhas))

    # H4: volume, falsos positivos, KPI
    md.append("\n\n## H4: volume enviado à nuvem, descartes, falsos positivos e cobertura de KPI\n")
    linhas = []
    for perfil in REDES:
        for off in OFFLINE:
            for arq in ARQUITETURAS:
                ls = r[(arq, perfil, off)]
                linhas.append([perfil, off, arq, f"{mean(l['bytes_nuvem'] for l in ls) / 1024:.0f}", f"{mean(l['msgs_nuvem'] for l in ls):.0f}",
                               f"{mean(l['descartados_buffer'] for l in ls):.0f}", f"{mean(l['falsos_positivos'] for l in ls):.2f}",
                               f"{100 * mean(l['kpi_cobertura'] for l in ls):.0f}%"])
    md.append(md_tabela(["Rede", "Offline", "Arquitetura", "KB/rodada", "msgs/rodada", "descartes buffer", "falsos positivos", "KPI entregues"], linhas))

    # degradação lenta: a nuvem com agregados perde algo?
    md.append("\n\n## Cenário de janela longa (Degradação do sensor): latência de detecção por arquitetura\n")
    linhas = []
    for perfil in REDES:
        for off in OFFLINE:
            row = [perfil, off]
            for arq in ARQUITETURAS:
                ls = g[(arq, perfil, off, "Degradação do sensor")]
                lat = [l["lat_decisao"] for l in ls if l["lat_decisao"] is not None]
                row.append(f"{100 * mean(l['detectado'] for l in ls):.0f}% / {mean(lat):.1f} s" if lat else "0%")
            linhas.append(row)
    md.append(md_tabela(["Rede", "Offline", *ARQUITETURAS], linhas))
    return "\n".join(md) + "\n", g, r


def figuras(g, r):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cores = {"A0_nuvem": "#8a8f98", "A1_local+nuvem": "#2b5d8f"}
    rot = {"A0_nuvem": "A0: só nuvem", "A1_local+nuvem": "A1: local + nuvem"}

    def barras(ax, cats, valores, ylabel, titulo, log=False):
        w, x = 0.38, range(len(cats))
        for i, arq in enumerate(ARQUITETURAS):
            ax.bar([k + (i - 0.5) * w for k in x], valores[arq], w, label=rot[arq], color=cores[arq])
        ax.set_xticks(list(x), cats)
        ax.set_ylabel(ylabel)
        ax.set_title(titulo, fontsize=10)
        if log:
            ax.set_yscale("log")
        ax.grid(axis="y", alpha=.3)

    fig, ax = plt.subplots(figsize=(6, 3.6))
    # só frenagem tardia e fantasma: o ataque tem 200 ms embutidos na própria regra (janela de 5 msgs)
    vals = {arq: [1000 * p95([l["lat_decisao"] for c in ["Frenagem tardia (atraso de mensagem)", "Frenagem fantasma"]
                               for l in g[(arq, p, "nenhum", c)]]) for p in REDES] for arq in ARQUITETURAS}
    barras(ax, [f"rede {p}" for p in REDES], vals, "latência de decisão p95 (ms)", "Frenagem tardia e fantasma, sem offline (H1)", log=True)
    ax.axhline(P["latencia_max_ms"], color="#b00", ls="--", lw=1, label="limite RQ1 (100 ms)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_latencia.png", dpi=160)

    fig, ax = plt.subplots(figsize=(6, 3.6))
    vals = {arq: [100 * mean(l["detectado"] for c in RISCO for l in g[(arq, "media", o, c)]) for o in OFFLINE] for arq in ARQUITETURAS}
    barras(ax, [f"offline {o}" for o in OFFLINE], vals, "falhas detectadas (%)", "Cobertura de políticas, rede media (H2)")
    ax.set_ylim(0, 105)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_deteccao.png", dpi=160)

    fig, ax = plt.subplots(figsize=(6, 3.6))
    vals = {arq: [100 * mean(l["evid_completude"] >= 1.0 for c in LOCAIS for l in g[(arq, "media", o, c)] if l["detectado"]) for o in OFFLINE] for arq in ARQUITETURAS}
    barras(ax, [f"offline {o}" for o in OFFLINE], vals, "decisões com trilha completa (%)", "Trilha auditável, rede media (H3)")
    ax.set_ylim(0, 105)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_evidencia.png", dpi=160)

    fig, ax = plt.subplots(figsize=(6, 3.6))
    vals = {arq: [mean(l["bytes_nuvem"] for l in r[(arq, "media", o)]) / 1024 for o in OFFLINE] for arq in ARQUITETURAS}
    barras(ax, [f"offline {o}" for o in OFFLINE], vals, "KB enviados por rodada de 240 s", "Volume veículo -> nuvem, rede media (H4)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_volume.png", dpi=160)


if __name__ == "__main__":
    seeds = range(3) if "--rapido" in sys.argv else range(20)
    OUT.mkdir(exist_ok=True)
    por_cen, por_rod = executar(list(seeds))
    gravar_csv(OUT / "por_cenario.csv", por_cen)
    gravar_csv(OUT / "por_rodada.csv", por_rod)
    md, g, r = resumir(por_cen, por_rod)
    (OUT / "resumo.md").write_text(md, encoding="utf-8")
    figuras(g, r)
    sys.stdout.reconfigure(encoding="utf-8")
    print(md)
