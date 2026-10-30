"""
Complemento H1a / H1b: efeito ISOLADO do atraso e da desordenação da telemetria sobre a decisão
de frenagem do AEB e sobre o desfecho físico (colisão, velocidade de impacto, distância de parada).

Cadeia simulada:  percepção (20 ms) -> rede (atraso / desordem) -> estratégia de ordenação -> ECU AEB
(Kalman + FSM + PID em malha aberta, 10 ms, calibração do projeto AEB-stellantis) -> veículo (CCRs).

A ECU segue a calibração real do firmware (aeb_config.h / aeb_fsm.c): TTC 4.0/3.0/2.2/1.8 s, pisos de
distância 20/10/5 m, d_brake = v²/12, WARNING mínimo 0,8 s, histerese de descida 0,2 s, decel 2/4/6 m/s²
com rampa de 1,667 %/ciclo (100 % = 10 m/s² no scenario_controller), detector ROC (3 frames com |Δd|>10 m
-> falha -> OFF), Kalman 2 estados com os R/Q do firmware. Percepção: ruído σ = 0,25 m, mesma distância
para radar e lidar (como no SIL).

Rodar:  py -3.12 experimento_h1.py            (30 sementes)   -> resultados_h1/
        py -3.12 experimento_h1.py --rapido   (5 sementes)
"""
from __future__ import annotations

import csv
import random
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev

AQUI = Path(__file__).resolve().parent
OUT = AQUI / "resultados_h1"

# ------------------------------------------------------------------ calibração da ECU (aeb_config.h)
TTC_WARN, TTC_L1, TTC_L2, TTC_L3 = 4.0, 3.0, 2.2, 1.8
D_FLOOR_L1, D_FLOOR_L2, D_FLOOR_L3 = 20.0, 10.0, 5.0
DECEL = {3: 2.0, 4: 4.0, 5: 6.0}            # L1, L2, L3
PCT = {3: 20.0, 4: 40.0, 5: 60.0}           # PID em malha aberta: L1≈20 %, L2≈40 %, L3≈60 %
JERK_PCT_CICLO = 1.667                      # subida 0 -> 60 % em 0,36 s
WARNING_MIN, HYST = 0.8, 0.2
V_REL_MIN, DT_ECU, DT_PERC = 0.5, 0.010, 0.020
ROC_LIMIT, FAULT_CYCLES = 10.0, 3
R_LIDAR, R_RADAR_D, R_RADAR_V, Q_D, Q_V = 0.0025, 0.09, 0.01, 1e-4, 1e-5
STANDBY, WARNING, L1, L2, L3 = 1, 2, 3, 4, 5
NOME = {1: "STANDBY", 2: "WARNING", 3: "L1", 4: "L2", 5: "L3"}

CFG = dict(gap0=95.5, sigma=0.25, limite_ms=100.0, t_max=30.0, a_max=6.0)   # gap0: alvo em 100 m menos 4,5 m de carroceria (SIL)
ATRASOS_MS = (0, 25, 50, 100, 200, 400, 600, 800, 1000)
LAT_MEDIA_H1B = 100   # ms; latência média mantida constante em todas as células de H1b (o atraso base é reduzido
                      # na proporção dos eventos desordenados: 100 ms comporta 20 % de eventos com +400 ms)


