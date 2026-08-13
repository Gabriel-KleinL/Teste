"""
Heuristicas para o Problema do Caixeiro Viajante (TSP) aplicadas a um
subconjunto de nos do grafo, sempre partindo e retornando ao Centro de
Distribuicao (CD).

Metodologia (ver relatorio para a discussao de complexidade):
  1. Construcao gulosa por vizinho mais proximo (nearest neighbor): O(n^2).
  2. Refinamento por busca local 2-opt ate convergencia (otimo local): a
     cada iteracao completa sem melhoria, o algoritmo para. Complexidade de
     cada passada O(n^2); numero de passadas limitado por MAX_ITERACOES.

O custo otimizado e o TEMPO (tempo_min), pois e o criterio mais relevante
operacionalmente para uma transportadora (janelas de entrega, jornada de
trabalho); a distancia total tambem e reportada.
"""

MAX_ITERACOES_2OPT = 200


def custo_total(tour, matriz):
    """tour: lista de indices (0..n-1) formando um ciclo CD -> ... -> CD (CD implicito nas pontas)."""
    total = 0.0
    for i in range(len(tour) - 1):
        total += matriz[tour[i]][tour[i + 1]]
    return total


def vizinho_mais_proximo(indices_entrega, cd_idx, matriz):
    """
    indices_entrega: indices (na matriz global) dos municipios de entrega.
    cd_idx: indice do Centro de Distribuicao.
    Retorna um tour [cd_idx, ..., cd_idx] guloso por vizinho mais proximo.
    """
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


def _reversao_2opt(tour, i, k):
    return tour[:i] + tour[i : k + 1][::-1] + tour[k + 1 :]


def two_opt(tour, matriz, max_iteracoes=MAX_ITERACOES_2OPT):
    """
    Busca local 2-opt: repetidamente tenta remover duas arestas e reconectar
    o tour de outra forma, aceitando a troca sempre que reduz o custo total.
    O CD (posicoes 0 e -1) nunca e movido, pois toda rota deve iniciar e
    terminar nele.
    """
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


def resolver_tsp(indices_entrega, cd_idx, matriz):
    """Pipeline completo: vizinho mais proximo + refinamento 2-opt."""
    tour_inicial = vizinho_mais_proximo(indices_entrega, cd_idx, matriz)
    custo_inicial = custo_total(tour_inicial, matriz)
    tour_final, custo_final = two_opt(tour_inicial, matriz)
    return {
        "tour": tour_final,
        "custo_inicial_nn": custo_inicial,
        "custo_final_2opt": custo_final,
        "ganho_2opt_pct": (custo_inicial - custo_final) / custo_inicial * 100 if custo_inicial > 0 else 0.0,
    }
