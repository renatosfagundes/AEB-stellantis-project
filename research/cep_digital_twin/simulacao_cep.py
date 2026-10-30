"""
Simulação da integração: eventos do veículo (AEB) chegando ao Gêmeo Digital,
um motor CEP simples detectando eventos complexos e disparando os cenários
de governança da tabela do grupo.

Rodar:  py -3.12 simulacao_cep.py
Só usa a biblioteca padrão.
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from statistics import mean, quantiles

random.seed(4)

# ---------------------------------------------------------------- parâmetros
# Limiares de cada cenário (coluna "Parâmetros considerados" da tabela)
P = {
    "latencia_max_ms": 100,      # sensor -> atuador
    "carga_bus_max": 70.0,       # % de ocupação do CAN
    "perda_max_janela": 5,       # mensagens perdidas por janela de 10 s
    "erros_sensor_min": 3,       # erros na janela de 10 s (e crescendo)
    "divergencia_max": 0.15,     # |radar - lidar| / lidar
    "divergencia_frac": 0.30,    # fração das amostras divergentes
    "ataque_min_msgs": 5,        # msgs suspeitas em 1 s
    "reacao_lenta_s": 1.5,       # tempo de reação do motorista
    "janela_kpi_s": 10.0,
}
IDS_VALIDOS = {0x101, 0x102, 0x103, 0x200, 0x300}   # radar, lidar, câmera, AEB, freio


# ---------------------------------------------------------------- domínio
@dataclass(order=True)
class Evento:
    """Evento simples (primitivo) vindo do mundo real."""
    t: float
    tipo: str = field(compare=False)
    origem: str = field(compare=False)
    dados: dict = field(compare=False, default_factory=dict)


@dataclass
class EventoComplexo:
    """Evento derivado pelo CEP, que dispara um cenário de governança."""
    t: float
    cenario: str
    detalhe: str


CENARIOS = {
    # cenário: (N/R, decisão que a Gestão toma)
    "Saúde da rede de mensagens": ("Operação Normal", "Atualiza painel de KPIs e evidência de conformidade"),
    "Comportamento do motorista": ("Operação Normal", "Alimenta melhoria de calibração e de interface (HMI)"),
    "Degradação do sensor": ("Risco preventivo", "Agenda manutenção / recalibração do sensor"),
    "Degradação do barramento": ("Risco preventivo", "Abre inspeção elétrica / revisão da matriz CAN"),
    "Ataque cibernético": ("Risco preventivo", "Aciona time de segurança (VSOC), isola ECU"),
    "Frenagem fantasma": ("Risco reativo", "Abre análise de incidente, prepara correção via OTA"),
    "Frenagem tardia (atraso de mensagem)": ("Risco reativo", "Análise de causa raiz; avalia OTA ou recall"),
}


# ---------------------------------------------------------------- gerador
def gerar_eventos(duracao: float = 120.0) -> list[Evento]:
    """Gera a linha do tempo de eventos primitivos com falhas injetadas."""
    ev: list[Evento] = []
    t, alive = 0.0, 0
    while t < duracao:
        dist = 30 + 3 * random.random()
        # radar degradando entre 30 s e 60 s: diverge cada vez mais do lidar
        desvio = 0.0 if not 30 <= t < 60 else (t - 30) / 30 * 0.4
        radar = dist * (1 + random.choice([-1, 1]) * desvio * random.random())
        lat = random.gauss(40, 8)
        ev.append(Evento(t, "deteccao", "radar", {"dist": radar}))
        ev.append(Evento(t + 0.002, "deteccao", "lidar", {"dist": dist}))
        ev.append(Evento(t, "can_msg", "radar", {"id": 0x101, "alive": alive % 16, "mac_ok": True, "lat_ms": lat}))
        alive += 1
        t += 0.05                                              # 20 Hz

    # erros de sensor com frequência crescente (30-60 s)
    for k in range(1, 15):
        ev.append(Evento(30 + 30 * (1 - 1 / k), "erro_sensor", "radar", {"codigo": "U0235"}))

    # status do barramento a cada 1 s; sobrecarga entre 80 e 95 s
    for s in range(int(duracao)):
        carga = 45 + random.random() * 5 + (35 if 80 <= s < 95 else 0)
        perdidas = (random.random() < 0.1) + ((s - 79) if 80 <= s < 95 else 0)
        ev.append(Evento(float(s), "bus_status", "gateway", {"carga": carga, "perdidas": perdidas}))

    # motorista: alerta e reação (normal em 20 s, lenta em 45 s)
    for ta, reacao in [(20.0, 0.9), (45.0, 2.2)]:
        ev.append(Evento(ta, "alerta", "hmi"))
        ev.append(Evento(ta + reacao, "freio_motorista", "pedal"))

    # frenagem fantasma em 70 s: radar vê alvo a 8 m, lidar vê pista livre
    ev.append(Evento(70.003, "deteccao", "radar", {"dist": 8.0}))
    ev.append(Evento(70.004, "deteccao", "lidar", {"dist": 80.0}))
    ev.append(Evento(70.01, "freio_aeb", "ecu_aeb", {"decel": 6.0, "lat_ms": 45}))

    # ataque em 100 s: rajada de IDs desconhecidos / MAC inválido
    for i in range(12):
        ev.append(Evento(100 + i * 0.05, "can_msg", "desconhecida", {"id": 0x7FF, "alive": 0, "mac_ok": False, "lat_ms": 1}))

    # frenagem tardia em 110 s: obstáculo real, mensagem chega com 180 ms
    ev.append(Evento(110.0, "freio_aeb", "ecu_aeb", {"decel": 8.0, "lat_ms": 180}))

    return sorted(ev)


# ---------------------------------------------------------------- regras CEP
class Regra:
    nome = ""

    def avaliar(self, e: Evento, dt: "GemeoDigital") -> list[EventoComplexo]:
        raise NotImplementedError


class SaudeRede(Regra):
    nome = "Saúde da rede de mensagens"

    def __init__(self):
        self.lats, self.cargas, self.perdas, self.fim = [], [], 0, P["janela_kpi_s"]

    def avaliar(self, e, dt):
        out = []
        if e.t >= self.fim and self.lats:
            p95 = quantiles(self.lats, n=20)[-1] if len(self.lats) >= 2 else self.lats[0]
            carga = mean(self.cargas) if self.cargas else 0.0
            ok = (p95 <= P["latencia_max_ms"] and carga <= P["carga_bus_max"]
                  and self.perdas <= P["perda_max_janela"])
            out.append(EventoComplexo(self.fim, self.nome,
                       f"KPI janela: lat p95={p95:.0f} ms, carga={carga:.0f}%, "
                       f"perdidas={self.perdas} -> {'CONFORME' if ok else 'FORA DO NOMINAL'}"))
            self.lats, self.cargas, self.perdas = [], [], 0
            self.fim += P["janela_kpi_s"]
        if e.tipo == "can_msg" and e.dados["mac_ok"]:
            self.lats.append(e.dados["lat_ms"])
        elif e.tipo == "bus_status":
            self.cargas.append(e.dados["carga"])
            self.perdas += e.dados["perdidas"]
        return out


class ComportamentoMotorista(Regra):
    nome = "Comportamento do motorista"

    def __init__(self):
        self.alerta = None

    def avaliar(self, e, dt):
        if e.tipo == "alerta":
            self.alerta = e.t
        elif e.tipo == "freio_motorista" and self.alerta is not None:
            r = e.t - self.alerta
            self.alerta = None
            tag = "reação lenta" if r > P["reacao_lenta_s"] else "reação adequada"
            return [EventoComplexo(e.t, self.nome, f"alerta -> freio do motorista em {r:.1f} s ({tag})")]
        return []


class DegradacaoSensor(Regra):
    """Padrão: erros crescendo na janela  OU  radar e lidar divergindo com frequência."""
    nome = "Degradação do sensor"

    def __init__(self):
        self.erros = deque()
        self.pares = deque(maxlen=40)
        self.ultimo_radar = None
        self.anterior = 0
        self.ult_disparo = -999.0

    def avaliar(self, e, dt):
        if e.tipo == "erro_sensor":
            self.erros.append(e.t)
        if e.tipo == "deteccao" and e.origem == "radar":
            self.ultimo_radar = e.dados["dist"]
        if e.tipo == "deteccao" and e.origem == "lidar" and self.ultimo_radar:
            self.pares.append(abs(self.ultimo_radar - e.dados["dist"]) / e.dados["dist"])
        while self.erros and self.erros[0] < e.t - 10:
            self.erros.popleft()
        if e.t - self.ult_disparo < 10:
            return []
        frac = sum(d > P["divergencia_max"] for d in self.pares) / max(len(self.pares), 1)
        n = len(self.erros)
        crescendo = n >= P["erros_sensor_min"] and n > self.anterior
        self.anterior = n
        if crescendo or (len(self.pares) == 40 and frac > P["divergencia_frac"]):
            self.ult_disparo = e.t
            return [EventoComplexo(e.t, self.nome,
                    f"radar: {n} erros em 10 s (crescendo={crescendo}), {frac:.0%} das leituras divergem do lidar")]
        return []


class DegradacaoBarramento(Regra):
    nome = "Degradação do barramento"

    def __init__(self):
        self.janela = deque()
        self.ult_disparo = -999.0

    def avaliar(self, e, dt):
        if e.tipo != "bus_status":
            return []
        self.janela.append(e)
        while self.janela[0].t < e.t - 10:
            self.janela.popleft()
        carga = mean(x.dados["carga"] for x in self.janela)
        perdas = sum(x.dados["perdidas"] for x in self.janela)
        if (carga > P["carga_bus_max"] or perdas > P["perda_max_janela"]) and e.t - self.ult_disparo >= 10:
            self.ult_disparo = e.t
            return [EventoComplexo(e.t, self.nome, f"carga média {carga:.0f}% e {perdas} msgs perdidas em 10 s")]
        return []


class AtaqueCibernetico(Regra):
    nome = "Ataque cibernético"

    def __init__(self):
        self.suspeitas = deque()
        self.ult_disparo = -999.0

    def avaliar(self, e, dt):
        if e.tipo != "can_msg":
            return []
        if e.dados["id"] not in IDS_VALIDOS or not e.dados["mac_ok"]:
            self.suspeitas.append(e.t)
        while self.suspeitas and self.suspeitas[0] < e.t - 1:
            self.suspeitas.popleft()
        if len(self.suspeitas) >= P["ataque_min_msgs"] and e.t - self.ult_disparo >= 5:
            self.ult_disparo = e.t
            return [EventoComplexo(e.t, self.nome,
                    f"{len(self.suspeitas)} msgs em 1 s com ID 0x{e.dados['id']:X} desconhecido / MAC inválido")]
        return []


class FrenagemFantasma(Regra):
    """Padrão: freio do AEB  E  NÃO existe obstáculo confirmado pelo lidar nos últimos 300 ms."""
    nome = "Frenagem fantasma"

    def avaliar(self, e, dt):
        if e.tipo != "freio_aeb":
            return []
        radar, lidar = dt.ultima("radar", e.t, 0.3), dt.ultima("lidar", e.t, 0.3)
        if radar and lidar and lidar.dados["dist"] > 2 * radar.dados["dist"]:
            return [EventoComplexo(e.t, self.nome,
                    f"AEB freou {e.dados['decel']} m/s² com radar={radar.dados['dist']:.0f} m "
                    f"mas lidar={lidar.dados['dist']:.0f} m (sem obstáculo confirmado)")]
        return []


class FrenagemTardia(Regra):
    nome = "Frenagem tardia (atraso de mensagem)"

    def avaliar(self, e, dt):
        if e.tipo == "freio_aeb" and e.dados["lat_ms"] > P["latencia_max_ms"]:
            return [EventoComplexo(e.t, self.nome,
                    f"comando de freio chegou com {e.dados['lat_ms']} ms (limite {P['latencia_max_ms']} ms)")]
        return []


# ---------------------------------------------------------------- gêmeo digital
class GemeoDigital:
    """Espelha o estado do veículo e roda as regras CEP sobre o fluxo de eventos."""

    def __init__(self, regras: list[Regra]):
        self.regras = regras
        self.historico: dict[str, deque] = {"radar": deque(maxlen=50), "lidar": deque(maxlen=50)}
        self.disparos: list[EventoComplexo] = []

    def ultima(self, sensor: str, t: float, janela: float):
        for x in reversed(self.historico[sensor]):
            if t - janela <= x.t <= t:
                return x
        return None

    def receber(self, e: Evento):
        if e.tipo == "deteccao":
            self.historico[e.origem].append(e)
        for r in self.regras:
            self.disparos.extend(r.avaliar(e, self))


class Gestao:
    """Lado da governança: recebe o evento complexo e registra a decisão."""

    @staticmethod
    def decidir(ec: EventoComplexo) -> str:
        tipo, acao = CENARIOS[ec.cenario]
        return f"[{ec.t:6.1f} s] {tipo:<16} | {ec.cenario:<37} | {ec.detalhe}\n{'':>28}-> Gestão: {acao}"


if __name__ == "__main__":
    eventos = gerar_eventos()
    dt = GemeoDigital([SaudeRede(), ComportamentoMotorista(), DegradacaoSensor(),
                       DegradacaoBarramento(), AtaqueCibernetico(), FrenagemFantasma(), FrenagemTardia()])
    for e in eventos:
        dt.receber(e)

    print(f"{len(eventos)} eventos simples processados -> {len(dt.disparos)} eventos complexos\n")
    for ec in sorted(dt.disparos, key=lambda x: x.t):
        print(Gestao.decidir(ec))
    print("\nResumo por cenário:")
    for nome, (tipo, _) in CENARIOS.items():
        print(f"  {tipo:<16} {nome:<37} {sum(d.cenario == nome for d in dt.disparos):>3}")