# ------------------------------------------------------------------ ECU (Kalman + FSM + PID aberto)
class ECU:
    def __init__(self):
        self.x = None                       # [d, v_rel]
        self.P = [[1.0, 0.0], [0.0, 0.25]]
        self.state, self.timer = STANDBY, 0.0
        self.pct, self.fault, self.bad = 0.0, False, 0
        self.prev_d = None
        self.transicoes = []                # (t, de, para)
        self.liberacoes_espurias = 0        # descida de nível enquanto a verdade ainda exige o nível

    def _predict(self):
        if self.x is None:
            return
        d, v = self.x
        self.x = [d - v * DT_ECU, v]
        P = self.P
        F = [[1.0, -DT_ECU], [0.0, 1.0]]
        FP = [[F[0][0] * P[0][0] + F[0][1] * P[1][0], F[0][0] * P[0][1] + F[0][1] * P[1][1]],
              [P[1][0], P[1][1]]]
        self.P = [[FP[0][0] * F[0][0] + FP[0][1] * F[0][1] + Q_D, FP[0][1]],
                  [FP[1][0] * F[0][0] + FP[1][1] * F[0][1], FP[1][1] + Q_V]]

    def _update_d(self, z, R):
        d, v = self.x
        P = self.P
        S = P[0][0] + R
        K0, K1 = P[0][0] / S, P[1][0] / S
        y = z - d
        self.x = [d + K0 * y, v + K1 * y]
        self.P = [[(1 - K0) * P[0][0], (1 - K0) * P[0][1]], [P[1][0] - K1 * P[0][0], P[1][1] - K1 * P[0][1]]]

    def _update_v(self, z, R):
        d, v = self.x
        P = self.P
        S = P[1][1] + R
        K0, K1 = P[0][1] / S, P[1][1] / S
        y = z - v
        self.x = [d + K0 * y, v + K1 * y]
        self.P = [[P[0][0] - K0 * P[1][0], P[0][1] - K0 * P[1][1]], [(1 - K1) * P[1][0], (1 - K1) * P[1][1]]]

    def medir(self, d_meas, v_rel):
        """Frame de percepção (mesma distância para lidar e radar, como no SIL)."""
        if self.prev_d is not None and abs(d_meas - self.prev_d) > ROC_LIMIT:
            self.bad += 1
            if self.bad >= FAULT_CYCLES:
                self.fault = True
            return
        self.bad, self.prev_d = 0, d_meas
        if self.x is None:
            self.x = [d_meas, v_rel]
            return
        self._update_d(d_meas, R_LIDAR)
        self._update_d(d_meas, R_RADAR_D)
        self._update_v(v_rel, R_RADAR_V)

    def desejado(self, d, v_ego, v_rel):
        if v_rel < V_REL_MIN:
            return STANDBY
        if v_ego * v_ego / (2 * CFG["a_max"]) >= d or d <= D_FLOOR_L3:
            return L3
        if d <= D_FLOOR_L2:
            return L2
        if d <= D_FLOOR_L1:
            return L1
        ttc = d / v_rel
        if ttc <= TTC_L3:
            return L3
        if ttc <= TTC_L2:
            return L2
        if ttc <= TTC_L1:
            return L1
        if ttc <= TTC_WARN:
            return WARNING
        return STANDBY

    def passo(self, t, v_ego, nivel_verdade):
        """Um ciclo de 10 ms. Devolve a desaceleração comandada (m/s²)."""
        self._predict()
        if self.fault or self.x is None:
            self.pct = 0.0
            return 0.0
        des = self.desejado(max(self.x[0], 0.5), v_ego, self.x[1])
        s = self.state
        novo = s
        if s == STANDBY:
            if des >= WARNING:
                novo, self.timer = WARNING, 0.0
        elif s == WARNING:
            self.timer += DT_ECU
            if des >= L1 and self.timer >= WARNING_MIN:
                novo = des
            elif des == STANDBY and self.timer >= HYST:
                novo = STANDBY
        else:  # freando
            if des > s:
                novo, self.timer = des, 0.0
            elif des < s:
                self.timer += DT_ECU
                if self.timer >= HYST:
                    novo = max(des, STANDBY)
            else:
                self.timer = 0.0
        if novo != s:
            self.transicoes.append((t, s, novo))
            if novo < s and s >= L1 and nivel_verdade >= s:
                self.liberacoes_espurias += 1
            self.state, self.timer = novo, 0.0
        alvo = PCT.get(self.state, 0.0)
        if alvo > self.pct:
            self.pct = min(alvo, self.pct + JERK_PCT_CICLO)
        else:
            self.pct = alvo                                      # liberação instantânea
        return self.pct / 100.0 * 10.0


# ------------------------------------------------------------------ estratégias de ordenação
class Chegada:
    """Processa na ordem em que chega (sem reordenação)."""
    nome = "ordem de chegada"

    def __init__(self, **_):
        self.espera, self.descartados = [], 0

    def liberar(self, chegados, agora):
        return chegados


class Watermark:
    """Segura cada evento até t_evento + L; o que chega depois disso é tardio e é descartado."""
    nome = "watermark"

    def __init__(self, L=0.15, **_):
        self.L, self.buf, self.espera, self.descartados = L, [], [], 0

    def liberar(self, chegados, agora):
        for ev in chegados:
            if ev["t"] + self.L < agora - 1e-9:
                self.descartados += 1
                continue
            self.buf.append(ev)
        prontos = sorted((e for e in self.buf if e["t"] + self.L <= agora + 1e-9), key=lambda e: e["t"])
        self.buf = [e for e in self.buf if e["t"] + self.L > agora + 1e-9]
        for e in prontos:
            self.espera.append(agora - e["chegada"])
        return prontos


