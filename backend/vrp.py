"""
Extensao para multiplos veiculos - Vehicle Routing Problem (VRP).

Estrategia adotada (heuristica classica de "sweep"/varredura angular,
Gillett & Miller, 1974): os municipios de entrega sao ordenados pelo angulo
polar em relacao ao Centro de Distribuicao e divididos em K grupos
contiguos (K = tamanho da frota), de forma que cada veiculo atenda uma
"fatia" geografica coerente do estado - o que reduz cruzamentos de rota
entre veiculos e tende a minimizar deslocamento total. Cada grupo e entao
resolvido independentemente como um TSP (vizinho mais proximo + 2-opt),
sempre partindo e retornando ao CD.

Isso e uma heuristica de particao-e-roteamento (cluster-first,
route-second), uma das abordagens mais usuais e didaticas para VRP, e
adequada ao escopo deste trabalho academico (o VRP exato tambem e
NP-dificil, assim como o TSP).
"""
import math

from tsp import resolver_tsp, custo_total


def _angulo(cd, ponto):
    dx = ponto["lon"] - cd["lon"]
    dy = ponto["lat"] - cd["lat"]
    return math.atan2(dy, dx)


def clusters_por_varredura(indices_entrega, cd_idx, municipios_por_id, n_veiculos):
    """
    Retorna uma lista de n_veiculos listas de indices, particionando os
    municipios de entrega em fatias angulares contiguas e de tamanho
    balanceado (diferenca maxima de 1 municipio entre fatias).
    """
    cd = municipios_por_id[cd_idx]
    ordenados = sorted(indices_entrega, key=lambda i: _angulo(cd, municipios_por_id[i]))

    n = len(ordenados)
    base = n // n_veiculos
    resto = n % n_veiculos

    clusters = []
    cursor = 0
    for v in range(n_veiculos):
        tamanho = base + (1 if v < resto else 0)
        clusters.append(ordenados[cursor : cursor + tamanho])
        cursor += tamanho

    return [c for c in clusters if c]  # descarta veiculos sem municipios, se houver


def resolver_vrp(indices_entrega, cd_idx, municipios_por_id, matriz_dist, matriz_tempo, n_veiculos):
    """
    Resolve o VRP dividindo os municipios entre n_veiculos por varredura
    angular e aplicando TSP (NN + 2-opt) em cada sub-rota, otimizando por
    tempo (matriz_tempo). Retorna uma lista de rotas por veiculo.
    """
    clusters = clusters_por_varredura(indices_entrega, cd_idx, municipios_por_id, n_veiculos)

    rotas = []
    for idx_veiculo, cluster in enumerate(clusters):
        resultado_tsp = resolver_tsp(cluster, cd_idx, matriz_tempo)
        tour = resultado_tsp["tour"]
        dist_km = custo_total(tour, matriz_dist)
        tempo_min = resultado_tsp["custo_final_2opt"]
        rotas.append(
            {
                "veiculo": idx_veiculo,
                "tour": tour,
                "municipios_atendidos": [municipios_por_id[i]["nome"] for i in cluster],
                "dist_km": dist_km,
                "tempo_min": tempo_min,
            }
        )

    return rotas


def comparar_single_vs_frota(rota_single, rotas_frota):
    """
    rota_single: dict com 'dist_km' e 'tempo_min' da rota de veiculo unico.
    rotas_frota: lista de rotas (saida de resolver_vrp).

    Retorna metricas de comparacao:
      - dist_total_frota: soma das distancias de todos os veiculos (custo
        operacional total de combustivel/km rodado).
      - tempo_total_frota: soma dos tempos de todos os veiculos (custo total
        de mao de obra/horas de condutor).
      - makespan_frota: MAIOR tempo entre os veiculos (tempo ate a operacao
        inteira terminar, considerando que rodam em paralelo) - esta e a
        metrica de "tempo total da operacao" comparavel ao tempo unico do
        veiculo solo.
      - ganho_makespan_pct: reducao percentual do makespan da frota em
        relacao ao tempo do veiculo unico.
    """
    dist_total_frota = sum(r["dist_km"] for r in rotas_frota)
    tempo_total_frota = sum(r["tempo_min"] for r in rotas_frota)
    makespan_frota = max(r["tempo_min"] for r in rotas_frota) if rotas_frota else 0.0

    tempo_single = rota_single["tempo_min"]
    ganho_makespan_pct = (
        (tempo_single - makespan_frota) / tempo_single * 100 if tempo_single > 0 else 0.0
    )

    return {
        "dist_total_frota_km": dist_total_frota,
        "tempo_total_frota_min": tempo_total_frota,
        "makespan_frota_min": makespan_frota,
        "dist_single_km": rota_single["dist_km"],
        "tempo_single_min": tempo_single,
        "ganho_makespan_pct": ganho_makespan_pct,
    }
