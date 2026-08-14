/**
 * Estado da aplicacao, orquestracao da simulacao (relogio simulado,
 * animacao dos veiculos) e renderizacao dos paineis de frota/resumo.
 *
 * O numero de veiculos e livremente customizavel pelo usuario (qualquer
 * quantidade). O VRP e resolvido ao vivo no navegador (js/otimizacao.js)
 * sobre a matriz completa de tempo/distancia real embutida em
 * solution.json. Dois indicadores avisam o usuario quando a frota
 * escolhida excede o necessario:
 *   - "veiculos ociosos": quando ha mais veiculos do que municipios de
 *     entrega, o excedente fica sem rota atribuida.
 *   - "sem ganho": quando o veiculo adicional nao reduziu o tempo total
 *     da operacao (makespan) em relacao a um veiculo a menos - situacao
 *     real observada neste problema (ver relatorio, ex.: k=6 e k=7 ou
 *     k=9,10,11 empatam no makespan).
 */

const state = {
  cdId: null, // id do municipio-sede do Centro de Distribuicao (customizavel)
  entregaIds: [], // ids dos municipios de entrega ativos (customizavel)
  nVeiculosSolicitados: 1,
  rotas: [], // { idx, cor, tourNomes, municipiosAtendidos, distKm, tempoMin, trilha, departureMin, carMarker, status, idle }
  simClockMin: 360, // 06:00
  playing: false,
  speedMinPorSeg: 20,
  showNaive: false,
  naiveTrilha: null,
  tempoIngenuoMin: null,
  distIngenuoKm: null,
  makespanCache: {}, // n -> makespan (so tempo, sem geometria) para detectar "sem ganho" - invalidado ao mudar a selecao
  lastFrameTs: null,
  lastPanelRefresh: 0,
  carregando: false,
  seletor: { cdTemp: null, entregaTemp: null, filtro: "" }, // estado temporario do modal de localizacoes
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

// ---------------------------------------------------------------- calculo (puro, sem geometria)

/** Calcula so o makespan (mais rapido, sem buscar geometria) - usado para comparacoes. */
function calcularMakespan(n) {
  if (state.makespanCache[n] !== undefined) return state.makespanCache[n];
  const { rotas } = Otimizacao.resolverVRP(
    state.entregaIds,
    state.cdId,
    AppData.getMunicipiosPorId(),
    AppData.getMatrizDist(),
    AppData.getMatrizTempo(),
    n
  );
  const makespan = Math.max(...rotas.map((r) => r.tempoMin));
  state.makespanCache[n] = makespan;
  return makespan;
}

/** Recalcula a linha de base "ingenua" e limpa caches dependentes da selecao de municipios/CD. */
function recalcularBaseline() {
  state.makespanCache = {};
  state.naiveTrilha = null;
  const ing = AppData.getCenarioIngenuo(state.cdId, state.entregaIds);
  state.tempoIngenuoMin = ing.tempoMin;
  state.distIngenuoKm = ing.distKm;
}

// ---------------------------------------------------------------- cenario

async function gerarCenario(nSolicitado) {
  const n = Math.max(1, Math.round(nSolicitado));
  state.nVeiculosSolicitados = n;
  state.carregando = true;
  document.getElementById("map-loading").style.display = "flex";
  document.getElementById("map-loading").textContent = "Calculando rotas…";

  const cdIdx = state.cdId;
  const indicesEntrega = state.entregaIds;
  const municipiosPorId = AppData.getMunicipiosPorId();
  const matrizDist = AppData.getMatrizDist();
  const matrizTempo = AppData.getMatrizTempo();

  const { rotas: rotasBrutas, nUtil, nIdle } = Otimizacao.resolverVRP(
    indicesEntrega,
    cdIdx,
    municipiosPorId,
    matrizDist,
    matrizTempo,
    n
  );
  state.makespanCache[nUtil] = Math.max(...rotasBrutas.filter((r) => !r.idle).map((r) => r.tempoMin));

  // garante a geometria real (cache pre-aquecido ou busca ao vivo no OSRM) de todos os trechos usados
  const paresNecessarios = [];
  rotasBrutas.forEach((r) => {
    for (let k = 0; k < r.tourIds.length - 1; k++) {
      if (r.tourIds[k] !== r.tourIds[k + 1]) paresNecessarios.push([r.tourIds[k], r.tourIds[k + 1]]);
    }
  });
  await AppData.garantirArestas(paresNecessarios, (feitos, total) => {
    document.getElementById("map-loading").textContent = `Buscando rotas reais no OSRM… (${feitos}/${total})`;
  });

  MapView.limparRotas();
  const trilhas = [];
  state.rotas = rotasBrutas.map((r, idx) => {
    const trilha = AppData.montarTrilha(r.tourIds);
    let carMarker = null;
    if (!r.idle) {
      carMarker = MapView.desenharRota(idx, trilha, trilha.paradas);
      trilhas.push(trilha);
    }
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
      status: r.idle ? "ocioso" : "aguardando",
      idle: r.idle,
    };
  });

  if (trilhas.length) MapView.ajustarZoomPara(trilhas);

  atualizarDisplayFrota(n);
  atualizarBanner(n, nUtil, nIdle);

  resetarRelogio();
  renderFleetPanel();
  renderSummaryPanel();
  atualizarIngenua();

  state.carregando = false;
  document.getElementById("map-loading").style.display = "none";
}