class KSlack:
    """K-slack adaptativo: libera eventos com t <= max_t_visto - K, K = maior atraso relativo observado."""
    nome = "K-slack"

    def __init__(self, **_):
        self.K, self.max_t, self.buf, self.espera, self.descartados = 0.0, -1.0, [], [], 0

    def liberar(self, chegados, agora):
        for ev in chegados:
            if ev["t"] > self.max_t:
                self.max_t = ev["t"]
            else:
                self.K = max(self.K, self.max_t - ev["t"])
            if ev["t"] < self.max_t - self.K - 1e-9:
                self.descartados += 1
                continue
            self.buf.append(ev)
        marca = self.max_t - self.K
        prontos = sorted((e for e in self.buf if e["t"] <= marca + 1e-9), key=lambda e: e["t"])
        self.buf = [e for e in self.buf if e["t"] > marca + 1e-9]
        for e in prontos:
            self.espera.append(agora - e["chegada"])
        return prontos


ESTRATEGIAS = {"chegada": Chegada, "watermark": Watermark, "kslack": KSlack}


# ------------------------------------------------------------------ verdade de referência
def niveis_verdade(v0, gap0):
    """Instantes em que a cinemática real cruza cada nível (sem ruído, sem atraso, sem frenagem)."""
    ecu = ECU()
    t, gap, out = 0.0, gap0, {}
    while gap > 0 and t < CFG["t_max"]:
        n = ecu.desejado(gap, v0, v0)
        for lvl in (WARNING, L1, L2, L3):
            if n >= lvl and lvl not in out:
                out[lvl] = t
        gap -= v0 * DT_ECU
        t += DT_ECU
    return out


