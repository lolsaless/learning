"""
data_builder.py — DB 엑셀(한탄강_수질DB.xlsx) → 대시보드 데이터(D) 만들기

하는 일
- 지점정보·측정결과·기준값·연평균색도·설정 시트를 읽어 화면이 쓰는 데이터(dict)로 바꾼다.
- 자료 점검(자동): 전월과 같은 값, 시료번호별 이상값 의심(로버스트 z), 정량한계 미만, 같은 달 중복 채취, 좌표 추정
- HTML 조립은 하지 않는다(tools/build.py 가 담당).

이럴 때 고침
- 엑셀에 새 열·시트를 추가해 화면에서 쓰고 싶을 때 → build_data() 의 data 사전에 항목 추가
- 자동 점검 규칙을 바꿀 때 → '자료 점검(QC)' 부분
"""
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wq_common as W  # noqa: E402


def build_data(db_path):
    db = W.read_db(db_path)
    cfg = W.settings_dict(db)
    warns = []
    loq_mode = str(cfg.get("정량한계_처리") or "한계값")

    stations = []
    for r in db["stations"]:
        if not r.get("시료번호"):
            continue
        stations.append({
            "id": r.get("지점ID") or f"X{len(stations) + 1:02d}", "name": str(r["시료번호"]).strip(),
            "river": str(r.get("하천명") or "미분류").strip(), "sigun": r.get("시군") or "",
            "addr": r.get("주소") or "", "lat": W.to_num(r.get("위도")), "lon": W.to_num(r.get("경도")),
            "coord": r.get("좌표상태") or "", "coordSrc": r.get("좌표출처") or "", "note": r.get("비고") or "",
            "order": W.to_num(r.get("정렬순서")) or 999,
        })
    stations.sort(key=lambda s: s["order"])
    names = {s["name"] for s in stations}

    items = [{"code": str(r["항목"]).strip(), "name": r.get("표시명") or r["항목"], "unit": r.get("단위") or "",
              "dec": int(W.to_num(r.get("소수자리"))) if W.to_num(r.get("소수자리")) is not None else 2,
              "desc": r.get("설명") or ""} for r in db["items"] if r.get("항목")]
    codes = [i["code"] for i in items]

    limits, target = defaultdict(list), {}
    for r in db["limits"]:
        it = str(r.get("항목") or "").strip()
        if not it:
            continue
        if r.get("구분") == "목표":
            target[it] = W.to_num(r.get("상한값"))
        else:
            limits[it].append({"code": r.get("등급코드"), "name": r.get("등급명"), "max": W.to_num(r.get("상한값"))})

    acc = defaultdict(lambda: defaultdict(list))
    loq = {}
    manual, dates, months = defaultdict(dict), defaultdict(dict), set()
    for i, r in enumerate(db["meas"], start=2):
        st = str(r.get("시료번호") or "").strip()
        if not st or not r.get("조사연월"):
            continue
        if st not in names:
            warns.append(f"측정결과 {i}행: 지점정보에 없는 시료번호 '{st}' — 건너뜀")
            continue
        try:
            ym = W.norm_month(r["조사연월"])
        except Exception:  # noqa: BLE001
            warns.append(f"측정결과 {i}행: 조사연월 형식 오류 '{r['조사연월']}' — 건너뜀")
            continue
        months.add(ym)
        for c in codes:
            v, lq = W.parse_value(r.get(c))
            if lq:
                loq[f"{st}|{ym}|{c}"] = lq
                if v is not None:
                    v = {"한계값": v, "절반": v / 2}.get(loq_mode, None)
            if v is not None:
                acc[(st, ym)][c].append(v)
            elif r.get(c) not in (None, "") and not lq:
                warns.append(f"측정결과 {i}행 {st} {ym} {c}: 숫자가 아닌 값 '{r.get(c)}' — 빈 값 처리")
        d = r.get("채취일")
        if isinstance(d, datetime):
            dates[st][ym] = d.strftime("%Y-%m-%d")
        if r.get("검토표시"):
            note = str(r.get("비고") or r.get("검토표시"))
            its = [c for c in codes if c in note] or None
            manual[st][ym] = {"note": note, "items": its}
    months = sorted(months)

    values, multi = {}, []
    for s in stations:
        values[s["name"]] = {}
        for c in codes:
            row = []
            for m in months:
                vs = acc.get((s["name"], m), {}).get(c)
                row.append(round(sum(vs) / len(vs), 6) if vs else None)
                if vs and len(vs) > 1:
                    multi.append((s["name"], m, c, len(vs)))
            values[s["name"]][c] = row

    # ── 자료 점검(QC) ─────────────────────────────
    qc = []
    for st, mm in manual.items():
        for m, x in mm.items():
            for c in (x["items"] or [None]):
                qc.append({"type": "manual", "st": st, "m": m, "item": c, "note": x["note"]})
    nrep = int(W.to_num(cfg.get("전월동일_항목수")) or 4)
    for s in stations:
        n = s["name"]
        for i in range(1, len(months)):
            same = [c for c in codes if values[n][c][i] is not None and values[n][c][i] == values[n][c][i - 1]]
            if len(same) >= nrep:
                for c in same:
                    qc.append({"type": "repeat", "st": n, "m": months[i], "item": c,
                               "note": f"전월({months[i - 1]})과 {len(same)}개 항목 값이 같음 — 복사 입력 여부 확인"})
    zthr = float(W.to_num(cfg.get("이상값_기준")) or 6)
    ratio = float(W.to_num(cfg.get("이상값_배율")) or 5)
    for s in stations:
        n = s["name"]
        for c in codes:
            v = [x for x in values[n][c] if x is not None]
            if len(v) < 5:
                continue
            med = statistics.median(v)
            mad = statistics.median([abs(x - med) for x in v])
            if mad == 0:
                continue
            for i, x in enumerate(values[n][c]):
                if x is None:
                    continue
                z = 0.6745 * (x - med) / mad
                r = x / med if med else float("inf")
                if abs(z) >= zthr and (r >= ratio or r <= 1 / ratio):
                    qc.append({"type": "outlier", "st": n, "m": months[i], "item": c, "z": round(z, 1),
                               "note": f"지점 중앙값 {med:g}의 {r:.1f}배 (z={z:.1f})"})
    for k, lq in loq.items():
        st, m, c = k.split("|")
        qc.append({"type": "loq", "st": st, "m": m, "item": c, "note": f"정량한계 미만 {lq} → 계산값: {loq_mode}"})
    for st, m, c, k in multi:
        qc.append({"type": "multi", "st": st, "m": m, "item": c, "note": f"같은 달 {k}회 채취 → 평균값 사용"})
    for s in stations:
        if s["coord"] in ("추정", "미입력", ""):
            qc.append({"type": "coord", "st": s["name"], "m": None, "item": None,
                       "note": "좌표 미입력" if s["lat"] is None else "주소 기반 추정 좌표 — '지점 관리'에서 수정 권장"})

    yearly, yinfo = defaultdict(dict), {}
    for r in db["yearly"]:
        try:
            st, y, v = str(r["시료번호"]).strip(), int(W.to_num(r["연도"])), W.to_num(r["평균색도"])
        except Exception:  # noqa: BLE001
            continue
        if v is not None:
            yearly[st][y] = v
            yinfo.setdefault(st, {"river": r.get("하천명") or "", "addr": r.get("주소") or ""})


    data = {
        "title": "한탄강 수계 수질 대시보드",
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"), "source": Path(db_path).name,
        "items": items, "limits": limits, "target": target, "stations": stations, "months": months,
        "values": values, "dates": dates, "loq": loq, "qc": qc,
        "yearly": yearly, "yearlyInfo": yinfo,
        "settings": {
            "vworldKey": str(cfg.get("VWORLD_KEY") or "").strip(),
            "basemap": str(cfg.get("기본배경지도") or "자동"),
            "item": str(cfg.get("기본항목") or "색도"),
            "band": {"표준편차": "sd", "퍼센트": "pct", "전체": "all"}.get(str(cfg.get("평균대비_판정")), "sd"),
            "k": float(W.to_num(cfg.get("평균대비_k")) or 1), "p": float(W.to_num(cfg.get("평균대비_p")) or 30),
            "loqMode": loq_mode,
            "spike": float(W.to_num(cfg.get("특이경향_기준")) or 8),
        },
        # 설정 화면에 보여 줄 설정 시트 전체(이름·값·설명·선택지)
        "settingsRaw": [{"key": k, "value": cfg.get(k, dv), "desc": d, "choices": ch} for k, dv, d, ch in W.SETTINGS],
    }
    return data, warns


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="DB → 대시보드 데이터(JSON) 확인용")
    ap.add_argument("db", nargs="?", default=str(W.DEFAULT_DB))
    a = ap.parse_args()
    d, w = build_data(a.db)
    for x in w:
        print("[확인]", x)
    print(json.dumps({k: (len(v) if hasattr(v, "__len__") else v) for k, v in d.items()}, ensure_ascii=False, indent=1))
