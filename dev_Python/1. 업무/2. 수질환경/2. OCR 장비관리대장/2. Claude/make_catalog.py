# -*- coding: utf-8 -*-
"""
마스터 엑셀(equipment.xlsx) -> 장비 카탈로그 HTML (파일 1개, 인터넷 연결 불필요)

  python make_catalog.py equipment.xlsx                 -> catalog.html (엑셀과 같은 폴더)
  python make_catalog.py equipment.xlsx --out my.html --photo-max 800

HTML 기능
  · 검색(관리번호/물품명/제조사/도입처/성능 등 전체 텍스트)
  · 금액 필터: 단가(도입가격) 또는 총액(단가×장비대수) 기준, 최소~최대(원/만원/억원), 빠른 구간 버튼
  · 도입연도 범위 / 제조국 / 사진 있는 장비만 / 정렬 / 카드·표 보기
  · [엑셀로 내보내기] 현재 필터 결과를 .xlsx 로 저장 (사진 제외, 텍스트만; equipment/components/history 3시트)
  · [양식으로 인쇄] 현재 필터 결과를 원본 '시험장비관리대장' 양식(가로 A4, 앞면+뒷면)으로 열어 인쇄/PDF 저장
필요 라이브러리: pandas, openpyxl, Pillow
"""
import argparse
import base64
import hashlib
import io
import json
import os
import sys

import pandas as pd
from PIL import Image

from ledger_common import COLS, load_master, MAIN_COLS, MAIN_ROWS, COMP_ROW, COMP_MIN_ROWS, \
    HIST_COLS, HIST_ROWS, HIST_PER_PAGE, TITLE_TEXT, FONT_NAME


