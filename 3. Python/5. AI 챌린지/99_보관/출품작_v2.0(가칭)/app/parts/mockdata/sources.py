# -*- coding: utf-8 -*-
"""[가상자료 ④] 원본 엑셀 만들기. 같은 표라도 원본은 문서와 '다르게' 생기게 한다.

배치 변형(variant)
  transpose  : 행·열 뒤바꿈            shuffle   : 행 순서 섞기
  extra_cols : 문서에 없는 열 더하기    extra_rows: 문서에 없는 행 더하기
  with_total : 원본에 합계 행 넣기      filler    : 사용안내·세부 대장 시트 더하기
  (표 자체 설정) src_cols/src_rows: 다른 머리글·코드, src_scale: 원 단위, monthly: 월별 시트 + 평균

돌려주는 것: {"file", "sheets", "cellmap": {(행, 열): "시트!A1"}, "numbers": {원본에 들어간 숫자}}
"""
from app.formats.xlsx import ref as a1ref

H = {"bold": True, "fill": "#DDE6F0", "align": "center"}
TOTAL_LABELS = ["합계", "합계", "계", "총계"]


def hd(v):
    return dict(H, v=v)


def _fmt(dec):
    return "#,##0" if dec <= 0 else "#,##0." + "0" * dec


def raw_value(t, r, c):
    """원본에 적는 값(반올림 전, 배율 적용)."""
    v = t.values[(r, c)]
    sc = t.src_scale.get(c, 1)
    if sc != 1:
        return int(round(v * sc))
    if t.dec(r, c) == 0 and float(v).is_integer():
        return int(v)
    return v


def raw_fmt(t, r, c):
    sc = t.src_scale.get(c, 1)
    if sc != 1:
        return "#,##0"
    if t.ratio and c == t.ratio[0]:
        return "0.0"
    d = t.dec(r, c)
    return _fmt(d + 1 if d else 0) if not t.monthly else "0.000"


def _extra_value(rng, t, c):
    vs = [t.values[(r, c)] for r in t.body_rows()]
    lo, hi = min(vs), max(vs)
    x = rng.uniform(lo * 0.8, hi * 1.2 + 1)
    if t.dec(t.body_rows()[0], c) == 0 and all(float(v).is_integer() for v in vs):
        return int(x)
    return round(x, t.dec(t.body_rows()[0], c) + 1)


