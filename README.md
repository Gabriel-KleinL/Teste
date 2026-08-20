# Otimização de Rotas de Entrega no Espírito Santo (TSP/VRP em Grafos)

Trabalho acadêmico de otimização de rotas de entrega usando grafos,
aplicado ao estado do Espírito Santo (Brasil), com dados geográficos reais
(IBGE) e roteamento rodoviário real (OSRM). Inclui aplicação web
interativa com mapa real, frota animada e gestão de horários de saída.

**Relatório acadêmico completo:** [`relatorio/relatorio.md`](relatorio/relatorio.md)
(modelagem, metodologia, algoritmos, arquitetura, resultados e limitações).

## Estrutura do repositório

```
backend/            Pipeline Python (grafo, TSP, VRP, integração OSRM)
  data/              Dados de municípios (78 no total, 25 selecionados)
  cache/             Cache em disco das respostas do OSRM
  selecao_municipios.py
  routing.py
  graph_builder.py
  tsp.py
  vrp.py
  main.py            Ponto de entrada: gera frontend/data/solution.json

frontend/            Aplicação web (HTML/CSS/JS + Leaflet, sem build step)
  index.html
  css/style.css
  js/data.js
  js/map.js
  js/main.js
  vendor/leaflet/     Leaflet vendorizado localmente (sem dependência de CDN)
  data/solution.json  Dados pré-computados consumidos pela aplicação

relatorio/relatorio.md   Relatório acadêmico completo (PT-BR)
```

## Como rodar

### 1. Backend e API dinâmica

Para iniciar a API e servir o frontend integrado:

```bash
cd backend
pip install -r requirements.txt
uvicorn api:app --reload
```

Acesse `http://localhost:8000` (Swagger em `/docs`). Com a API ativa, o
painel permite escolher municípios, demandas, serviços, janelas, frota,
capacidades e saídas. O OR-Tools resolve o CVRPTW, mantendo o Sweep como
fallback e baseline. Sem a API, o frontend continua usando
`frontend/data/solution.json`.

#### Pipeline acadêmico offline (preservado)

O arquivo `frontend/data/solution.json` já está gerado e versionado no
repositório, então **não é necessário rodar o backend para usar a
aplicação web**. Para regenerá-lo (por exemplo, após alterar a seleção de
municípios ou o tamanho da frota):

```bash
cd backend
pip install -r requirements.txt
python3 selecao_municipios.py   # gera data/municipios_selecionados.json
python3 main.py                 # consulta o OSRM e gera ../frontend/data/solution.json
```

Requer acesso à internet (API pública do OSRM, `router.project-osrm.org`).
Sem acesso à rede, o backend usa automaticamente uma aproximação por
distância Haversine (ver relatório, seção 3.2).

### 2. Frontend (aplicação web)

Como o navegador bloqueia `fetch()` de arquivos locais (`file://`) por
CORS, sirva a pasta `frontend/` com um servidor HTTP simples:

```bash
cd frontend
python3 -m http.server 8080
```

Acesse `http://localhost:8080` no navegador. Requer internet apenas para
carregar os mosaicos do mapa (OpenStreetMap) — o restante da aplicação
(Leaflet, dados, lógica) é local.

## Principais decisões de escopo

- **25 municípios** (Centro de Distribuição em Serra + 24 destinos de
  entrega mais populosos do estado), dentro da faixa de 20–30 sugerida.
- **OSRM** (instância pública) para distância/tempo/geometria reais de
  estrada, com fallback automático por Haversine caso a rede falhe.
- **Modo dinâmico via FastAPI** com OR-Tools e restrições operacionais;
  sem a API, o frontend alterna os cenários pré-computados de 1 a 5 veículos.
- **Leaflet + JavaScript vanilla** (sem framework/build step) para o
  frontend, priorizando simplicidade de execução e ausência de
  dependência de CDN.

Justificativas completas de cada decisão estão no relatório acadêmico.
