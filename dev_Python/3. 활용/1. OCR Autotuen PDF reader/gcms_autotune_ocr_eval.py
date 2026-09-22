#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gcms_autotune_ocr_eval.py
==========================================================================
Agilent GC/MS(5977 계열) Autotune 리포트(atune.u 출력물)를 스캔 이미지 또는
PDF로 입력받아 OCR로 판독하고, 사전 정의된 판정 기준(규칙 기반)에 따라
항목별로 평가한 뒤 A4 한 장짜리 PDF 평가서를 생성하는 프로그램.

------------------------------------------------------------------------
파이프라인 구조 (규칙 기반 OCR 파이프라인)
------------------------------------------------------------------------
1. 입력 처리   : PDF -> 300dpi 이미지 렌더링 (pdf2image), 이미지 파일은 그대로 사용
2. 관심영역 분할(ROI) : Autotune 리포트는 매번 동일한 고정 양식으로 출력되므로,
                 좌/우로 나뉜 구간을 통째로 OCR하지 않고 표(파라미터 표,
                 Actual m/z 표, Temperatures and Pressures, Target m/z 표,
                 Ramp Criteria)별로 잘라서 각각 OCR한다.
                 -> 좌/우 열이 한 줄에서 섞여 읽히는 "컬럼 번짐" 오류를 방지.
3. 전처리      : 격자선이 있는 표(파라미터 표)는 모폴로지 연산으로 테두리 선을
                 제거한 뒤 OCR한다 -> 격자선 때문에 통째로 누락되던 행(Ion Focus 등)
                 복구.
4. OCR         : pytesseract(Tesseract 5) 사용, 표 영역은 --psm 6.
5. 정규식 추출 : 리포트 항목명이 항상 같은 위치/문구로 출력된다는 점을 이용해
                 정규식으로 값만 추출. OCR 오탈자에 대비해 관대한 패턴 사용.
6. 판정 로직   : 각 항목마다 미리 정의된 [정상/주의/경고] 범위(CRITERIA)와
                 비교하여 등급을 매긴다. Repeller/Ion Focus는 리포트 자체에
                 인쇄된 Ramp Criteria 최대값을 기준으로 상대(%) 판정한다.
7. 출력        : reportlab로 A4 한 페이지에 들어가는 표 형태의 평가서(PDF) 생성.

------------------------------------------------------------------------
사용법
------------------------------------------------------------------------
    python3 gcms_autotune_ocr_eval.py <입력파일.pdf|.png|.jpg> [-o 출력.pdf]

필요 패키지 (전부 pip 설치 가능):
    pytesseract, opencv-python, pillow, pdf2image, numpy, reportlab
    시스템 : tesseract-ocr, poppler-utils(=pdftoppm, pdf2image가 사용)

------------------------------------------------------------------------
주의
------------------------------------------------------------------------
- ROI 좌표(비율)는 MassHunter의 표준 Autotune 인쇄 양식(atune.u) 기준으로
  잡은 값이다. 스캐너/프린터 설정에 따라 여백이 달라지면 ROI 좌표를
  `ROI` 딕셔너리에서 조정해야 한다.
- OCR은 100% 정확할 수 없으므로, 물리적으로 말이 안 되는 값(예: Mass
  배정이 기준 이온과 2 이상 차이)이 나오면 "판정 보류(OCR 재확인 필요)"로
  표시하고 자동으로 FAIL 처리하지 않는다. 최종 판단은 반드시 원본 대조 후
  사람이 확정한다.
- 판정 기준값(CRITERIA)은 Agilent 5977 시리즈 권장값을 기본값으로 넣어둔
  것이며, 사내 SOP나 장비별 이력에 맞게 CRITERIA 딕셔너리만 수정하면 된다.