def build_source(t, rng, variant, year):
    nums = set()
    cellmap = {}
    sheets = []
    rows_order = list(t.body_rows())
    if variant.get("shuffle"):
        rng.shuffle(rows_order)
    total_label = rng.choice(TOTAL_LABELS)
    show_total = t.total and variant.get("with_total", True)
    transpose = getattr(t, "force_transpose", False) or (t.allow_transpose and variant.get("transpose"))
    sheet = t.src_sheet
    extra_cols = []
    for i in range(variant.get("extra_cols", 0)):
        extra_cols.append(f"참고{i + 1}")
    ex_src_cols = getattr(t, "extra_src_cols", {})
    ex_src_rows = getattr(t, "extra_src_rows", {})

    title = [[{"v": t.src_title, "bold": True, "border": False}], [{"v": t.sheet_unit or t.unit, "border": False}]]
    grid = []
    if not transpose:
        head = [hd(t.row_head)] + [hd(t.src_cols.get(c, c)) for c in t.cols] + [hd(k) for k in ex_src_cols] + \
               [hd(c) for c in extra_cols]
        grid.append(head)
        order = rows_order + ([t.TOTAL] if show_total else [])
        for r in order:
            lab = total_label if r == t.TOTAL else t.src_rows.get(r, r)
            line = [hd(lab) if r == t.TOTAL else lab]
            for c in t.cols:
                v = raw_value(t, r, c)
                cellmap[(r, c)] = f"{sheet}!{a1ref(len(title) + len(grid), len(line))}"
                nums.add(round(float(v), 6))
                line.append({"v": v, "fmt": raw_fmt(t, r, c)})
            for k, d in ex_src_cols.items():
                v = sum(d.values()) if r == t.TOTAL else d[r]
                nums.add(float(v))
                line.append(v)
            for c in extra_cols:
                v = _extra_value(rng, t, t.cols[0])
                nums.add(round(float(v), 6))
                line.append(v)
            grid.append(line)
        for k, v in ex_src_rows.items():
            grid.append([k] + [v if i == len(t.cols) - 1 else "" for i in range(len(t.cols))])
            nums.add(float(v))
        for i in range(variant.get("extra_rows", 0)):
            line = [f"기타{i + 1}"]
            for c in t.cols:
                v = _extra_value(rng, t, c)
                nums.add(round(float(v), 6))
                line.append(v)
            grid.append(line)
    else:
        order = rows_order + ([t.TOTAL] if show_total else [])
        cols = list(t.cols)
        if variant.get("shuffle"):
            rng.shuffle(cols)
        grid.append([hd(t.row_head if t.row_head != "구분" else "측정소")] + [hd(t.src_rows.get(r, r)) for r in order])
        for c in cols:
            line = [t.src_cols.get(c, c)]
            for r in order:
                v = raw_value(t, r, c)
                cellmap[(r, c)] = f"{sheet}!{a1ref(len(title) + len(grid), len(line))}"
                nums.add(round(float(v), 6))
                line.append({"v": v, "fmt": raw_fmt(t, r, c)})
            grid.append(line)
        # 뒤집은 표: 원본의 행 = 문서의 열, 원본의 열 = 문서의 행
        cellmap = {}
        rlabs = [x["v"] if isinstance(x, dict) else x for x in [row[0] for row in grid]]
        clabs = [x["v"] if isinstance(x, dict) else x for x in grid[0]]
        inv_r = {t.src_rows.get(r, r): r for r in order}
        inv_r[total_label] = t.TOTAL
        inv_c = {t.src_cols.get(c, c): c for c in t.cols}
        for gi in range(1, len(grid)):
            for gj in range(1, len(grid[gi])):
                c = inv_c.get(rlabs[gi])
                r = inv_r.get(clabs[gj])
                if r is not None and c is not None:
                    cellmap[(r, c)] = f"{sheet}!{a1ref(len(title) + gi, gj)}"
        grid = [[hd(x["v"] if isinstance(x, dict) else x) if i == 0 or j == 0 else x for j, x in enumerate(row)]
                for i, row in enumerate(grid)]
    sheets.append({"name": sheet, "rows": title + grid, "widths": [18] + [12] * (len(grid[0]) - 1), "freeze": (3, 1)})

    if t.monthly:
        md = t.monthly_data
        code_rows = title_rows("측정지점 코드표", "※ 지점코드 ↔ 지점명")
        code_rows.append([hd("지점코드"), hd("지점명")])
        for r in t.body_rows():
            code_rows.append([t.src_rows[r], r])
        sheets.insert(0, {"name": "측정지점", "rows": code_rows, "widths": [12, 18]})
        for m in range(9):
            rows = title_rows(f"{year}년 {m + 1}월 하천 수질 측정결과", "단위: mg/L")
            rows.append([hd("지점코드"), hd("채수일")] + [hd(t.src_cols.get(c, c)) for c in t.cols])
            for r in rows_order:
                vals = [md[(r, c)][m] for c in t.cols]
                for v in vals:
                    nums.add(round(float(v), 6))
                rows.append([t.src_rows[r], f"{year}-{m + 1:02d}-{rng.randint(3, 9):02d}"] + vals)
            sheets.append({"name": f"{m + 1}월", "rows": rows, "widths": [10, 12] + [8] * len(t.cols), "freeze": (3, 1)})
    if variant.get("filler"):
        sheets.insert(0, {"name": "사용안내", "rows": [[{"v": "이 파일 사용 안내", "bold": True, "border": False}],
                                                     ["1. 원자료 시트는 수정하지 말고 집계 시트만 참고합니다."],
                                                     ["2. 값은 반올림 전 값입니다. 문서에는 표시 자릿수로 적습니다."],
                                                     [f"3. 작성 기준일: {year}. 9. 30."]], "widths": [60]})
        det = title_rows("세부 기록(참고)", "자동 생성된 가상 기록")
        det.append([hd("번호"), hd("일자"), hd("구분"), hd("수량"), hd("금액(원)")])
        for i in range(rng.randint(40, 160)):
            q = rng.randint(1, 30)
            amt = q * rng.choice([12000, 18200, 23500, 31800])
            det.append([i + 1, f"{year}-{rng.randint(1, 9):02d}-{rng.randint(1, 28):02d}", rng.choice(["가", "나", "다"]), q,
                        {"v": amt, "fmt": "#,##0"}])
        sheets.append({"name": "세부기록", "rows": det, "widths": [8, 12, 8, 8, 12], "freeze": (3, 0)})
    return {"file": t.src_file, "sheets": sheets, "cellmap": cellmap, "numbers": nums}


def title_rows(title, sub=""):
    return [[{"v": title, "bold": True, "border": False}], [{"v": sub, "border": False}]]
