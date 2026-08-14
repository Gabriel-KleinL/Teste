"""
Orquestrador principal do backend de otimizacao de rotas.

Pipeline:
  1. Carrega os municipios selecionados (CD + 24 municipios de entrega).
  2. Constroi o grafo completo de distancias/tempos reais (NetworkX + OSRM).
  3. Roda os algoritmos de TSP (veiculo unico) e VRP (varredura angular) para
     uma faixa de tamanhos de frota (1 a MAX_FROTA_PRE_AQUECIDA), apenas para
     validar os resultados no console e "pre-aquecer" o cache de geometria
     real de rota do OSRM para os cenarios mais comuns.
  4. Salva em frontend/data/solution.json: os municipios, a matriz completa
     de distancia/tempo real entre todos os pares (usada pelo frontend para
     rodar o MESMO algoritmo de TSP/VRP, em JavaScript, para QUALQUER
     tamanho de frota que o usuario escolher na interface) e o cache de
     geometria de rota pre-aquecido (o frontend busca ao vivo no OSRM a
     geometria de trechos que nao estejam nesse cache, ja que a API publica
     do OSRM permite chamadas diretas do navegador via CORS).

Execute com: python3 main.py  (a partir da pasta backend/)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from graph_builder import construir_grafo, resumo_grafo  # noqa: E402
from tsp import resolver_tsp, custo_total  # noqa: E402
from vrp import resolver_vrp, comparar_single_vs_frota  # noqa: E402
from routing import obter_geometrias_em_lote  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
FRONTEND_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "data")
MAX_FROTA_PRE_AQUECIDA = 12  # frotas de 1 a 12 veiculos tem a geometria pre-cacheada


def carregar_municipios():
    with open(os.path.join(DATA_DIR, "municipios_selecionados.json"), encoding="utf-8") as f:
        return json.load(f)


def rota_ingenua(indices_entrega, cd_idx, matriz_dist, matriz_tempo):
    """Rota sem otimizacao: visita os municipios na ordem em que aparecem
    no dataset (ordem de populacao), simulando o planejamento manual de um
    despachante sem apoio algoritmico. Usada so para validacao no console."""
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
    municipios = carregar_municipios()
    municipios_por_id = {m["id"]: m for m in municipios}
    cd_idx = next(m["id"] for m in municipios if m["papel"] == "CD")
    indices_entrega = [m["id"] for m in municipios if m["papel"] == "entrega"]

    print(f"Municipios: {len(municipios)} | CD: {municipios_por_id[cd_idx]['nome']} | entregas: {len(indices_entrega)}")

    grafo, matriz_dist, matriz_tempo, fonte_matriz = construir_grafo(municipios)
    print(f"Grafo construido: {resumo_grafo(grafo)} | fonte da matriz: {fonte_matriz}")

    # --- validacao no console + coleta de trechos para pre-aquecer o cache ---
    ingenua = rota_ingenua(indices_entrega, cd_idx, matriz_dist, matriz_tempo)
    print(f"[validacao] Rota ingenua: {ingenua['dist_km']:.1f} km / {ingenua['tempo_min']:.1f} min")

    todos_tours_para_arestas = [ingenua["tour"]]

    max_util = min(MAX_FROTA_PRE_AQUECIDA, len(indices_entrega))
    for k in range(1, max_util + 1):
        rotas = resolver_vrp(indices_entrega, cd_idx, municipios_por_id, matriz_dist, matriz_tempo, k)
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
            "cd_id": cd_idx,
            "cd_nome": municipios_por_id[cd_idx]["nome"],
            "n_municipios_entrega": len(indices_entrega),
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