"""

import os
import re
import sys
import argparse
import warnings
from datetime import datetime

import cv2
import numpy as np
import pytesseract
from PIL import Image

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

warnings.filterwarnings("ignore")

# ==========================================================================
# 0. 한글 폰트 등록
#    실제 트루타입 한글 폰트(맑은 고딕 등)를 찾으면 PDF에 임베드하여 어떤
#    PDF 뷰어에서도 동일하게 보이도록 하고, 못 찾으면 reportlab 내장
#    CID 폰트(HYGothic-Medium, 임베딩 없이 뷰어의 CJK 폰트로 대체 표시)로
#    자동 대체한다. Windows에서 실행하면 맑은 고딕이 우선 선택된다.
# ==========================================================================
def register_korean_font():
    candidates = [
        ("MalgunGothic", r"C:\Windows\Fonts\malgun.ttf", r"C:\Windows\Fonts\malgunbd.ttf"),
        ("MalgunGothic", "/mnt/c/Windows/Fonts/malgun.ttf", "/mnt/c/Windows/Fonts/malgunbd.ttf"),
        ("NanumGothic", "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                         "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),
        ("AppleGothic", "/System/Library/Fonts/Supplemental/AppleGothic.ttf", None),
    ]
    for name, reg_path, bold_path in candidates:
        if os.path.exists(reg_path):
            pdfmetrics.registerFont(TTFont(name, reg_path))
            bold_name = name
            if bold_path and os.path.exists(bold_path):
                pdfmetrics.registerFont(TTFont(name + "-Bold", bold_path))
                bold_name = name + "-Bold"
            pdfmetrics.registerFontFamily(
                name, normal=name, bold=bold_name, italic=name, boldItalic=bold_name)
            return name, bold_name
    # 마지막 대체: 별도 폰트 파일 없이 동작하는 reportlab 내장 CID 폰트
    pdfmetrics.registerFont(UnicodeCIDFont("HYGothic-Medium"))
    return "HYGothic-Medium", "HYGothic-Medium"


KFONT, KFONT_BOLD = register_korean_font()

# ==========================================================================
# 1. 판정 기준표 (여기만 수정하면 기준을 바꿀 수 있음)
#    각 항목: 정상범위 / 주의범위 / 그 외는 경고(FAIL)
# ==========================================================================
CRITERIA_NOTE = {
    "mass_assign":  "Actual m/z가 69.0/219.0/502.0 대비 ±0.2 이내",
    "pw50":         "Peak Width(50%) 0.60 ± 0.05",
    "rel_219":      "Rel Abund(219) ≥ 40%",
    "rel_502":      "Rel Abund(502) ≥ 2%",
    "iso_ratio":    "이론값(1.08 / 4.32 / 10.09%) 대비 ±20% 이내",
    "abund69":      "m/z 69 절대 Abundance 200,000 ~ 550,000 counts",
    "em_volts":     "1,400~1,600V 정상 / 1,600~2,800V 주의 / 2,800V~ 경고",
    "repeller_pct": "Ramp Criteria 상한 대비 90% 미만 정상",
    "ionfocus_pct": "Ramp Criteria 상한 대비 85% 미만 정상",
    "airwater":     "H2O·N2·O2 모두 m/z69 대비 10% 미만",
    "hivac":        "1×10^-6 ~ 1.4×10^-4 Torr",
    "turbo":        "Turbo Speed 100%(≥95%) 유지",
}

ISO_THEORY = {70: 1.08, 220: 4.32, 503: 10.09}

# ==========================================================================
# 2. ROI 좌표 (전체 페이지 대비 비율 x1,y1,x2,y2) - atune.u 표준 인쇄 양식 기준
# ==========================================================================
ROI = {
    "header":      (0.03, 0.000, 0.97, 0.115),
    "param_table": (0.555, 0.115, 0.935, 0.315),   # 격자선 있는 파라미터 표
    "actual_mz":   (0.05, 0.325, 0.57, 0.405),     # Actual m/z / Abund / PW50
    "temp_press":  (0.555, 0.325, 0.935, 0.400),   # Temperatures and Pressures
    "target_tbl":  (0.05, 0.615, 0.935, 0.705),    # Target m/z 표 + Air/Water
    "ramp":        (0.05, 0.735, 0.935, 0.775),    # Ramp Criteria
}

# ==========================================================================
# 3. 이미지 입력 / 전처리 유틸
# ==========================================================================
def load_page_image(path: str, dpi: int = 300) -> Image.Image:
    """PDF든 이미지든 받아서 첫 페이지를 PIL 이미지로 반환한다."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        from pdf2image import convert_from_path
        pages = convert_from_path(path, dpi=dpi)
        if not pages:
            raise ValueError("PDF에서 페이지를 렌더링하지 못했습니다.")
        return pages[0].convert("RGB")
    return Image.open(path).convert("RGB")


