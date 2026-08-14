/**
 * Carregamento dos dados gerados pelo backend Python
 * (frontend/data/solution.json): municipios, matriz completa de
 * distancia/tempo real (usada pelo modulo Otimizacao para resolver
 * TSP/VRP para QUALQUER numero de veiculos direto no navegador) e um
 * cache pre-aquecido de geometria real de rota para os cenarios mais
 * comuns (1 a 12 veiculos). Para trechos fora desse cache, a geometria e
 * buscada ao vivo na API publica do OSRM (que permite chamada direta do
 * navegador via CORS), com fallback para linha reta caso a rede falhe.
 */

const AppData = (() => {
  const OSRM_BASE_URL = "https://router.project-osrm.org";
  const FATOR_SINUOSIDADE = 1.3;
  const VELOCIDADE_MEDIA_KMH = 60.0;

  let solution = null;
  let municipiosPorId = null;
  const arestasEmMemoria = {}; // cache adicional para trechos buscados ao vivo nesta sessao

  async function carregar() {
    const resp = await fetch("data/solution.json");
    if (!resp.ok) throw new Error("Falha ao carregar data/solution.json");
    solution = await resp.json();
    municipiosPorId = {};
    solution.municipios.forEach((m) => (municipiosPorId[m.id] = m));
    return solution;
  }

  function getMunicipio(id) {
    return municipiosPorId[id];
  }

  function getMunicipiosPorId() {
    return municipiosPorId;
  }

  function getMeta() {
    return solution.meta;
  }

  function getTodosMunicipios() {
    return solution.municipios;
  }

  function getMatrizDist() {
    return solution.matrizes.dist_km;
  }

  function getMatrizTempo() {
    return solution.matrizes.tempo_min;
  }

  function haversineKm(lat1, lon1, lat2, lon2) {
    const R = 6371.0088;
    const toRad = (d) => (d * Math.PI) / 180;
    const dphi = toRad(lat2 - lat1);
    const dlmb = toRad(lon2 - lon1);
    const a =
      Math.sin(dphi / 2) ** 2 +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dlmb / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  function distanciaPontoSegmento(p, a, b) {
    const [px, py] = p, [ax, ay] = a, [bx, by] = b;
    const dx = bx - ax, dy = by - ay;
    if (dx === 0 && dy === 0) return Math.hypot(px - ax, py - ay);
    let t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy);
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
  }

  /** Simplificacao Ramer-Douglas-Peucker (mesma logica de backend/routing.py). */
  function simplificarGeometria(pontos, toleranciaGraus = 0.0008) {
    if (pontos.length <= 2) return pontos;
    const manter = new Array(pontos.length).fill(false);
    manter[0] = manter[pontos.length - 1] = true;
    const pilha = [[0, pontos.length - 1]];

    while (pilha.length) {
      const [ini, fim] = pilha.pop();
      if (fim - ini < 2) continue;
      const a = pontos[ini], b = pontos[fim];
      let maxDist = -1, idxMax = -1;
      for (let i = ini + 1; i < fim; i++) {
        const d = distanciaPontoSegmento(pontos[i], a, b);
        if (d > maxDist) { maxDist = d; idxMax = i; }
      }
      if (maxDist > toleranciaGraus) {
        manter[idxMax] = true;
        pilha.push([ini, idxMax]);
        pilha.push([idxMax, fim]);
      }
    }
    return pontos.filter((_, i) => manter[i]);
  }

  function linhaRetaFallback(origem, destino) {
    const d = haversineKm(origem.lat, origem.lon, destino.lat, destino.lon) * FATOR_SINUOSIDADE;
    return {
      geometria: [[origem.lat, origem.lon], [destino.lat, destino.lon]],
      dist_km: d,
      tempo_min: (d / VELOCIDADE_MEDIA_KMH) * 60,
      fonte: "haversine_fallback_cliente",
    };
  }

  const TIMEOUT_OSRM_MS = 7000;

  /** Busca ao vivo, no OSRM, a geometria real de um trecho nao pre-cacheado. */
  async function buscarGeometriaAoVivo(i, j) {
    const origem = getMunicipio(i);
    const destino = getMunicipio(j);
    const url = `${OSRM_BASE_URL}/route/v1/driving/${origem.lon},${origem.lat};${destino.lon},${destino.lat}?overview=full&geometries=geojson`;

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_OSRM_MS);
      const resp = await fetch(url, { signal: controller.signal });
      clearTimeout(timeoutId);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      if (data.code !== "Ok") throw new Error(data.message || "erro OSRM");
      const rota = data.routes[0];
      const geometriaBruta = rota.geometry.coordinates.map(([lon, lat]) => [lat, lon]);
      const geometria = simplificarGeometria(geometriaBruta).map(([lat, lon]) => [
        Math.round(lat * 1e5) / 1e5,
        Math.round(lon * 1e5) / 1e5,
      ]);
      return {
        geometria,
        dist_km: rota.distance / 1000,
        tempo_min: rota.duration / 60,
        fonte: "osrm_route_cliente",
      };
    } catch (err) {
      console.warn(`[AppData] Falha ao buscar rota ${i}->${j} ao vivo no OSRM (${err.message}). Usando linha reta.`);
      return linhaRetaFallback(origem, destino);
    }
  }

  /** Retorna a geometria (sincrona) do trecho i->j, assumindo que ja foi garantida por garantirArestas(). */
  function getAresta(i, j) {
    const chave = `${i}-${j}`;
    if (arestasEmMemoria[chave]) return arestasEmMemoria[chave];
    if (solution.arestas[chave]) return solution.arestas[chave];
    // fallback de seguranca (nao deveria ocorrer se garantirArestas foi chamado antes)
    return linhaRetaFallback(getMunicipio(i), getMunicipio(j));
  }

  /**
   * Garante que a geometria de todos os pares (i,j) da lista esteja
   * disponivel (no cache pre-aquecido ou buscada ao vivo), buscando em
   * paralelo apenas os trechos que ainda faltam. onProgress(feitos, total)
   * e chamado a cada trecho resolvido, para a UI informar o andamento em
   * frotas grandes que exigem muitas buscas ao vivo no OSRM.
   */
  async function garantirArestas(pares, onProgress) {
    const faltantes = pares.filter(([i, j]) => {
      const chave = `${i}-${j}`;
      return !solution.arestas[chave] && !arestasEmMemoria[chave];
    });
    if (faltantes.length === 0) return;

    let feitos = 0;
    await Promise.all(
      faltantes.map(async ([i, j]) => {
        const chave = `${i}-${j}`;
        arestasEmMemoria[chave] = await buscarGeometriaAoVivo(i, j);
        feitos++;
        if (onProgress) onProgress(feitos, faltantes.length);
      })
    );
  }

  /**
   * Monta a trilha completa (polilinha real + marcacao temporal) de um
   * tour (lista de ids de municipio incluindo CD nas pontas), concatenando
   * a geometria real de cada trecho e distribuindo o tempo de cada trecho
   * proporcionalmente à distância percorrida dentro dele.
   *
   * Pre-requisito: garantirArestas() deve ter sido chamado para todos os
   * pares consecutivos do tour antes de montarTrilha.
   *
   * Retorna:
   *   pontos: [{ lat, lon, t }]  t = minutos acumulados desde a saida do CD
   *   paradas: [{ id, nome, t }] t = minuto de chegada a cada municipio (exclui o CD final)
   *   tempoTotalMin, distTotalKm
   */
  function montarTrilha(tourIds) {
    const pontos = [];
    const paradas = [];
    let cumTempo = 0;
    let cumDist = 0;

    for (let k = 0; k < tourIds.length - 1; k++) {
      const i = tourIds[k];
      const j = tourIds[k + 1];
      if (i === j) continue; // veiculo ocioso (tour [CD, CD])
      const aresta = getAresta(i, j);
      const geo = aresta.geometria;

      const dists = [0];
      for (let p = 1; p < geo.length; p++) {
        dists.push(dists[p - 1] + haversineKm(geo[p - 1][0], geo[p - 1][1], geo[p][0], geo[p][1]));
      }
      const totalDist = dists[dists.length - 1] || 1e-9;

      for (let p = 0; p < geo.length; p++) {
        const frac = dists[p] / totalDist;
        const t = cumTempo + frac * aresta.tempo_min;
        if (p === 0 && pontos.length > 0) continue; // evita ponto duplicado na juncao
        pontos.push({ lat: geo[p][0], lon: geo[p][1], t });
      }

      cumTempo += aresta.tempo_min;
      cumDist += aresta.dist_km;
      paradas.push({ id: j, nome: getMunicipio(j).nome, t: cumTempo });
    }

    if (pontos.length === 0) {
      const cd = getMunicipio(tourIds[0]);
      pontos.push({ lat: cd.lat, lon: cd.lon, t: 0 });
    }

    return { pontos, paradas, tempoTotalMin: cumTempo, distTotalKm: cumDist };
  }

  /** Rota "ingenua": visita os municipios de entrega na ordem dada (sem otimizacao). */
  function getCenarioIngenuo(cdId, entregaIds) {
    const tourIds = [cdId, ...entregaIds, cdId];
    const matrizDist = getMatrizDist();
    const matrizTempo = getMatrizTempo();
    return {
      tourIds,
      distKm: Otimizacao.custoTotal(tourIds, matrizDist),
      tempoMin: Otimizacao.custoTotal(tourIds, matrizTempo),
    };
  }

  return {
    carregar,
    getMunicipio,
    getMunicipiosPorId,
    getTodosMunicipios,
    getMeta,
    getMatrizDist,
    getMatrizTempo,
    getAresta,
    garantirArestas,
    getCenarioIngenuo,
    montarTrilha,
  };
})();
