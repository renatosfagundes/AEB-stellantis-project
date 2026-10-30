"""Renderiza um .mmd em PNG com Playwright + Mermaid (CDN).
Uso: py -3.12 render_mermaid.py entrada.mmd saida.png [TB|LR]
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
direcao = sys.argv[3] if len(sys.argv) > 3 else None
codigo = src.read_text(encoding="utf-8")
if direcao:
    codigo = "\n".join(("    direction " + direcao) if l.strip().startswith("direction ") else l for l in codigo.splitlines())

html = f"""<!doctype html><html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script>
<style>body{{margin:0;background:#fff;font-family:'Segoe UI',Arial,sans-serif}}</style></head>
<body><div id="alvo"></div>
<script>
const codigo = {json.dumps(codigo)};
window.pronto = false;
(async () => {{
  try {{
    mermaid.initialize({{startOnLoad:false, theme:'neutral', themeVariables:{{fontFamily:'Segoe UI, Arial, sans-serif', fontSize:'13px'}}}});
    const {{svg}} = await mermaid.render('fig', codigo);
    document.getElementById('alvo').innerHTML = svg;
    window.erro = null;
  }} catch (e) {{ window.erro = String(e); }}
  window.pronto = true;
}})();
</script></body></html>"""
tmp = dst.with_suffix(".html")
tmp.write_text(html, encoding="utf-8")

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(device_scale_factor=2.5, viewport={"width": 1800, "height": 1200})
    msgs = []
    pg.on("console", lambda m: msgs.append(m.text))
    pg.goto(tmp.resolve().as_uri())
    pg.wait_for_function("window.pronto === true", timeout=60000)
    erro = pg.evaluate("window.erro")
    if erro:
        print("ERRO:", erro, msgs[:5])
        sys.exit(1)
    el = pg.query_selector("#alvo svg")
    box = el.bounding_box()
    pg.set_viewport_size({"width": int(box["width"]) + 40, "height": int(box["height"]) + 40})
    el.screenshot(path=str(dst))
    print(dst, int(box["width"]), "x", int(box["height"]))
    b.close()
tmp.unlink()