def crop_frac(img: Image.Image, box_frac):
    """비율 좌표(0~1) 박스를 픽셀 좌표로 변환해 크롭한다."""
    w, h = img.size
    x1, y1, x2, y2 = box_frac
    return img.crop((int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h)))


def remove_gridlines(gray: np.ndarray) -> np.ndarray:
    """표 격자선을 모폴로지 연산으로 제거해 OCR 누락을 방지한다."""
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1)))
    vert = cv2.morphologyEx(bw, cv2.MORPH_OPEN,
                             cv2.getStructuringElement(cv2.MORPH_RECT, (1, 25)))
    lines = cv2.bitwise_or(horiz, vert)
    clean = cv2.bitwise_and(bw, cv2.bitwise_not(lines))
    return cv2.bitwise_not(clean)  # 흰 배경 검은 글씨로 복원


def ocr_region(page_img: Image.Image, roi_key: str, psm: int = 6) -> str:
    crop_img = crop_frac(page_img, ROI[roi_key])
    gray = cv2.cvtColor(np.array(crop_img), cv2.COLOR_RGB2GRAY)
    if roi_key == "param_table":
        gray = remove_gridlines(gray)
    return pytesseract.image_to_string(gray, config=f"--psm {psm}")


# ==========================================================================
# 4. 정규식 기반 필드 추출
# ==========================================================================
def _search(pattern, text, flags=re.IGNORECASE):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def _to_float(s):
    if s is None:
        return None
    s = s.replace(",", "").replace("~", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def extract_all_fields(page_img: Image.Image):
    """모든 ROI를 OCR하고 정규식으로 값을 뽑아 dict로 반환한다."""
    raw = {key: ocr_region(page_img, key) for key in ROI}
    data = {}

    # --- 헤더 (메타정보) ---
    data["title"] = _search(r"(Autotune\s*-?\s*\d+)", raw["header"])
    data["timestamp"] = _search(
        r"Tune\s*timestamp:\s*([0-9/]+\s+[0-9:]+\s*[AP]M[^\n]*)", raw["header"])
    data["method_path"] = _search(r"([A-Za-z]:\\[^\s]+\.u)", raw["header"])

    # --- 파라미터 표 (격자선 제거 후 OCR) ---
    pt = raw["param_table"]
    data["repeller"] = _to_float(_search(r"Repel\w*\D+([\d]+\.?\d*)", pt))
    data["ion_focus"] = _to_float(_search(r"[IJi][oc0]n\s*Focus\D+([\d]+\.?\d*)", pt))
    data["em_volts"] = _to_float(_search(r"EM\s*Vo[l1]ts?\D+([\d,]+\.?\d*)", pt))

    # --- Actual m/z 표 (PW50) ---
    am = raw["actual_mz"]
    pw_matches = re.findall(
        r"(\d{2,3}\.\d{1,2})\s+[\d,]+\s+\d{1,3}\.\d%\s+(\d\.\d{2})", am)
    data["pw50_list"] = [float(pw) for _, pw in pw_matches] if pw_matches else []

    # --- Temperatures and Pressures ---
    tp = raw["temp_press"]
    data["turbo_speed"] = _to_float(_search(r"Turbo\s*Speed\D*([\d.]+)", tp))
    data["hi_vac"] = _search(r"Hi\s*Vac\D*([\d.]+e[+-]?\d+)", tp, re.IGNORECASE)
    if data["hi_vac"] is None:
        data["hi_vac_val"] = None
    else:
        try:
            data["hi_vac_val"] = float(data["hi_vac"])
        except ValueError:
            data["hi_vac_val"] = None

    # --- Target m/z 표 (mass 배정 / Rel Abund / Isotope Ratio) ---
    tt = raw["target_tbl"]
    rows = re.findall(
        r"(\d{2,3}\.\d{2})\s+(\d{2,3}\.\d{2})\s+([\d,]+)\s+(\d{1,3}\.\d)%\s+"
        r"(\d{2,3}\.\d{2})\s+([\d,]+)\s+(\d{1,3}\.\d)%", tt)
    target_rows = []
    for target_mz, actual_mz, abund, rel_abund, iso_mz, iso_abund, iso_ratio in rows:
        target_rows.append({
            "target_mz": float(target_mz),
            "actual_mz": float(actual_mz),
            "abund": float(abund.replace(",", "")),
            "rel_abund": float(rel_abund),
            "iso_mz": float(iso_mz),
            "iso_abund": float(iso_abund.replace(",", "")),
            "iso_ratio": float(iso_ratio),
        })
    data["target_rows"] = target_rows

    aw = _search(
        r"H2?0\D+~?([\d.]+)%\s*N2\D+~?([\d.]+)%\s*O2\D+~?([\d.]+)%\s*CO2\D+~?([\d.]+)%",
        tt.replace("\n", " "))
    m = re.search(
        r"H2?0\D+~?([\d.]+)%\s*N2\D+~?([\d.]+)%\s*O2\D+~?([\d.]+)%\s*CO2\D+~?([\d.]+)%",
        tt.replace("\n", " "), re.IGNORECASE)
    if m:
        data["h2o"], data["n2"], data["o2"], data["co2"] = map(float, m.groups())
    else:
        data["h2o"] = data["n2"] = data["o2"] = data["co2"] = None

    # --- Ramp Criteria (Repeller/Ion Focus 최대값) ---
    rp = raw["ramp"]
    data["ion_focus_max"] = _to_float(
        _search(r"[FfIiJj]on\s*Focus\s*maximum\D*(\d+)\s*volts", rp))
    data["repeller_max"] = _to_float(
        _search(r"Repe[l1]+\w*\s*maximum\D*(\d+)\s*volts", rp))

    data["_raw_ocr"] = raw
    return data


# ==========================================================================
# 5. 판정 로직 (규칙 기반)
# ==========================================================================
PASS, WARN, FAIL, UNKNOWN = "정상", "주의", "경고", "확인필요"


def grade(label, value, ok, warn=None):
    """value가 None이면 확인필요, ok(bool)면 정상, warn(bool)이면 주의, 아니면 경고."""
    if value is None:
        return UNKNOWN
    if ok:
        return PASS
    if warn:
        return WARN
    return FAIL


def evaluate(data: dict):
    rows = []  # (항목, 측정값, 기준, 판정)
    target_rows = data.get("target_rows", [])
    by_target = {int(round(r["target_mz"])): r for r in target_rows}

    # 1) Mass 배정 정확도
    mass_devs = []          # (target, dev) 신뢰 가능한 편차만
    uncertain_targets = []  # OCR 신뢰도 낮아 판정 보류된 target m/z
    for t in (69, 219, 502):
        r = by_target.get(t)
        if r is None:
            uncertain_targets.append(t)
            continue
        dev = abs(r["actual_mz"] - t)
        if dev > 2.0:
            uncertain_targets.append(t)  # 물리적으로 불가능한 편차 -> OCR 오독 가능성
        else:
            mass_devs.append((t, dev))
    if uncertain_targets:
        verdict = UNKNOWN
    elif mass_devs and max(d for _, d in mass_devs) <= 0.2:
        verdict = PASS
    else:
        verdict = FAIL
    dev_str = ", ".join(f"{t}: {d:.2f}" for t, d in mass_devs) if mass_devs else "-"
    if uncertain_targets:
        unc_str = "/".join(str(t) for t in uncertain_targets)
        val_str = f"{dev_str} (m/z {unc_str} 판독 불확실 - 원본 대조 필요)"
    else:
        val_str = f"편차 {dev_str}"
    rows.append(("Mass 배정 정확도 (69/219/502)", val_str,
                 CRITERIA_NOTE["mass_assign"], verdict))

    # 2) PW50
    pw_list = data.get("pw50_list", [])
    if not pw_list:
        verdict = UNKNOWN
        val_str = "판독불가"
    else:
        ok = all(0.55 <= v <= 0.65 for v in pw_list)
        verdict = PASS if ok else FAIL
        val_str = ", ".join(f"{v:.2f}" for v in pw_list)
    rows.append(("Peak Width (PW50)", val_str, CRITERIA_NOTE["pw50"], verdict))

    # 3) Rel Abund (219, 502)
    r219 = by_target.get(219)
    val = r219["rel_abund"] if r219 else None
    verdict = grade("rel219", val, val is not None and val >= 40)
    rows.append(("Rel Abund (m/z 219)",
                 f"{val:.1f}%" if val is not None else "판독불가",
                 CRITERIA_NOTE["rel_219"], verdict))

    r502 = by_target.get(502)
    val = r502["rel_abund"] if r502 else None
    verdict = grade("rel502", val, val is not None and val >= 2)
    rows.append(("Rel Abund (m/z 502)",
                 f"{val:.1f}%" if val is not None else "판독불가",
                 CRITERIA_NOTE["rel_502"], verdict))

    # 4) Isotope Ratio (70/220/503)
    iso_devs_pct = []
    iso_uncertain = not target_rows
    for r in target_rows:
        theo = ISO_THEORY.get(int(round(r["iso_mz"])))
        if theo:
            iso_devs_pct.append(abs(r["iso_ratio"] - theo) / theo * 100)
    if iso_uncertain or not iso_devs_pct:
        verdict = UNKNOWN
        val_str = "판독불가"
    else:
        ok = max(iso_devs_pct) <= 20
        verdict = PASS if ok else WARN
        val_str = ", ".join(f"{r['iso_ratio']:.1f}%" for r in target_rows)
    rows.append(("Isotope Ratio (70/220/503)", val_str,
                 CRITERIA_NOTE["iso_ratio"], verdict))

    # 5) m/z 69 절대 Abundance
    r69 = by_target.get(69)
    val = r69["abund"] if r69 else None
    ok = val is not None and 200000 <= val <= 550000
    verdict = grade("abund69", val, ok)
    rows.append(("m/z 69 절대 Abundance",
                 f"{val:,.0f} counts" if val is not None else "판독불가",
                 CRITERIA_NOTE["abund69"], verdict))

    # 6) EM Volts
    em = data.get("em_volts")
    if em is None:
        verdict = UNKNOWN
    elif em <= 1600:
        verdict = PASS
    elif em <= 2800:
        verdict = WARN
    else:
        verdict = FAIL
    rows.append(("EM Volts", f"{em:,.1f} V" if em is not None else "판독불가",
                 CRITERIA_NOTE["em_volts"], verdict))

    # 7) Repeller (Ramp Criteria 상한 대비 %)
    rep, rep_max = data.get("repeller"), data.get("repeller_max")
    if rep is not None and rep_max:
        pct = rep / rep_max * 100
        verdict = PASS if pct < 90 else WARN
        val_str = f"{rep:.2f}V (상한 대비 {pct:.0f}%)"
    else:
        verdict = UNKNOWN
        val_str = "판독불가"
    rows.append(("Repeller", val_str, CRITERIA_NOTE["repeller_pct"], verdict))

    # 8) Ion Focus (Ramp Criteria 상한 대비 %)
    ifc, ifc_max = data.get("ion_focus"), data.get("ion_focus_max")
    if ifc is not None and ifc_max:
        pct = ifc / ifc_max * 100
        verdict = PASS if pct < 85 else WARN
        val_str = f"{ifc:.1f}V (상한 대비 {pct:.0f}%)"
    else:
        verdict = UNKNOWN
        val_str = "판독불가"
    rows.append(("Ion Focus", val_str, CRITERIA_NOTE["ionfocus_pct"], verdict))

    # 9) Air/Water
    h2o, n2, o2 = data.get("h2o"), data.get("n2"), data.get("o2")
    if None in (h2o, n2, o2):
        verdict = UNKNOWN
        val_str = "판독불가"
    else:
        ok = max(h2o, n2, o2) < 10
        verdict = PASS if ok else WARN
        val_str = f"H2O {h2o:.1f}% / N2 {n2:.1f}% / O2 {o2:.1f}%"
    rows.append(("Air/Water Check", val_str, CRITERIA_NOTE["airwater"], verdict))

    # 10) Hi Vac 압력
    hv = data.get("hi_vac_val")
    ok = hv is not None and 1e-6 <= hv <= 1.4e-4
    verdict = grade("hivac", hv, ok)
    rows.append(("Hi Vac (Analyzer 압력)",
                 f"{hv:.2e} Torr" if hv is not None else "판독불가",
                 CRITERIA_NOTE["hivac"], verdict))

    # 11) Turbo Speed
    ts = data.get("turbo_speed")
    ok = ts is not None and ts >= 95
    verdict = grade("turbo", ts, ok)
    rows.append(("Turbo Speed", f"{ts:.1f}%" if ts is not None else "판독불가",
                 CRITERIA_NOTE["turbo"], verdict))

    return rows


# ==========================================================================
# 6. PDF 리포트 생성 (A4 한 페이지)
# ==========================================================================
VERDICT_COLOR = {
    PASS: colors.HexColor("#E2EFDA"),
    WARN: colors.HexColor("#FFF2CC"),
    FAIL: colors.HexColor("#F8CBAD"),
    UNKNOWN: colors.HexColor("#D9D9D9"),
}


def build_pdf(data, rows, src_path, out_path):
    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        topMargin=1.0 * cm, bottomMargin=1.0 * cm,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm,
    )

    style_title = ParagraphStyle("title", fontName=KFONT, fontSize=15,
                                  leading=18, alignment=TA_LEFT)
    style_sub = ParagraphStyle("sub", fontName=KFONT, fontSize=8.5,
                                leading=12, alignment=TA_LEFT,
                                textColor=colors.HexColor("#444444"))
    style_cell = ParagraphStyle("cell", fontName=KFONT, fontSize=8,
                                 leading=10, alignment=TA_LEFT)
    style_cell_c = ParagraphStyle("cellc", fontName=KFONT, fontSize=8,
                                   leading=10, alignment=TA_CENTER)
    style_header = ParagraphStyle("header", fontName=KFONT, fontSize=8.5,
                                   leading=10, alignment=TA_CENTER,
                                   textColor=colors.white)

    story = []
    story.append(Paragraph("GC/MS Autotune 자동 판독 평가서", style_title))

    n_pass = sum(1 for r in rows if r[3] == PASS)
    n_warn = sum(1 for r in rows if r[3] == WARN)
    n_fail = sum(1 for r in rows if r[3] == FAIL)
    n_unk = sum(1 for r in rows if r[3] == UNKNOWN)
    overall = "경고" if n_fail else ("주의" if n_warn or n_unk else "정상"
                                    ) if not n_unk else ("경고" if n_fail else "주의")
    overall = "경고" if n_fail else ("주의" if (n_warn or n_unk) else "정상")

    meta_line1 = (
        f"장비: Agilent 5977 GC/MSD ({data.get('title') or 'Autotune'})   |   "
        f"튠 일시: {data.get('timestamp') or '판독불가'}"
    )
    meta_line2 = (
        f"메소드: {data.get('method_path') or '판독불가'}   |   "
        f"원본 파일: {os.path.basename(src_path)}   |   "
        f"평가 처리시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    story.append(Paragraph(meta_line1, style_sub))
    story.append(Paragraph(meta_line2, style_sub))
    story.append(Spacer(1, 6))

    summary_txt = (
        f"<b>종합판정: {overall}</b>  "
        f"(정상 {n_pass} · 주의 {n_warn} · 경고 {n_fail} · 확인필요 {n_unk} / 총 {len(rows)}항목)"
    )
    summary_style = ParagraphStyle("summary", fontName=KFONT, fontSize=10,
                                    leading=13, alignment=TA_LEFT)
    summary_table = Table(
        [[Paragraph(summary_txt, summary_style)]],
        colWidths=[doc.width],
    )
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1),
         VERDICT_COLOR[FAIL] if overall == "경고" else
         VERDICT_COLOR[WARN] if overall == "주의" else VERDICT_COLOR[PASS]),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 8))

    # 항목별 평가 표
    header = ["항목", "측정값", "판정 기준", "판정"]
    col_w = [doc.width * 0.24, doc.width * 0.24, doc.width * 0.38, doc.width * 0.14]
    table_data = [[Paragraph(h, style_header) for h in header]]
    for name, val, crit, verdict in rows:
        table_data.append([
            Paragraph(name, style_cell),
            Paragraph(val, style_cell),
            Paragraph(crit, style_cell),
            Paragraph(verdict, style_cell_c),
        ])

    tbl = Table(table_data, colWidths=col_w, repeatRows=1)
    ts = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#404040")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFBFBF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ])
    for i, r in enumerate(rows, start=1):
        ts.add("BACKGROUND", (3, i), (3, i), VERDICT_COLOR[r[3]])
    tbl.setStyle(ts)
    story.append(tbl)
    story.append(Spacer(1, 8))

    note = (
        "※ '확인필요'는 OCR 인식 신뢰도가 낮거나(격자선/스캔 품질 등) 물리적으로 "
        "불가능한 값이 검출되어 자동 판정을 보류한 항목입니다. 원본 리포트와 반드시 "
        "대조 확인하십시오. 판정 기준은 Agilent 5977 시리즈 권장값이며 사내 기준으로 "
        "교체 가능합니다."
    )
    story.append(Paragraph(note, ParagraphStyle(
        "note", fontName=KFONT, fontSize=7, leading=9,
        textColor=colors.HexColor("#666666"))))

    doc.build(story)