function atualizarDisplayFrota(n) {
  document.getElementById("input-fleet-size").value = n;
  document.getElementById("fleet-size-suffix").textContent = n === 1 ? "veículo" : "veículos";
}

function atualizarBanner(nSolicitado, nUtil, nIdle) {
  const banner = document.getElementById("fleet-banner");

  if (nIdle > 0) {
    banner.hidden = false;
    banner.className = "fleet-banner banner-idle";
    banner.textContent =
      `⚠ Você configurou ${nSolicitado} veículos, mas há apenas ${state.entregaIds.length} municípios de entrega. ` +
      `${nIdle} veículo(s) ficará(ão) parado(s) no CD, sem rota atribuída — não são necessários para esta operação.`;
    return;
  }

  if (nUtil > 1) {
    const makespanAtual = state.makespanCache[nUtil];
    const makespanAnterior = calcularMakespan(nUtil - 1);
    if (makespanAtual >= makespanAnterior - 1e-6) {
      banner.hidden = false;
      banner.className = "fleet-banner banner-no-gain";
      banner.textContent =
        `ℹ Adicionar este veículo (${nUtil}ª unidade) não reduziu o tempo total da operação ` +
        `em relação a ${nUtil - 1} veículo(s) (${formatMin(makespanAnterior)} → ${formatMin(makespanAtual)}). ` +
        `A frota atual já é suficiente.`;
      return;
    }
  }

  banner.hidden = true;
}

async function atualizarIngenua() {
  MapView.limparIngenua();
  if (state.showNaive) {
    if (!state.naiveTrilha) {
      const ing = AppData.getCenarioIngenuo(state.cdId, state.entregaIds);
      const pares = [];
      for (let k = 0; k < ing.tourIds.length - 1; k++) {
        if (ing.tourIds[k] !== ing.tourIds[k + 1]) pares.push([ing.tourIds[k], ing.tourIds[k + 1]]);
      }
      await AppData.garantirArestas(pares);
      state.naiveTrilha = AppData.montarTrilha(ing.tourIds);
    }
    MapView.desenharIngenua(state.naiveTrilha);
  }
}

// ---------------------------------------------------------------- painel de frota

