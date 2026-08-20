"""Contratos HTTP para o recálculo dinâmico de rotas."""
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class EntregaInput(BaseModel):
    codigo_ibge: str
    demanda: int = Field(default=1, ge=0)
    tempo_servico_min: int = Field(default=15, ge=0)
    janela_inicio: str = "08:00"
    janela_fim: str = "18:00"


class VeiculoInput(BaseModel):
    capacidade: int = Field(default=30, gt=0)
    horario_saida: str = "08:00"
    custo_km: float = Field(default=2.5, ge=0)
    custo_hora: float = Field(default=30, ge=0)


class OtimizacaoInput(BaseModel):
    entregas: list[EntregaInput] = Field(min_length=1)
    veiculos: list[VeiculoInput] = Field(min_length=1, max_length=20)
    solver: Literal["ortools", "sweep"] = "ortools"
    limite_tempo_s: int = Field(default=10, ge=1, le=60)

    @model_validator(mode="after")
    def validar(self):
        codigos = [e.codigo_ibge for e in self.entregas]
        if len(codigos) != len(set(codigos)):
            raise ValueError("Cada município deve aparecer apenas uma vez")
        if sum(e.demanda for e in self.entregas) > sum(v.capacidade for v in self.veiculos):
            raise ValueError("A capacidade total da frota é menor que a demanda total")
        for e in self.entregas:
            if hora_para_min(e.janela_inicio) > hora_para_min(e.janela_fim):
                raise ValueError(f"Janela inválida para {e.codigo_ibge}")
        return self


def hora_para_min(valor: str) -> int:
    try:
        hora, minuto = (int(p) for p in valor.split(":"))
        if not (0 <= hora <= 23 and 0 <= minuto <= 59):
            raise ValueError
        return hora * 60 + minuto
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Horário inválido: {valor!r}; use HH:MM") from exc
