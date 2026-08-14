"""
Orquestrador principal do backend de otimizacao de rotas.

Pipeline:
  1. Carrega os 78 municipios do Espirito Santo (ids globais 0-77, estaveis).
  2. Constroi o grafo COMPLETO dos 78 municipios (matriz 78x78 de
     distancia/tempo real via OSRM /table, uma unica requisicao).
  3. Roda os algoritmos de TSP (veiculo unico) e VRP (varredura angular)
     para o preset padrao (CD = Serra, 24 municipios mais populosos) e uma
     faixa de tamanhos de frota (1 a MAX_FROTA_PRE_AQUECIDA), para validar
     os resultados no console e "pre-aquecer" o cache de geometria real de
     rota do OSRM para o cenario que a aplicacao mostra ao abrir.
  4. Salva em frontend/data/solution.json: os 78 municipios, a matriz
     completa 78x78 de distancia/tempo real (usada pelo frontend para
     rodar o MESMO algoritmo de TSP/VRP, em JavaScript, para QUALQUER
     subconjunto de municipios e QUALQUER numero de veiculos que o usuario
     escolher no seletor de localizacoes da interface) e o cache de
     geometria pre-aquecido para o preset padrao (o frontend busca ao vivo
     no OSRM a geometria de trechos que nao estejam nesse cache).

Execute com: python3 main.py  (a partir da pasta backend/)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from selecao_municipios import carregar_municipios_completos, preset_padrao  # noqa: E402
from graph_builder import construir_grafo, resumo_grafo  # noqa: E402
from tsp import resolver_tsp, custo_total  # noqa: E402
from vrp import resolver_vrp  # noqa: E402
from routing import obter_geometrias_em_lote  # noqa: E402

FRONTEND_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "data")
MAX_FROTA_PRE_AQUECIDA = 12  # frotas de 1 a 12 veiculos tem a geometria pre-cacheada (preset padrao)


def rota_ingenua(indices_entrega, cd_idx, matriz_dist, matriz_tempo):
    """Rota sem otimizacao: visita os municipios na ordem em que aparecem
    no preset, sem apoio algoritmico. Usada so para validacao no console."""
    tour = [cd_idx] + list(indices_entrega) + [cd_idx]
    return {
        "tour": tour,
        "dist_km": custo_total(tour, matriz_dist),
        "tempo_min": custo_total(tour, matriz_tempo),
    }


def coletar_arestas(tours):
    arestas = set()
    for tour in tours:
        for a, b in zip(tour, tour[1:]):
            arestas.add((a, b))
    return arestas


def main():
    municipios = carregar_municipios_completos()
    municipios_por_id = {m["id"]: m for m in municipios}
    cd_id, entrega_ids_padrao = preset_padrao(municipios)

    print(f"Municipios no dataset: {len(municipios)} | CD padrao: {municipios_por_id[cd_id]['nome']} | entrega padrao: {len(entrega_ids_padrao)}")

    grafo, matriz_dist, matriz_tempo, fonte_matriz = construir_grafo(municipios)
    print(f"Grafo construido: {resumo_grafo(grafo)} | fonte da matriz: {fonte_matriz}")

    # --- validacao no console (preset padrao) + coleta de trechos para pre-aquecer o cache ---
    ingenua = rota_ingenua(entrega_ids_padrao, cd_id, matriz_dist, matriz_tempo)
    print(f"[validacao] Rota ingenua: {ingenua['dist_km']:.1f} km / {ingenua['tempo_min']:.1f} min")

    todos_tours_para_arestas = [ingenua["tour"]]

    max_util = min(MAX_FROTA_PRE_AQUECIDA, len(entrega_ids_padrao))
    for k in range(1, max_util + 1):
        rotas = resolver_vrp(entrega_ids_padrao, cd_id, municipios_por_id, matriz_dist, matriz_tempo, k)
        makespan = max(r["tempo_min"] for r in rotas)
        dist_total = sum(r["dist_km"] for r in rotas)
        print(f"[validacao] k={k}: makespan={makespan:.1f} min, dist_total_frota={dist_total:.1f} km")
        for r in rotas:
            todos_tours_para_arestas.append(r["tour"])

    # --- geometria real de todos os trechos utilizados nos cenarios de validacao ---
    arestas_unicas = coletar_arestas(todos_tours_para_arestas)
    print(f"Buscando geometria real de {len(arestas_unicas)} trechos unicos via OSRM (pre-aquecimento do cache)...")
    geometrias = obter_geometrias_em_lote(sorted(arestas_unicas), municipios_por_id)

    arestas_serializadas = {
        f"{i}-{j}": {
            "geometria": info["geometria"],
            "dist_km": info["dist_km"],
            "tempo_min": info["tempo_min"],
            "fonte": info["fonte"],
        }
        for (i, j), info in geometrias.items()
    }

    fontes_geometria = {info["fonte"] for info in geometrias.values()}

    saida = {
        "meta": {
            "n_municipios_total": len(municipios),
            "cd_id_padrao": cd_id,
            "entrega_ids_padrao": entrega_ids_padrao,
            "fonte_matriz_distancias": fonte_matriz,
            "fontes_geometria_utilizadas": sorted(fontes_geometria),
            "frota_pre_aquecida_ate": max_util,
        },
        "municipios": municipios,
        "matrizes": {
            "dist_km": matriz_dist,
            "tempo_min": matriz_tempo,
        },
        "arestas": arestas_serializadas,
    }

    os.makedirs(FRONTEND_DATA_DIR, exist_ok=True)
    out_path = os.path.join(FRONTEND_DATA_DIR, "solution.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)

    print(f"\nArquivo salvo em {out_path}")


if __name__ == "__main__":
    main()
