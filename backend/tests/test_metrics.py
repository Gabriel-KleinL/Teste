import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.modules.setdefault("networkx", types.ModuleType("networkx"))
sys.modules.setdefault("requests", types.ModuleType("requests"))

from api_models import EntregaInput, OtimizacaoInput, VeiculoInput
import optimization_service
from optimization_service import _serializar_rota
from ortools_solver import SolverIndisponivel


class MetricsTest(unittest.TestCase):
    def test_rota_respeita_saida_real(self):
        municipios = [{"id": 0, "nome": "CD"}, {"id": 1, "nome": "Entrega"}]
        matriz = [[0, 30], [30, 0]]
        rota = _serializar_rota(
            {"veiculo": 0, "tour": [0, 1, 0]}, municipios, matriz, matriz,
            [EntregaInput(codigo_ibge="x", demanda=2, tempo_servico_min=15)],
            VeiculoInput(capacidade=5, horario_saida="10:00"),
        )
        self.assertEqual(rota["saida_min"], 600)
        self.assertEqual(rota["fim_min"], 675)
        self.assertEqual(rota["tempo_min"], 75)

    def test_servico_entrega_envelope_compativel_com_frontend(self):
        original = (
            optimization_service.construir_grafo,
            optimization_service.resolver_ortools,
            optimization_service.obter_geometrias_em_lote,
        )
        optimization_service.construir_grafo = lambda ms: (None, [[0, 10], [10, 0]], [[0, 20], [20, 0]], "teste")
        optimization_service.resolver_ortools = lambda *args, **kwargs: (_ for _ in ()).throw(SolverIndisponivel("teste"))
        optimization_service.obter_geometrias_em_lote = lambda pares, ms, pausa_s=0: {
            p: {"geometria": [[ms[p[0]]["lat"], ms[p[0]]["lon"]], [ms[p[1]]["lat"], ms[p[1]]["lon"]]], "dist_km": 10, "tempo_min": 20, "fonte": "teste"}
            for p in pares
        }
        try:
            result = optimization_service.otimizar(OtimizacaoInput(
                entregas=[EntregaInput(codigo_ibge="3205200", demanda=2, tempo_servico_min=15)],
                veiculos=[VeiculoInput(capacidade=5, horario_saida="10:00")],
            ))
        finally:
            (optimization_service.construir_grafo, optimization_service.resolver_ortools,
             optimization_service.obter_geometrias_em_lote) = original
        self.assertEqual(result["meta"]["solver"], "sweep_fallback")
        self.assertIn("1", result["cenarios_frota"])
        self.assertEqual(result["cenarios_frota"]["1"]["metricas"]["makespan_min"], 55)


if __name__ == "__main__":
    unittest.main()
