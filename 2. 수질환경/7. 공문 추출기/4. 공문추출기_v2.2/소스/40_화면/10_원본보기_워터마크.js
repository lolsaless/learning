/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [40_화면/10_원본보기_워터마크.js] 원본 보기·워터마크
   하는 일 : 의뢰공문·첨부(HWPX·XLSX·PDF·그림)·시행공문·성적서 보기, 시료접수일 워터마크, 새 창 크게 보기, 파일 내려받기
   주요 이름: WM_CSS, wmHtml, odtPreview, pdfPreviewHtml, viewerHtml, showPreview, openPreviewWindow, downloadFile
   이럴 때 고침: 워터마크 모양·위치, 보기 방식
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ───── 원본 보기 (ODT · PDF · HWPX · XLSX · 그림) ───── */
const WM_CSS = `.wm-wrap{position:relative;width:max-content;max-width:100%;margin:0 auto}
.wm-stamp{position:absolute;top:.5cm;right:.25cm;border:2.5px solid rgba(200,30,30,.6);color:rgba(190,25,25,.72);border-radius:8px;padding:5px 12px;font:600 13px/1.35 "Malgun Gothic","맑은 고딕",sans-serif;text-align:center;transform:rotate(-5deg);background:rgba(255,255,255,.4);z-index:3;pointer-events:none;white-space:nowrap}
.wm-stamp b{font-size:15px}`;
function wmHtml(d) {
  const n = peekNotes(d.key); if (!n.recv) return '';
  return `<div class="wm-stamp">시료접수일<br><b>${esc(fmtFull(n.recv))}</b>${n.before13 ? '<br><small>13시 이전 접수</small>' : ''}</div>`;
}
async function odtPreview(f) {
  const ck = 'pv:' + fkey(f);
  if (state.previewCache.has(ck)) return state.previewCache.get(ck);
  const r = await E.renderOdtHtml(await fileBytes(f), inflateRaw);
  if (!document.getElementById('odt-css')) { const st = document.createElement('style'); st.id = 'odt-css'; st.textContent = r.css + WM_CSS; document.head.appendChild(st); }
  if (state.previewCache.size > 40) state.previewCache.delete(state.previewCache.keys().next().value);
  state.previewCache.set(ck, r);
  return r;
}
async function pdfPreviewHtml(f, pages) {
  const ck = 'pdfpv:' + fkey(f) + '|' + (pages || []).join(',');
  if (state.previewCache.has(ck)) return state.previewCache.get(ck);
  const cs = await DG.pdfToCanvases(await fileBytes(f), pages, 1.6);
  const html = cs.map(c => `<div class="pdf-page"><img src="${c.toDataURL('image/png')}" alt=""></div>`).join('');
  state.previewCache.set(ck, html);
  return html;
}
async function viewerHtml(d, v) {
  if (v.type === 'odt') { const r = await odtPreview(v.f); return v.req && state.settings.watermark ? `<div class="wm-wrap">${wmHtml(d)}${r.html}</div>` : r.html; }
  if (v.type === 'pdf') return pdfPreviewHtml(v.f);
  if (v.type === 'hwpx') { const h = await parseHwpxEntry(v.f); return E2.hwpxHtml(h, v.f.nm); }
  if (v.type === 'xlsx') { const x = await parseXlsxEntry(v.f); return E2.xlsxHtml(x, v.f.nm); }
  if (v.type === 'img') { const b = await fileBytes(v.f); const url = URL.createObjectURL(new Blob([b], { type: DG.IMG_MIME[v.f.nm.split('.').pop().toLowerCase()] })); return `<div class="pdf-page"><img src="${url}" alt=""></div>`; }
  return `<div class="notice">이 형식(${esc(v.f.nm.split('.').pop())})은 화면에 표시할 수 없습니다. [원본 파일 열기]로 내려받아 여세요.</div>`;
}
async function showPreview(d, scrollTop) {
  const v = viewerList(d).find(x => x.k === state.viewer) || viewerList(d)[0];
  try {
    const html = await viewerHtml(d, v);
    const pv = $('#pv');
    if (!pv || state.selected !== d.id || state.viewer !== v.k) return;
    pv.innerHTML = html; fitPreview();
    if (scrollTop) { const b = $('#detail .pane-org'); if (b) b.scrollTop = scrollTop; }
  } catch (e) {
    console.error(e);
    const pv = $('#pv'); if (pv) pv.innerHTML = `<div class="notice">표시할 수 없습니다: ${esc(explain(e))}</div>`;
  }
}
function fitPreview() {
  const pv = $('#pv'); if (!pv) return;
  const page = pv.querySelector('.wm-wrap') || pv.querySelector('.odt-page'); if (!page) return;
  page.style.zoom = '';
  const avail = pv.clientWidth - 24, w = page.offsetWidth;
  if (w > avail && avail > 100) page.style.zoom = (avail / w).toFixed(3);
}
async function openPreviewWindow(d) {
  const v = viewerList(d).find(x => x.k === state.viewer) || viewerList(d)[0];
  try {
    const html = await viewerHtml(d, v);
    const css = (await odtPreview(d.f)).css;
    const w = window.open('', '_blank');
    if (!w) { toast('팝업이 차단되었습니다. 주소창 오른쪽의 팝업 차단 아이콘에서 허용해 주세요.', 'err'); return; }
    w.document.write(`<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>${esc(v.f.nm)}</title><style>body{margin:0;background:#80868f;padding:24px}${css}${WM_CSS}.odt-page{box-shadow:0 2px 12px rgba(0,0,0,.35);padding:1cm 1.5cm}.pdf-page{text-align:center;margin:0 auto 16px}.pdf-page img{max-width:100%;box-shadow:0 2px 12px rgba(0,0,0,.35);background:#fff}@media print{body{background:#fff;padding:0}.odt-page,.pdf-page img{box-shadow:none}.odt-page{padding:0}.pdf-page{page-break-after:always;margin:0}}</style></head><body>${html}</body></html>`);
    w.document.close();
  } catch (e) { toast('열지 못했습니다: ' + explain(e), 'err'); }
}
async function downloadFile(f) {
  try {
    const url = URL.createObjectURL(new Blob([await fileBytes(f)]));
    const a = document.createElement('a'); a.href = url; a.download = f.nm; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    toast('파일을 내려받았습니다. 브라우저의 다운로드 목록에서 열면 한글(또는 기본 프로그램)로 열립니다.');
  } catch (e) { toast('파일을 열지 못했습니다: ' + explain(e), 'err'); }
}
