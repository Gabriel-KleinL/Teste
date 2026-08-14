"""
Cliente de roteamento real de estrada.

Usa a API publica e gratuita do OSRM (Open Source Routing Machine),
instancia de demonstracao http://router.project-osrm.org, para obter:
  - matriz completa de distancia (m) e duracao (s) entre todos os pares de
    municipios selecionados, via servico /table (uma unica requisicao);
  - a geometria real (sequencia de coordenadas seguindo as rodovias) de cada
    trecho efetivamente utilizado nas rotas finais, via servico /route.

Todas as respostas sao cacheadas em disco (backend/cache/) para tornar as
execucoes seguintes deterministicas e independentes de disponibilidade de
rede, e para nao sobrecarregar o servidor publico de demonstracao.

Limitacao assumida (ver relatorio): a instancia publica do OSRM é um servico
de demonstracao, sem SLA, com limite informal de uso e sem oferecer chave de
API. Caso a rede esteja indisponivel ou o servico retorne erro, o modulo cai
automaticamente para uma aproximacao por distancia Haversine (linha reta
corrigida por um fator de sinuosidade media rodoviaria), deixando isso
explicito nos metadados salvos em solution.json.
"""
import hashlib
import json
import math
import os
import time

import requests

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

OSRM_BASE_URL = "http://router.project-osrm.org"
FATOR_SINUOSIDADE = 1.30  # correcao empirica media entre linha reta e rodovia
VELOCIDADE_MEDIA_KMH = 60.0  # usada apenas no fallback haversine


class RoutingUnavailableError(Exception):
    pass


