"""V8: revisão da V7 (Ane) com alterações controladas do Word, para preservar a rastreabilidade.

Entrada: diretório com a V7 desempacotada (merge_runs já aplicado). Saída: o mesmo diretório editado.
Cada mudança de texto vira <w:ins>/<w:del> com autor AUTOR; nada é reescrito sem marca.
Uso: py -3.12 v8_revisao.py <dir_desempacotado>
"""
import re
import sys
from copy import deepcopy
from pathlib import Path

from lxml import etree

sys.stdout.reconfigure(encoding="utf-8")
NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = "{%s}" % NS
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
AUTOR = "Claude (revisão V8)"
DATA = "2026-10-31T21:00:00Z"
_id = [9000]


def novo_id():
    _id[0] += 1
    return str(_id[0])


def el(tag, **attrs):
    e = etree.Element(W + tag)
    for k, v in attrs.items():
        e.set(W + k, v)
    return e


def marca(tag):
    return el(tag, id=novo_id(), author=AUTOR, date=DATA)


def texto(tag, s):
    t = el(tag)
    t.text = s
    t.set(XML_SPACE, "preserve")
    return t


def run(rpr, s, tag="t"):
    r = el("r")
    if rpr is not None:
        r.append(deepcopy(rpr))
    r.append(texto(tag, s))
    return r


def fora_de_marca(e):
    return not any(a.tag in (W + "ins", W + "del") for a in e.iterancestors())


def trocar_no_t(t, ini, fim, novo):
    """Divide o run de t: texto[ini:fim] vira <w:del>, novo vira <w:ins>."""
    r = t.getparent()
    rpr = r.find(W + "rPr")
    filhos = [c for c in r if c.tag != W + "rPr"]
    k = filhos.index(t)
    s = t.text or ""
    a, velho, b = s[:ini], s[ini:fim], s[fim:]
    pecas = []
    r1 = el("r")
    if rpr is not None:
        r1.append(deepcopy(rpr))
    for c in filhos[:k]:
        r1.append(c)
    if a:
        r1.append(texto("t", a))
    if len(r1) > (1 if rpr is not None else 0):
        pecas.append(r1)
    if velho:
        d = marca("del")
        d.append(run(rpr, velho, "delText"))
        pecas.append(d)
    if novo:
        i = marca("ins")
        i.append(run(rpr, novo))
        pecas.append(i)
    r2 = el("r")
    if rpr is not None:
        r2.append(deepcopy(rpr))
    if b:
        r2.append(texto("t", b))
    for c in filhos[k + 1:]:
        r2.append(c)
    if len(r2) > (1 if rpr is not None else 0):
        pecas.append(r2)
    pai = r.getparent()
    pos = pai.index(r)
    pai.remove(r)
    for j, p in enumerate(pecas):
        pai.insert(pos + j, p)


def txt(p):
    return "".join(t.text or "" for t in p.iter(W + "t") if fora_de_marca(t))


def substituir(raiz, velho, novo, unico=True):
    """Troca controlada de um trecho que está inteiro dentro de um único w:t."""
    achados = [t for t in raiz.iter(W + "t") if fora_de_marca(t) and t.text and velho in t.text]
    if unico:
        assert len(achados) == 1, f"{len(achados)} ocorrências de: {velho[:60]}"
    t = achados[0]
    ini = t.text.index(velho)
    trocar_no_t(t, ini, ini + len(velho), novo)


def inserir_depois(raiz, ancora, novo):
    achados = [t for t in raiz.iter(W + "t") if fora_de_marca(t) and t.text and ancora in t.text]
    assert len(achados) == 1, f"{len(achados)} ocorrências da âncora: {ancora[:60]}"
    t = achados[0]
    fim = t.text.index(ancora) + len(ancora)
    trocar_no_t(t, fim, fim, novo)


def marcar_pmark(p, tag):
    ppr = p.find(W + "pPr")
    if ppr is None:
        ppr = el("pPr")
        p.insert(0, ppr)
    rpr = ppr.find(W + "rPr")
    if rpr is None:
        rpr = el("rPr")
        sect = ppr.find(W + "sectPr")
        if sect is not None:
            sect.addprevious(rpr)
        else:
            ppr.append(rpr)
    rpr.insert(0, marca(tag))


