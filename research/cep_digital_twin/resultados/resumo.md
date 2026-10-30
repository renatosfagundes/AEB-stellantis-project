# Resumo do experimento (20 sementes por célula, 240 s por rodada)

## H1 (RQ1): latência de decisão nos cenários reativos, sem janela offline

| Cenário | Rede | Arquitetura | Detecção | Decisão média (ms) | Decisão p95 (ms) | Até a Gestão p95 (ms) |
|---|---|---|---|---|---|---|
| Frenagem tardia (atraso de mensagem) | boa | A0_nuvem | 100% | 80 | 80 | 80 |
| Frenagem tardia (atraso de mensagem) | boa | A1_local+nuvem | 100% | 5 | 5 | 70 |
| Frenagem tardia (atraso de mensagem) | media | A0_nuvem | 100% | 313 | 1083 | 1083 |
| Frenagem tardia (atraso de mensagem) | media | A1_local+nuvem | 100% | 5 | 5 | 1123 |
| Frenagem tardia (atraso de mensagem) | ruim | A0_nuvem | 100% | 957 | 2343 | 2343 |
| Frenagem tardia (atraso de mensagem) | ruim | A1_local+nuvem | 100% | 5 | 5 | 1535 |
| Frenagem fantasma | boa | A0_nuvem | 100% | 90 | 90 | 90 |
| Frenagem fantasma | boa | A1_local+nuvem | 100% | 15 | 15 | 91 |
| Frenagem fantasma | media | A0_nuvem | 100% | 280 | 280 | 280 |
| Frenagem fantasma | media | A1_local+nuvem | 100% | 15 | 15 | 226 |
| Frenagem fantasma | ruim | A0_nuvem | 100% | 880 | 2296 | 2296 |
| Frenagem fantasma | ruim | A1_local+nuvem | 100% | 15 | 15 | 2480 |
| Ataque cibernético | boa | A0_nuvem | 100% | 280 | 280 | 280 |
| Ataque cibernético | boa | A1_local+nuvem | 100% | 205 | 205 | 273 |
| Ataque cibernético | media | A0_nuvem | 100% | 475 | 520 | 520 |
| Ataque cibernético | media | A1_local+nuvem | 100% | 205 | 205 | 438 |
| Ataque cibernético | ruim | A0_nuvem | 100% | 987 | 1105 | 1105 |
| Ataque cibernético | ruim | A1_local+nuvem | 100% | 205 | 205 | 1632 |


## H2 (RG1): taxa de detecção das falhas de risco por janela offline (rede media)

| Cenário | Offline | A0_nuvem | A1_local+nuvem |
|---|---|---|---|
| Frenagem tardia (atraso de mensagem) | nenhum | 100% | 100% |
| Frenagem tardia (atraso de mensagem) | curto | 100% (na janela: 100%, n=5) | 100% (na janela: 100%, n=5) |
| Frenagem tardia (atraso de mensagem) | longo | 65% (na janela: 30%, n=10) | 100% (na janela: 100%, n=10) |
| Frenagem fantasma | nenhum | 100% | 100% |
| Frenagem fantasma | curto | 95% (na janela: 0%, n=1) | 100% (na janela: 100%, n=1) |
| Frenagem fantasma | longo | 60% (na janela: 0%, n=8) | 100% (na janela: 100%, n=8) |
| Ataque cibernético | nenhum | 100% | 100% |
| Ataque cibernético | curto | 90% (na janela: 60%, n=5) | 100% (na janela: 100%, n=5) |
| Ataque cibernético | longo | 75% (na janela: 44%, n=9) | 100% (na janela: 100%, n=9) |
| Degradação do barramento | nenhum | 100% | 100% |
| Degradação do barramento | curto | 100% (na janela: 100%, n=3) | 100% (na janela: 100%, n=3) |
| Degradação do barramento | longo | 70% (na janela: 40%, n=10) | 100% (na janela: 100%, n=10) |
| Degradação do sensor | nenhum | 100% | 100% |
| Degradação do sensor | curto | 100% (na janela: 100%, n=3) | 100% (na janela: 100%, n=3) |
| Degradação do sensor | longo | 70% (na janela: 73%, n=11) | 100% (na janela: 100%, n=11) |


