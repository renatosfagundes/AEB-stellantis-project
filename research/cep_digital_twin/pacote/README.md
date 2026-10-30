# Artigo: Gêmeo digital borda-nuvem para a governança de sistemas AEB

Autores: Renato Silva Fagundes, Ane Varoto, Reginaldo Arakaki (PCS5039, Poli-USP).

## O que há em cada pasta

| Pasta | Conteúdo |
|---|---|
| `01_artigo` | Artigo em Word e PDF (versão completa, 13 páginas; limite da disciplina: 8) e o gerador (`gerar_artigo.js`, roda com `node` e a biblioteca `docx`) |
| `02_diagramas` | Diagrama de classes em Mermaid (completo e reduzido), as imagens renderizadas, as figuras de arquitetura (contexto, implantação borda-nuvem) e do simulador (blocos, linha do tempo), e o editor de diagramas (`editor_classes.html`: abrir no navegador, arrastar blocos, exportar PNG) |
| `03_experimento` | Plano experimental (hipóteses, fatores, métricas, ameaças à validade), código da simulação (`simulacao_cep.py`, `experimento.py`), scripts das figuras e a pasta `resultados` com os CSV das 360 rodadas, o resumo em tabelas e as figuras de resultado |
| `04_referencias` | Lista de referências do artigo e candidatas a acrescentar |
| `05_dinamica` | Tabela de cenários da Dinâmica 1, não-riscos, divisão local × nuvem e pontos levados ao professor |
| `06_propostas_anteriores` | Propostas de artigo de outubro (CEP, eventos atrasados e fora de ordem, bancada SIL) |
| `07_complemento_h1a_h1b` | Complemento pedido em 29/10: H1a (atraso isolado) e H1b (desordenação isolada) na cadeia de decisão do AEB com desfecho físico; texto pronto para a V3 (`Complemento_H1a_H1b.docx`), código (`experimento_h1.py`, `verificar_reproducao.py`), CSV, resumo e figuras |

## Como reproduzir o experimento

```
py -3.12 experimento.py            # 20 sementes, 360 rodadas, ~2 min; gera resultados/
py -3.12 experimento.py --rapido   # 3 sementes, para testar
py -3.12 figuras_arquitetura.py    # figuras 1 e 3 do artigo
py -3.12 figuras_simulador.py      # figuras 4 e 5 (precisa de experimento.py ao lado)
py -3.12 render_mermaid.py diagrama_classes_slide.mmd fig_classes.png TB   # precisa de Playwright
```

Requisitos: Python 3.12 com matplotlib; Playwright só para renderizar o Mermaid.

## Resultados em uma linha

Borda decide os cenários reativos em 5 a 15 ms em qualquer rede (nuvem: 80 ms a 1,5 s p95); sob 90 s
sem rede mantém 100 % de detecção e 100 % de trilhas completas (nuvem: 71 % e 95 %); envia 9,7× menos
dados; detecção de degradação lenta com ~1 s de atraso em relação ao processamento dos brutos.
