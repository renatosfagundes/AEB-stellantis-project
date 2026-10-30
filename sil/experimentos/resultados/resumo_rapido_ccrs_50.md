# SIL, plano reduzido (ccrs_50): 43 rodadas válidas de 45

Válida = percepção sem trava > 100 ms nos 3 s antes do TTC crítico (entrada do relé).

## H1a: atraso isolado

| Atraso (ms) | n | TTC crítico → freio (ms) | σ | > 100 ms | Dist. parada (m) | Colisões | v impacto (km/h) | ECU OFF |
|---|---|---|---|---|---|---|---|---|
| 0 | 5 | 293 | 264 | 60% | 3.28 | 0/5 | - | 1/5 |
| 100 | 5 | 166 | 67 | 100% | 4.42 | 0/5 | - | 0/5 |
| 200 | 5 | 386 | 347 | 100% | 5.20 | 1/5 | 9.7 | 1/5 |
| 400 | 5 | 425 | 10 | 100% | 4.18 | 0/5 | - | 0/5 |
| 600 | 5 | 624 | 21 | 100% | 2.26 | 0/5 | - | 0/5 |
| 800 | 5 | 834 | 13 | 100% | 0.36 | 0/5 | - | 3/5 |


## H1b: 20 % fora de ordem (+200 a 600 ms), latência média 100 ms

| Política | n | TTC crítico → freio (ms) | Descartados | Lacunas > 60 ms à ECU | ECU OFF | Dist. parada (m) | Colisões | v impacto (km/h) |
|---|---|---|---|---|---|---|---|---|
| arrival | 4 | 1486 | 0.0 | 5.5 | 3/4 | 1.10 | 2/4 | 10.6 |
| watermark | 4 | 2057 | 102.0 | 10.0 | 4/4 | - | 4/4 | 10.7 |
| kslack | 5 | 694 | 0.4 | 0.2 | 0/5 | 2.14 | 0/5 | - |