def apagar_paragrafo(p):
    for r in list(p.findall(W + "r")):
        for t in r.findall(W + "t"):
            t.tag = W + "delText"
            t.set(XML_SPACE, "preserve")
        d = marca("del")
        r.addprevious(d)
        d.append(r)
    marcar_pmark(p, "del")


def paragrafo_inserido(modelo_ppr, segmentos, rpr_base):
    p = el("p")
    ppr = deepcopy(modelo_ppr)
    for x in ppr.findall(W + "rPr"):
        ppr.remove(x)
    p.append(ppr)
    marcar_pmark(p, "ins")
    ins = marca("ins")
    for s, italico in segmentos:
        rpr = deepcopy(rpr_base)
        if italico:
            rpr.insert(0, el("i"))
        ins.append(run(rpr, s))
    p.append(ins)
    return p


def segmentos(s):
    """'texto *itálico* texto' -> [(texto, False), (itálico, True), ...]"""
    partes = re.split(r"(\*[^*]+\*)", s)
    return [(x[1:-1], True) if x.startswith("*") else (x, False) for x in partes if x]


# ------------------------------------------------------------------ dados da revisão
CITA = {
    1: ("Akidau et al.", 2015), 3: ("Brown et al.", 2001), 4: ("Cicchino", 2017), 5: ("Cugola & Margara", 2012),
    7: ("Euro NCAP", 2023), 8: ("Fildes et al.", 2015), 9: ("Grieves & Vickers", 2017), 10: ("Hespanha et al.", 2007),
    11: ("ISO", 2013), 12: ("ISO", 2018), 13: ("ISO", 2022), 14: ("ISO/IEC", 1998), 15: ("Koenig & Howard", 2004),
    17: ("Lee", 1976), 18: ("Li et al.", 2008), 19: ("Luckham", 2002), 20: ("Macenski et al.", 2022),
    21: ("Minerva et al.", 2020), 22: ("Mutschler & Philippsen", 2013), 24: ("Shi et al.", 2016),
    25: ("Srivastava & Widom", 2004), 26: ("Tao et al.", 2019), 27: ("Tucker et al.", 2003), 28: ("UNECE", 2020),
    29: ("Zhang et al.", 2001),
}

