const stages = {
  drop: document.getElementById("dropStage"),
  loading: document.getElementById("loadingStage"),
  error: document.getElementById("errorStage"),
  result: document.getElementById("resultStage"),
};

let currentReportId = null;

function showStage(name) {
  Object.values(stages).forEach((el) => el.classList.add("hidden"));
  stages[name].classList.remove("hidden");
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

async function uploadFile(file) {
  showStage("loading");
  document.getElementById("loadingText").textContent =
    `"${file.name}" 판독 중입니다... 잠시만 기다려주세요.`;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/evaluate", { method: "POST", body: formData });
    const data = await res.json();
    if (!data.success) {
      showError(data.error || "알 수 없는 오류가 발생했습니다.");
      return;
    }
    renderResult(data);
  } catch (e) {
    showError("서버와 통신 중 오류가 발생했습니다: " + e.message);
  }
}

function showError(message) {
  document.getElementById("errorMessage").textContent = message;
  showStage("error");
}

function renderResult(data) {
  currentReportId = data.reportId;

  const banner = document.getElementById("summaryBanner");
  banner.classList.remove("warn", "fail");
  if (data.overall === "경고") banner.classList.add("fail");
  else if (data.overall === "주의") banner.classList.add("warn");

  document.getElementById("overallVerdict").textContent = data.overall;
  const c = data.counts;
  document.getElementById("summaryCounts").textContent =
    `정상 ${c.pass} · 주의 ${c.warn} · 경고 ${c.fail} · 확인필요 ${c.unknown} / 총 ${c.total}항목`;

  document.getElementById("metaFile").textContent = data.fileName;
  document.getElementById("metaTitle").textContent = data.meta.title;
  document.getElementById("metaTimestamp").textContent = data.meta.timestamp;
  document.getElementById("metaMethod").textContent = data.meta.methodPath;

  const body = document.getElementById("resultBody");
  body.innerHTML = "";
  data.rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(row.name)}</td>
      <td>${escapeHtml(row.value)}</td>
      <td>${escapeHtml(row.criteria)}</td>
      <td class="verdict-cell v-${escapeHtml(row.verdict)}">${escapeHtml(row.verdict)}</td>
    `;
    body.appendChild(tr);
  });

  showStage("result");
}

function resetToDrop() {
  currentReportId = null;
  document.getElementById("fileInput").value = "";
  showStage("drop");
}

function setupDropzone() {
  const dz = document.getElementById("dropzone");
  const input = document.getElementById("fileInput");

  dz.addEventListener("click", () => input.click());
  dz.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") input.click();
  });

  input.addEventListener("change", () => {
    if (input.files.length) uploadFile(input.files[0]);
  });

  ["dragenter", "dragover"].forEach((evt) => {
    dz.addEventListener(evt, (e) => {
      e.preventDefault();
      dz.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((evt) => {
    dz.addEventListener(evt, (e) => {
      e.preventDefault();
      dz.classList.remove("dragover");
    });
  });

  dz.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length) uploadFile(files[0]);
  });
}

function setupActions() {
  document.getElementById("retryBtn").addEventListener("click", resetToDrop);
  document.getElementById("newBtn").addEventListener("click", resetToDrop);
  document.getElementById("downloadBtn").addEventListener("click", () => {
    if (currentReportId) {
      window.location.href = `/api/report/${currentReportId}`;
    }
  });
}

setupDropzone();
setupActions();
