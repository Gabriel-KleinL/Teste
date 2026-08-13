/**
 * Carregamento e normalizacao dos dados gerados pelo backend Python
 * (frontend/data/solution.json). Concentra toda a logica de "achatar" os
 * diferentes formatos vindos do backend (cenario_single_vehicle vs
 * cenarios_frota) em uma unica estrutura de cenario, mais simples de
 * consumir pela UI.
 */

const AppData = (() => {
  let solution = null;
  let municipiosPorId = null;

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

  function getCdId() {
    return solution.meta.cd_id;
  }

  function getMeta() {
    return solution.meta;
  }

  /** Retorna a geometria (lista [lat,lon]) do trecho i->j. */
  function getAresta(i, j) {
    const aresta = solution.arestas[`${i}-${j}`];
    if (!aresta) {
      console.warn(`Aresta ${i}-${j} nao encontrada; usando linha reta.`);
      const a = getMunicipio(i);
      const b = getMunicipio(j);
      return { geometria: [[a.lat, a.lon], [b.lat, b.lon]], dist_km: 0, tempo_min: 0, fonte: "indisponivel" };
    }
    return aresta;
  }

  /** Numero maximo de veiculos com cenario VRP pre-computado. */
  function getMaxFrota() {
    const chaves = Object.keys(solution.cenarios_frota).map(Number);
    return Math.max(1, ...chaves);
  }

  /**
   * Retorna um cenario normalizado para n veiculos:
   * { nVeiculos, rotas: [{ veiculo, tourIds, tourNomes, municipiosAtendidos, distKm, tempoMin }] }
   */
  function getCenario(nVeiculos) {
    if (nVeiculos <= 1) {
      const c = solution.cenario_single_vehicle;
      return {
        nVeiculos: 1,
        rotas: [
          {
            veiculo: 0,
            tourIds: c.tour_ids,
            tourNomes: c.tour_nomes,
            municipiosAtendidos: c.tour_nomes.slice(1, -1),
            distKm: c.dist_km,
            tempoMin: c.tempo_min,
          },
        ],
      };
    }
    const c = solution.cenarios_frota[String(nVeiculos)];
    return {
      nVeiculos: c.n_veiculos,
      rotas: c.rotas.map((r) => ({
        veiculo: r.veiculo,
        tourIds: r.tour_ids,
        tourNomes: r.tour_nomes,
        municipiosAtendidos: r.municipios_atendidos,
        distKm: r.dist_km,
        tempoMin: r.tempo_min,
      })),
    };
  }

  function getCenarioIngenuo() {
    const c = solution.cenario_ingenuo;
    return {
      tourIds: c.tour_ids,
      tourNomes: c.tour_nomes,
      distKm: c.dist_km,
      tempoMin: c.tempo_min,
    };
  }

  /**
   * Monta a trilha completa (polilinha real + marcacao temporal) de um
   * tour (lista de ids de municipio incluindo CD nas pontas), concatenando
   * a geometria real de cada trecho e distribuindo o tempo de cada trecho
   * proporcionalmente à distância percorrida dentro dele.
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

    return { pontos, paradas, tempoTotalMin: cumTempo, distTotalKm: cumDist };
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

  return {
    carregar,
    getMunicipio,
    getCdId,
    getMeta,
    getAresta,
    getMaxFrota,
    getCenario,
    getCenarioIngenuo,
    montarTrilha,
  };
})();
