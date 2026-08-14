# Otimização de Rotas de Entrega no Espírito Santo: Modelagem em Grafos, Heurísticas de TSP/VRP e Aplicação Web Interativa

**Trabalho acadêmico — Otimização de Rotas de Entrega usando Grafos**
**Estudo de caso: transportadora fictícia sediada na Grande Vitória (ES)**

---

## Resumo

Este trabalho modela o problema de planejamento semanal de entregas de uma
transportadora fictícia sediada na Grande Vitória/ES como um problema de
roteamento em grafos — o clássico Problema do Caixeiro Viajante (*Traveling
Salesman Problem*, TSP) e sua extensão para múltiplos veículos, o Problema
de Roteamento de Veículos (*Vehicle Routing Problem*, VRP). Os 78 municípios
do Espírito Santo foram obtidos de fontes públicas (IBGE), dos quais um
subconjunto de 25 (1 Centro de Distribuição + 24 destinos de entrega) foi
selecionado por relevância populacional/logística. As distâncias e tempos
reais de deslocamento rodoviário — e a geometria das rotas — foram obtidas
via API pública do OSRM (*Open Source Routing Machine*). O grafo foi
construído em Python com NetworkX; o TSP foi resolvido por uma heurística
construtiva (vizinho mais próximo) seguida de refinamento por busca local
(2-opt); o VRP foi resolvido por uma heurística de particionamento
geográfico (varredura angular) seguida da mesma heurística de TSP em cada
sub-rota. Os resultados mostram uma redução de tempo total de operação de
até **65,9%** apenas com a otimização de rota de um único veículo em
relação a uma rota sem otimização, e ganhos adicionais de até **63,3%** no
tempo de conclusão da operação (*makespan*) ao distribuir as entregas entre
uma frota de veículos (economia total de até **87,5%** em relação à rota
ingênua, com 12 veículos). O número de veículos é **livremente
customizável** na aplicação web — o algoritmo de VRP roda ao vivo no
próprio navegador — e o sistema **sinaliza automaticamente** tanto quando a
frota configurada excede o número de municípios de entrega (veículos
ociosos, sem rota atribuída) quanto quando um veículo adicional deixa de
reduzir o tempo total da operação (retorno decrescente). Uma aplicação web
interativa, com mapa real, animação da frota conforme horários de saída
configuráveis e painéis de gestão/resumo, foi desenvolvida como principal
entregável do projeto.

---

## Sumário

