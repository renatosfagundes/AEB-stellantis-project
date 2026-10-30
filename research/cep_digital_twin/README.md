# Gêmeo digital borda-nuvem e eventos atrasados / fora de ordem em sistemas AEB

Código, dados e figuras dos experimentos do artigo *Impacto de eventos atrasados e fora de ordem na
segurança de sistemas AEB* (Renato Silva Fagundes, Ane Varoto, Reginaldo Arakaki; PCS5039, Poli-USP).
Tudo é determinístico: duas execuções produzem os mesmos CSV, tabelas e figuras.

## Experimentos

| Script | O que faz | Saída |
|---|---|---|
| `simulacao_cep.py` | Domínio: eventos, 7 regras CEP, gêmeo digital, gestão; demo de 120 s | terminal |
| `experimento.py` | Plano fatorial A0 (só nuvem) × A1 (local + nuvem) × 3 redes × 3 janelas offline × 20 sementes = 360 rodadas; hipóteses H1–H4 do artigo | `resultados/` |
| `experimento_h1.py` | Complemento H1a (atraso isolado, 0–1000 ms) e H1b (desordenação isolada, 0–20 %, duas distâncias, três estratégias de ordenação) na cadeia de decisão do AEB com desfecho físico (CCRs, 40 e 50 km/h, 30 sementes) | `resultados_h1/` |
| `verificar_reproducao.py` | Reexecuta, confere determinismo e as afirmações centrais; `--completo` compara com os CSV publicados | código de saída |
| `figuras_arquitetura.py`, `figuras_simulador.py` | Figuras de arquitetura (contexto, implantação) e do simulador (blocos, linha do tempo) | `resultados/fig_*.png` |
| `render_mermaid.py` | Renderiza os `.mmd` em PNG (Playwright + Mermaid) | PNG |

A ECU simulada em `experimento_h1.py` usa a calibração do firmware do projeto
[AEB-stellantis-project](https://github.com/erycaaf/AEB-stellantis-project) (TTC 4,0/3,0/2,2/1,8 s,
pisos 20/10/5 m, decel 2/4/6 m/s², WARNING 0,8 s, histerese 0,2 s, Kalman e detector ROC) e é
confrontada com as distâncias de parada medidas na bancada SIL (`resultados_h1/resumo_h1.md`).

## Reproduzir

```
py -3.12 -m pip install -r requirements.txt
py -3.12 experimento.py          # ~2 min
py -3.12 experimento_h1.py       # ~5 min
py -3.12 verificar_reproducao.py # ~1 min; --completo para conferir os CSV publicados
```

Parâmetros: `CFG`, `REDES`, `OFFLINE` em `experimento.py`; limiares `P` em `simulacao_cep.py`;
`CFG`, `ATRASOS_MS`, `LAT_MEDIA_H1B` e a calibração da ECU em `experimento_h1.py`.

## Conteúdo

- `plano_experimental.md`: hipóteses, fatores, métricas operacionais, ameaças à validade.
- `resultados/`: `por_cenario.csv`, `por_rodada.csv`, `resumo.md`, figuras.
- `resultados_h1/`: `h1a.csv`, `h1b.csv`, `resumo_h1.md`, figuras.
- `diagrama_classes.mmd`, `diagrama_classes_slide.mmd`: modelo de classes (Mermaid); `editor_classes.html`: editor
  para arrastar blocos e exportar PNG.
- `artigo/`: geradores do Word (`gerar_artigo.js`, `gerar_complemento.js`; `npm install docx`).
