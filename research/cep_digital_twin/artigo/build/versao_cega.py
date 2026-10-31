"""Gera a versão cega para submissão a partir de artigo_v62.md (já montado e renumerado).

Remove autores e afiliação, troca a autorreferência "do grupo" e apaga o autor dos metadados do docx.
Uso (na pasta artigo): py -3.12 build/versao_cega.py  -> artigo_cego.md e Artigo_AEB_V6.3_cego.docx
"""
import subprocess
import sys
from pathlib import Path

from docx import Document

ART = Path(__file__).resolve().parent.parent
src = (ART / "artigo_v62.md").read_text(encoding="utf-8")
pares = [
    ("Renato Silva Fagundes · Ane Varoto · Leopoldo Yoshioka · Reginaldo Arakaki", "Autores omitidos para avaliação cega"),
    ("*Escola Politécnica da Universidade de São Paulo*", "*Afiliação omitida*"),
    ("em um experimento anterior do grupo com", "em um experimento anterior com"),
]
for a, b in pares:
    assert a in src, a
    src = src.replace(a, b)
for proibido in ("Fagundes", "Varoto", "Yoshioka", "Arakaki", "Politécnica", "github", "do grupo"):
    assert proibido.lower() not in src.lower(), proibido
(ART / "artigo_cego.md").write_text(src, encoding="utf-8", newline="")
dst = "Artigo_AEB_V6.3_cego.docx"
subprocess.run([sys.executable, str(ART / "build" / "gerar_rascunho.py"), "artigo_cego.md", dst], check=True, cwd=ART)
doc = Document(ART / dst)
cp = doc.core_properties
cp.author = ""
cp.last_modified_by = ""
cp.title = ""
doc.save(ART / dst)
print("ok", dst)
