# -*- coding: utf-8 -*-
"""
공통 모듈: 장비 마스터 엑셀(equipment.xlsx)을 읽어 장비별 dict 리스트로 돌려준다.
make_catalog.py(HTML 카탈로그), make_ledger_docx.py(장비관리대장 Word 양식)가 함께 사용한다.

마스터 엑셀 구조
  equipment  : 장비 1건 = 1행 (아래 COLS 의 한글 머리글)
  components : 장비구성내역 (mgmt_no, seq, name, qty, unit)
  history    : 수리/교정 이력  (mgmt_no, hist_date, content, is_calibration ...)
  photos     : 사진 (mgmt_no, seq, file_path)  file_path 는 엑셀 파일 폴더 기준 상대경로
사용자가 엑셀에서 값을 고치거나 행을 정렬해도 '관리번호'로 연결하므로 그대로 동작한다.
"""
import os
import re

import pandas as pd

# 내부 키 -> equipment 시트의 머리글. 엑셀 머리글을 바꾸면 여기만 고치면 된다.
COLS = {
    "seq": "순번", "mgmt": "관리번호", "name": "물품명", "spec": "스펙",
    "maker": "제조사", "country": "제조국", "date": "도입시기(날짜)",
    "price_raw": "price_raw", "price": "price_krw", "units": "장비대수",
    "vendor": "도입 회사명", "addr": "도입처 주소", "tel": "연락처",
    "use": "사용 용도", "cond": "상태", "perf": "내용",
    "item_no": "물품분류번호", "mgmt_hist": "관리 이력", "tel_note": "연락처 비고",
}


def clean(v):
    """NaN/빈 문자열 -> None, 정수형 실수 -> int, 문자열은 strip"""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def _sheet(xl, name):
    for s in xl.sheet_names:
        if s.strip().lower() == name:
            return pd.read_excel(xl, s, dtype=object)
    return pd.DataFrame()


def _num(v):
    v = clean(v)
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    d = re.sub(r"[^\d]", "", str(v))
    return int(d) if d else None


def load_master(excel_path):
    """-> (records, logo_path or None)"""
    excel_path = os.path.abspath(excel_path)
    base = os.path.dirname(excel_path)
    xl = pd.ExcelFile(excel_path)
    eq = _sheet(xl, "equipment")
    if eq.empty:
        raise ValueError("equipment 시트를 찾을 수 없습니다.")
    eq.columns = [str(c).strip() for c in eq.columns]
    co, hi, ph = _sheet(xl, "components"), _sheet(xl, "history"), _sheet(xl, "photos")

    def group(df):
        g = {}
        if df.empty:
            return g
        df.columns = [str(c).strip() for c in df.columns]
        for _, row in df.iterrows():
            g.setdefault(clean(row.get("mgmt_no")), []).append(row)
        return g

    gco, ghi, gph = group(co), group(hi), group(ph)
    recs = []
    for i, (_, row) in enumerate(eq.iterrows(), 1):
        r = {k: clean(row.get(h)) for k, h in COLS.items()}
        if not r["mgmt"]:
            continue
        r["seq"] = _num(r["seq"]) or i
        r["price"] = _num(r["price"])
        r["units"] = _num(r["units"]) or 1
        r["date"] = str(r["date"])[:10] if r["date"] else None
        for k in ("spec", "maker", "country", "vendor", "addr", "tel", "use", "cond", "perf",
                  "item_no", "mgmt_hist", "tel_note", "price_raw", "name"):
            if r[k] is not None:
                r[k] = str(r[k])
        r["comps"] = [{"seq": clean(x.get("seq")), "name": clean(x.get("name")),
                       "qty": clean(x.get("qty")), "unit": clean(x.get("unit"))}
                      for x in gco.get(r["mgmt"], [])]
        r["hist"] = [{"date": clean(x.get("hist_date")), "content": clean(x.get("content")),
                      "cal": int(_num(x.get("is_calibration")) or 0)}
                     for x in ghi.get(r["mgmt"], [])]
        photos = []
        for x in sorted(gph.get(r["mgmt"], []), key=lambda x: _num(x.get("seq")) or 0):
            fp = clean(x.get("file_path"))
            if fp:
                p = os.path.join(base, fp)
                if os.path.exists(p):
                    photos.append(p)
        r["photos"] = photos
        recs.append(r)
    logo = os.path.join(base, "logo.png")
    return recs, (logo if os.path.exists(logo) else None)


def dot_date(iso):
    """1995-01-21 -> 1995.01.21."""
    if not iso:
        return ""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso)
    return f"{m.group(1)}.{m.group(2)}.{m.group(3)}." if m else iso


def maker_text(r):
    """제작회사(제조국) 칸에 들어갈 문자열: 'SANYO (일본)'"""
    if not r["maker"]:
        return ""
    return f"{r['maker']} ({r['country']})" if r["country"] else r["maker"]


def price_text(r):
    """도입가격 칸: 원문(price_raw) 우선, 없으면 정수를 천 단위 공백으로"""
    if r["price_raw"]:
        return r["price_raw"]
    if r["price"] is not None:
        return f"{r['price']:,}".replace(",", " ")
    return ""


def tel_text(r):
    return "\n".join(x for x in (r["tel"], r["tel_note"]) if x)


# ── 양식(원본 HWP에서 측정한 치수, 단위 mm) ─────────────────────────
MAIN_COLS = [17.7, 9.8, 27.5, 27.5, 17.3, 1.5, 17.8, 27.5, 27.5, 31.5, 49.5]      # 앞면 표 11열
MAIN_ROWS = [5.3, 5.3, 6.5, 6.5, 4.5, 47.8]                                        # 앞면 표 앞쪽 행 높이
COMP_ROW = 8.8                                                                      # 구성내역 행 높이
COMP_MIN_ROWS = 5                                                                   # 구성내역 기본 행 수
HIST_COLS = [26.8, 53.8, 23.4, 24.4, 25.4, 54.4, 23.9, 23.9]                        # 뒷면 표 8열
HIST_ROWS = [9.0, 7.5, 7.5] + [13.0] * 9                                            # 제목, 머리글2행, 데이터 9행
HIST_PER_PAGE = 18                                                                  # 왼쪽 9 + 오른쪽 9
TITLE_TEXT = "시 험 장 비 관 리 대 장"
FONT_NAME = "경기천년바탕 Regular"   # 원본 글꼴. PC에 없으면 '바탕' 또는 '맑은 고딕'으로 바꾸세요.
