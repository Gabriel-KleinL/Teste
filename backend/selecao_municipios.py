"""
Selecao dos municipios representativos do Espirito Santo para o estudo de
otimizacao de rotas.

Fonte dos dados brutos (backend/data/municipios_es_78.json):
  - Coordenadas: dataset publico "kelvins/Municipios-Brasileiros" (derivado do IBGE)
  - Populacao residente estimada 2021: API de agregados do IBGE
    (agregado 6579, variavel 9324 - Populacao residente estimada)
    https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/2021/variaveis/9324

Criterio de selecao (justificado no relatorio academico):
  1. O Centro de Distribuicao (CD) fica fixo no municipio de Serra/ES, por ser
     o municipio mais populoso do estado e um polo logistico-industrial real
     da Grande Vitoria (regiao onde uma transportadora fictícia atuaria).
  2. Os demais municipios de entrega sao os N-1 mais populosos do estado,
     excluindo o CD. Populacao é usada como proxy de relevancia economica e
     logistica (maior populacao -> maior demanda de entregas, maior geracao
     de carga/comercio).
  3. Esse criterio, aplicado ao ES, produz naturalmente uma boa dispersao
     geografica entre as macrorregioes do estado (Metropolitana, Norte,
     Noroeste, Central Serrana e Sul), o que é verificado apos a selecao e
     reportado, em vez de forcado manualmente.
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CD_NOME = "Serra"
N_TOTAL = 25  # CD + 24 municipios de entrega (dentro da faixa 20-30 pedida)


def carregar_municipios_completos():
    with open(os.path.join(DATA_DIR, "municipios_es_78.json"), encoding="utf-8") as f:
        return json.load(f)


def selecionar_municipios():
    municipios = carregar_municipios_completos()
    sem_populacao = [m for m in municipios if m["populacao_2021"] is None]
    if sem_populacao:
        raise ValueError(f"Municipios sem populacao: {sem_populacao}")

    cd = next(m for m in municipios if m["nome"] == CD_NOME)
    demais = [m for m in municipios if m["nome"] != CD_NOME]
    demais_ordenados = sorted(demais, key=lambda m: -m["populacao_2021"])

    selecionados = [dict(cd, papel="CD")] + [
        dict(m, papel="entrega") for m in demais_ordenados[: N_TOTAL - 1]
    ]

    for i, m in enumerate(selecionados):
        m["id"] = i

    return selecionados


def resumo_regional(selecionados):
    """Classificacao aproximada por macrorregiao (apenas para o relatorio)."""
    regioes = {
        "Metropolitana": ["Serra", "Vitória", "Vila Velha", "Cariacica", "Viana", "Guarapari"],
        "Norte": ["Linhares", "São Mateus", "Aracruz", "Jaguaré", "Conceição da Barra", "Sooretama"],
        "Noroeste": ["Colatina", "Nova Venécia", "Barra de São Francisco", "São Gabriel da Palha", "Baixo Guandu"],
        "Central Serrana": ["Santa Maria de Jetibá", "Domingos Martins", "Afonso Cláudio"],
        "Sul": ["Cachoeiro de Itapemirim", "Castelo", "Itapemirim", "Marataízes", "Guaçuí"],
    }
    contagem = {r: 0 for r in regioes}
    for m in selecionados:
        for regiao, nomes in regioes.items():
            if m["nome"] in nomes:
                contagem[regiao] += 1
    return contagem


if __name__ == "__main__":
    selecionados = selecionar_municipios()
    out_path = os.path.join(DATA_DIR, "municipios_selecionados.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(selecionados, f, ensure_ascii=False, indent=2)

    print(f"{len(selecionados)} municipios selecionados (CD + {len(selecionados) - 1} de entrega)")
    print(f"CD: {selecionados[0]['nome']}")
    print("\nDistribuicao por macrorregiao:")
    for regiao, qtd in resumo_regional(selecionados).items():
        print(f"  {regiao}: {qtd}")
    print(f"\nSalvo em {out_path}")
