"""Aceita alterações controladas de um diretório .docx desempacotado (document.xml), no lugar.

Cobre o que v8_revisao.py produz: <w:ins> (desembrulha), <w:del> (remove), parágrafos com marca de
parágrafo apagada e sem texto restante (remove), marcas <w:ins>/<w:del> em pPr/rPr e <w:rPrChange>.
Uso: py -3.12 aceitar_alteracoes.py <dir_desempacotado>
"""
import sys
from pathlib import Path

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def main(d):
    doc = Path(d) / "word" / "document.xml"
    arv = etree.parse(str(doc))
    raiz = arv.getroot()
    # parágrafos inteiros apagados
    for p in list(raiz.iter(W + "p")):
        rpr = p.find(W + "pPr/" + W + "rPr")
        if rpr is not None and rpr.find(W + "del") is not None:
            for d_ in list(p.iter(W + "del")):
                if d_.getparent() is not rpr:
                    d_.getparent().remove(d_)
            if not "".join(t.text or "" for t in p.iter(W + "t")).strip() and not p.findall(".//" + W + "drawing"):
                p.getparent().remove(p)
            else:
                rpr.remove(rpr.find(W + "del"))
    for d_ in list(raiz.iter(W + "del")):
        d_.getparent().remove(d_)
    for i in list(raiz.iter(W + "ins")):
        pai = i.getparent()
        if pai.tag == W + "rPr":
            pai.remove(i)
            continue
        pos = pai.index(i)
        for k, c in enumerate(list(i)):
            pai.insert(pos + k, c)
        pai.remove(i)
    for c in list(raiz.iter(W + "rPrChange")):
        c.getparent().remove(c)
    arv.write(str(doc), xml_declaration=True, encoding="UTF-8", standalone=True)
    print("ok", doc)


if __name__ == "__main__":
    main(sys.argv[1])
