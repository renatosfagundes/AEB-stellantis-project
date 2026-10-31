"""Monta a V8 a partir da V7 da Ane: versão com alterações controladas e versão limpa (aceita).

Passos: desempacota a V7, junta runs fragmentados (merge_runs da skill docx), aplica v8_revisao.py,
troca as Figuras 2 a 4 pelas versões em escala de cinza (mesmas dimensões), limpa o campo
"modificado por" dos metadados, empacota; copia, aceita as alterações e empacota a versão limpa.
Uso: py -3.12 montar_v8.py <v7.docx> <pasta_trabalho> <skill_docx_dir>
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
FIG = AQUI.parent.parent / "resultados_tikz"


def empacotar(src, dst):
    arqs = sorted(p for p in src.rglob("*") if p.is_file())
    arqs.sort(key=lambda p: (p.name != "[Content_Types].xml", str(p)))
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for p in arqs:
            z.write(p, p.relative_to(src).as_posix())


def main(v7, trab, skill):
    v7, trab, skill = Path(v7), Path(trab), Path(skill)
    if trab.exists():
        shutil.rmtree(trab)
    un = trab / "un"
    un.mkdir(parents=True)
    with zipfile.ZipFile(v7) as z:
        z.extractall(un)
    subprocess.run([sys.executable, str(skill / "scripts" / "merge_runs.py"), str(un)], check=True)
    subprocess.run([sys.executable, str(AQUI / "v8_revisao.py"), str(un)], check=True)
    for n, f in ((2, "fig_fsm_cinza.png"), (3, "fig_h1a_cinza.png"), (4, "fig_h1b_cinza.png")):
        shutil.copy(FIG / f, un / "word" / "media" / f"image{n}.png")
    core = un / "docProps" / "core.xml"
    s = core.read_text(encoding="utf-8")
    i, j = s.find("<cp:lastModifiedBy>"), s.find("</cp:lastModifiedBy>")
    if i >= 0:
        s = s[:i] + "<cp:lastModifiedBy>" + s[j:]
    core.write_text(s, encoding="utf-8")
    empacotar(un, trab / "v8_controlado.docx")
    limpo = trab / "limpo"
    shutil.copytree(un, limpo)
    subprocess.run([sys.executable, str(AQUI / "aceitar_alteracoes.py"), str(limpo)], check=True)
    empacotar(limpo, trab / "v8_limpo.docx")
    print("ok", trab)


if __name__ == "__main__":
    main(*sys.argv[1:4])
