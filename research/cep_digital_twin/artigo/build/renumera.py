import re
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
corpo, refs = s.split("# REFERÊNCIAS", 1)
pat = re.compile(r"\\\[([\d, ]+)\\\]")
ordem = []
for m in pat.finditer(corpo):
    for n in m.group(1).split(","):
        n = int(n)
        if n not in ordem:
            ordem.append(n)
mapa = {old: i + 1 for i, old in enumerate(ordem)}
corpo = pat.sub(lambda m: "\\[" + ", ".join(str(mapa[int(n)]) for n in m.group(1).split(",")) + "\\]", corpo)
itens = {int(m.group(1)): m.group(2) for m in re.finditer(r"\\\[(\d+)\\\] (.+)", refs)}
faltando = [o for o in ordem if o not in itens]
if faltando:
    raise SystemExit(f"referências citadas sem entrada: {faltando}")
refs_novas = "\n\n".join(f"\\[{mapa[o]}\\] {itens[o]}" for o in ordem)
open(p, "w", encoding="utf-8").write(corpo + "# REFERÊNCIAS\n\n" + refs_novas + "\n")
print(mapa)
