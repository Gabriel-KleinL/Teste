"""
Orquestrador principal do backend de otimizacao de rotas.

Pipeline:
  1. Carrega os municipios selecionados (CD + 24 municipios de entrega).
  2. Constroi o grafo completo de distancias/tempos reais (NetworkX + OSRM).
  3. Calcula a rota "ingenua" (ordem arbitraria, sem otimizacao) como linha
     de base para comparacao.
  4. Resolve o TSP para veiculo unico (vizinho mais proximo + 2-opt).
  5. Resolve o VRP para frotas de 2 a 5 veiculos (varredura angular + TSP
     por veiculo).
  6. Busca a geometria real (poligono seguindo a rodovia) de cada trecho
     efetivamente utilizado em algum dos cenarios acima.
  7. Salva tudo em frontend/data/solution.json, consumido pelo frontend.

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
FROTAS_A_CALCULAR = [2, 3, 4, 5]


def carregar_municipios():
    with open(os.path.join(DATA_DIR, "municipios_selecionados.json"), encoding="utf-8") as f:
        return json.load(f)


def rota_ingenua(indices_entrega, cd_idx, matriz_dist, matriz_tempo):
    """Rota sem otimizacao: visita os municipios na ordem em que aparecem
    no dataset (ordem de populacao), simulando o planejamento manual de um
    despachante sem apoio algoritmico."""
    tour = [cd_idx] + list(indices_entrega) + [cd_idx]
    return {
        "tour": tour,
        "dist_km": custo_total(tour, matriz_dist),
        "tempo_min": custo_total(tour, matriz_tempo),
    }


def montar_rota_serializavel(tour, municipios_por_id, matriz_dist, matriz_tempo):
    return {
        "tour_ids": tour,
        "tour_nomes": [municipios_por_id[i]["nome"] for i in tour],
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

    # --- cenario ingenuo (linha de base) ---
    ingenua = rota_ingenua(indices_entrega, cd_idx, matriz_dist, matriz_tempo)
    print(f"Rota ingenua: {ingenua['dist_km']:.1f} km / {ingenua['tempo_min']:.1f} min")

    # --- TSP veiculo unico ---
    resultado_tsp = resolver_tsp(indices_entrega, cd_idx, matriz_tempo)
    tour_single = resultado_tsp["tour"]
    rota_single = montar_rota_serializavel(tour_single, municipios_por_id, matriz_dist, matriz_tempo)
    print(
        f"TSP single-vehicle: {rota_single['dist_km']:.1f} km / {rota_single['tempo_min']:.1f} min "
        f"(ganho 2-opt sobre NN: {resultado_tsp['ganho_2opt_pct']:.1f}%)"
    )

    todos_tours_para_arestas = [ingenua["tour"], tour_single]

    # --- VRP para cada tamanho de frota ---
    cenarios_frota = {}
    for k in FROTAS_A_CALCULAR:
        rotas = resolver_vrp(indices_entrega, cd_idx, municipios_por_id, matriz_dist, matriz_tempo, k)
        comparacao = comparar_single_vs_frota(rota_single, rotas)

        rotas_serializadas = []
        for r in rotas:
            rotas_serializadas.append(
                {
                    "veiculo": r["veiculo"],
                    "tour_ids": r["tour"],
                    "tour_nomes": [municipios_por_id[i]["nome"] for i in r["tour"]],
                    "municipios_atendidos": r["municipios_atendidos"],
                    "dist_km": r["dist_km"],
                    "tempo_min": r["tempo_min"],
                }
            )
            todos_tours_para_arestas.append(r["tour"])

        cenarios_frota[str(k)] = {
            "n_veiculos": k,
            "rotas": rotas_serializadas,
            "comparacao": comparacao,
        }
        print(
            f"VRP k={k}: makespan={comparacao['makespan_frota_min']:.1f} min "
            f"(ganho de {comparacao['ganho_makespan_pct']:.1f}% vs veiculo unico), "
            f"dist_total_frota={comparacao['dist_total_frota_km']:.1f} km"
        )

    # --- geometria real de todos os trechos utilizados em algum cenario ---
    arestas_unicas = coletar_arestas(todos_tours_para_arestas)
    print(f"Buscando geometria real de {len(arestas_unicas)} trechos unicos via OSRM...")
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
        },
        "municipios": municipios,
        "cenario_ingenuo": {
            "tour_ids": ingenua["tour"],
            "tour_nomes": [municipios_por_id[i]["nome"] for i in ingenua["tour"]],
            "dist_km": ingenua["dist_km"],
            "tempo_min": ingenua["tempo_min"],
        },
        "cenario_single_vehicle": {
            **rota_single,
            "ganho_2opt_sobre_nn_pct": resultado_tsp["ganho_2opt_pct"],
            "economia_vs_ingenua_pct": (ingenua["tempo_min"] - rota_single["tempo_min"]) / ingenua["tempo_min"] * 100,
        },
        "cenarios_frota": cenarios_frota,
        "arestas": arestas_serializadas,
    }

    os.makedirs(FRONTEND_DATA_DIR, exist_ok=True)
    out_path = os.path.join(FRONTEND_DATA_DIR, "solution.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)

    print(f"\nArquivo salvo em {out_path}")


if __name__ == "__main__":
    main()
