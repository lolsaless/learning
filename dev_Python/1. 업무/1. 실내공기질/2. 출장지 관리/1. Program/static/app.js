let map;
let clusterGroup;
let allMarkers = []; // 서버에서 받은 원본 데이터
let leafletMarkers = new Map(); // id -> leaflet marker
let facilityColors = new Map(); // 서버가 계산해 준 색상을 시설군별로 캐싱

const state = {
  search: "",
  region: "",
  hideDone: false,
  excludedFacilities: new Set(),
};

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.remove("show"), 2200);
}

function makeIcon(color) {
  return L.divIcon({
    className: "",
    html: `<div class="marker-dot" style="width:16px;height:16px;background:${color};"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    popupAnchor: [0, -8],
  });
}

function popupHtml(m) {
  const badgeColor = m.color;
  return `
    <div class="popup-title">${escapeHtml(m.name)}</div>
    <span class="popup-badge" style="background:${badgeColor}">${escapeHtml(m.facility)}</span>
    <div class="popup-address">${escapeHtml(m.address)}</div>
    <div class="popup-actions">
      ${m.done
        ? `<button data-action="cancel" data-id="${m.id}">완료 취소</button>`
        : `<button data-action="complete" data-id="${m.id}" class="primary">완료 처리</button>`}
    </div>
  `;
}

async function toggleDone(id, done) {
  try {
    const res = await fetch(`/api/markers/${id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ done }),
    });
    const data = await res.json();
    if (!data.success) {
      showToast("업데이트 실패: " + data.error);
      return;
    }
    applyMarkerUpdate(data.marker);
    renderSummary(data.summary);
    showToast(done ? "완료 처리되었습니다." : "완료가 취소되었습니다.");
  } catch (e) {
    showToast("네트워크 오류가 발생했습니다.");
  }
}

function applyMarkerUpdate(updated) {
  const idx = allMarkers.findIndex((m) => m.id === updated.id);
  if (idx !== -1) allMarkers[idx] = updated;
  refreshMarkerVisual(updated);
}

function refreshMarkerVisual(m) {
  const marker = leafletMarkers.get(m.id);
  if (!marker) return;
  marker.setIcon(makeIcon(m.color));
  marker.setPopupContent(popupHtml(m));
  marker.__data = m;
}

function matchesFilters(m) {
  if (state.region && m.region !== state.region) return false;
  if (state.excludedFacilities.has(m.facility)) return false;
  if (state.hideDone && m.done) return false;
  if (state.search) {
    const q = state.search.toLowerCase();
    if (!m.name.toLowerCase().includes(q) && !m.address.toLowerCase().includes(q)) {
      return false;
    }
  }
  return true;
}

function applyFilters() {
  clusterGroup.clearLayers();
  const visible = allMarkers.filter(matchesFilters);
  visible.forEach((m) => {
    const marker = leafletMarkers.get(m.id);
    clusterGroup.addLayer(marker);
  });
}

function buildMarkers(markers) {
  clusterGroup = L.markerClusterGroup();
  markers.forEach((m) => {
    const marker = L.marker([m.lat, m.lng], { icon: makeIcon(m.color) });
    marker.bindPopup(popupHtml(m));
    marker.__data = m;
    marker.on("popupopen", (e) => {
      const el = e.popup.getElement();
      const btn = el.querySelector("button[data-action]");
      if (!btn) return;
      btn.addEventListener("click", () => {
        const done = btn.dataset.action === "complete";
        toggleDone(Number(btn.dataset.id), done);
      });
    });
    leafletMarkers.set(m.id, marker);
  });
  applyFilters();
  map.addLayer(clusterGroup);
}

function buildFilterControls(markers) {
  const regions = [...new Set(markers.map((m) => m.region))].sort();
  const regionSelect = document.getElementById("regionSelect");
  regions.forEach((r) => {
    const opt = document.createElement("option");
    opt.value = r;
    opt.textContent = r;
    regionSelect.appendChild(opt);
  });

  const facilities = [...new Set(markers.map((m) => m.facility))].sort();
  markers.forEach((m) => facilityColors.set(m.facility, m.done ? null : m.color));
  // done 마커만 있던 시설군의 색상 보정: 원본 색상을 다시 찾아 채움
  markers.forEach((m) => {
    if (!m.done) facilityColors.set(m.facility, m.color);
  });

  const list = document.getElementById("facilityList");
  facilities.forEach((f) => {
    const id = `facility-${f}`;
    const row = document.createElement("label");
    row.className = "checkbox-row";
    const color = facilityColors.get(f) || "#999999";
    row.innerHTML = `
      <input type="checkbox" id="${id}" checked />
      <span class="swatch" style="background:${color}"></span>
      ${escapeHtml(f)}
    `;
    row.querySelector("input").addEventListener("change", (e) => {
      if (e.target.checked) state.excludedFacilities.delete(f);
      else state.excludedFacilities.add(f);
      applyFilters();
    });
    list.appendChild(row);
  });
}

function renderSummary(summary) {
  const overallText = document.getElementById("overallText");
  const overallBar = document.getElementById("overallBar");
  overallText.textContent = `${summary.completed} / ${summary.total}`;
  const pct = summary.total ? (summary.completed / summary.total) * 100 : 0;
  overallBar.style.width = `${pct}%`;

  const regionList = document.getElementById("regionList");
  regionList.innerHTML = "";
  Object.entries(summary.by_region).forEach(([region, info]) => {
    const pct = info.total ? (info.completed / info.total) * 100 : 0;
    const item = document.createElement("div");
    item.className = "region-item";
    item.innerHTML = `
      <div class="progress-label"><span>${escapeHtml(region)}</span><span>${info.completed} / ${info.total}</span></div>
      <div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>
    `;
    regionList.appendChild(item);
  });
}

function setupControls() {
  document.getElementById("searchInput").addEventListener("input", (e) => {
    state.search = e.target.value.trim();
    applyFilters();
  });
  document.getElementById("regionSelect").addEventListener("change", (e) => {
    state.region = e.target.value;
    applyFilters();
  });
  document.getElementById("hideDone").addEventListener("change", (e) => {
    state.hideDone = e.target.checked;
    applyFilters();
  });
  document.getElementById("facilityToggle").addEventListener("click", () => {
    const boxes = document.querySelectorAll("#facilityList input[type=checkbox]");
    const shouldCheck = state.excludedFacilities.size > 0;
    boxes.forEach((box) => {
      box.checked = shouldCheck;
      box.dispatchEvent(new Event("change"));
    });
  });
}

async function init() {
  map = L.map("map").setView([37.4, 127.2], 10);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19,
  }).addTo(map);

  const [markers, summary] = await Promise.all([
    fetch("/api/markers").then((r) => r.json()),
    fetch("/api/summary").then((r) => r.json()),
  ]);

  allMarkers = markers;
  if (markers.length) {
    const bounds = L.latLngBounds(markers.map((m) => [m.lat, m.lng]));
    map.fitBounds(bounds, { padding: [30, 30] });
  }

  buildMarkers(markers);
  buildFilterControls(markers);
  renderSummary(summary);
  setupControls();
}

init();