# ==========================================================================
# 7. 메인
# ==========================================================================
def main():
    ap = argparse.ArgumentParser(description="GC/MS Autotune 리포트 OCR 자동 평가")
    ap.add_argument("input", help="입력 파일 (PDF 스캔 또는 이미지)")
    ap.add_argument("-o", "--output", default=None, help="출력 PDF 경로")
    ap.add_argument("--dpi", type=int, default=300, help="PDF 렌더링 해상도(기본 300)")
    ap.add_argument("--dump-json", default=None, help="추출값을 JSON으로 저장할 경로(선택)")
    args = ap.parse_args()

    out_path = args.output or (
        os.path.splitext(os.path.basename(args.input))[0] + "_평가서.pdf"
    )

    page_img = load_page_image(args.input, dpi=args.dpi)
    data = extract_all_fields(page_img)
    rows = evaluate(data)
    build_pdf(data, rows, args.input, out_path)

    if args.dump_json:
        import json
        dump = {k: v for k, v in data.items() if k != "_raw_ocr"}
        with open(args.dump_json, "w", encoding="utf-8") as f:
            json.dump(dump, f, ensure_ascii=False, indent=2)

    print(f"평가서 생성 완료: {out_path}")
    n_fail = sum(1 for r in rows if r[3] == FAIL)
    n_warn = sum(1 for r in rows if r[3] == WARN)
    n_unk = sum(1 for r in rows if r[3] == UNKNOWN)
    print(f"  정상 {sum(1 for r in rows if r[3]==PASS)} / 주의 {n_warn} "
          f"/ 경고 {n_fail} / 확인필요 {n_unk}")


if __name__ == "__main__":
    main()