REFS = [
    "Akidau, T., Bradshaw, R., Chambers, C., Chernyak, S., Fernández-Moctezuma, R. J., Lax, R., McVeety, S., Mills, D., Perry, F., Schmidt, E., & Whittle, S. (2015). The dataflow model: A practical approach to balancing correctness, latency, and cost in massive-scale, unbounded, out-of-order data processing. *Proceedings of the VLDB Endowment, 8*(12), 1792–1803. https://doi.org/10.14778/2824032.2824076",
    "Brown, L. D., Cai, T. T., & DasGupta, A. (2001). Interval estimation for a binomial proportion. *Statistical Science, 16*(2), 101–133. https://doi.org/10.1214/ss/1009213286",
    "Cicchino, J. B. (2017). Effectiveness of forward collision warning and autonomous emergency braking systems in reducing front-to-rear crash rates. *Accident Analysis & Prevention, 99*, 142–152. https://doi.org/10.1016/j.aap.2016.11.009",
    "Cugola, G., & Margara, A. (2012). Processing flows of information: From data stream to complex event processing. *ACM Computing Surveys, 44*(3), 15:1–15:62. https://doi.org/10.1145/2187671.2187677",
    "Euro NCAP. (2023). *Test protocol: AEB Car-to-Car systems*. European New Car Assessment Programme.",
    "Fildes, B., Keall, M., Bos, N., Lie, A., Page, Y., Pastor, C., Pennisi, L., Rizzi, M., Thomas, P., & Tingvall, C. (2015). Effectiveness of low speed autonomous emergency braking in real-world rear-end crashes. *Accident Analysis & Prevention, 81*, 24–29. https://doi.org/10.1016/j.aap.2015.03.029",
    "Grieves, M., & Vickers, J. (2017). Digital twin: Mitigating unpredictable, undesirable emergent behavior in complex systems. In F.-J. Kahlen, S. Flumerfelt, & A. Alves (Eds.), *Transdisciplinary perspectives on complex systems* (pp. 85–113). Springer. https://doi.org/10.1007/978-3-319-38756-7_4",
    "Hespanha, J. P., Naghshtabrizi, P., & Xu, Y. (2007). A survey of recent results in networked control systems. *Proceedings of the IEEE, 95*(1), 138–162. https://doi.org/10.1109/JPROC.2006.887288",
    "ISO. (2013). *ISO 22839:2013 Intelligent transport systems: Forward vehicle collision mitigation systems: Operation, performance, and verification requirements*. International Organization for Standardization.",
    "ISO. (2018). *ISO 26262:2018 Road vehicles: Functional safety*. International Organization for Standardization.",
    "ISO. (2022). *ISO 21448:2022 Road vehicles: Safety of the intended functionality*. International Organization for Standardization.",
    "ISO/IEC. (1998). *ISO/IEC 10746-1:1998 Information technology: Open distributed processing: Reference model: Overview*. International Organization for Standardization.",
    "Koenig, N., & Howard, A. (2004). Design and use paradigms for Gazebo, an open-source multi-robot simulator. In *Proceedings of the 2004 IEEE/RSJ International Conference on Intelligent Robots and Systems* (Vol. 3, pp. 2149–2154). IEEE. https://doi.org/10.1109/IROS.2004.1389727",
    "Lee, D. N. (1976). A theory of visual control of braking based on information about time-to-collision. *Perception, 5*(4), 437–459. https://doi.org/10.1068/p050437",
    "Li, J., Tufte, K., Shkapenyuk, V., Papadimos, V., Johnson, T., & Maier, D. (2008). Out-of-order processing: A new architecture for high-performance stream systems. *Proceedings of the VLDB Endowment, 1*(1), 274–288. https://doi.org/10.14778/1453856.1453890",
    "Luckham, D. (2002). *The power of events: An introduction to complex event processing in distributed enterprise systems*. Addison-Wesley.",
    "Macenski, S., Foote, T., Gerkey, B., Lalancette, C., & Woodall, W. (2022). Robot Operating System 2: Design, architecture, and uses in the wild. *Science Robotics, 7*(66), eabm6074. https://doi.org/10.1126/scirobotics.abm6074",
    "Minerva, R., Lee, G. M., & Crespi, N. (2020). Digital twin in the IoT context: A survey on technical features, scenarios, and architectural models. *Proceedings of the IEEE, 108*(10), 1785–1824. https://doi.org/10.1109/JPROC.2020.2998530",
    "Mutschler, C., & Philippsen, M. (2013). Distributed low-latency out-of-order event processing for high data rate sensor streams. In *Proceedings of the 27th IEEE International Symposium on Parallel and Distributed Processing* (pp. 1133–1144). IEEE. https://doi.org/10.1109/IPDPS.2013.29",
    "Referência do projeto e do repositório omitida para preservar a avaliação cega; os dados completos serão inseridos na versão final.",
    "Shi, W., Cao, J., Zhang, Q., Li, Y., & Xu, L. (2016). Edge computing: Vision and challenges. *IEEE Internet of Things Journal, 3*(5), 637–646. https://doi.org/10.1109/JIOT.2016.2579198",
    "Srivastava, U., & Widom, J. (2004). Flexible time management in data stream systems. In *Proceedings of the 23rd ACM SIGMOD-SIGACT-SIGART Symposium on Principles of Database Systems* (pp. 263–274). ACM. https://doi.org/10.1145/1055558.1055596",
    "Tao, F., Zhang, H., Liu, A., & Nee, A. Y. C. (2019). Digital twin in industry: State-of-the-art. *IEEE Transactions on Industrial Informatics, 15*(4), 2405–2415. https://doi.org/10.1109/TII.2018.2873186",
    "Tucker, P. A., Maier, D., Sheard, T., & Fegaras, L. (2003). Exploiting punctuation semantics in continuous data streams. *IEEE Transactions on Knowledge and Data Engineering, 15*(3), 555–568. https://doi.org/10.1109/TKDE.2003.1198390",
    "UNECE. (2020). *UN Regulation No. 152: Uniform provisions concerning the approval of motor vehicles with regard to the Advanced Emergency Braking System (AEBS) for M1 and N1 vehicles*. United Nations Economic Commission for Europe.",
    "Zhang, W., Branicky, M. S., & Phillips, S. M. (2001). Stability of networked control systems. *IEEE Control Systems Magazine, 21*(1), 84–99. https://doi.org/10.1109/37.898794",
]