# ------------------------------------------------------------------ uma rodada
def rodar(v0_kmh, seed, atraso_ms=0.0, jitter_ms=0.0, p_desordem=0.0, dist_desordem=(0.04, 0.2), estrategia="chegada", L=0.15, ref=None):
    """`ref` é a rodada de referência da mesma semente (atraso 0, ordem preservada): o ruído de percepção é
    idêntico (gerador separado), então latência e níveis perdidos são medidos contra ela."""
    rng, rng_rede = random.Random(seed), random.Random(seed + 100_000)
    v0 = v0_kmh / 3.6
    gap0 = CFG["gap0"]
    verdade = ref["_t_nivel"] if ref else niveis_verdade(v0, gap0)
    # atraso base ajustado para manter a latência média constante (= atraso_ms) quando há desordem
    extra_medio = (dist_desordem[0] + dist_desordem[1]) / 2
    base = atraso_ms / 1000 - p_desordem * extra_medio
    if base < 0:
        raise ValueError(f"latência média de {atraso_ms} ms não comporta {p_desordem:.0%} de eventos com {extra_medio*1000:.0f} ms extras")
    est, est_mon = ESTRATEGIAS[estrategia](L=L), ESTRATEGIAS[estrategia](L=L)
    ecu = ECU()
    v, gap, t = v0, gap0, 0.0
    pendentes, pendentes_mon, k = [], [], 0   # eventos em trânsito para a ECU e para o monitor CEP
    n_fora, dist_ms, dist_pos = 0, [], []
    gerados = []
    t_cmd, t_nivel = None, {}
    resultado, v_impacto, decel = None, 0.0, 0.0
    # monitor CEP (padrões de governança sobre o mesmo canal): "sem reação" e "frenagem fantasma"
    mon_percep, mon_freio, mon_ff_falso, mon_sem_reacao, t_ttc_critico = [], [], 0, 0, None
    estado_ant = ecu.state

    def sortear_atraso():
        nonlocal n_fora
        extra = 0.0
        if p_desordem > 0 and rng_rede.random() < p_desordem:
            extra = rng_rede.uniform(*dist_desordem)
            n_fora += 1
            dist_ms.append(extra * 1000)
        return max(0.0, base + extra + (rng_rede.gauss(0, jitter_ms / 1000) if jitter_ms else 0.0))

    while t < CFG["t_max"]:
        # percepção a 20 ms
        if abs(t / DT_PERC - round(t / DT_PERC)) < 1e-6:
            d_meas = gap + rng.gauss(0, CFG["sigma"])
            ev = dict(t=t, d=d_meas, v_rel=v, chegada=t + sortear_atraso(), k=k, tipo="percepcao")
            pendentes.append(ev)
            pendentes_mon.append(ev)
            gerados.append(ev)
            k += 1
        # chegada à ECU neste ciclo
        chegados = sorted((e for e in pendentes if e["chegada"] <= t + 1e-9), key=lambda e: e["chegada"])
        pendentes = [e for e in pendentes if e["chegada"] > t + 1e-9]
        for e in chegados:
            # distância da desordenação em posições: quantos eventos gerados depois dele já tinham chegado
            n_antes = sum(1 for g in gerados[e["k"] + 1:e["k"] + 60] if g["chegada"] < e["chegada"])
            if n_antes:
                dist_pos.append(n_antes)
        for e in est.liberar(chegados, t):
            ecu.medir(e["d"], e["v_rel"])
        nivel_verdade = ecu.desejado(gap, v0, v) if v > V_REL_MIN else STANDBY
        a_cmd = ecu.passo(t, v, nivel_verdade)
        if ecu.state >= L1 and t_cmd is None:
            t_cmd = t
        for lvl in (WARNING, L1, L2, L3):
            if ecu.state >= lvl and lvl not in t_nivel:
                t_nivel[lvl] = t
        # comando de freio (mudança de nível) vira evento para o monitor CEP, pelo mesmo canal
        if ecu.state != estado_ant and ecu.state >= L1:
            pendentes_mon.append(dict(t=t, nivel=ecu.state, chegada=t + sortear_atraso(), k=-1, tipo="freio"))
        estado_ant = ecu.state
        # monitor CEP: processa o que chegou, com a mesma estratégia de ordenação
        cheg_mon = sorted((e for e in pendentes_mon if e["chegada"] <= t + 1e-9), key=lambda e: e["chegada"])
        pendentes_mon = [e for e in pendentes_mon if e["chegada"] > t + 1e-9]
        for e in est_mon.liberar(cheg_mon, t):
            if e["tipo"] == "percepcao":
                ttc = e["d"] / e["v_rel"] if e["v_rel"] >= V_REL_MIN else 99.0
                mon_percep.append((e["t"], ttc))
                if ttc <= TTC_L1:
                    if t_ttc_critico is None:
                        t_ttc_critico = e["t"]
                    # padrão "AEB sem reação": TTC crítico há mais de 0,2 s e nenhum comando de freio conhecido
                    if e["t"] - t_ttc_critico >= 0.2 and not any(f[0] <= e["t"] for f in mon_freio):
                        mon_sem_reacao = 1
            else:
                # padrão "frenagem fantasma": comando de freio sem leitura com TTC <= 4 s nos 300 ms anteriores
                if not any(e["t"] - 0.3 <= pt <= e["t"] and pttc <= TTC_WARN for pt, pttc in mon_percep):
                    mon_ff_falso = 1
                mon_freio.append((e["t"], e["nivel"]))
        # veículo (desaceleração comandada aplicada no ciclo)
        decel = a_cmd
        v_new = max(0.0, v - decel * DT_ECU)
        gap -= (v + v_new) / 2 * DT_ECU
        v = v_new
        t += DT_ECU
        if gap <= 0:
            resultado, v_impacto = "COLISAO", v
            break
        if v <= 0.01:
            resultado = "PARADO"
            break
    if resultado is None:
        resultado = "TIMEOUT"
    # margem temporal no 1º comando de freio: tempo até o último instante em que 6 m/s² ainda evitaria a colisão
    margem = None
    if t_cmd is not None:
        gap_cmd = gap0 - v0 * t_cmd
        d_ultimo = v0 * v0 / (2 * CFG["a_max"])
        margem = (gap_cmd - d_ultimo) / v0
    lat = {lvl: (t_nivel[lvl] - verdade[lvl]) if lvl in t_nivel and lvl in verdade else None for lvl in (L1, L2)}
    perdidos = sum(1 for lvl in (L1, L2, L3) if lvl in verdade and lvl not in t_nivel)
    lat_media = mean(e["chegada"] - e["t"] for e in gerados) * 1000 if gerados else 0.0
    t_ttc_truth = next((e["t"] for e in gerados if e["v_rel"] >= V_REL_MIN and e["d"] / e["v_rel"] <= TTC_L1), None)
    return dict(_t_nivel=t_nivel,
        v0_kmh=v0_kmh, seed=seed, atraso_ms=atraso_ms, p_desordem=p_desordem, dist_desordem=f"{int(dist_desordem[0]*1000)}-{int(dist_desordem[1]*1000)}",
        estrategia=estrategia, resultado=resultado, v_impacto_kmh=round(v_impacto * 3.6, 2),
        dist_parada_m=round(max(gap, 0.0), 2), t_cmd_s=t_cmd, lat_media_efetiva_ms=round(lat_media, 1),
        lat_L1_ms=None if lat[L1] is None else round(lat[L1] * 1000, 1),
        lat_L2_ms=None if lat[L2] is None else round(lat[L2] * 1000, 1), margem_s=None if margem is None else round(margem, 3),
        excede_limite=int(lat[L1] is not None and lat[L1] * 1000 > CFG["limite_ms"]) if lat[L1] is not None else 1,
        niveis_perdidos=perdidos, liberacoes_espurias=ecu.liberacoes_espurias, n_transicoes=len(ecu.transicoes),
        falha_sensor=int(ecu.fault), eventos_fora_ordem=n_fora, dist_desordem_ms=round(mean(dist_ms), 1) if dist_ms else 0.0,
        dist_desordem_pos=round(mean(dist_pos), 2) if dist_pos else 0.0, espera_media_ms=round(mean(est.espera) * 1000, 1) if est.espera else 0.0,
        descartados=est.descartados,
        mon_sem_reacao_alarme=mon_sem_reacao,
        # falso se a ECU de fato reagiu em até 0,2 s após a 1ª leitura com TTC <= 3 s (o alarme veio só da desordem/descarte)
        mon_sem_reacao_falso=int(mon_sem_reacao and t_cmd is not None and t_ttc_truth is not None and t_cmd - t_ttc_truth <= 0.2),
        mon_fantasma_falso=mon_ff_falso,
        mon_freio_perdido=int(t_cmd is not None and not mon_freio),
    )


