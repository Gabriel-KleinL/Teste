"""Serviço compartilhado pela FastAPI e por testes de integração."""
import json
import os

from api_models import hora_para_min
from graph_builder import construir_grafo
from ortools_solver import SolverIndisponivel, resolver_ortools
from routing import obter_geometrias_em_lote
from tsp import custo_total, resolver_tsp
from vrp import resolver_vrp

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def carregar_catalogo():
    with open(os.path.join(DATA_DIR, "municipios_es_78.json"), encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _serializar_rota(base, municipios, matriz_dist, matriz_tempo, entregas, veiculo):
    tour = base["tour"]
    por_id = {m["id"]: m for m in municipios}
    demanda = {i + 1: e.demanda for i, e in enumerate(entregas)}
    servico = {i + 1: e.tempo_servico_min for i, e in enumerate(entregas)}
    saida = base.get("saida_min", hora_para_min(veiculo.horario_saida))
    paradas, relogio = [], saida
    if base.get("paradas"):
        paradas = [dict(p, nome=por_id[p["id"]]["nome"], demanda=demanda[p["id"]]) for p in base["paradas"]]
    else:
        for anterior, atual in zip(tour, tour[1:]):
            relogio += matriz_tempo[anterior][atual]
            if atual != 0:
                inicio = relogio
                paradas.append({
                    "id": atual,
                    "nome": por_id[atual]["nome"],
                    "chegada_min": relogio,
                    "inicio_servico_min": inicio,
                    "fim_servico_min": inicio + servico[atual],
                    "demanda": demanda[atual],
                })
                relogio += servico[atual]
    fim = base.get("fim_min", relogio)
    dist = custo_total(tour, matriz_dist)
    carga = base.get("carga", sum(demanda.get(i, 0) for i in tour))
    return {
        "veiculo": base["veiculo"], "tour_ids": tour,
        "tour_nomes": [por_id[i]["nome"] for i in tour],
        "municipios_atendidos": [por_id[i]["nome"] for i in tour[1:-1]],
        "dist_km": dist, "tempo_min": fim - saida, "saida_min": saida,
        "fim_min": fim, "carga": carga, "capacidade": veiculo.capacidade,
        "utilizacao_pct": carga / veiculo.capacidade * 100, "paradas": paradas,
        "custo_estimado": dist * veiculo.custo_km + (fim - saida) / 60 * veiculo.custo_hora,
    }


def otimizar(requisicao):
    catalogo = {m["codigo_ibge"]: m for m in carregar_catalogo()}
    if any(e.codigo_ibge not in catalogo for e in requisicao.entregas):
        raise ValueError("Um ou mais códigos IBGE não pertencem ao Espírito Santo")
    cd = dict(catalogo["3205002"], papel="CD", id=0)
    selecionados = [cd] + [dict(catalogo[e.codigo_ibge], papel="entrega", id=i + 1) for i, e in enumerate(requisicao.entregas)]
    _, matriz_dist, matriz_tempo, fonte = construir_grafo(selecionados)
    por_id = {m["id"]: m for m in selecionados}
    indices = list(range(1, len(selecionados)))

    tsp = resolver_tsp(indices, 0, matriz_tempo)
    ingenua_tour = [0] + indices + [0]
    solver_usado, aviso = requisicao.solver, None
    if requisicao.solver == "ortools":
        try:
            brutas = resolver_ortools(selecionados, matriz_dist, matriz_tempo, requisicao.entregas, requisicao.veiculos, requisicao.limite_tempo_s)
        except SolverIndisponivel as exc:
            solver_usado, aviso = "sweep_fallback", str(exc)
            brutas = resolver_vrp(indices, 0, por_id, matriz_dist, matriz_tempo, len(requisicao.veiculos))
    else:
        brutas = resolver_vrp(indices, 0, por_id, matriz_dist, matriz_tempo, len(requisicao.veiculos))

    usados = {r["veiculo"] for r in brutas}
    for idx, veiculo in enumerate(requisicao.veiculos):
        if idx not in usados:
            saida = hora_para_min(veiculo.horario_saida)
            brutas.append({"veiculo": idx, "tour": [0, 0], "saida_min": saida, "fim_min": saida, "carga": 0})
    brutas.sort(key=lambda r: r["veiculo"])

    rotas = [_serializar_rota(r, selecionados, matriz_dist, matriz_tempo, requisicao.entregas, requisicao.veiculos[r["veiculo"]]) for r in brutas]
    sweep_brutas = resolver_vrp(indices, 0, por_id, matriz_dist, matriz_tempo, len(requisicao.veiculos))
    usados_sweep = {r["veiculo"] for r in sweep_brutas}
    for idx, veiculo in enumerate(requisicao.veiculos):
        if idx not in usados_sweep:
            saida = hora_para_min(veiculo.horario_saida)
            sweep_brutas.append({"veiculo": idx, "tour": [0, 0], "saida_min": saida, "fim_min": saida, "carga": 0})
    sweep_brutas.sort(key=lambda r: r["veiculo"])
    sweep_rotas = [_serializar_rota(r, selecionados, matriz_dist, matriz_tempo, requisicao.entregas, requisicao.veiculos[r["veiculo"]]) for r in sweep_brutas]
    arestas = {(a, b) for r in rotas for a, b in zip(r["tour_ids"], r["tour_ids"][1:]) if a != b}
    geometrias = obter_geometrias_em_lote(sorted(arestas), por_id, pausa_s=0)
    arestas_json = {f"{a}-{b}": info for (a, b), info in geometrias.items()}

    rotas_ativas = [r for r in rotas if r["carga"] > 0]
    inicio_operacao = min(r["saida_min"] for r in rotas_ativas)
    fim_operacao = max(r["fim_min"] for r in rotas_ativas)
    dist_total = sum(r["dist_km"] for r in rotas)
    tempo_motoristas = sum(r["tempo_min"] for r in rotas)
    metricas = {
        "distancia_total_km": dist_total,
        "tempo_total_motoristas_min": tempo_motoristas,
        "makespan_min": fim_operacao - inicio_operacao,
        "inicio_operacao_min": inicio_operacao, "fim_operacao_min": fim_operacao,
        "utilizacao_frota_pct": sum(r["carga"] for r in rotas) / sum(r["capacidade"] for r in rotas) * 100,
        "carga_total": sum(r["carga"] for r in rotas),
        "capacidade_total": sum(r["capacidade"] for r in rotas),
        "custo_estimado": sum(r["custo_estimado"] for r in rotas),
    }
    return {
        "meta": {"cd_id": 0, "cd_nome": cd["nome"], "n_municipios_entrega": len(indices), "fonte_matriz_distancias": fonte, "solver": solver_usado, "aviso": aviso},
        "municipios": selecionados,
        "cenario_ingenuo": {"tour_ids": ingenua_tour, "tour_nomes": [por_id[i]["nome"] for i in ingenua_tour], "dist_km": custo_total(ingenua_tour, matriz_dist), "tempo_min": custo_total(ingenua_tour, matriz_tempo)},
        "cenario_single_vehicle": {"tour_ids": tsp["tour"], "tour_nomes": [por_id[i]["nome"] for i in tsp["tour"]], "dist_km": custo_total(tsp["tour"], matriz_dist), "tempo_min": custo_total(tsp["tour"], matriz_tempo), "ganho_2opt_sobre_nn_pct": tsp["ganho_2opt_pct"]},
        "cenarios_frota": {str(len(requisicao.veiculos)): {"n_veiculos": len(requisicao.veiculos), "rotas": rotas, "metricas": metricas}},
        "baseline_sweep": {"rotas": sweep_rotas, "makespan_min": max(r["fim_min"] for r in sweep_rotas if r["carga"] > 0) - min(r["saida_min"] for r in sweep_rotas if r["carga"] > 0)},
        "arestas": arestas_json,
    }