TEXTO = [
    # (velho, novo): trocas controladas no corpo
    ("Por isso, os 100 ms empregados neste estudo constituem uma referência experimental para comparar condições, não um FTTI universal do AEB.",
     "Por isso, este estudo não adota um FTTI e compara as condições pelo desfecho físico."),
    ("No modelo foram usadas 30 sementes por célula a 40 e 50 km/h.",
     "No modelo foram usadas 30 sementes por célula a 40 e 50 km/h; os resultados apresentados são os de 50 km/h, comparáveis aos da bancada."),
    ("transição para OFF, episódios de desligamento, falso alarme do monitor e margem no primeiro freio.",
     "transição para OFF, episódios de desligamento e falso alarme do monitor."),
    ("mas introduz 422 e 657 ms até o freio.",
     "mas eleva a latência até o freio para 422 e 657 ms, contra 180 a 260 ms sem desordem."),
    ("Figura 4. H1b: colisões e desligamentos do AEB por política e fração fora de ordem.",
     "Figura 4. H1b: colisões (linha cheia) e desligamentos do AEB (tracejada) por política e fração fora de ordem na bancada; em (c), colisões no modelo."),
]
INSERCOES = [
    # (âncora, texto inserido logo depois)
    ("Rodadas não conformes são repetidas.",
     " A auditoria a cada 20 rodadas reprovou 2 de 47 blocos, com K-slack entregando até 4,6 % fora de ordem; a "
     "política foi corrigida e as rodadas, refeitas. As 900 rodadas aceitas têm registro por quadro que liga "
     "perturbação, comando, estado da ECU e desfecho."),
    ("reiniciar a espera de 0,8 s em alerta.",
     " Com 20 % de desordem, houve em média 3 a 4 desligamentos por rodada, quase sempre durante a frenagem: a "
     "latência até o primeiro freio subiu pouco, mas a frenagem foi interrompida repetidas vezes."),
]
# Tabela 6: (linha, coluna) -> novo texto; linha 0 = cabeçalho
TAB6 = {
    (0, 2): "Latência até o freio", (0, 3): "AEB desligado (episódios/rodada)", (0, 4): "Colisões (IC 95 %)",
    (0, 5): "Dist. remanescente",
    (1, 3): "30/30 (3,1)", (2, 3): "29/30 (3,5)", (3, 3): "12/30 (0,6)", (4, 3): "30/30 (3,3)", (5, 3): "30/30 (4,3)",
    (6, 3): "2/30 (0,1)",
    (1, 4): "12/30 (25–58 %)", (2, 4): "16/30 (36–70 %)", (3, 4): "4/30 (5–30 %)", (4, 4): "12/30 (25–58 %)",
    (5, 4): "18/30 (42–75 %)", (6, 4): "1/30 (1–17 %)",
    (2, 1): "marca d’água", (5, 1): "marca d’água",
}


def citacao(grupo):
    nums = [int(x) for x in re.split(r",\s*", grupo)]
    if nums == [23]:
        return "(referência omitida para avaliação cega)"
    itens = sorted((CITA[n] for n in nums), key=lambda c: (c[0].lower(), c[1]))
    return "(" + "; ".join(f"{a}, {y}" for a, y in itens) + ")"


