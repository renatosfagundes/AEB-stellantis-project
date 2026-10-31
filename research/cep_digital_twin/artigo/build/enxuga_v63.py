"""V6.3: cortes para caber em 8 páginas depois da correção de H1b."""
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ART = AQUI.parent / "artigo_v6.md"
SEC5 = AQUI / "secao5_v62.md"


def troca(path, pares):
    s = path.read_text(encoding="utf-8")
    for a, b in pares:
        assert a in s, f"{path.name}: não achei: {a[:70]}"
        s = s.replace(a, b)
    path.write_text(s, encoding="utf-8", newline="")


troca(ART, [
    ("*AEB desligado:* rodada em que a ECU passou a OFF entre o instante crítico e o desfecho físico (menor "
     "distância real), detectado no estado publicado a cada 50 ms e no modo do comando de freio a cada 10 ms; "
     "não contam a queda para espera abaixo de 10 km/h nem o OFF por alcance mínimo do lidar (d < 1 m), que "
     "decorre do contato.",
     "*AEB desligado:* transição da ECU para OFF entre o instante crítico e o desfecho físico, sem contar o OFF "
     "por alcance mínimo do lidar (d < 1 m), que decorre do contato."),
    (" A idade média dos quadros não muda (100 ms); é o "
     "intervalo entre chegadas que ultrapassa a supervisão.", ""),
    (" Sem desordem, a latência até o freio foi de 180 a 260 ms.", ""),
])
troca(SEC5, [
    (" Fora desses casos, H1a teve no máximo 3 de 30 desligamentos por nível, "
     "sem relação com o atraso, atribuídos a pausas de escalonamento da bancada.", ""),
    ("É um limite superior: parte dos "
     "pares fica abaixo do limiar, e um quadro atrasado às vezes chega dentro da lacuna e a fecha.",
     "É um limite superior, porque parte dos pares fica abaixo do limiar."),
])
print("ok")