## H3 (RG2): completude da trilha e tempo até a evidência (rede media, cenários decididos na borda)

| Offline | Arquitetura | Completude média | Decisões com trilha completa | Evidência média (s) | Evidência p95 (s) |
|---|---|---|---|---|---|
| nenhum | A0_nuvem | 100.0% | 99% | 4.3 | 6.4 |
| nenhum | A1_local+nuvem | 100.0% | 100% | 3.8 | 5.9 |
| curto | A0_nuvem | 100.0% | 100% | 6.4 | 24.5 |
| curto | A1_local+nuvem | 100.0% | 100% | 5.9 | 22.4 |
| longo | A0_nuvem | 98.2% | 94% | 6.0 | 19.4 |
| longo | A1_local+nuvem | 100.0% | 100% | 22.5 | 77.1 |


## H4: volume enviado à nuvem, descartes, falsos positivos e cobertura de KPI

| Rede | Offline | Arquitetura | KB/rodada | msgs/rodada | descartes buffer | falsos positivos | KPI entregues |
|---|---|---|---|---|---|---|---|
| boa | nenhum | A0_nuvem | 917 | 14674 | 0 | 0.10 | 100% |
| boa | nenhum | A1_local+nuvem | 95 | 256 | 0 | 0.10 | 100% |
| boa | curto | A0_nuvem | 917 | 14674 | 0 | 0.55 | 100% |
| boa | curto | A1_local+nuvem | 95 | 256 | 0 | 0.10 | 100% |
| boa | longo | A0_nuvem | 917 | 14674 | 3460 | 0.90 | 100% |
| boa | longo | A1_local+nuvem | 95 | 256 | 0 | 0.10 | 100% |
| media | nenhum | A0_nuvem | 917 | 14674 | 0 | 0.10 | 100% |
| media | nenhum | A1_local+nuvem | 95 | 256 | 0 | 0.10 | 100% |
| media | curto | A0_nuvem | 917 | 14674 | 0 | 0.65 | 100% |
| media | curto | A1_local+nuvem | 95 | 256 | 0 | 0.10 | 100% |
| media | longo | A0_nuvem | 917 | 14674 | 3459 | 0.75 | 100% |
| media | longo | A1_local+nuvem | 95 | 256 | 0 | 0.25 | 100% |
| ruim | nenhum | A0_nuvem | 917 | 14674 | 0 | 0.10 | 100% |
| ruim | nenhum | A1_local+nuvem | 95 | 256 | 0 | 0.10 | 100% |
| ruim | curto | A0_nuvem | 917 | 14674 | 0 | 0.45 | 100% |
| ruim | curto | A1_local+nuvem | 95 | 256 | 0 | 0.15 | 100% |
| ruim | longo | A0_nuvem | 917 | 14674 | 3458 | 0.60 | 100% |
| ruim | longo | A1_local+nuvem | 95 | 256 | 0 | 0.35 | 100% |


## Cenário de janela longa (Degradação do sensor): latência de detecção por arquitetura

| Rede | Offline | A0_nuvem | A1_local+nuvem |
|---|---|---|---|
| boa | nenhum | 100% / 16.6 s | 100% / 17.6 s |
| boa | curto | 100% / 17.0 s | 100% / 17.9 s |
| boa | longo | 70% / 26.7 s | 100% / 47.1 s |
| media | nenhum | 100% / 16.7 s | 100% / 17.7 s |
| media | curto | 100% / 21.6 s | 100% / 22.0 s |
| media | longo | 70% / 26.9 s | 100% / 45.9 s |
| ruim | nenhum | 100% / 17.4 s | 100% / 18.1 s |
| ruim | curto | 100% / 22.8 s | 100% / 23.0 s |
| ruim | longo | 75% / 26.3 s | 100% / 39.9 s |