def main(d):
    doc = Path(d) / "word" / "document.xml"
    arv = etree.parse(str(doc))
    corpo = arv.getroot().find(W + "body")
    pars = list(corpo.iter(W + "p"))
    i_ref = next(i for i, p in enumerate(pars) if txt(p).strip() == "REFERÊNCIAS")
    titulo_ref = pars[i_ref]
    antigas = [p for p in pars[i_ref + 1:] if re.match(r"\[\d+\]", txt(p).strip())]
    assert len(antigas) == 29, len(antigas)

    # 1) citações numéricas -> autor-data, só antes das referências
    alvo = re.compile(r"\[(\d+(?:,\s*\d+)*)\]")
    n_cit = 0
    for p in pars[:i_ref]:
        while True:
            t = next((t for t in p.iter(W + "t") if fora_de_marca(t) and t.text and alvo.search(t.text)), None)
            if t is None:
                break
            m = alvo.search(t.text)
            ini, fim = m.span()
            if ini > 0 and t.text[ini - 1] == " ":
                pass
            trocar_no_t(t, ini, fim, citacao(m.group(1)))
            n_cit += 1
    print("citações convertidas:", n_cit)

    # 2) trocas e inserções de texto
    for velho, novo in TEXTO:
        substituir(corpo, velho, novo)
    for anc, novo in INSERCOES:
        inserir_depois(corpo, anc, novo)

    # 3) Tabela 6
    tab6 = next(tb for tb in corpo.iter(W + "tbl")
                if [txt(c).strip() for c in tb.find(W + "tr").findall(W + "tc")][:3] == ["Atraso extra", "Política", "Freio"])
    linhas = tab6.findall(W + "tr")
    for (li, co), novo in TAB6.items():
        cel = linhas[li].findall(W + "tc")[co]
        t = next(t for t in cel.iter(W + "t") if fora_de_marca(t))
        trocar_no_t(t, 0, len(t.text), novo)

    # 4) título REFERÊNCIAS em Times New Roman (alteração de formatação registrada)
    for r in titulo_ref.findall(W + "r"):
        rpr = r.find(W + "rPr")
        if rpr is None:
            rpr = el("rPr")
            r.insert(0, rpr)
        antigo = deepcopy(rpr)
        f = el("rFonts", ascii="Times New Roman", hAnsi="Times New Roman", cs="Times New Roman")
        rpr.insert(0, f)
        ch = marca("rPrChange")
        ch.append(antigo)
        rpr.append(ch)

    # 5) referências: apaga as 29 numeradas e insere as 26 em autor-data (sem AUTOSAR, Davis e Koopman,
    #    que não eram citadas no texto)
    modelo_ppr = antigas[0].find(W + "pPr")
    rpr_base = deepcopy(antigas[0].findall(W + "r")[-1].find(W + "rPr"))
    for p in antigas:
        apagar_paragrafo(p)
    ultimo = antigas[-1]
    for ref in REFS:
        novo = paragrafo_inserido(modelo_ppr, segmentos(ref), rpr_base)
        ultimo.addnext(novo)
        ultimo = novo

    # 6) parágrafos vazios entre tabelas e títulos (apagados como alteração controlada) para caber em 8 páginas
    vazios = 0
    for p in list(corpo.findall(W + "p")):
        if (not txt(p).strip() and not p.findall(".//" + W + "drawing") and p.find(".//" + W + "sectPr") is None
                and not p.findall(".//" + W + "ins") and not p.findall(".//" + W + "del")):
            marcar_pmark(p, "del")
            vazios += 1
    print("parágrafos vazios apagados:", vazios)

    # 7) referências novas alinhadas à esquerda (justificado abria lacunas entre palavras e DOIs)
    for p in corpo.findall(W + "p"):
        ppr = p.find(W + "pPr")
        if ppr is not None and ppr.find(W + "rPr/" + W + "ins") is not None:
            jc = ppr.find(W + "jc")
            if jc is not None:
                jc.set(W + "val", "left")

    # 8) Tabela 6 na largura útil da página (15,5 cm = 8787 dxa), para os rótulos novos não quebrarem
    larg = [1020, 1250, 1560, 2007, 1830, 1120]
    grade = tab6.find(W + "tblGrid")
    for gc, w_ in zip(grade.findall(W + "gridCol"), larg):
        gc.set(W + "w", str(w_))
    tblw = tab6.find(W + "tblPr/" + W + "tblW")
    if tblw is not None:
        tblw.set(W + "w", str(sum(larg)))
        tblw.set(W + "type", "dxa")
    for tr in tab6.findall(W + "tr"):
        for tc, w_ in zip(tr.findall(W + "tc"), larg):
            tcw = tc.find(W + "tcPr/" + W + "tcW")
            if tcw is not None:
                tcw.set(W + "w", str(w_))

    # 9) Figuras 1 e 2 a 90 % e Figura 3 a 88 % do tamanho (formatação), para a Figura 3 caber na página 5
    A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
    R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    for dr in corpo.iter(W + "drawing"):
        blip = next(dr.iter(A + "blip"), None)
        fator = {"rId8": 0.9, "rId9": 0.9, "rId10": 0.88}.get(blip.get(R + "embed")) if blip is not None else None
        if fator is None:
            continue
        for ext in list(dr.iter(WP + "extent")) + list(dr.iter(A + "ext")):
            for k in ("cx", "cy"):
                if ext.get(k):
                    ext.set(k, str(int(int(ext.get(k)) * fator)))

    arv.write(str(doc), xml_declaration=True, encoding="UTF-8", standalone=True)
    print("ok", doc)


if __name__ == "__main__":
    main(sys.argv[1])