# ------------------------------------------------------------------ planos
REFS = {}


def referencia(v0, s):
    if (v0, s) not in REFS:
        REFS[(v0, s)] = rodar(v0, s)
    return REFS[(v0, s)]


def limpar(l):
    return {k: v for k, v in l.items() if not k.startswith("_")}


def plano_h1a(seeds):
    out = []
    for v0 in (40, 50):
        for atraso in ATRASOS_MS:
            for s in seeds:
                out.append(limpar(rodar(v0, s, atraso_ms=atraso, ref=referencia(v0, s))))
    return out


def plano_h1b(seeds):
    out = []
    for v0 in (40, 50):
        for dist in ((0.04, 0.2), (0.2, 0.6)):
            for p in (0.0, 0.05, 0.10, 0.20):
                for est in ESTRATEGIAS:
                    for s in seeds:
                        out.append(limpar(rodar(v0, s, atraso_ms=LAT_MEDIA_H1B, p_desordem=p, dist_desordem=dist, estrategia=est, ref=referencia(v0, s))))
    return out


# ------------------------------------------------------------------ resumo
def md_tabela(cab, linhas):
    out = ["| " + " | ".join(cab) + " |", "|" + "|".join("---" for _ in cab) + "|"]
    out += ["| " + " | ".join(str(c) for c in l) + " |" for l in linhas]
    return "\n".join(out)


def f1(xs, k=1):
    xs = [x for x in xs if x is not None]
    return f"{mean(xs):.{k}f}" if xs else "-"


