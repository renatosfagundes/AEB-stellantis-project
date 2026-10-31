import shutil
S = r"C:\Users\rfagu\AppData\Local\Temp\claude\c--Users-rfagu-Estudo\ea1b3a81-fea8-4657-be1b-6371be5e76e3\scratchpad"
base = r"C:\Users\rfagu\Estudo\dinamica_dt_aeb\artigo"
shutil.copy(base + r"\artigo_v6.md", base + r"\artigo_v62.md")
p = base + r"\artigo_v62.md"
s = open(p, encoding="utf-8").read()
i, j = s.index("# 5. DISCUSSÃO"), s.index("# 6. CONCLUSÃO")
s = s[:i] + open(S + r"\secao5_v62.md", encoding="utf-8").read() + "\n" + s[j:]
s = s.rstrip("\n") + "\n\n" + open(S + r"\refs_v62.md", encoding="utf-8").read()
rep = [
 ("Uma detecção correta, mas tardia, também é uma falha de segurança: a ISO 26262",
  r"O AEB é requisito regulamentar para veículos novos \[14\], tem desempenho especificado por normas e protocolos de ensaio \[15, 9\] e reduz as colisões traseiras em campo \[18, 19\]. Uma detecção correta, mas tardia, também é uma falha de segurança: a ISO 26262"),
 (r'ou "risco sem reação" \[2\]', r'ou "risco sem reação" \[13, 2\]'),
 (r"e trata a desordem por esperas limitadas, como marcas d'água e K-slack, que recuperam a ordem ao custo de latência \[3, 4\]",
  r"e trata a desordem por esperas limitadas, como pulsações, pontuação, K-slack e marcas d'água, que recuperam a ordem ao custo de latência \[11, 12, 3, 4, 10\]"),
 (r"decisões de manutenção ou atualização \[5, 6, 7\].", r"decisões de manutenção ou atualização \[5, 6, 7, 22\]."),
 ("Os estudos de CEP quantificam o compromisso entre correção e latência sem relacioná-lo à consequência física de um sistema de segurança, e os estudos de AEB raramente tratam a ordem dos eventos.",
  r"Os estudos de CEP quantificam o compromisso entre correção e latência sem relacioná-lo à consequência física de um sistema de segurança; a teoria de controle em rede trata o atraso no laço, mas não a desordem nem os mecanismos discretos de supervisão \[20, 21\]; e os estudos de AEB raramente tratam a ordem dos eventos."),
 ("e TTC = d/v, definido apenas para v > 0,5 m/s", r"e TTC = d/v \[26\], definido apenas para v > 0,5 m/s"),
 ("o barramento CAN emulado por um relé TCP e a dinâmica em Gazebo/ROS 2.", r"o barramento CAN emulado por um relé TCP e a dinâmica em Gazebo/ROS 2 \[27, 28\]."),
]
for a, b in rep:
    assert a in s, a[:60]
    s = s.replace(a, b)
open(p, "w", encoding="utf-8").write(s)
print("ok")
