"""CVRPTW com capacidade, serviço, janelas e partidas independentes."""
from api_models import hora_para_min


class SolverIndisponivel(RuntimeError):
    pass


def resolver_ortools(municipios, matriz_dist, matriz_tempo, entregas, veiculos, limite_tempo_s=10):
    try:
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    except ImportError as exc:
        raise SolverIndisponivel("Google OR-Tools não está instalado") from exc

    n_veiculos = len(veiculos)
    manager = pywrapcp.RoutingIndexManager(len(municipios), n_veiculos, 0)
    routing = pywrapcp.RoutingModel(manager)
    servicos = [0] + [e.tempo_servico_min for e in entregas]
    demandas = [0] + [e.demanda for e in entregas]

    def custo_tempo(from_index, to_index):
        i, j = manager.IndexToNode(from_index), manager.IndexToNode(to_index)
        return round((matriz_tempo[i][j] + servicos[i]) * 60)

    tempo_cb = routing.RegisterTransitCallback(custo_tempo)
    routing.SetArcCostEvaluatorOfAllVehicles(tempo_cb)

    demanda_cb = routing.RegisterUnaryTransitCallback(lambda index: demandas[manager.IndexToNode(index)])
    routing.AddDimensionWithVehicleCapacity(
        demanda_cb, 0, [v.capacidade for v in veiculos], True, "Carga"
    )

    routing.AddDimension(tempo_cb, 24 * 60 * 60, 48 * 60 * 60, False, "Tempo")
    dimensao_tempo = routing.GetDimensionOrDie("Tempo")
    for node, entrega in enumerate(entregas, start=1):
        index = manager.NodeToIndex(node)
        dimensao_tempo.CumulVar(index).SetRange(
            hora_para_min(entrega.janela_inicio) * 60,
            hora_para_min(entrega.janela_fim) * 60,
        )
    for idx, veiculo in enumerate(veiculos):
        partida = hora_para_min(veiculo.horario_saida) * 60
        dimensao_tempo.CumulVar(routing.Start(idx)).SetRange(partida, partida)
        dimensao_tempo.CumulVar(routing.End(idx)).SetRange(partida, 48 * 60 * 60)
        routing.AddVariableMinimizedByFinalizer(dimensao_tempo.CumulVar(routing.End(idx)))

    parametros = pywrapcp.DefaultRoutingSearchParameters()
    parametros.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    parametros.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    parametros.time_limit.seconds = limite_tempo_s
    solucao = routing.SolveWithParameters(parametros)
    if not solucao:
        raise ValueError("Nenhuma solução atende capacidade, horários e janelas informados")

    rotas = []
    for veiculo_idx in range(n_veiculos):
        index = routing.Start(veiculo_idx)
        tour, paradas = [], []
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            tour.append(node)
            chegada = solucao.Value(dimensao_tempo.CumulVar(index)) / 60
            if node:
                inicio = chegada
                paradas.append({
                    "id": node,
                    "chegada_min": chegada,
                    "inicio_servico_min": inicio,
                    "fim_servico_min": inicio + servicos[node],
                })
            index = solucao.Value(routing.NextVar(index))
        tour.append(0)
        fim = solucao.Value(dimensao_tempo.CumulVar(index)) / 60
        if len(tour) > 2:
            rotas.append({
                "veiculo": veiculo_idx,
                "tour": tour,
                "paradas": paradas,
                "carga": sum(demandas[i] for i in tour[1:-1]),
                "capacidade": veiculos[veiculo_idx].capacidade,
                "saida_min": hora_para_min(veiculos[veiculo_idx].horario_saida),
                "fim_min": fim,
            })
    return rotas