def resumir(h1a, h1b, seeds):
    md = [f"# Complemento H1a / H1b ({len(seeds)} sementes por célula, CCRs, alvo parado a 100 m)\n"]
    # validação do modelo
    md.append("## Calibração: modelo sem atraso × referência do SIL (reports/sil)\n")
    ref = {40: 5.3, 50: 4.7}
    linhas = []
    for v0 in (40, 50):
        ls = [l for l in h1a if l["v0_kmh"] == v0 and l["atraso_ms"] == 0]
        linhas.append([f"ccrs_{v0}", f1([l["dist_parada_m"] for l in ls], 2), f"{ref[v0]}", f1([l["t_cmd_s"] for l in ls], 2)])
    md.append(md_tabela(["Cenário", "Distância de parada, modelo (m)", "Distância de parada, SIL (m)", "1º comando de freio (s)"], linhas))

    md.append("\n\n## H1a: atraso isolado (ordem preservada, sem jitter, sem perda)\n")
    linhas = []
    for v0 in (40, 50):
        for atraso in ATRASOS_MS:
            ls = [l for l in h1a if l["v0_kmh"] == v0 and l["atraso_ms"] == atraso]
            col = [l for l in ls if l["resultado"] == "COLISAO"]
            linhas.append([v0, atraso, f1([l["lat_L1_ms"] for l in ls]), f1([l["lat_L2_ms"] for l in ls]),
                           f1([l["margem_s"] for l in ls], 2), f"{100 * mean(l['excede_limite'] for l in ls):.0f}%",
                           f1([l["liberacoes_espurias"] for l in ls], 2),
                           f1([l["dist_parada_m"] for l in ls], 2), f"{100 * len(col) / len(ls):.0f}%",
                           f1([l["v_impacto_kmh"] for l in col], 1) if col else "-"])
    md.append(md_tabela(["v0 (km/h)", "Atraso (ms)", "Latência L1 (ms)", "Latência L2 (ms)", "Margem no 1º freio (s)", "Excede 100 ms",
                         "Liberações espúrias", "Dist. parada (m)", "Colisões", "v impacto (km/h)"], linhas))

    md.append(f"\n\n## H1b: desordenação isolada (latência média constante de {LAT_MEDIA_H1B} ms, sem perda)\n")
    for dist in ("40-200", "200-600"):
        md.append(f"\n### Distância da desordenação {dist} ms\n")
        linhas = []
        for v0 in (40, 50):
            for p in (0.0, 0.05, 0.10, 0.20):
                for est in ESTRATEGIAS:
                    ls = [l for l in h1b if l["v0_kmh"] == v0 and l["dist_desordem"] == dist and l["p_desordem"] == p and l["estrategia"] == est]
                    if not ls:
                        continue
                    col = [l for l in ls if l["resultado"] == "COLISAO"]
                    linhas.append([v0, f"{100 * p:.0f}%", ESTRATEGIAS[est].nome, f1([l["lat_media_efetiva_ms"] for l in ls], 0),
                                   f1([l["dist_desordem_pos"] for l in ls], 1),
                                   f1([l["niveis_perdidos"] for l in ls], 2), f1([l["liberacoes_espurias"] for l in ls], 2),
                                   f1([l["espera_media_ms"] for l in ls]), f1([l["descartados"] for l in ls]),
                                   f1([l["lat_L1_ms"] for l in ls]), f1([l["dist_parada_m"] for l in ls], 2),
                                   f"{100 * len(col) / len(ls):.0f}%",
                                   f"{100 * mean(l['mon_sem_reacao_alarme'] for l in ls):.0f}% / {100 * mean(l['mon_sem_reacao_falso'] for l in ls):.0f}%",
                                   f"{100 * mean(l['mon_fantasma_falso'] for l in ls):.0f}%",
                                   f"{100 * mean(l['mon_freio_perdido'] for l in ls):.0f}%"])
        md.append(md_tabela(["v0", "Fora de ordem", "Estratégia", "Lat. média (ms)", "Dist. (posições)", "Níveis perdidos", "Liberações espúrias",
                             "Espera adicional (ms)", "Descartados", "Latência L1 (ms)", "Dist. parada (m)", "Colisões",
                             "Monitor 'sem reação': alarmes / falsos", "Monitor 'fantasma' falso", "Monitor sem o freio"], linhas))
    return "\n".join(md) + "\n"


