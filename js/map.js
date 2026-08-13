/**
 * Camada de visualizacao no mapa (Leaflet). Responsavel por desenhar o
 * Centro de Distribuicao, as rotas reais de cada veiculo (geometria vinda
 * do OSRM), as paradas de entrega e os icones de carro animados.
 */

const MapView = (() => {
  const CORES_VEICULO = ["#2f6fb0", "#16a34a", "#d97706", "#7c3aed", "#0891b2", "#be185d"];

  let map = null;
  let cdMarker = null;
  let camadaRotas = null; // L.layerGroup com polylines + paradas
  let camadaCarros = null; // L.layerGroup com icones de carro
  let camadaIngenua = null;

  function init() {
    map = L.map("map", { zoomControl: true }).setView([-19.6, -40.5], 8);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    camadaRotas = L.layerGroup().addTo(map);
    camadaCarros = L.layerGroup().addTo(map);
    camadaIngenua = L.layerGroup().addTo(map);

    return map;
  }

  function corVeiculo(idx) {
    return CORES_VEICULO[idx % CORES_VEICULO.length];
  }

  function desenharCD(municipioCd) {
    if (cdMarker) map.removeLayer(cdMarker);
    const icon = L.divIcon({
      className: "",
      html: '<div class="cd-icon" title="Centro de Distribuição">🏭</div>',
      iconSize: [30, 30],
      iconAnchor: [15, 22],
    });
    cdMarker = L.marker([municipioCd.lat, municipioCd.lon], { icon, zIndexOffset: 1000 })
      .addTo(map)
      .bindPopup(`<b>Centro de Distribuição</b><br>${municipioCd.nome}/ES`);
  }

  function limparRotas() {
    camadaRotas.clearLayers();
    camadaCarros.clearLayers();
  }

  function limparIngenua() {
    camadaIngenua.clearLayers();
  }

  /**
   * Desenha a rota real de um veiculo (polyline seguindo a rodovia) e as
   * paradas de entrega. Retorna o marcador do carro (para ser movido pela
   * simulacao em main.js).
   */
  function desenharRota(veiculoIdx, trilha, paradas) {
    const cor = corVeiculo(veiculoIdx);
    const latlngs = trilha.pontos.map((p) => [p.lat, p.lon]);

    L.polyline(latlngs, { color: cor, weight: 4, opacity: 0.85 }).addTo(camadaRotas);

    paradas.forEach((parada, ordem) => {
      const m = AppData.getMunicipio(parada.id);
      L.circleMarker([m.lat, m.lon], {
        radius: 6,
        color: "#fff",
        weight: 2,
        fillColor: cor,
        fillOpacity: 1,
      })
        .bindTooltip(`${ordem + 1}. ${m.nome}`, { direction: "top" })
        .addTo(camadaRotas);
    });

    const carIcon = L.divIcon({
      className: "",
      html: `<div class="car-icon" style="color:${cor}">🚚</div>`,
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });

    const carMarker = L.marker(latlngs[0], { icon: carIcon, zIndexOffset: 2000 }).addTo(camadaCarros);
    return carMarker;
  }

  function desenharIngenua(trilha) {
    const latlngs = trilha.pontos.map((p) => [p.lat, p.lon]);
    L.polyline(latlngs, {
      color: "#5b6b76",
      weight: 3,
      opacity: 0.7,
      dashArray: "6 8",
    })
      .bindTooltip("Rota ingênua (sem otimização)")
      .addTo(camadaIngenua);
  }

  function moverCarro(carMarker, lat, lon) {
    carMarker.setLatLng([lat, lon]);
  }

  function ajustarZoomPara(rotas) {
    const bounds = [];
    rotas.forEach((t) => t.pontos.forEach((p) => bounds.push([p.lat, p.lon])));
    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
  }

  return {
    init,
    desenharCD,
    limparRotas,
    limparIngenua,
    desenharRota,
    desenharIngenua,
    moverCarro,
    corVeiculo,
    ajustarZoomPara,
    getMap: () => map,
  };
})();
