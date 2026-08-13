/**
 * Estado da aplicacao, orquestracao da simulacao (relogio simulado,
 * animacao dos veiculos) e renderizacao dos paineis de frota/resumo.
 */

const state = {
  nVeiculos: 1,
  maxFrota: 1,
  veiculos: [], // { idx, cor, tourNomes, municipiosAtendidos, distKm, tempoMin, trilha, departureMin, carMarker, status }
  simClockMin: 360, // 06:00
  playing: false,
  speedMinPorSeg: 20,
  showNaive: false,
  naiveTrilha: null,
  tempoSingleVehicleMin: null,
  tempoIngenuoMin: null,
  distIngenuoKm: null,
  lastFrameTs: null,
  lastPanelRefresh: 0,
};

function formatMin(min) {
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return `${h}h${String(m).padStart(2, "0")}min`;
}

function formatClock(absMin) {
  const dayOffset = Math.floor(absMin / 1440);
  const hh = String(Math.floor(absMin / 60) % 24).padStart(2, "0");
  const mm = String(Math.floor(absMin % 60)).padStart(2, "0");
  return dayOffset > 0 ? `${hh}:${mm} (dia ${dayOffset + 1})` : `${hh}:${mm}`;
}

function timeStrToMin(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

function minToTimeStr(min) {
  const h = String(Math.floor(min / 60) % 24).padStart(2, "0");
  const m = String(Math.floor(min % 60)).padStart(2, "0");
  return `${h}:${m}`;
}

// ---------------------------------------------------------------- cenario

function carregarCenario(n) {
  state.nVeiculos = Math.max(1, Math.min(n, state.maxFrota));

  const cenario = AppData.getCenario(state.nVeiculos);
  MapView.limparRotas();

  const trilhas = [];
  state.veiculos = cenario.rotas.map((r, idx) => {
    const trilha = AppData.montarTrilha(r.tourIds);
    const carMarker = MapView.desenharRota(idx, trilha, trilha.paradas);
    trilhas.push(trilha);
    return {
      idx,
      cor: MapView.corVeiculo(idx),
      tourNomes: r.tourNomes,
      municipiosAtendidos: r.municipiosAtendidos,
      distKm: r.distKm,
      tempoMin: r.tempoMin,
      trilha,
      departureMin: 480 + idx * 90, // padrao: 08:00, 09:30, 11:00, ...
      carMarker,
      status: "aguardando",
    };
  });

  MapView.ajustarZoomPara(trilhas);

  document.getElementById("fleet-size-display").textContent =
    state.nVeiculos === 1 ? "1 veículo" : `${state.nVeiculos} veículos`;

  resetarRelogio();
  renderFleetPanel();
  renderSummaryPanel();
  atualizarIngenua();
}

function atualizarIngenua() {
  MapView.limparIngenua();
  if (state.showNaive) {
    if (!state.naiveTrilha) {
      const ing = AppData.getCenarioIngenuo();
      state.naiveTrilha = AppData.montarTrilha(ing.tourIds);
    }
    MapView.desenharIngenua(state.naiveTrilha);
  }
}

// ---------------------------------------------------------------- painel de frota

function renderFleetPanel() {
  const container = document.getElementById("fleet-list");
  container.innerHTML = "";

  state.veiculos.forEach((v) => {
    const card = document.createElement("div");
    card.className = "vehicle-card";
    card.style.borderLeftColor = v.cor;

    const statusClass =
      v.status === "aguardando" ? "status-aguardando" : v.status === "em-rota" ? "status-em-rota" : "status-concluida";
    const statusLabel =
      v.status === "aguardando" ? "Aguardando saída" : v.status === "em-rota" ? "Em rota" : "Entrega concluída";

    const stopsHtml = v.municipiosAtendidos
      .map((nome, i) => {
        const parada = v.trilha.paradas[i];
        const visitado = state.simClockMin >= v.departureMin + parada.t;
        return `<li class="${visitado ? "visited" : ""}">${nome}</li>`;
      })
      .join("");

    card.innerHTML = `
      <div class="vehicle-card-header">
        <span class="vehicle-name"><span class="vehicle-dot" style="background:${v.cor}"></span>Veículo ${v.idx + 1}</span>
        <span class="vehicle-status ${statusClass}">${statusLabel}</span>
      </div>
      <div class="vehicle-departure">
        Saída do CD:
        <input type="time" value="${minToTimeStr(v.departureMin)}" data-idx="${v.idx}" class="input-departure" />
      </div>
      <div class="vehicle-meta">
        <span>Municípios: <b>${v.municipiosAtendidos.length}</b></span>
        <span>Distância: <b>${v.distKm.toFixed(0)} km</b></span>
        <span>Tempo estimado: <b>${formatMin(v.tempoMin)}</b></span>
      </div>
      <div class="vehicle-stops">
        <ol>${stopsHtml}</ol>
      </div>
    `;
    container.appendChild(card);
  });

  container.querySelectorAll(".input-departure").forEach((input) => {
    input.addEventListener("change", (e) => {
      const idx = Number(e.target.dataset.idx);
      state.veiculos[idx].departureMin = timeStrToMin(e.target.value);
    });
  });
}

// ---------------------------------------------------------------- painel de resumo

function renderSummaryPanel() {
  const grid = document.getElementById("summary-grid");
  const distTotal = state.veiculos.reduce((s, v) => s + v.distKm, 0);
  const municipiosTotal = state.veiculos.reduce((s, v) => s + v.municipiosAtendidos.length, 0);
  const makespan = Math.max(...state.veiculos.map((v) => v.departureMin - 480 + v.tempoMin));

  grid.innerHTML = `
    <div class="stat-card"><div class="stat-value">${state.nVeiculos}</div><div class="stat-label">Veículo(s) na frota</div></div>
    <div class="stat-card"><div class="stat-value">${municipiosTotal}</div><div class="stat-label">Municípios atendidos</div></div>
    <div class="stat-card"><div class="stat-value">${distTotal.toFixed(0)} km</div><div class="stat-label">Distância total da operação</div></div>
    <div class="stat-card"><div class="stat-value">${formatMin(makespan)}</div><div class="stat-label">Duração total da operação</div></div>
  `;

  const compare = document.getElementById("summary-compare");
  const tempoIngenuo = state.tempoIngenuoMin;
  const tempoSingle = state.tempoSingleVehicleMin;
  const tempoFrotaMakespan = Math.max(...state.veiculos.map((v) => v.tempoMin));
  const maxRef = Math.max(tempoIngenuo, tempoSingle);

  const economiaVsIngenua = ((tempoIngenuo - tempoFrotaMakespan) / tempoIngenuo) * 100;

  const bar = (label, value, cls) =>
    `<div class="compare-bar-row">
       <span class="compare-bar-label">${label}</span>
       <span class="compare-bar-track"><span class="compare-bar-fill ${cls}" style="width:${(value / maxRef) * 100}%"></span></span>
       <span class="compare-value">${formatMin(value)}</span>
     </div>`;

  compare.innerHTML = `
    <div class="compare-title">Comparação de tempo total (menor é melhor)</div>
    ${bar("Rota ingênua", tempoIngenuo, "naive")}
    ${bar("Veículo único", tempoSingle, "single")}
    ${bar(`Frota (${state.nVeiculos}v)`, tempoFrotaMakespan, "frota")}
    <div style="margin-top:8px;">
      Economia da frota atual vs. rota ingênua:
      <span class="economia-pct">${economiaVsIngenua.toFixed(1)}%</span>
    </div>
  `;
}

// ---------------------------------------------------------------- simulacao

function resetarRelogio() {
  state.simClockMin = 360;
  state.playing = false;
  state.lastFrameTs = null;
  document.getElementById("btn-play").textContent = "▶ Play";
  document.getElementById("btn-play").classList.remove("playing");
  atualizarPosicoes();
  document.getElementById("sim-clock-display").textContent = formatClock(state.simClockMin);
}

function atualizarPosicoes() {
  state.veiculos.forEach((v) => {
    const elapsed = state.simClockMin - v.departureMin;
    let status;
    let pos;

    if (elapsed < 0) {
      status = "aguardando";
      pos = v.trilha.pontos[0];
    } else if (elapsed >= v.trilha.tempoTotalMin) {
      status = "concluida";
      pos = v.trilha.pontos[v.trilha.pontos.length - 1];
    } else {
      status = "em-rota";
      pos = interpolarPosicao(v.trilha.pontos, elapsed);
    }

    v.status = status;
    MapView.moverCarro(v.carMarker, pos.lat, pos.lon);
  });
}

function interpolarPosicao(pontos, t) {
  // busca binaria pelo primeiro ponto com tempo >= t
  let lo = 0;
  let hi = pontos.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (pontos[mid].t < t) lo = mid + 1;
    else hi = mid;
  }
  if (lo === 0) return pontos[0];
  const b = pontos[lo];
  const a = pontos[lo - 1];
  const span = b.t - a.t;
  const frac = span > 0 ? (t - a.t) / span : 0;
  return { lat: a.lat + (b.lat - a.lat) * frac, lon: a.lon + (b.lon - a.lon) * frac };
}

