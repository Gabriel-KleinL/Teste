import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api_models import EntregaInput, OtimizacaoInput, VeiculoInput, hora_para_min


class ApiModelsTest(unittest.TestCase):
    def test_hora_para_min(self):
        self.assertEqual(hora_para_min("08:30"), 510)

    def test_rejeita_frota_sem_capacidade(self):
        with self.assertRaises(ValueError):
            OtimizacaoInput(
                entregas=[EntregaInput(codigo_ibge="3205200", demanda=11)],
                veiculos=[VeiculoInput(capacidade=10)],
            )

    def test_aceita_partidas_diferentes(self):
        req = OtimizacaoInput(
            entregas=[EntregaInput(codigo_ibge="3205200", demanda=2)],
            veiculos=[VeiculoInput(capacidade=2, horario_saida="08:00"), VeiculoInput(capacidade=2, horario_saida="10:00")],
        )
        self.assertEqual(req.veiculos[1].horario_saida, "10:00")


if __name__ == "__main__":
    unittest.main()