def figuras(h1a, h1b):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cor = {40: "#2b5d8f", 50: "#b03a2e"}
    atrasos = list(ATRASOS_MS)
    fig, axs = plt.subplots(1, 3, figsize=(10.5, 3.3))
    for v0 in (40, 50):
        sel = lambda a: [l for l in h1a if l["v0_kmh"] == v0 and l["atraso_ms"] == a]
        lat = [mean(l["lat_L1_ms"] for l in sel(a) if l["lat_L1_ms"] is not None) for a in atrasos]
        axs[0].plot(atrasos, lat, "o-", color=cor[v0], label=f"{v0} km/h")
        axs[1].plot(atrasos, [mean(l["dist_parada_m"] for l in sel(a)) for a in atrasos], "o-", color=cor[v0], label=f"{v0} km/h")
        axs[2].plot(atrasos, [100 * mean(l["resultado"] == "COLISAO" for l in sel(a)) for a in atrasos], "o-", color=cor[v0], label=f"{v0} km/h")
    axs[0].axhline(CFG["limite_ms"], color="#888", ls="--", lw=1)
    axs[0].set_xlabel("atraso da telemetria (ms)"); axs[0].set_ylabel("latência de detecção L1 (ms)")
    axs[1].set_xlabel("atraso da telemetria (ms)"); axs[1].set_ylabel("distância de parada (m)")
    axs[2].set_xlabel("atraso da telemetria (ms)"); axs[2].set_ylabel("colisões (%)"); axs[2].set_ylim(-3, 103)
    for ax in axs:
        ax.grid(alpha=.3); ax.legend(fontsize=8)
    fig.suptitle("H1a: atraso isolado (ordem, jitter e perda constantes)", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "fig_h1a.png", dpi=160)

    ps = [0.0, 0.05, 0.10, 0.20]
    cores_e = {"chegada": "#8a8f98", "watermark": "#2b5d8f", "kslack": "#2e7d4f"}
    for dist in ("40-200", "200-600"):
        fig, axs = plt.subplots(1, 4, figsize=(13, 3.3))
        for est in ESTRATEGIAS:
            sel = lambda p: [l for l in h1b if l["v0_kmh"] == 50 and l["dist_desordem"] == dist and l["p_desordem"] == p and l["estrategia"] == est]
            axs[0].plot([100 * p for p in ps], [100 * mean(l["mon_sem_reacao_falso"] for l in sel(p)) for p in ps], "o-", color=cores_e[est], label=ESTRATEGIAS[est].nome)
            axs[0].plot([100 * p for p in ps], [100 * mean(l["mon_sem_reacao_alarme"] for l in sel(p)) for p in ps], "x--", color=cores_e[est], alpha=.6)
            axs[1].plot([100 * p for p in ps], [mean(l["liberacoes_espurias"] for l in sel(p)) for p in ps], "o-", color=cores_e[est], label=ESTRATEGIAS[est].nome)
            axs[2].plot([100 * p for p in ps], [mean(l["espera_media_ms"] for l in sel(p)) for p in ps], "o-", color=cores_e[est], label=ESTRATEGIAS[est].nome)
            axs[3].plot([100 * p for p in ps], [mean(l["dist_parada_m"] for l in sel(p)) for p in ps], "o-", color=cores_e[est], label=ESTRATEGIAS[est].nome)
        axs[0].set_ylabel("alarme 'AEB sem reação' (% rodadas)\n(o = falso, x = total)"); axs[0].set_ylim(-3, 103)
        axs[1].set_ylabel("liberações espúrias do freio / rodada"); axs[2].set_ylabel("espera adicional (ms)"); axs[3].set_ylabel("distância de parada (m)")
        for ax in axs:
            ax.set_xlabel("eventos fora de ordem (%)"); ax.grid(alpha=.3); ax.legend(fontsize=8)
        fig.suptitle(f"H1b: desordenação isolada, 50 km/h, latência média {LAT_MEDIA_H1B} ms, distância da desordem {dist} ms", fontsize=10)
        fig.tight_layout()
        fig.savefig(OUT / f"fig_h1b_{dist}.png", dpi=160)


def gravar_csv(path, linhas):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)


if __name__ == "__main__":
    seeds = list(range(5)) if "--rapido" in sys.argv else list(range(30))
    OUT.mkdir(exist_ok=True)
    h1a = plano_h1a(seeds)
    print(f"H1a: {len(h1a)} rodadas", file=sys.stderr)
    h1b = plano_h1b(seeds)
    print(f"H1b: {len(h1b)} rodadas", file=sys.stderr)
    gravar_csv(OUT / "h1a.csv", h1a)
    gravar_csv(OUT / "h1b.csv", h1b)
    md = resumir(h1a, h1b, seeds)
    (OUT / "resumo_h1.md").write_text(md, encoding="utf-8")
    figuras(h1a, h1b)
    sys.stdout.reconfigure(encoding="utf-8")
    print(md)