def _data_url(path, max_px, quality=80):
    """사진을 max_px 로 축소한 JPEG data URL (투명 PNG는 흰 배경)"""
    with Image.open(path) as im:
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, "white")
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        im.thumbnail((max_px, max_px))
        bio = io.BytesIO()
        im.save(bio, "JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(bio.getvalue()).decode()


def build(excel_path, out_html=None, photo_max=640):
    recs, logo = load_master(excel_path)
    out_html = out_html or os.path.join(os.path.dirname(os.path.abspath(excel_path)), "catalog.html")

    # 엑셀 equipment 시트에 실제로 있는 열만 내보내기 대상으로
    head = pd.read_excel(excel_path, sheet_name=None, nrows=0)
    eq_head = next(v.columns for k, v in head.items() if k.strip().lower() == "equipment")
    eq_head = {str(c).strip() for c in eq_head}
    export_cols = [[k, h] for k, h in COLS.items() if h in eq_head]

    images, by_hash = {}, {}
    for r in recs:
        keys = []
        for p in r.pop("photos"):
            with open(p, "rb") as f:
                h = hashlib.md5(f.read()).hexdigest()
            if h not in by_hash:                       # 같은 사진이 여러 장비에 공유되면 1번만 저장
                by_hash[h] = f"i{len(by_hash)}"
                images[by_hash[h]] = _data_url(p, photo_max)
            keys.append(by_hash[h])
        r["photos"] = keys
    data = {
        "records": recs, "images": images, "cols": export_cols,
        "logo": ("data:image/png;base64," + base64.b64encode(open(logo, "rb").read()).decode()) if logo else None,
        "form": {"mainCols": MAIN_COLS, "mainRows": MAIN_ROWS, "compRow": COMP_ROW, "compMin": COMP_MIN_ROWS,
                 "histCols": HIST_COLS, "histRows": HIST_ROWS, "histPer": HIST_PER_PAGE,
                 "title": TITLE_TEXT, "font": FONT_NAME},
        "source": os.path.basename(excel_path),
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("/*__DATA__*/null", payload)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML 카탈로그 생성: {out_html} (장비 {len(recs)}건, 사진 {len(images)}장, {os.path.getsize(out_html)/1e6:.1f}MB)")
    return out_html


TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>시험장비 카탈로그</title>
<style>
:root{--bg:#f4f6f8;--card:#fff;--ink:#1b2530;--mute:#66727f;--line:#dfe4ea;--acc:#1f5fa8;--acc2:#e8f0fa}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 'Malgun Gothic','Apple SD Gothic Neo','Noto Sans KR',sans-serif}
header{display:flex;flex-wrap:wrap;align-items:center;gap:12px;padding:14px 20px;background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
h1{font-size:18px;margin:0}
.sub{color:var(--mute);font-size:12px;flex:1}
button,select,input{font:inherit}
button{border:1px solid var(--line);background:#fff;border-radius:6px;padding:6px 12px;cursor:pointer}
button:hover{background:var(--acc2)}
button.pri{background:var(--acc);border-color:var(--acc);color:#fff}
button.pri:hover{background:#184d88}
.filters{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px 16px;padding:14px 20px;background:#fff;border-bottom:1px solid var(--line)}
.f{display:flex;flex-direction:column;gap:4px}
.f>label,.f>.lb{font-size:12px;color:var(--mute);font-weight:600}
.f input[type=text],.f input[type=number],.f select{border:1px solid var(--line);border-radius:6px;padding:6px 8px;width:100%}
.row{display:flex;gap:6px;align-items:center}
.row input{min-width:0}
.chips{display:flex;flex-wrap:wrap;gap:4px}
.chips button{padding:2px 8px;font-size:12px;border-radius:12px}
.radio{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:13px}.radio label{white-space:nowrap}
#summary{padding:10px 20px;color:var(--mute);font-size:13px;display:flex;flex-wrap:wrap;gap:6px 18px}
#summary b{color:var(--ink)}
main{padding:0 20px 40px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;cursor:pointer;display:flex;flex-direction:column}
.card:hover{box-shadow:0 2px 10px rgba(0,0,0,.12)}
.ph{position:relative;aspect-ratio:4/3;background:#eef1f4;display:flex;align-items:center;justify-content:center;color:var(--mute);font-size:12px}
.ph img{width:100%;height:100%;object-fit:cover}
.cnt{position:absolute;right:6px;bottom:6px;background:rgba(0,0,0,.65);color:#fff;border-radius:10px;padding:0 7px;font-size:11px}
.cb{padding:10px 12px;display:flex;flex-direction:column;gap:2px}
.mg{font-size:12px;color:var(--acc);font-weight:700}
.cb h3{margin:0;font-size:14px}
.price{font-weight:700;margin-top:2px}
.meta,.spec{font-size:12px;color:var(--mute)}
table.tb{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line)}
.tb th,.tb td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;font-size:13px;vertical-align:top}
.tb th{background:#eef2f6;position:sticky;top:0}
.tb tr:hover td{background:var(--acc2);cursor:pointer}
.tb .num{text-align:right;white-space:nowrap}
.empty{padding:60px;text-align:center;color:var(--mute)}
#modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:20;overflow:auto;padding:24px}
#modal.on{display:block}
.mbox{background:#fff;max-width:980px;margin:0 auto;border-radius:12px;padding:20px 24px;position:relative}
.mx{position:absolute;right:14px;top:10px;font-size:20px;border:none;background:none}
.gal{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.gal img{max-height:220px;max-width:100%;border-radius:6px;border:1px solid var(--line);cursor:zoom-in}
dl.kv{display:grid;grid-template-columns:120px 1fr;gap:4px 12px;margin:10px 0}
dl.kv dt{color:var(--mute);font-size:12px;padding-top:2px}
dl.kv dd{margin:0;white-space:pre-wrap}
.sec{font-weight:700;margin:16px 0 4px;border-bottom:1px solid var(--line);padding-bottom:3px}
.mt{width:100%;border-collapse:collapse;font-size:13px}
.mt td,.mt th{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top;white-space:pre-wrap}
.mt th{background:#eef2f6}
@media (max-width:640px){dl.kv{grid-template-columns:90px 1fr}}
</style>
</head>
<body>
<header>
  <h1>시험장비 카탈로그</h1>
  <div class="sub" id="sub"></div>
  <button id="bXlsx" class="pri">엑셀로 내보내기</button>
  <button id="bPrint">양식으로 인쇄</button>
</header>

<section class="filters">
  <div class="f"><label for="q">검색</label><input type="text" id="q" placeholder="관리번호, 물품명, 제조사, 도입처, 성능 …"></div>
  <div class="f">
    <span class="lb">금액 기준</span>
    <div class="radio">
      <label><input type="radio" name="basis" value="unit" checked> 단가(도입가격)</label>
      <label><input type="radio" name="basis" value="total"> 총액(단가×대수)</label>
    </div>
    <div class="row">
      <input type="number" id="pmin" min="0" placeholder="최소"> ~
      <input type="number" id="pmax" min="0" placeholder="최대">
      <select id="punit"><option value="1">원</option><option value="10000">만원</option><option value="100000000">억원</option></select>
    </div>
    <div class="chips" id="chips">
      <button data-a="0" data-b="1000000">100만 미만</button>
      <button data-a="1000000" data-b="10000000">100만~1천만</button>
      <button data-a="10000000" data-b="100000000">1천만~1억</button>
      <button data-a="100000000" data-b="">1억 이상</button>
    </div>
  </div>
  <div class="f"><span class="lb">도입연도</span>
    <div class="row"><input type="number" id="y1" placeholder="부터" min="1900" max="2100"> ~ <input type="number" id="y2" placeholder="까지" min="1900" max="2100"></div>
    <label style="margin-top:6px"><input type="checkbox" id="onlyPhoto"> 사진 있는 장비만</label>
  </div>
  <div class="f"><label for="country">제조국</label><select id="country"><option value="">전체</option></select>
    <label for="sort" style="margin-top:6px">정렬</label>
    <select id="sort">
      <option value="seq">순번</option><option value="pa">금액 낮은순</option><option value="pd">금액 높은순</option>
      <option value="da">도입일 오래된순</option><option value="dd">도입일 최신순</option><option value="name">물품명</option>
    </select>
  </div>
  <div class="f" style="justify-content:flex-end"><div class="row"><button id="vCards">카드</button><button id="vTable">표</button><button id="bReset">초기화</button></div></div>
</section>
<div id="summary"></div>
<main id="list"></main>
<div id="modal"><div class="mbox" id="mbox"></div></div>

<script>
const DATA = /*__DATA__*/null;
const R = DATA.records, IMG = DATA.images;
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const nl = s => esc(s).replace(/\n/g, '<br>');
const won = n => n == null ? '-' : n.toLocaleString('ko-KR') + '원';
const st = {basis:'unit', view:'cards'};

/* ───────── 필터 ───────── */
const amount = r => st.basis === 'total' ? (r.price == null ? null : r.price * (r.units || 1)) : r.price;
const yearOf = r => r.date ? parseInt(r.date.slice(0, 4)) : null;
const hay = r => (r._h || (r._h = [r.mgmt, r.name, r.spec, r.maker, r.country, r.vendor, r.addr, r.use, r.perf, r.item_no,
  r.mgmt_hist, r.tel, r.tel_note, r.cond, r.date, r.price_raw, ...r.comps.map(c => c.name)].join(' ').toLowerCase()));

function current() {
  const q = $('q').value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const u = +$('punit').value;
  const lo = $('pmin').value === '' ? null : +$('pmin').value * u;
  const hi = $('pmax').value === '' ? null : +$('pmax').value * u;
  const y1 = $('y1').value === '' ? null : +$('y1').value, y2 = $('y2').value === '' ? null : +$('y2').value;
  const ctry = $('country').value, ph = $('onlyPhoto').checked;
  let out = R.filter(r => {
    if (q.length && !q.every(t => hay(r).includes(t))) return false;
    const a = amount(r);
    if ((lo != null || hi != null) && a == null) return false;
    if (lo != null && a < lo) return false;
    if (hi != null && a > hi) return false;
    const y = yearOf(r);
    if ((y1 != null || y2 != null) && y == null) return false;
    if (y1 != null && y < y1) return false;
    if (y2 != null && y > y2) return false;
    if (ctry && r.country !== ctry) return false;
    if (ph && !r.photos.length) return false;
    return true;
  });
  const s = $('sort').value, cmpN = (a, b) => (a == null) - (b == null) || a - b;
  const key = {seq: r => r.seq, pa: r => amount(r), pd: r => amount(r), da: r => r.date, dd: r => r.date, name: r => r.name}[s];
  out.sort((a, b) => {
    const x = key(a), y = key(b);
    if (s === 'name') return String(x).localeCompare(String(y), 'ko');
    if (s === 'da' || s === 'dd') { const c = (x == null) - (y == null) || (x < y ? -1 : x > y ? 1 : 0); return s === 'dd' ? ((x == null) - (y == null) || -c) : c; }
    const c = cmpN(x, y);
    return s === 'pd' ? ((x == null) - (y == null) || -c) : c;
  });
  return out;
}

/* ───────── 화면 ───────── */
function render() {
  const L = current();
  const sum = L.reduce((t, r) => t + (amount(r) || 0), 0);
  $('summary').innerHTML = `<span><b>${L.length}</b> / ${R.length}건</span><span>금액 합계(${st.basis === 'total' ? '총액' : '단가'} 기준) <b>${won(sum)}</b></span>` +
    `<span>사진 있는 장비 <b>${L.filter(r => r.photos.length).length}</b>건</span>`;
  $('bPrint').textContent = `양식으로 인쇄 (${L.length}건)`;
  $('bXlsx').textContent = `엑셀로 내보내기 (${L.length}건)`;
  const el = $('list');
  if (!L.length) { el.innerHTML = '<div class="empty">조건에 맞는 장비가 없습니다.</div>'; return; }
  if (st.view === 'cards') {
    el.innerHTML = '<div class="grid">' + L.map(r => {
      const im = r.photos[0] ? `<img loading="lazy" src="${IMG[r.photos[0]]}" alt="">` : '사진 없음';
      const pr = r.price == null ? '-' : (r.units > 1 ? `${won(r.price)} × ${r.units}대` : won(r.price));
      return `<article class="card" data-id="${r.seq}"><div class="ph">${im}${r.photos.length > 1 ? `<span class="cnt">${r.photos.length}</span>` : ''}</div>
      <div class="cb"><div class="mg">${esc(r.mgmt)}</div><h3>${esc(r.name)}</h3><div class="price">${pr}</div>
      <div class="meta">${esc(r.date || '')} · ${esc(r.vendor || '')}</div><div class="spec">${esc(r.spec || '')}</div></div></article>`;
    }).join('') + '</div>';
  } else {
    el.innerHTML = `<table class="tb"><thead><tr><th>순번</th><th>관리번호</th><th>물품명</th><th>스펙</th><th>제조사</th><th>도입일</th><th class="num">단가(원)</th><th class="num">대수</th><th class="num">총액(원)</th><th>도입처</th><th>사진</th></tr></thead><tbody>` +
      L.map(r => `<tr data-id="${r.seq}"><td>${r.seq}</td><td>${esc(r.mgmt)}</td><td>${esc(r.name)}</td><td>${esc(r.spec || '')}</td><td>${esc(r.maker || '')}</td><td>${esc(r.date || '')}</td>
      <td class="num">${r.price == null ? '-' : r.price.toLocaleString('ko-KR')}</td><td class="num">${r.units || 1}</td><td class="num">${r.price == null ? '-' : (r.price * (r.units || 1)).toLocaleString('ko-KR')}</td>
      <td>${esc(r.vendor || '')}</td><td>${r.photos.length || ''}</td></tr>`).join('') + '</tbody></table>';
  }
}

function openModal(seq) {
  const r = R.find(x => x.seq === seq); if (!r) return;
  const kv = [['관리번호', r.mgmt], ['스펙', r.spec], ['제조사(제조국)', [r.maker, r.country && `(${r.country})`].filter(Boolean).join(' ')],
    ['도입시기', r.date], ['도입가격', r.price_raw], ['단가 / 대수', r.price == null ? '' : `${won(r.price)} × ${r.units || 1}대 = ${won(r.price * (r.units || 1))}`],
    ['도입처', r.vendor], ['주소', r.addr], ['연락처', [r.tel, r.tel_note].filter(Boolean).join('\n')], ['용도', r.use], ['상태', r.cond],
    ['물품분류번호', r.item_no], ['관리 이력', r.mgmt_hist]].filter(x => x[1]);
  $('mbox').innerHTML = `<button class="mx" onclick="closeModal()">✕</button><h2 style="margin:0">${esc(r.name)}</h2>
    <div class="gal">${r.photos.map(k => `<img src="${IMG[k]}" onclick="window.open(this.src)">`).join('')}</div>
    <dl class="kv">${kv.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join('')}</dl>
    ${r.perf ? `<div class="sec">주요 성능 및 특징</div><div style="white-space:pre-wrap">${esc(r.perf)}</div>` : ''}
    ${r.comps.length ? `<div class="sec">장비구성내역</div><table class="mt"><tr><th>연번</th><th>장비명</th><th>수량</th><th>단위</th></tr>${r.comps.map(c => `<tr><td>${esc(c.seq)}</td><td>${esc(c.name)}</td><td>${esc(c.qty)}</td><td>${esc(c.unit)}</td></tr>`).join('')}</table>` : ''}
    ${r.hist.length ? `<div class="sec">수리·교정 이력</div><table class="mt"><tr><th>일자</th><th>내용</th></tr>${r.hist.map(h => `<tr><td>${esc(h.date)}</td><td>${esc(h.content)}</td></tr>`).join('')}</table>` : ''}
    <p style="margin-top:16px"><button class="pri" onclick="printLedger([${r.seq}])">이 장비 양식으로 인쇄</button></p>`;
  $('modal').classList.add('on');
}
function closeModal() { $('modal').classList.remove('on'); }

/* ───────── 엑셀(.xlsx) 내보내기: 라이브러리 없이 직접 생성 ───────── */
const enc = new TextEncoder();
const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
const crc32 = b => { let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
const u16 = v => [v & 255, (v >> 8) & 255], u32 = v => [v & 255, (v >> 8) & 255, (v >> 16) & 255, (v >>> 24) & 255];
function zip(files) {
  const parts = [], cen = []; let off = 0;
  for (const f of files) {
    const nm = enc.encode(f.name), data = enc.encode(f.text), crc = crc32(data), sz = data.length;
    const lh = new Uint8Array([0x50, 0x4b, 3, 4, ...u16(20), ...u16(0x0800), ...u16(0), ...u16(0), ...u16(0x21), ...u32(crc), ...u32(sz), ...u32(sz), ...u16(nm.length), ...u16(0)]);
    parts.push(lh, nm, data); cen.push({nm, crc, sz, off}); off += lh.length + nm.length + sz;
  }
  let cs = 0;
  for (const c of cen) {
    const h = new Uint8Array([0x50, 0x4b, 1, 2, ...u16(20), ...u16(20), ...u16(0x0800), ...u16(0), ...u16(0), ...u16(0x21), ...u32(c.crc), ...u32(c.sz), ...u32(c.sz), ...u16(c.nm.length), ...u16(0), ...u16(0), ...u16(0), ...u16(0), ...u32(0), ...u32(c.off)]);
    parts.push(h, c.nm); cs += h.length + c.nm.length;
  }
  parts.push(new Uint8Array([0x50, 0x4b, 5, 6, 0, 0, 0, 0, ...u16(cen.length), ...u16(cen.length), ...u32(cs), ...u32(off), 0, 0]));
  return new Blob(parts, {type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
}
const xesc = s => String(s).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const colName = i => { let s = ''; for (i++; i > 0; i = Math.floor((i - 1) / 26)) s = String.fromCharCode(65 + (i - 1) % 26) + s; return s; };
function sheetXml(header, rows, numCols, widths) {
  const all = [header, ...rows];
  const body = all.map((row, ri) => '<row r="' + (ri + 1) + '">' + row.map((v, ci) => {
    if (v == null || v === '') return '';
    const ref = colName(ci) + (ri + 1);
    if (ri === 0) return `<c r="${ref}" s="1" t="inlineStr"><is><t>${xesc(v)}</t></is></c>`;
    if (typeof v === 'number') return `<c r="${ref}" s="${numCols.has(ci) ? 2 : 3}"><v>${v}</v></c>`;
    return `<c r="${ref}" s="0" t="inlineStr"><is><t xml:space="preserve">${xesc(v)}</t></is></c>`;
  }).join('') + '</row>').join('');
  const cols = '<cols>' + widths.map((w, i) => `<col min="${i + 1}" max="${i + 1}" width="${w}" customWidth="1"/>`).join('') + '</cols>';
  const last = colName(header.length - 1) + all.length;
  return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
    '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>' +
    cols + '<sheetData>' + body + '</sheetData><autoFilter ref="A1:' + last + '"/></worksheet>';
}
function makeXlsx(sheets) {
  const STY = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
    '<fonts count="2"><font><sz val="10"/><name val="Malgun Gothic"/></font><font><b/><sz val="10"/><name val="Malgun Gothic"/></font></fonts>' +
    '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE8EEF4"/></patternFill></fill></fills>' +
    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>' +
    '<cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>' +
    '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>' +
    '<xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top"/></xf>' +
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" horizontal="left"/></xf></cellXfs>' +
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>';
  const files = [
    {name: '[Content_Types].xml', text: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' + sheets.map((s, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('') + '</Types>'},
    {name: '_rels/.rels', text: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'},
    {name: 'xl/workbook.xml', text: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + sheets.map((s, i) => `<sheet name="${s.name}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join('') + '</sheets></workbook>'},
    {name: 'xl/_rels/workbook.xml.rels', text: '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + sheets.map((s, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join('') + `<Relationship Id="rId${sheets.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`},
    {name: 'xl/styles.xml', text: STY},
    ...sheets.map((s, i) => ({name: `xl/worksheets/sheet${i + 1}.xml`, text: sheetXml(s.header, s.rows, s.numCols || new Set(), s.widths)})),
  ];
  return zip(files);
}
function download(blob, name) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}
function exportXlsx() {
  const L = current();
  if (!L.length) { alert('내보낼 장비가 없습니다.'); return; }
  const cols = DATA.cols;                                   // [[key, 머리글], ...]  (사진 제외, 텍스트만)
  const width = (h, rows) => Math.min(60, Math.max(8, h.length * 1.6, ...rows.slice(0, 300).map(r => Math.max(...String(r ?? '').split('\n').map(x => x.length)) * 1.3 + 2)));
  const eqRows = L.map(r => cols.map(([k]) => r[k] == null ? null : r[k]));
  const eqH = cols.map(c => c[1]);
  const numIdx = new Set(cols.map((c, i) => c[0] === 'price' ? i : -1).filter(i => i >= 0));
  const eq = {name: 'equipment', header: eqH, rows: eqRows, numCols: numIdx, widths: eqH.map((h, i) => width(h, eqRows.map(r => r[i])))};
  const coRows = [], hiRows = [];
  L.forEach(r => { r.comps.forEach(c => coRows.push([r.mgmt, c.seq, c.name, c.qty, c.unit])); r.hist.forEach(h => hiRows.push([r.mgmt, h.date, h.content, h.cal ? '교정' : ''])); });
  const coH = ['관리번호', '연번', '장비명', '수량', '단위'], hiH = ['관리번호', '일자', '내용', '구분'];
  const sheets = [eq,
    {name: 'components', header: coH, rows: coRows, widths: [16, 8, 40, 10, 8]},
    {name: 'history', header: hiH, rows: hiRows, widths: [16, 14, 60, 8]}];
  const d = new Date(), p = n => String(n).padStart(2, '0');
  download(makeXlsx(sheets), `장비목록_${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}.xlsx`);
}

/* ───────── 장비관리대장 양식 인쇄 ───────── */
function ledgerPages(r) {
  const F = DATA.form, e = esc, mk = (r.maker ? r.maker + (r.country ? ` (${r.country})` : '') : '');
  const date = r.date ? r.date.replace(/-/g, '.') + '.' : '';
  const price = r.price_raw || (r.price != null ? r.price.toLocaleString('ko-KR').replace(/,/g, ' ') : '');
  const tel = [r.tel, r.tel_note].filter(Boolean).join('\n');
  const n = Math.max(F.compMin, r.comps.length);
  const cols = w => '<colgroup>' + w.map(x => `<col style="width:${x}mm">`).join('') + '</colgroup>';
  const head = `<div class="hl"><span>물품명 : ${e(r.name)}</span><span>관리번호 (${e(r.mgmt)})</span></div>`;
  const photoH = F.mainRows[5] + F.compRow * (2 + n) - 3, ph = r.photos;
  let pw, phh;
  if (ph.length <= 1) { pw = 132; phh = photoH; } else if (ph.length === 2) { pw = 64; phh = photoH; } else { pw = 64; phh = photoH / 2 - 1; }
  const photos = ph.length ? `<div class="phs" style="height:${photoH}mm">${ph.slice(0, 4).map(k => `<img src="${IMG[k]}" style="width:${pw}mm;height:${phh}mm">`).join('')}</div>` : '';
  const rows = F.mainRows, ch = F.compRow;
  const comp = Array.from({length: n}, (_, i) => { const c = r.comps[i] || {}; return `<tr style="height:${ch}mm"><td>${i + 1}</td><td colspan="3">${e(c.name || '')}</td><td>${e(c.qty || '')}</td><td colspan="2">${e(c.unit || '')}</td></tr>`; }).join('');
  const front = `<div class="pg"><table class="tt"><colgroup><col style="width:24.7mm"><col style="width:230.3mm"></colgroup><tr style="height:22mm"><td>${DATA.logo ? `<img src="${DATA.logo}" style="height:19mm">` : ''}</td><td class="ti">${e(F.title)}</td></tr></table>${head}
  <table class="mn">${cols(F.mainCols)}
  <tr style="height:${rows[0]}mm"><th colspan="2" rowspan="2">형식 및<br>규격</th><th rowspan="2">제 작 회 사<br>(제 조 국)</th><th rowspan="2">도 입<br>년 월 일</th><th colspan="3" rowspan="2">도입가격 (원)</th><th colspan="3">도 입 처</th><th rowspan="2">용도 및 특기사항</th></tr>
  <tr style="height:${rows[1]}mm"><th>회 사 명</th><th>주 소</th><th>전 화 번 호</th></tr>
  <tr style="height:${rows[2]}mm"><td colspan="2" rowspan="3">${nl(r.spec || '')}</td><td rowspan="3">${nl(mk)}</td><td rowspan="3">${e(date)}</td><td colspan="3">${e(price)}</td><td rowspan="3">${nl(r.vendor || '')}</td><td rowspan="3">${nl(r.addr || '')}</td><td rowspan="3">${nl(tel)}</td><td rowspan="3">${nl(r.use || '')}</td></tr>
  <tr style="height:${rows[3]}mm"><td colspan="3">입고시 상태</td></tr>
  <tr style="height:${rows[4]}mm"><td colspan="2">${r.cond === '신품' ? '■' : '□'} 신품</td><td>${r.cond === '중고품' ? '■' : '□'}중고품</td></tr>
  <tr style="height:${rows[5]}mm"><td colspan="7" class="perf"><b>주요 성능 및 특징</b><div>${e(r.perf || '')}</div></td><td colspan="4" rowspan="${3 + n}" class="pc">${photos}</td></tr>
  <tr style="height:${ch}mm"><th colspan="7">장비구성내역</th></tr>
  <tr style="height:${ch}mm"><th>연 번</th><th colspan="3">장비명</th><th>수 량</th><th colspan="2">단위</th></tr>${comp}
  </table><div class="cap">(앞면)</div></div>`;
  const pages = [front];
  const H = r.hist.length ? r.hist : [];
  const np = Math.max(1, Math.ceil(H.length / F.histPer));
  for (let p = 0; p < np; p++) {
    const part = H.slice(p * F.histPer, (p + 1) * F.histPer), half = F.histPer / 2;
    const body = Array.from({length: half}, (_, i) => {
      const L = part[i] || {}, Rr = part[i + half] || {};
      return `<tr style="height:${F.histRows[3 + i] || 13}mm"><td>${e(L.date || '')}</td><td class="lf">${nl(L.content || '')}</td><td></td><td></td><td>${e(Rr.date || '')}</td><td class="lf">${nl(Rr.content || '')}</td><td></td><td></td></tr>`;
    }).join('');
    pages.push(`<div class="pg">${head}<table class="hs">${cols(F.histCols)}
    <tr style="height:${F.histRows[0]}mm"><th colspan="8">수리 또는 부품 교체 이력</th></tr>
    <tr style="height:${F.histRows[1]}mm"><th rowspan="2">일 자</th><th rowspan="2">내 용</th><th colspan="2">결 재</th><th rowspan="2">일 자</th><th rowspan="2">내 용</th><th colspan="2">결 재</th></tr>
    <tr style="height:${F.histRows[2]}mm"><th>담당자</th><th>팀장</th><th>담당자</th><th>팀장</th></tr>${body}</table><div class="cap">(뒷면)</div></div>`);
  }
  return pages.join('');
}
function printLedger(seqs) {
  const L = seqs ? seqs.map(s => R.find(r => r.seq === s)).filter(Boolean) : current();
  if (!L.length) { alert('인쇄할 장비가 없습니다.'); return; }
  if (L.length > 30 && !confirm(`${L.length}건(약 ${L.length * 2}쪽)을 양식으로 엽니다. 계속할까요?`)) return;
  const css = `@page{size:A4 landscape;margin:12mm 20mm 8mm 20mm}*{box-sizing:border-box}
  body{margin:0;font-family:'${DATA.form.font}','바탕','Batang','Noto Serif CJK KR',serif;color:#000}
  .pg{width:255mm;page-break-after:always}.pg:last-child{page-break-after:auto}
  table{border-collapse:collapse;table-layout:fixed;width:255mm}
  td,th{border:.3mm solid #000;padding:.6mm 1mm;text-align:center;vertical-align:middle;font-size:10pt;font-weight:normal;overflow-wrap:anywhere;line-height:1.25}
  th{font-size:11pt;font-weight:bold}
  .tt td{border:none;padding:0}.ti{font-size:24pt;font-weight:bold;letter-spacing:.5mm}
  .hl{display:flex;justify-content:space-between;font-size:12pt;font-weight:bold;margin:3mm 0 1mm}
  .perf{text-align:left;vertical-align:top;font-size:10pt}.perf b{font-size:10pt}.perf div{white-space:pre-wrap;margin-top:1mm}
  .pc{padding:0}.phs{display:flex;flex-wrap:wrap;align-content:center;justify-content:center;gap:1mm;overflow:hidden}
  .phs img{object-fit:contain}
  td.lf{text-align:left;white-space:pre-wrap}.cap{font-size:10pt;font-weight:bold;margin-top:1mm}
  .bar{position:fixed;right:8px;top:8px;font:13px sans-serif}@media print{.bar{display:none}}`;
  const doc = `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>시험장비관리대장</title><style>${css}</style></head><body>
  <div class="bar"><button onclick="print()">인쇄 / PDF 저장</button></div>${L.map(ledgerPages).join('')}</body></html>`;
  const w = window.open(URL.createObjectURL(new Blob([doc], {type: 'text/html;charset=utf-8'})), '_blank');
  if (!w) alert('팝업이 차단되었습니다. 이 페이지의 팝업을 허용한 뒤 다시 눌러 주세요.');
}

/* ───────── 이벤트 ───────── */
(function init() {
  $('sub').textContent = `원본: ${DATA.source} · 장비 ${R.length}건`;
  [...new Set(R.map(r => r.country).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ko')).forEach(c => $('country').insertAdjacentHTML('beforeend', `<option>${esc(c)}</option>`));
  ['q', 'pmin', 'pmax', 'punit', 'y1', 'y2', 'country', 'onlyPhoto', 'sort'].forEach(id => $(id).addEventListener('input', render));
  document.querySelectorAll('input[name=basis]').forEach(x => x.addEventListener('change', () => { st.basis = x.value; render(); }));
  $('chips').addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    $('punit').value = '1'; $('pmin').value = b.dataset.a; $('pmax').value = b.dataset.b; render();
  });
  $('bReset').onclick = () => { ['q', 'pmin', 'pmax', 'y1', 'y2'].forEach(id => $(id).value = ''); $('country').value = ''; $('onlyPhoto').checked = false; $('sort').value = 'seq'; $('punit').value = '1'; render(); };
  $('vCards').onclick = () => { st.view = 'cards'; render(); };
  $('vTable').onclick = () => { st.view = 'table'; render(); };
  $('bXlsx').onclick = exportXlsx;
  $('bPrint').onclick = () => printLedger();
  $('list').addEventListener('click', e => { const t = e.target.closest('[data-id]'); if (t) openModal(+t.dataset.id); });
  $('modal').addEventListener('click', e => { if (e.target.id === 'modal') closeModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
  render();
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("excel", help="마스터 엑셀(equipment.xlsx)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--photo-max", type=int, default=640, help="HTML에 넣을 사진 최대 변 길이(px)")
    a = ap.parse_args()
    if not os.path.exists(a.excel):
        sys.exit(f"엑셀 파일을 찾을 수 없습니다: {a.excel}")
    build(a.excel, a.out, a.photo_max)
