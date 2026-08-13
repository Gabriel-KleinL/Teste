"""
Construcao do grafo de distancias/tempos reais entre os municipios
selecionados, usando NetworkX.

O grafo e completo (K25): como o problema e o Caixeiro Viajante / VRP
classico, assume-se que existe um caminho rodoviario (nao necessariamente
uma aresta direta unica) entre quaisquer dois municipios, com peso igual ao
menor caminho rodoviario real entre eles (distancia e tempo), obtido do
OSRM. O grafo e direcionado (DiGraph) porque distancia/tempo de A->B podem
diferir de B->A em rodovias reais (sentidos unicos, pedagios, relevo etc.).
"""
import networkx as nx

from routing import obter_matriz_osrm


def construir_grafo(municipios):
    """
    municipios: lista de dicts com 'id', 'nome', 'lat', 'lon' (na ordem que
    define os indices da matriz).
    Retorna (grafo, dist_km_matrix, tempo_min_matrix, fonte).
    """
    dist_km, tempo_min, fonte = obter_matriz_osrm(municipios)

    g = nx.DiGraph()
    for m in municipios:
        g.add_node(m["id"], nome=m["nome"], lat=m["lat"], lon=m["lon"], papel=m.get("papel", "entrega"))

    n = len(municipios)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            g.add_edge(
                municipios[i]["id"],
                municipios[j]["id"],
                dist_km=dist_km[i][j],
                tempo_min=tempo_min[i][j],
            )

    return g, dist_km, tempo_min, fonte


def resumo_grafo(g):
    return {
        "n_nos": g.number_of_nodes(),
        "n_arestas": g.number_of_edges(),
        "densidade": nx.density(g),
    }