def _cache_path(chave: str) -> str:
    h = hashlib.sha1(chave.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.json")


def _cache_get(chave: str):
    path = _cache_path(chave)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _cache_set(chave: str, valor):
    with open(_cache_path(chave), "w", encoding="utf-8") as f:
        json.dump(valor, f)


def _distancia_ponto_segmento(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    proj_x, proj_y = ax + t * dx, ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def simplificar_geometria(pontos, tolerancia_graus=0.0008):
    """
    Simplificacao de Ramer-Douglas-Peucker (iterativa, sem dependencias
    externas). Reduz drasticamente o numero de vertices de uma polilinha
    mantendo sua forma visual, o que e essencial para manter o solution.json
    em tamanho razoavel dado que o OSRM retorna geometrias com milhares de
    pontos por trecho. Tolerancia em graus (~0.0008 grau ~ 90 m), imperceptivel
    na escala de visualizacao de um mapa estadual.
    """
    if len(pontos) <= 2:
        return pontos

    manter = [False] * len(pontos)
    manter[0] = manter[-1] = True
    pilha = [(0, len(pontos) - 1)]

    while pilha:
        ini, fim = pilha.pop()
        if fim - ini < 2:
            continue
        a, b = pontos[ini], pontos[fim]
        max_dist, idx_max = -1.0, -1
        for i in range(ini + 1, fim):
            d = _distancia_ponto_segmento(pontos[i], a, b)
            if d > max_dist:
                max_dist, idx_max = d, i
        if max_dist > tolerancia_graus:
            manter[idx_max] = True
            pilha.append((ini, idx_max))
            pilha.append((idx_max, fim))

    return [p for p, k in zip(pontos, manter) if k]


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def obter_matriz_osrm(municipios, usar_fallback_se_falhar=True):
    """
    Retorna (dist_km_matrix, tempo_min_matrix, fonte) para a lista de
    municipios (cada um com 'lat' e 'lon'), usando o servico /table do OSRM
    numa unica requisicao. Cai para haversine em caso de falha de rede.
    """
    n = len(municipios)
    chave = "table_" + "_".join(f"{m['lat']:.5f},{m['lon']:.5f}" for m in municipios)
    cached = _cache_get(chave)
    if cached is not None:
        return cached["dist_km"], cached["tempo_min"], cached["fonte"]

    coords = ";".join(f"{m['lon']},{m['lat']}" for m in municipios)
    url = f"{OSRM_BASE_URL}/table/v1/driving/{coords}?annotations=distance,duration"

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "Ok":
            raise RoutingUnavailableError(data.get("message", "erro OSRM /table"))
        dist_km = [[v / 1000.0 for v in linha] for linha in data["distances"]]
        tempo_min = [[v / 60.0 for v in linha] for linha in data["durations"]]
        fonte = "osrm_table"
    except Exception as exc:  # rede indisponivel, timeout, HTTP erro, etc.
        if not usar_fallback_se_falhar:
            raise
        print(f"[routing] Aviso: falha ao consultar OSRM /table ({exc}). Usando fallback Haversine.")
        dist_km = [[0.0] * n for _ in range(n)]
        tempo_min = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                d = haversine_km(municipios[i]["lat"], municipios[i]["lon"], municipios[j]["lat"], municipios[j]["lon"])
                d_rodovia = d * FATOR_SINUOSIDADE
                dist_km[i][j] = d_rodovia
                tempo_min[i][j] = (d_rodovia / VELOCIDADE_MEDIA_KMH) * 60.0
        fonte = "haversine_fallback"

    _cache_set(chave, {"dist_km": dist_km, "tempo_min": tempo_min, "fonte": fonte})
    return dist_km, tempo_min, fonte


def obter_geometria_rota(origem, destino, usar_fallback_se_falhar=True):
    """
    Retorna (lista_de_[lat,lon], distancia_km, tempo_min, fonte) para o
    trecho rodoviario real entre origem e destino (dicts com 'lat'/'lon'),
    via servico /route do OSRM (overview completo, geometria em GeoJSON).
    """
    chave = f"route_{origem['lat']:.5f},{origem['lon']:.5f}_{destino['lat']:.5f},{destino['lon']:.5f}"
    cached = _cache_get(chave)
    if cached is not None:
        return cached["geometria"], cached["dist_km"], cached["tempo_min"], cached["fonte"]

    coords = f"{origem['lon']},{origem['lat']};{destino['lon']},{destino['lat']}"
    url = f"{OSRM_BASE_URL}/route/v1/driving/{coords}?overview=full&geometries=geojson"

    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "Ok":
            raise RoutingUnavailableError(data.get("message", "erro OSRM /route"))
        rota = data["routes"][0]
        geometria_bruta = [[lat, lon] for lon, lat in rota["geometry"]["coordinates"]]
        geometria_simplificada = simplificar_geometria(geometria_bruta)
        geometria = [[round(lat, 5), round(lon, 5)] for lat, lon in geometria_simplificada]
        dist_km = rota["distance"] / 1000.0
        tempo_min = rota["duration"] / 60.0
        fonte = "osrm_route"
    except Exception as exc:
        if not usar_fallback_se_falhar:
            raise
        print(f"[routing] Aviso: falha ao consultar OSRM /route ({exc}). Usando linha reta (fallback).")
        d = haversine_km(origem["lat"], origem["lon"], destino["lat"], destino["lon"])
        d_rodovia = d * FATOR_SINUOSIDADE
        geometria = [[origem["lat"], origem["lon"]], [destino["lat"], destino["lon"]]]
        dist_km = d_rodovia
        tempo_min = (d_rodovia / VELOCIDADE_MEDIA_KMH) * 60.0
        fonte = "haversine_fallback"

    _cache_set(chave, {"geometria": geometria, "dist_km": dist_km, "tempo_min": tempo_min, "fonte": fonte})
    return geometria, dist_km, tempo_min, fonte


def obter_geometrias_em_lote(pares, municipios_por_id, pausa_s=0.15):
    """
    pares: lista de tuplas (id_origem, id_destino).
    Retorna dict {(id_origem, id_destino): {geometria, dist_km, tempo_min, fonte}}.
    Aplica uma pequena pausa entre chamadas nao cacheadas para ser gentil com
    o servidor publico de demonstracao do OSRM.
    """
    resultado = {}
    for (i, j) in pares:
        chave_cache = f"route_{municipios_por_id[i]['lat']:.5f},{municipios_por_id[i]['lon']:.5f}_{municipios_por_id[j]['lat']:.5f},{municipios_por_id[j]['lon']:.5f}"
        ja_em_cache = _cache_get(chave_cache) is not None
        geometria, dist_km, tempo_min, fonte = obter_geometria_rota(municipios_por_id[i], municipios_por_id[j])
        resultado[(i, j)] = {
            "geometria": geometria,
            "dist_km": dist_km,
            "tempo_min": tempo_min,
            "fonte": fonte,
        }
        if not ja_em_cache and fonte == "osrm_route":
            time.sleep(pausa_s)
    return resultado
