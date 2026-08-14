"""
Preset padrao de municipios para o estudo de otimizacao de rotas.

Fonte dos dados brutos (backend/data/municipios_es_78.json):
  - Coordenadas: dataset publico "kelvins/Municipios-Brasileiros" (derivado do IBGE)
  - Populacao residente estimada 2021: API de agregados do IBGE
    (agregado 6579, variavel 9324 - Populacao residente estimada)
    https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/2021/variaveis/9324

Desde que a aplicacao web passou a permitir escolher livremente o Centro de
Distribuicao (CD) e os municipios de entrega entre os 78 do Espirito Santo
(ver frontend, seletor de localizacoes), este modulo nao filtra mais o
dataset: ele apenas define o PRESET PADRAO exibido ao usuario ao abrir a
aplicacao pela primeira vez, e usado pelo backend para pre-aquecer o cache
de geometria de rota (as combinacoes de trechos mais prováveis de serem
usadas). Os ids retornados sao os mesmos ids globais (0-77) usados em
todo o pipeline (municipios_es_78.json, ja ordenado e indexado).

Criterio do preset padrao (justificado no relatorio academico):
  1. O CD comeca fixado no municipio de Serra/ES, por ser o municipio mais
     populoso do estado e um polo logistico-industrial real da Grande
     Vitoria (regiao onde uma transportadora fictícia atuaria).
  2. Os demais municipios de entrega sugeridos sao os 24 mais populosos do
     estado, excluindo o CD. Populacao e usada como proxy de relevancia
     economica e logistica (maior populacao -> maior demanda de entregas).
  3. Esse criterio, aplicado ao ES, produz naturalmente uma boa dispersao
     geografica entre as macrorregioes do estado (Metropolitana, Norte,
     Noroeste, Central Serrana e Sul), o que e verificado a seguir.
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CD_NOME_PADRAO = "Serra"
N_ENTREGA_PADRAO = 24


def carregar_municipios_completos():
    with open(os.path.join(DATA_DIR, "municipios_es_78.json"), encoding="utf-8") as f:
        return json.load(f)


def preset_padrao(municipios):
    """Retorna (cd_id, entrega_ids) usando os ids globais (0-77)."""
    sem_populacao = [m for m in municipios if m["populacao_2021"] is None]
    if sem_populacao:
        raise ValueError(f"Municipios sem populacao: {sem_populacao}")

    cd = next(m for m in municipios if m["nome"] == CD_NOME_PADRAO)
    demais_ordenados = sorted(
        (m for m in municipios if m["id"] != cd["id"]), key=lambda m: -m["populacao_2021"]
    )
    entrega_ids = [m["id"] for m in demais_ordenados[:N_ENTREGA_PADRAO]]
    return cd["id"], entrega_ids


def resumo_regional(municipios_por_id, cd_id, entrega_ids):
    """Classificacao aproximada por macrorregiao (apenas para o relatorio)."""
    regioes = {
        "Metropolitana": ["Serra", "Vitória", "Vila Velha", "Cariacica", "Viana", "Guarapari"],
        "Norte": ["Linhares", "São Mateus", "Aracruz", "Jaguaré", "Conceição da Barra", "Sooretama"],
        "Noroeste": ["Colatina", "Nova Venécia", "Barra de São Francisco", "São Gabriel da Palha", "Baixo Guandu"],
        "Central Serrana": ["Santa Maria de Jetibá", "Domingos Martins", "Afonso Cláudio"],
        "Sul": ["Cachoeiro de Itapemirim", "Castelo", "Itapemirim", "Marataízes", "Guaçuí"],
    }
    contagem = {r: 0 for r in regioes}
    nomes_selecionados = [municipios_por_id[i]["nome"] for i in entrega_ids]
    for regiao, nomes in regioes.items():
        for nome in nomes_selecionados:
            if nome in nomes:
                contagem[regiao] += 1
    return contagem


if __name__ == "__main__":
    municipios = carregar_municipios_completos()
    municipios_por_id = {m["id"]: m for m in municipios}
    cd_id, entrega_ids = preset_padrao(municipios)

    print(f"Preset padrao: CD = {municipios_por_id[cd_id]['nome']} (id {cd_id})")
    print(f"{len(entrega_ids)} municipios de entrega sugeridos:")
    for i in entrega_ids:
        print(f"  - {municipios_por_id[i]['nome']} (id {i})")

    print("\nDistribuicao por macrorregiao:")
    for regiao, qtd in resumo_regional(municipios_por_id, cd_id, entrega_ids).items():
        print(f"  {regiao}: {qtd}")