function renderFleetPanel() {
  const container = document.getElementById("fleet-list");
  container.innerHTML = "";

  state.rotas.forEach((v) => {
    const card = document.createElement("div");
    card.className = "vehicle-card" + (v.idle ? " idle" : "");
    card.style.borderLeftColor = v.idle ? "var(--gray-400)" : v.cor;

    if (v.idle) {
      card.innerHTML = `
        <div class="vehicle-card-header">
          <span class="vehicle-name"><span class="vehicle-dot" style="background:var(--gray-400)"></span>Veículo ${v.idx + 1}</span>
          <span class="vehicle-status status-ocioso">Ocioso — não necessário</span>
        </div>
        <div class="vehicle-meta">
          <span>Sem municípios atribuídos: não há entregas restantes para este veículo.</span>
        </div>
      `;
      container.appendChild(card);
      return;
    }

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
      state.rotas[idx].departureMin = timeStrToMin(e.target.value);
    });
  });
}

// ---------------------------------------------------------------- painel de resumo

function renderSummaryPanel() {
  const grid = document.getElementById("summary-grid");
  const ativos = state.rotas.filter((v) => !v.idle);
  const distTotal = ativos.reduce((s, v) => s + v.distKm, 0);
  const municipiosTotal = ativos.reduce((s, v) => s + v.municipiosAtendidos.length, 0);
  const makespan = ativos.length ? Math.max(...ativos.map((v) => v.departureMin - 480 + v.tempoMin)) : 0;

  grid.innerHTML = `
    <div class="stat-card"><div class="stat-value">${ativos.length}${state.rotas.length > ativos.length ? ` (+${state.rotas.length - ativos.length} ocioso)` : ""}</div><div class="stat-label">Veículo(s) em operação</div></div>
    <div class="stat-card"><div class="stat-value">${municipiosTotal}</div><div class="stat-label">Municípios atendidos</div></div>
    <div class="stat-card"><div class="stat-value">${distTotal.toFixed(0)} km</div><div class="stat-label">Distância total da operação</div></div>
    <div class="stat-card"><div class="stat-value">${formatMin(makespan)}</div><div class="stat-label">Duração total da operação</div></div>
  `;

  const compare = document.getElementById("summary-compare");
  const tempoIngenuo = state.tempoIngenuoMin;
  const tempoSingle = calcularMakespan(1);
  const tempoFrotaMakespan = ativos.length ? Math.max(...ativos.map((v) => v.tempoMin)) : 0;
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
    ${bar(`Frota (${ativos.length}v)`, tempoFrotaMakespan, "frota")}
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
  state.rotas.forEach((v) => {
    if (v.idle) return;
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

// ---------------------------------------------------------------- seletor de localizacoes

function abrirSeletorLocais() {
  state.seletor.cdTemp = state.cdId;
  state.seletor.entregaTemp = new Set(state.entregaIds);
  state.seletor.filtro = "";
  document.getElementById("input-loc-search").value = "";
  document.getElementById("loc-modal-backdrop").hidden = false;
  renderSeletorLocais();
}

function fecharSeletorLocais() {
  document.getElementById("loc-modal-backdrop").hidden = true;
}

function renderSeletorLocais() {
  const lista = document.getElementById("loc-list");
  const todos = AppData.getTodosMunicipios();
  const filtro = state.seletor.filtro.toLocaleLowerCase("pt-BR");

  const filtrados = todos
    .filter((m) => !filtro || m.nome.toLocaleLowerCase("pt-BR").includes(filtro))
    .sort((a, b) => b.populacao_2021 - a.populacao_2021);

  lista.innerHTML = filtrados
    .map((m) => {
      const isCd = state.seletor.cdTemp === m.id;
      const isEntrega = state.seletor.entregaTemp.has(m.id);
      return `
        <div class="loc-row ${isCd ? "loc-row-cd" : ""}">
          <label class="loc-radio" title="Definir como Centro de Distribuição">
            <input type="radio" name="loc-cd" value="${m.id}" ${isCd ? "checked" : ""} />
            CD
          </label>
          <label class="loc-checkbox">
            <input type="checkbox" data-id="${m.id}" class="loc-entrega-chk" ${isEntrega ? "checked" : ""} ${isCd ? "disabled" : ""} />
          </label>
          <span class="loc-name">${m.nome}</span>
          <span class="loc-pop">${m.populacao_2021.toLocaleString("pt-BR")} hab.</span>
        </div>
      `;
    })
    .join("");

  lista.querySelectorAll('input[name="loc-cd"]').forEach((radio) => {
    radio.addEventListener("change", (e) => {
      const novoId = Number(e.target.value);
      state.seletor.entregaTemp.delete(novoId);
      state.seletor.cdTemp = novoId;
      renderSeletorLocais();
    });
  });

  lista.querySelectorAll(".loc-entrega-chk").forEach((chk) => {
    chk.addEventListener("change", (e) => {
      const id = Number(e.target.dataset.id);
      if (e.target.checked) state.seletor.entregaTemp.add(id);
      else state.seletor.entregaTemp.delete(id);
      atualizarContadorSeletor();
    });
  });

  atualizarContadorSeletor();
}

function atualizarContadorSeletor() {
  document.getElementById("loc-count").textContent = `${state.seletor.entregaTemp.size} município(s) de entrega selecionado(s)`;
}

async function aplicarSelecaoLocais() {
  if (state.seletor.entregaTemp.size === 0) {
    alert("Selecione ao menos um município de entrega.");
    return;
  }
  state.cdId = state.seletor.cdTemp;
  state.entregaIds = Array.from(state.seletor.entregaTemp);

  MapView.desenharCD(AppData.getMunicipio(state.cdId));
  recalcularBaseline();
  fecharSeletorLocais();

  const nAlvo = Math.min(state.nVeiculosSolicitados, state.entregaIds.length) || 1;
  await gerarCenario(nAlvo);
}

function restaurarPresetPadrao() {
  const meta = AppData.getMeta();
  state.seletor.cdTemp = meta.cd_id_padrao;
  state.seletor.entregaTemp = new Set(meta.entrega_ids_padrao);
  renderSeletorLocais();
}

// ---------------------------------------------------------------- eventos de UI

function ligarEventos() {
  document.getElementById("btn-add-vehicle").addEventListener("click", () => {
    if (!state.carregando) gerarCenario(state.nVeiculosSolicitados + 1);
  });
  document.getElementById("btn-remove-vehicle").addEventListener("click", () => {
    if (!state.carregando && state.nVeiculosSolicitados > 1) gerarCenario(state.nVeiculosSolicitados - 1);
  });

  const inputFrota = document.getElementById("input-fleet-size");
  inputFrota.addEventListener("change", (e) => {
    const valor = parseInt(e.target.value, 10);
    if (!state.carregando && valor >= 1) gerarCenario(valor);
    else e.target.value = state.nVeiculosSolicitados;
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

  document.getElementById("btn-locations").addEventListener("click", abrirSeletorLocais);
  document.getElementById("btn-loc-close").addEventListener("click", fecharSeletorLocais);
  document.getElementById("btn-loc-cancel").addEventListener("click", fecharSeletorLocais);
  document.getElementById("btn-loc-apply").addEventListener("click", aplicarSelecaoLocais);
  document.getElementById("btn-loc-restore").addEventListener("click", restaurarPresetPadrao);
  document.getElementById("loc-modal-backdrop").addEventListener("click", (e) => {
    if (e.target.id === "loc-modal-backdrop") fecharSeletorLocais();
  });
  document.getElementById("input-loc-search").addEventListener("input", (e) => {
    state.seletor.filtro = e.target.value;
    renderSeletorLocais();
  });
}

// ---------------------------------------------------------------- boot

async function iniciar() {
  MapView.init();
  const solution = await AppData.carregar();

  state.cdId = solution.meta.cd_id_padrao;
  state.entregaIds = solution.meta.entrega_ids_padrao.slice();

  MapView.desenharCD(AppData.getMunicipio(state.cdId));
  recalcularBaseline();

  ligarEventos();
  await gerarCenario(1);

  requestAnimationFrame(loopAnimacao);
}

iniciar().catch((err) => {
  console.error(err);
  document.getElementById("map-loading").textContent = "Erro ao carregar dados: " + err.message;
});
