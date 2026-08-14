/**
 * Porte para JavaScript dos algoritmos de TSP e VRP implementados em Python
 * (backend/tsp.py e backend/vrp.py), para permitir que o usuario escolha
 * QUALQUER numero de veiculos diretamente no navegador, sem depender de
 * cenarios pre-computados pelo backend. A logica e identica a da versao
 * Python (mesma heuristica, mesmos criterios), operando sobre a matriz
 * completa de tempo/distancia real (obtida uma unica vez via OSRM e
 * embutida em solution.json).
 */

const Otimizacao = (() => {
  const MAX_ITERACOES_2OPT = 200;

  function custoTotal(tour, matriz) {
    let total = 0;
    for (let i = 0; i < tour.length - 1; i++) total += matriz[tour[i]][tour[i + 1]];
    return total;
  }

  function vizinhoMaisProximo(indicesEntrega, cdIdx, matriz) {
    const naoVisitados = new Set(indicesEntrega);
    const tour = [cdIdx];
    let atual = cdIdx;
    while (naoVisitados.size > 0) {
      let proximo = null;
      let melhorCusto = Infinity;
      for (const j of naoVisitados) {
        if (matriz[atual][j] < melhorCusto) {
          melhorCusto = matriz[atual][j];
          proximo = j;
        }
      }
      tour.push(proximo);
      naoVisitados.delete(proximo);
      atual = proximo;
    }
    tour.push(cdIdx);
    return tour;
  }

  function reversao2opt(tour, i, k) {
    const meio = tour.slice(i, k + 1).reverse();
    return [...tour.slice(0, i), ...meio, ...tour.slice(k + 1)];
  }

  function twoOpt(tourInicial, matriz, maxIteracoes = MAX_ITERACOES_2OPT) {
    let melhor = tourInicial.slice();
    let melhorCusto = custoTotal(melhor, matriz);
    const n = melhor.length;

    for (let iter = 0; iter < maxIteracoes; iter++) {
      let melhorou = false;
      for (let i = 1; i < n - 2; i++) {
        for (let k = i + 1; k < n - 1; k++) {
          const novo = reversao2opt(melhor, i, k);
          const novoCusto = custoTotal(novo, matriz);
          if (novoCusto < melhorCusto - 1e-9) {
            melhor = novo;
            melhorCusto = novoCusto;
            melhorou = true;
          }
        }
      }
      if (!melhorou) break;
    }
    return { tour: melhor, custo: melhorCusto };
  }

  /** Resolve o TSP (vizinho mais proximo + 2-opt) para um subconjunto de municipios de entrega. */
  function resolverTSP(indicesEntrega, cdIdx, matriz) {
    if (indicesEntrega.length === 0) {
      return { tour: [cdIdx, cdIdx], custo: 0 };
    }
    const tourInicial = vizinhoMaisProximo(indicesEntrega, cdIdx, matriz);
    return twoOpt(tourInicial, matriz);
  }

  function angulo(cd, ponto) {
    return Math.atan2(ponto.lat - cd.lat, ponto.lon - cd.lon);
  }

  /** Particiona os municipios de entrega em n grupos contiguos por varredura angular (sweep). */
  function clustersPorVarredura(indicesEntrega, cdIdx, municipiosPorId, nVeiculos) {
    const cd = municipiosPorId[cdIdx];
    const ordenados = indicesEntrega
      .slice()
      .sort((a, b) => angulo(cd, municipiosPorId[a]) - angulo(cd, municipiosPorId[b]));

    const n = ordenados.length;
    const base = Math.floor(n / nVeiculos);
    const resto = n % nVeiculos;

    const clusters = [];
    let cursor = 0;
    for (let v = 0; v < nVeiculos; v++) {
      const tamanho = base + (v < resto ? 1 : 0);
      clusters.push(ordenados.slice(cursor, cursor + tamanho));
      cursor += tamanho;
    }
    return clusters.filter((c) => c.length > 0);
  }

  /**
   * Resolve o VRP para nVeiculos, dividindo os municipios de entrega por
   * varredura angular e aplicando TSP (NN + 2-opt) em cada sub-rota.
   * Se nVeiculos exceder o numero de municipios de entrega, os veiculos
   * excedentes ficam sem rota atribuida (idle=true) - nao ha necessidade
   * operacional de mais veiculos do que destinos a atender.
   */
  function resolverVRP(indicesEntrega, cdIdx, municipiosPorId, matrizDist, matrizTempo, nVeiculos) {
    const nUtil = Math.min(nVeiculos, indicesEntrega.length || 1);
    const clusters = clustersPorVarredura(indicesEntrega, cdIdx, municipiosPorId, nUtil);

    const rotas = clusters.map((cluster, idx) => {
      const { tour } = resolverTSP(cluster, cdIdx, matrizTempo);
      return {
        veiculo: idx,
        tourIds: tour,
        tourNomes: tour.map((i) => municipiosPorId[i].nome),
        municipiosAtendidos: cluster.map((i) => municipiosPorId[i].nome),
        distKm: custoTotal(tour, matrizDist),
        tempoMin: custoTotal(tour, matrizTempo),
        idle: false,
      };
    });

    const idleCount = nVeiculos - rotas.length;
    for (let i = 0; i < idleCount; i++) {
      rotas.push({
        veiculo: rotas.length,
        tourIds: [cdIdx, cdIdx],
        tourNomes: [municipiosPorId[cdIdx].nome, municipiosPorId[cdIdx].nome],
        municipiosAtendidos: [],
        distKm: 0,
        tempoMin: 0,
        idle: true,
      });
    }

    return { rotas, nUtil, nIdle: idleCount };
  }

  return { resolverTSP, resolverVRP, custoTotal };
})();