1. [Introdução e contexto do problema](#1-introdução-e-contexto-do-problema)
2. [Modelagem do problema como grafo](#2-modelagem-do-problema-como-grafo)
3. [Metodologia de obtenção de dados](#3-metodologia-de-obtenção-de-dados)
4. [Algoritmo de TSP (veículo único)](#4-algoritmo-de-tsp-veículo-único)
5. [Extensão para VRP (frota de veículos)](#5-extensão-para-vrp-frota-de-veículos)
6. [Arquitetura da aplicação web](#6-arquitetura-da-aplicação-web)
7. [Resultados obtidos](#7-resultados-obtidos)
8. [Limitações do estudo](#8-limitações-do-estudo)
9. [Conclusão](#9-conclusão)
10. [Referências](#10-referências)
11. [Apêndice A — Código-fonte comentado (backend)](#apêndice-a--código-fonte-comentado-backend)
12. [Apêndice B — Código-fonte comentado (frontend)](#apêndice-b--código-fonte-comentado-frontend)

---

## 1. Introdução e contexto do problema

Considera-se uma transportadora fictícia sediada na Grande Vitória (região
metropolitana composta por Vitória, Vila Velha, Serra, Cariacica e Viana)
que precisa realizar entregas semanais em municípios do Espírito Santo,
partindo de um Centro de Distribuição (CD) e retornando a ele ao final da
operação. O objetivo operacional é **minimizar o tempo total gasto na
operação de entregas**, respeitando a necessidade de visitar todos os
municípios-destino exatamente uma vez.

Formalmente, este é o Problema do Caixeiro Viajante (TSP) quando um único
veículo realiza todas as entregas, e sua generalização, o Problema de
Roteamento de Veículos (VRP), quando uma frota de veículos divide as
entregas entre si. Ambos os problemas são classificados como **NP-difíceis**
— não existe algoritmo conhecido capaz de garantir a solução ótima exata em
tempo polinomial para instâncias de tamanho realista — o que justifica o
uso de **heurísticas**, que produzem soluções de boa qualidade (ainda que
não necessariamente ótimas) em tempo computacional viável. Essa é a
abordagem adotada neste trabalho.

Como decisão de escopo, o Centro de Distribuição foi fixado no município de
**Serra/ES**: além de ser o município mais populoso do estado, é um polo
logístico-industrial real da Grande Vitória (nele se localizam o Porto de
Tubarão e o complexo industrial de Portocel, entre outros), o que faz dele
uma escolha coerente para a sede fictícia de uma transportadora regional.

---

## 2. Modelagem do problema como grafo

O problema é modelado como um **grafo completo direcionado** `G = (V, A)`:

- **Vértices (V):** cada município selecionado (1 Centro de Distribuição +
  24 municípios de entrega), num total de 25 nós. Cada nó carrega como
  atributo o nome do município e suas coordenadas geográficas
  (latitude/longitude).
- **Arestas (A):** para cada par ordenado de municípios `(i, j)`, existe uma
  aresta `i → j` com dois atributos de peso:
  - `dist_km`: distância rodoviária real entre `i` e `j`;
  - `tempo_min`: tempo de deslocamento rodoviário real entre `i` e `j`.

O grafo é **direcionado** (implementado como `networkx.DiGraph`) e não
necessariamente simétrico, pois vias de mão única, relevo, pedágios e
restrições de tráfego podem tornar o custo de `i → j` diferente do custo de
`j → i` no mundo real — o OSRM retorna, de fato, valores levemente
assimétricos para diversos pares.

O grafo é **completo** (`K25`, 600 arestas direcionadas) porque, para fins
de roteamento, assume-se que existe sempre um caminho rodoviário viável
entre quaisquer dois municípios — o peso da aresta é o custo do **menor
caminho rodoviário real** entre eles (já calculado pelo motor de roteamento
OSRM sobre a malha viária completa), e não uma conexão direta artificial.

O problema de otimização consiste em encontrar, sobre esse grafo:

- **(TSP)** um ciclo Hamiltoniano de custo mínimo que parte do CD, visita
  todos os 24 municípios de entrega exatamente uma vez, e retorna ao CD;
- **(VRP)** uma partição dos 24 municípios de entrega em `k` subconjuntos
  (um por veículo) e, para cada subconjunto, um ciclo Hamiltoniano
  CD → ... → CD de custo mínimo, de forma a minimizar o tempo total da
  operação.

O critério de custo minimizado é o **tempo de deslocamento** (`tempo_min`),
por ser o mais relevante operacionalmente (jornada de trabalho, janelas de
entrega); a distância também é computada e reportada para fins de análise
de custo de combustível/quilometragem.

---

## 3. Metodologia de obtenção de dados

### 3.1 Municípios e critério de seleção

A lista completa dos 78 municípios do Espírito Santo foi obtida a partir de
um dataset público derivado do IBGE (coordenadas geográficas de centróide
municipal) combinado com a **população residente estimada 2021**, obtida
diretamente da API de agregados do IBGE (agregado 6579, variável 9324 —
"População residente estimada").

Como 78 municípios tornariam o TSP/VRP visualmente poluído no mapa e
computacionalmente mais custoso para fins didáticos (sem alterar a
conclusão qualitativa do estudo), foi selecionado um subconjunto de **25
municípios**, dentro da faixa de 20 a 30 sugerida:

- O **Centro de Distribuição** foi fixado em **Serra** (justificativa na
  seção 1).
- Os demais **24 municípios de entrega** são os 24 municípios mais
  populosos do estado, excluído o próprio CD. A população foi usada como
  proxy de relevância econômica e logística: municípios mais populosos
  concentram maior comércio, indústria e demanda por transporte de
  mercadorias, sendo destinos mais prováveis para entregas semanais de uma
  transportadora regional.

Esse critério, embora simples e objetivo (evitando escolhas manuais
arbitrárias), produziu uma **boa dispersão geográfica** entre as
macrorregiões do estado, verificada a posteriori:

| Macrorregião       | Municípios selecionados |
|---------------------|:---:|
| Metropolitana        | 6 |
| Norte                | 6 |
| Noroeste             | 5 |
| Central Serrana      | 3 |
| Sul                  | 5 |

Os 24 municípios de entrega selecionados foram: Vila Velha, Cariacica,
Vitória, Cachoeiro de Itapemirim, Linhares, São Mateus, Guarapari, Colatina,
Aracruz, Viana, Nova Venécia, Barra de São Francisco, Santa Maria de
Jetibá, Marataízes, São Gabriel da Palha, Castelo, Itapemirim, Domingos
Martins, Jaguaré, Conceição da Barra, Guaçuí, Sooretama, Baixo Guandu e
Afonso Cláudio.

O código de seleção (`backend/selecao_municipios.py`) e o dataset completo
dos 78 municípios (`backend/data/municipios_es_78.json`) são mantidos no
repositório para transparência e reprodutibilidade do critério.

### 3.2 Distâncias, tempos e geometria de rota reais

Para obter distâncias e tempos **reais de estrada** (não linha reta), foi
utilizada a API pública e gratuita do **OSRM** (Open Source Routing
Machine), instância de demonstração `router.project-osrm.org`, por meio de
dois serviços:

- **`/table`**: calcula, em uma única requisição, a matriz completa `25×25`
  de distância e duração entre todos os pares de municípios selecionados.
  É o serviço mais eficiente para alimentar os algoritmos de otimização,
  pois evita 600 requisições individuais.
- **`/route`**: para cada trecho **efetivamente utilizado** em alguma rota
  final (TSP ou VRP, para diferentes tamanhos de frota), retorna a
  geometria completa (sequência de coordenadas seguindo o traçado real da
  rodovia), usada para desenhar a rota real no mapa interativo e para
  animar o deslocamento dos veículos.

Como a geometria bruta retornada pelo OSRM pode conter milhares de pontos
por trecho (grau de detalhe desnecessário para visualização em escala
estadual), aplicou-se uma simplificação de **Ramer–Douglas–Peucker** com
tolerância de ~90 m, reduzindo o volume de dados em mais de 95% sem perda
perceptível de fidelidade visual no mapa.

Todas as respostas do OSRM são **cacheadas em disco** (`backend/cache/`),
tornando as execuções subsequentes determinísticas e independentes da
disponibilidade da rede.

**Limitação assumida:** a instância pública do OSRM é um serviço de
demonstração, sem SLA formal e sem uso de chave de API. Caso a rede esteja
indisponível ou o serviço retorne erro, o módulo `backend/routing.py`
recorre automaticamente a uma **aproximação por distância Haversine**
(linha reta entre coordenadas), corrigida por um fator empírico de
sinuosidade rodoviária (1,30), e a fonte de cada dado (`osrm_table`,
`osrm_route` ou `haversine_fallback`) é registrada nos metadados de saída
(`solution.json`) para rastreabilidade. Em todas as execuções realizadas
para este trabalho, a API do OSRM esteve disponível e os dados reportados
refletem roteamento real.

### 3.3 Ferramentas

- **Python 3** com **NetworkX** para representação e manipulação do grafo;
- **requests** para consumo da API OSRM;
- Nenhuma dependência de otimização de terceiros (PuLP, OR-Tools etc.) foi
  utilizada — as heurísticas de TSP/VRP foram implementadas do zero, por
  ser um requisito didático do trabalho.

---

## 4. Algoritmo de TSP (veículo único)

A solução de veículo único é obtida em duas etapas (`backend/tsp.py`):

### 4.1 Construção gulosa — Vizinho Mais Próximo (Nearest Neighbor)

Partindo do CD, o algoritmo visita repetidamente o município não-visitado
mais próximo (em tempo de deslocamento) do município atual, até que todos
os 24 destinos tenham sido visitados, retornando então ao CD. É um
algoritmo guloso simples, de complexidade `O(n²)`, que produz rapidamente
uma solução inicial razoável, mas tipicamente 15–30% pior que o ótimo.

### 4.2 Refinamento por busca local — 2-opt

A solução inicial é refinada pelo algoritmo **2-opt**: a cada iteração,
todas as trocas possíveis de duas arestas do ciclo são avaliadas — removendo
duas arestas `(a,b)` e `(c,d)` e reconectando o ciclo como `(a,c)` e `(b,d)`
com o segmento entre elas invertido — e a melhor troca que reduz o custo
total é aplicada. O processo se repete até que nenhuma troca melhore mais
o custo (ótimo local), ou até um número máximo de iterações. Essa etapa
tipicamente recupera boa parte do "gap" da construção gulosa.

No cenário single-vehicle deste trabalho, o refinamento 2-opt reduziu o
tempo total da rota em **24,6%** em relação à solução inicial por vizinho
mais próximo (ver seção 7).

O CD nunca é movido durante o 2-opt (permanece fixo nas duas pontas do
ciclo), garantindo que toda rota sempre comece e termine no Centro de
Distribuição.

---

## 5. Extensão para VRP (frota de veículos)

Para dividir os municípios de entrega entre múltiplos veículos, foi adotada
a heurística clássica de **varredura angular** ("*sweep algorithm*",
Gillett & Miller, 1974), uma abordagem de **particionamento seguido de
roteamento** (*cluster-first, route-second*):

1. Calcula-se o ângulo polar de cada município de entrega em relação ao CD
   (usando `atan2` sobre a diferença de latitude/longitude);
2. Os municípios são ordenados por esse ângulo, formando uma "varredura"
   ao redor do CD;
3. A lista ordenada é dividida em `k` grupos contíguos (k = tamanho da
   frota), de tamanho o mais balanceado possível (diferença máxima de 1
   município entre grupos);
4. Cada grupo é resolvido **independentemente** como um TSP de veículo
   único (vizinho mais próximo + 2-opt), sempre partindo e retornando ao
   CD.

Essa estratégia tende a produzir rotas geograficamente coerentes (cada
veículo atende uma "fatia" contígua do mapa), reduzindo cruzamentos entre
rotas de veículos diferentes — um problema comum em partições ingênuas
(por exemplo, aleatórias ou apenas por proximidade sequencial na lista
de municípios).

### 5.1 Métricas de comparação

Como os veículos operam **em paralelo**, duas métricas de tempo são
distintas e ambas são reportadas (`backend/vrp.py`):

- **Tempo total somado** (soma do tempo de rota de todos os veículos):
  reflete o custo total de horas de condução/mão-de-obra da frota;
- ***Makespan*** (o maior tempo de rota entre os veículos): reflete quando
  a operação como um todo é concluída, e é a métrica operacionalmente mais
  relevante para efeito de "ganho de tempo" ao se comparar com o cenário de
  veículo único — é ela que aparece na aplicação web como o indicador
  principal de duração da operação.

---

## 6. Arquitetura da aplicação web

A aplicação é dividida em duas camadas, comunicando-se por um único
artefato de dados estático (`frontend/data/solution.json`): o backend
Python calcula, uma única vez, os dados geográficos que dependem de fontes
externas (coordenadas, população, matriz de distância/tempo real via OSRM);
o **algoritmo de otimização (TSP + VRP) roda no próprio navegador**, em
JavaScript, permitindo que o usuário escolha **qualquer número de
veículos** na interface sem depender de cenários fixos pré-computados:

```
backend/ (Python)                              frontend/ (HTML/CSS/JS + Leaflet)
─────────────────────                          ──────────────────────────────────
selecao_municipios.py  ─┐                      js/otimizacao.js  (TSP + VRP em JS - roda no navegador)
routing.py (OSRM)       ├─► main.py ──► solution.json ──► js/data.js  (carga, matriz, geometria sob demanda)
graph_builder.py        │   (matriz completa +           js/map.js   (Leaflet: rotas, marcadores, carros)
tsp.py / vrp.py        ─┘    cache de geometria)          js/main.js  (estado, relógio simulado, painéis)
```

### 6.1 Backend (Python)

Executado uma única vez (offline) para gerar `solution.json` contendo: os
25 municípios selecionados; a **matriz completa 25×25** de distância e
tempo real entre todos os pares (via OSRM `/table`); e um **cache
pré-aquecido** da geometria real de rota (via OSRM `/route`) para todos os
trechos utilizados nos cenários de 1 a 12 veículos — usado para validar os
algoritmos no console (seção 7) e para que os tamanhos de frota mais
comuns carreguem instantaneamente no navegador, sem round-trips de rede.

### 6.2 Frontend (HTML/CSS/JS + Leaflet)

Aplicação de página única, sem processo de build (JavaScript vanilla,
compatível com qualquer navegador moderno), estruturada em quatro módulos:

- **`js/otimizacao.js`**: porte para JavaScript dos mesmos algoritmos do
  backend (vizinho mais próximo + 2-opt para o TSP; varredura angular +
  TSP por veículo para o VRP), operando sobre a matriz de tempo/distância
  embutida em `solution.json`. É o que permite resolver o problema para
  **qualquer número de veículos** diretamente no navegador, sem precisar
  de um backend em produção.
- **`js/data.js`**: carrega `solution.json`; monta, para cada rota, a
  "trilha" completa (polilinha real + marcação temporal), concatenando a
  geometria de cada trecho e distribuindo o tempo de viagem proporcionalmente
  à distância percorrida dentro dele (aproximação de velocidade constante
  por trecho, já que o OSRM não fornece telemetria ponto-a-ponto na
  resposta agregada usada); e **busca ao vivo, diretamente no navegador**,
  a geometria de qualquer trecho que a frota escolhida precise e que não
  esteja no cache pré-aquecido — a instância pública do OSRM permite
  chamadas diretas do navegador via CORS (`Access-Control-Allow-Origin: *`,
  verificado empiricamente), com timeout de 7s e *fallback* automático por
  linha reta (Haversine) caso a chamada falhe ou demore demais, mantendo a
  aplicação responsiva mesmo em redes restritivas.
- **`js/map.js`**: encapsula toda a interação com a biblioteca **Leaflet**
  — mapa base OpenStreetMap, marcador do Centro de Distribuição, polilinhas
  coloridas por veículo seguindo a geometria real, marcadores de parada
  numerados e ícones de caminhão (🚚) que representam a posição atual de
  cada veículo.
- **`js/main.js`**: mantém o estado da aplicação (frota ativa, horários de
  saída, relógio de simulação), orquestra a chamada ao `js/otimizacao.js`
  sempre que o usuário muda o tamanho da frota, calcula os indicadores de
  frota excessiva/sem ganho (seção 6.3), e implementa o **relógio
  simulado**: um laço de animação (`requestAnimationFrame`) avança um
  contador de minutos simulados a uma velocidade ajustável (1×, 5×, 20× ou
  60× — minutos simulados por segundo real); a cada quadro, a posição de
  cada veículo é interpolada ao longo de sua trilha em função do tempo
  decorrido desde seu horário de saída configurado, e seu status
  (*aguardando saída* / *em rota* / *entrega concluída*) é atualizado de
  acordo.

A biblioteca Leaflet é **vendorizada localmente** no repositório
(`frontend/vendor/leaflet/`) em vez de referenciada por CDN, garantindo que
a aplicação funcione mesmo atrás de firewalls corporativos ou em ambientes
de avaliação com acesso restrito à internet (o carregamento dos mosaicos de
mapa do OpenStreetMap, esses sim, continua exigindo acesso à internet).

### 6.3 Interface e gestão da frota

- **Número de veículos totalmente customizável**: um campo numérico (e os
  botões "+"/"−") no topo da aplicação permite escolher **qualquer
  quantidade** de veículos; a cada mudança, o VRP é recalculado ao vivo no
  navegador (seção 6.2) e as rotas são redesenhadas no mapa.
- **Indicador de veículos ociosos**: como não há benefício em ter mais
  veículos do que municípios de entrega (24, neste estudo), se o usuário
  configurar mais veículos que isso, o excedente fica visivelmente marcado
  como *ocioso* (parado no CD, sem rota atribuída) e um aviso explica que
  não há necessidade operacional desses veículos extras.
- **Indicador de "sem ganho"**: mesmo dentro do limite de 24, adicionar um
  veículo pode não reduzir o tempo total da operação (*makespan*) em
  relação a um veículo a menos — fenômeno real do VRP com varredura
  angular, discutido na seção 7 (ex.: k=6 e k=7, ou k=9, 10 e 11, empatam
  no makespan neste estudo de caso). Quando isso ocorre, a aplicação exibe
  um aviso comparando o tempo antes/depois e informando que a frota atual
  já é suficiente — atendendo diretamente ao requisito de o sistema
  **indicar quando mais veículos não são necessários** para a rota
  existente.
- **Horário de saída por veículo**: cada veículo tem um campo de horário
  editável (padrão: 08:00, 09:30, 11:00, ... com 90 minutos de espaçamento),
  e sua animação no mapa só começa a partir desse horário no relógio
  simulado — reproduzindo fielmente o requisito de que veículos com saída
  posterior iniciem seu deslocamento mais tarde, respeitando a diferença
  configurada entre eles.
- **Painel de frota**: por veículo, exibe a lista de municípios de entrega
  (marcados visualmente conforme visitados), distância e tempo totais da
  rota, e o status atual.
- **Painel de resumo**: número de veículos ativos, total de municípios
  atendidos, distância total da operação, duração total da operação
  (makespan) e um comparativo visual (barras) entre a rota ingênua, o
  veículo único e a frota atualmente selecionada, com o percentual de
  economia de tempo.

---

## 7. Resultados obtidos

Os resultados a seguir foram gerados pela execução real do pipeline
(`backend/main.py`) sobre os 25 municípios selecionados, com dados de
distância/tempo/geometria obtidos ao vivo da API do OSRM (fonte:
`osrm_table` / `osrm_route`, sem uso do fallback Haversine).

| Cenário                        | Distância total | Tempo total (makespan) | Economia vs. rota ingênua |
|---------------------------------|:---:|:---:|:---:|
| Rota ingênua (sem otimização)   | 4.181,2 km | 73h42min | — (linha de base) |
| Veículo único (TSP: NN + 2-opt) | 1.364,7 km | 25h08min | **65,9%** |
| Frota de 2 veículos (VRP)       | 1.825,4 km (soma) | 18h27min | 75,0% |
| Frota de 3 veículos (VRP)       | 1.930,7 km (soma) | 12h42min | 82,8% |
| Frota de 4 veículos (VRP)       | 2.441,2 km (soma) | 13h29min | 81,7% |
| Frota de 5 veículos (VRP)       | 2.334,1 km (soma) | 9h57min  | 86,5% |
| Frota de 6 veículos (VRP)       | 2.816,9 km (soma) | 10h52min | 85,2% |
| Frota de 7 veículos (VRP)       | 3.204,7 km (soma) | 10h52min | 85,2% *(empate com k=6)* |
| Frota de 8 veículos (VRP)       | 3.424,7 km (soma) | 9h18min  | 87,4% |
| Frota de 9 veículos (VRP)       | 3.592,7 km (soma) | 9h18min  | 87,4% *(empate com k=8)* |
| Frota de 10 veículos (VRP)      | 3.949,8 km (soma) | 9h18min  | 87,4% *(empate com k=8)* |
| Frota de 11 veículos (VRP)      | 4.118,6 km (soma) | 9h18min  | 87,4% *(empate com k=8)* |
| Frota de 12 veículos (VRP)      | 4.216,4 km (soma) | 9h13min  | **87,5%** |

Observações relevantes:

- O refinamento **2-opt** reduziu o tempo da rota de veículo único em
  **24,6%** em relação à solução inicial gulosa de vizinho mais próximo —
  uma melhoria substancial obtida com uma heurística de baixo custo
  computacional.
- A distância total **somada** da frota cresce com o número de veículos
  (mais viagens de ida/volta ao CD), mas o **tempo de conclusão da
  operação (makespan)** cai substancialmente, que é o benefício real de se
  ter uma frota: entregas mais rápidas ao custo de mais quilometragem
  agregada e mais veículos/motoristas mobilizados — um trade-off explícito
  entre tempo e custo operacional que a aplicação web também evidencia.
- **Achado não-monótono relevante:** o *makespan* da frota de 4 veículos
  (13h29min) é **pior** que o da frota de 3 veículos (12h42min). Isso
  ocorre porque a heurística de varredura angular balanceia os grupos por
  **número de municípios**, não por **tempo de rota estimado** — um grupo
  de 6 municípios muito espalhados geograficamente pode consumir mais
  tempo que um grupo de 8 municípios próximos entre si. Esse resultado é
  mantido no relatório (em vez de ocultado) por ilustrar de forma concreta
  uma limitação real de heurísticas de particionamento simples, discutida
  em mais detalhe na seção 8.
- **Retornos decrescentes (diminishing returns):** a partir de certo ponto,
  veículos adicionais deixam de reduzir o makespan (k=6/k=7 empatam em
  10h52min; k=8, 9, 10 e 11 empatam em 9h18min). Isso ocorre porque, na
  varredura angular, adicionar um veículo apenas subdivide um grupo já
  existente — se o subgrupo mais lento não for o afetado pela nova divisão,
  o tempo total da operação (definido pelo veículo mais lento) não muda.
  É exatamente essa situação que a aplicação web detecta e sinaliza ao
  usuário (seção 6.3): adicionar mais um veículo além do ponto de retorno
  decrescente não traz benefício operacional.

---

## 8. Limitações do estudo

1. **NP-dificuldade e uso de heurísticas.** TSP e VRP são problemas
   NP-difíceis; as soluções aqui apresentadas são heurísticas (vizinho mais
   próximo + 2-opt; varredura angular) e não há garantia de otimalidade
   global. Para instâncias de 24-25 nós, é factível obter o ótimo exato com
   métodos exatos (programação dinâmica de Held-Karp, branch-and-bound, ou
   *solvers* de programação inteira como OR-Tools/Gurobi), o que ficou fora
   do escopo didático deste trabalho, focado na implementação própria dos
   algoritmos clássicos.
2. **Balanceamento do VRP por contagem, não por tempo.** Como discutido na
   seção 7, a varredura angular equilibra o número de paradas por veículo,
   não o tempo estimado de rota, o que pode gerar frotas com cargas de
   trabalho desbalanceadas (e, ocasionalmente, o *makespan* pode até
   piorar ao se adicionar um veículo). Uma extensão natural seria
   balancear os grupos por tempo/distância acumulada estimada, ou aplicar
   uma heurística de melhoria local entre rotas (*inter-route 2-opt* /
   *or-opt*) após o particionamento inicial.
3. **Ausência de restrições operacionais reais.** O modelo não considera
   capacidade de carga dos veículos, janelas de horário de entrega
   (*time windows*) nos municípios de destino, jornada máxima de condução,
   paradas para descanso, trânsito em tempo real ou custos variáveis de
   pedágio/combustível — todos tratáveis em extensões do tipo VRPTW
   (VRP with Time Windows) ou CVRP (Capacitated VRP).
4. **Dependência de um serviço público de roteamento sem SLA.** O uso da
   instância de demonstração do OSRM é adequado para fins acadêmicos, mas
   não deveria ser usado em produção sem uma instância própria hospedada
   ou um provedor comercial com SLA e chave de API.
5. **Precisão da geometria simplificada.** A simplificação de
   Ramer-Douglas-Peucker (tolerância ~90 m) reduz drasticamente o tamanho
   dos dados para viabilizar o carregamento no navegador, introduzindo uma
   perda de fidelidade geométrica imperceptível na escala de visualização
   estadual, mas que não deveria ser usada para navegação turn-by-turn.
6. **Interpolação de velocidade constante por trecho.** A animação dos
   veículos assume velocidade constante dentro de cada trecho (proporcional
   à distância percorrida), já que a API de tabela do OSRM não fornece
   telemetria de velocidade ponto a ponto — uma simplificação visualmente
   adequada, mas não uma simulação de tráfego real.
7. **Dependência de CORS do OSRM para frotas grandes no navegador.** Como o
   VRP roda ao vivo no frontend (seção 6.2), tamanhos de frota fora do
   cache pré-aquecido (1 a 12 veículos) exigem buscar a geometria de novos
   trechos diretamente do navegador para a API pública do OSRM. Isso
   funciona porque essa instância permite chamadas *cross-origin*
   (verificado empiricamente), mas é um comportamento de terceiros que pode
   mudar; o *fallback* por linha reta (limitação 4) garante que a aplicação
   nunca trave, apenas perca fidelidade visual da geometria nesse caso.
   Além disso, navegadores limitam conexões simultâneas por domínio, então
   frotas muito grandes (muitos trechos não cacheados) podem levar alguns
   segundos a mais para carregar.
8. **Limite de veículos úteis.** Como cada veículo precisa de ao menos um
   município para ter sentido operacional, o número de veículos
   "produtivos" está limitado ao número de municípios de entrega (24). A
   aplicação permite configurar frotas maiores livremente, mas sinaliza o
   excedente como ocioso (seção 6.3) em vez de impedir a escolha — uma
   decisão deliberada de deixar o usuário explorar o comportamento do
   sistema além do ponto útil, em vez de restringir artificialmente a
   interface.

---

## 9. Conclusão

Este trabalho demonstrou, de ponta a ponta, a aplicação de teoria de grafos
e heurísticas clássicas de otimização combinatória (TSP com vizinho mais
próximo + 2-opt; VRP com varredura angular) a um problema logístico real e
concreto — o planejamento de rotas de entrega de uma transportadora na
região do Espírito Santo — utilizando dados geográficos públicos e reais
(IBGE) e roteamento rodoviário real (OSRM), e não simplificações por linha
reta. Os ganhos obtidos foram expressivos: uma redução de quase 66% no
tempo total de operação apenas ao otimizar a rota de um único veículo em
relação a uma rota não-otimizada, e reduções de até 86% ao se empregar uma
frota adequadamente dimensionada. A aplicação web interativa desenvolvida
torna esses resultados tangíveis e exploráveis, permitindo visualizar,
comparar e simular diferentes configurações de frota sobre o mapa real do
estado.

---

## 10. Referências

- IBGE — Instituto Brasileiro de Geografia e Estatística. *API de
  Localidades* e *API de Agregados* (população residente estimada 2021,
  agregado 6579/variável 9324). https://servicodados.ibge.gov.br/api/docs/
- Dataset público de coordenadas municipais brasileiras (derivado do IBGE):
  https://github.com/kelvins/Municipios-Brasileiros
- OSRM — *Open Source Routing Machine*, instância pública de demonstração.
  http://project-osrm.org/
- Hagberg, A., Swart, P., & S Chult, D. (2008). *Exploring network
  structure, dynamics, and function using NetworkX*. Proceedings of the
  7th Python in Science Conference (SciPy2008).
- Gillett, B. E., & Miller, L. R. (1974). *A heuristic algorithm for the
  vehicle-dispatch problem*. Operations Research, 22(2), 340–349.
  (Heurística de varredura/*sweep algorithm*.)
- Croes, G. A. (1958). *A method for solving traveling-salesman
  problems*. Operations Research, 6(6), 791–812. (Origem do método 2-opt.)
- Leaflet.js — biblioteca JavaScript de mapas interativos.
  https://leafletjs.com/
- OpenStreetMap — dados de mapa base. https://www.openstreetmap.org/

---

## Apêndice A — Código-fonte comentado (backend)

O código-fonte completo do backend está disponível no repositório em
`backend/`, com os seguintes módulos principais (cada um comentado em
português no próprio arquivo, explicando a lógica e as decisões de
projeto):

| Arquivo | Responsabilidade |
|---|---|
| `backend/selecao_municipios.py` | Seleção dos 25 municípios (CD + 24 de entrega) a partir do dataset completo de 78, por critério populacional |
| `backend/routing.py` | Cliente OSRM (matriz `/table` e geometria `/route`), cache em disco, fallback Haversine, simplificação de geometria (RDP) |
| `backend/graph_builder.py` | Construção do grafo `networkx.DiGraph` a partir da matriz de distância/tempo |
| `backend/tsp.py` | Heurística de TSP: vizinho mais próximo + refinamento 2-opt |
| `backend/vrp.py` | Heurística de VRP: varredura angular (particionamento) + TSP por veículo; métricas de comparação frota vs. veículo único |
| `backend/main.py` | Orquestrador: gera `solution.json` com municípios, matriz completa 25×25 de distância/tempo e cache de geometria pré-aquecido (frotas de 1 a 12), além de validar os algoritmos no console |

Trechos centrais dos dois algoritmos de otimização, para referência direta
neste documento:

```python
# backend/tsp.py — construção gulosa por vizinho mais proximo
def vizinho_mais_proximo(indices_entrega, cd_idx, matriz):
    nao_visitados = set(indices_entrega)
    tour = [cd_idx]
    atual = cd_idx
    while nao_visitados:
        proximo = min(nao_visitados, key=lambda j: matriz[atual][j])
        tour.append(proximo)
        nao_visitados.remove(proximo)
        atual = proximo
    tour.append(cd_idx)
    return tour

# backend/tsp.py — refinamento por busca local 2-opt
def two_opt(tour, matriz, max_iteracoes=MAX_ITERACOES_2OPT):
    melhor = tour[:]
    melhor_custo = custo_total(melhor, matriz)
    n = len(melhor)
    for _ in range(max_iteracoes):
        melhorou = False
        for i in range(1, n - 2):
            for k in range(i + 1, n - 1):
                novo = _reversao_2opt(melhor, i, k)
                novo_custo = custo_total(novo, matriz)
                if novo_custo < melhor_custo - 1e-9:
                    melhor, melhor_custo = novo, novo_custo
                    melhorou = True
        if not melhorou:
            break
    return melhor, melhor_custo
```

```python
# backend/vrp.py — particionamento por varredura angular (sweep)
def clusters_por_varredura(indices_entrega, cd_idx, municipios_por_id, n_veiculos):
    cd = municipios_por_id[cd_idx]
    ordenados = sorted(indices_entrega, key=lambda i: _angulo(cd, municipios_por_id[i]))
    n = len(ordenados)
    base, resto = n // n_veiculos, n % n_veiculos
    clusters, cursor = [], 0
    for v in range(n_veiculos):
        tamanho = base + (1 if v < resto else 0)
        clusters.append(ordenados[cursor:cursor + tamanho])
        cursor += tamanho
    return [c for c in clusters if c]
```

O código completo, incluindo tratamento de erros, cache e comentários
detalhados, deve ser consultado diretamente nos arquivos do repositório
indicados na tabela acima.

---

## Apêndice B — Código-fonte comentado (frontend)

O código-fonte completo do frontend está em `frontend/`, estruturado como
uma aplicação de página única sem processo de build:

| Arquivo | Responsabilidade |
|---|---|
| `frontend/index.html` | Estrutura da página: barra superior (controles de frota/relógio), mapa, painéis laterais |
| `frontend/css/style.css` | Estilo visual (paleta de logística: azul-marinho, azul, verde, cinza) |
| `frontend/js/otimizacao.js` | TSP (NN + 2-opt) e VRP (varredura angular) em JavaScript — roda no navegador para qualquer nº de veículos |
| `frontend/js/data.js` | Carregamento de `solution.json`; montagem da trilha temporal de cada rota; busca ao vivo de geometria no OSRM com fallback |
| `frontend/js/map.js` | Integração com Leaflet: mapa base, marcador do CD, rotas coloridas, marcadores de parada, ícones de veículo |
| `frontend/js/main.js` | Estado da aplicação, geração de cenário sob demanda, indicadores de frota ociosa/sem ganho, relógio simulado (`requestAnimationFrame`), painéis de frota/resumo |

Trecho central da detecção de "frota suficiente" (indicadores de veículos
ociosos e de ganho nulo ao adicionar um veículo), e da lógica de animação
(interpolação de posição do veículo ao longo do tempo simulado), para
referência direta:

```javascript
// frontend/js/main.js — avisa quando a frota configurada excede o necessario
function atualizarBanner(nSolicitado, nUtil, nIdle) {
  const banner = document.getElementById("fleet-banner");

  if (nIdle > 0) {
    // mais veiculos do que municipios de entrega: excedente fica ocioso
    banner.hidden = false;
    banner.className = "fleet-banner banner-idle";
    banner.textContent = `${nIdle} veículo(s) sem rota atribuída — não são necessários.`;
    return;
  }

  if (nUtil > 1) {
    const makespanAtual = state.makespanCache[nUtil];
    const makespanAnterior = calcularMakespan(nUtil - 1);
    if (makespanAtual >= makespanAnterior - 1e-6) {
      // veiculo adicional nao reduziu o tempo total da operacao (makespan)
      banner.hidden = false;
      banner.className = "fleet-banner banner-no-gain";
      banner.textContent = "Frota atual já é suficiente.";
      return;
    }
  }

  banner.hidden = true;
}
```

```javascript
// frontend/js/main.js — posiciona cada veiculo conforme o relogio simulado
function atualizarPosicoes() {
  state.veiculos.forEach((v) => {
    const elapsed = state.simClockMin - v.departureMin;
    let status, pos;
    if (elapsed < 0) {
      status = "aguardando"; pos = v.trilha.pontos[0];
    } else if (elapsed >= v.trilha.tempoTotalMin) {
      status = "concluida"; pos = v.trilha.pontos[v.trilha.pontos.length - 1];
    } else {
      status = "em-rota"; pos = interpolarPosicao(v.trilha.pontos, elapsed);
    }
    v.status = status;
    MapView.moverCarro(v.carMarker, pos.lat, pos.lon);
  });
}
```

O código completo, incluindo o módulo de mapa e os painéis de UI, deve ser
consultado diretamente nos arquivos do repositório indicados na tabela
acima.