function loopAnimacao(ts) {
  if (state.playing) {
    if (state.lastFrameTs != null) {
      const deltaS = (ts - state.lastFrameTs) / 1000;
      state.simClockMin += deltaS * state.speedMinPorSeg;
    }
    state.lastFrameTs = ts;

    atualizarPosicoes();
    document.getElementById("sim-clock-display").textContent = formatClock(state.simClockMin);

    if (ts - state.lastPanelRefresh > 600) {
      renderFleetPanel();
      state.lastPanelRefresh = ts;
    }
  } else {
    state.lastFrameTs = null;
  }
  requestAnimationFrame(loopAnimacao);
}

// ---------------------------------------------------------------- eventos de UI

function ligarEventos() {
  document.getElementById("btn-add-vehicle").addEventListener("click", () => {
    if (state.nVeiculos < state.maxFrota) carregarCenario(state.nVeiculos + 1);
  });
  document.getElementById("btn-remove-vehicle").addEventListener("click", () => {
    if (state.nVeiculos > 1) carregarCenario(state.nVeiculos - 1);
  });

  document.getElementById("btn-play").addEventListener("click", (e) => {
    state.playing = !state.playing;
    e.target.textContent = state.playing ? "⏸ Pause" : "▶ Play";
    e.target.classList.toggle("playing", state.playing);
  });

  document.getElementById("btn-reset").addEventListener("click", resetarRelogio);

  document.getElementById("sel-speed").addEventListener("change", (e) => {
    state.speedMinPorSeg = Number(e.target.value);
  });

  document.getElementById("chk-naive").addEventListener("change", (e) => {
    state.showNaive = e.target.checked;
    atualizarIngenua();
  });
}

// ---------------------------------------------------------------- boot

async function iniciar() {
  MapView.init();
  const solution = await AppData.carregar();

  MapView.desenharCD(AppData.getMunicipio(AppData.getCdId()));

  state.maxFrota = AppData.getMaxFrota();
  const ing = AppData.getCenarioIngenuo();
  state.tempoIngenuoMin = ing.tempoMin;
  state.distIngenuoKm = ing.distKm;
  state.tempoSingleVehicleMin = AppData.getCenario(1).rotas[0].tempoMin;

  ligarEventos();
  carregarCenario(1);

  document.getElementById("map-loading").style.display = "none";
  requestAnimationFrame(loopAnimacao);
}

iniciar().catch((err) => {
  console.error(err);
  document.getElementById("map-loading").textContent = "Erro ao carregar dados: " + err.message;
});
