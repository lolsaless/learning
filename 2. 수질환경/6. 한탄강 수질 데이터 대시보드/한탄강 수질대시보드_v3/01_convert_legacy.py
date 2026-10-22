"""
01_convert_legacy.py — 기존 '월별 시트(YYYYMM)' 엑셀 전체를 표준 DB(한탄강_수질DB.xlsx)로 변환

사용법
    python 01_convert_legacy.py 원본.xlsx [출력DB.xlsx]

- 원본의 YYYYMM 시트를 모두 읽어 '측정결과'를 새로 만든다(기존 측정결과는 교체).
- 출력 DB가 이미 있으면 지점정보·항목정보·기준값·설정·측정망지점은 그대로 유지한다.
- 한 달치만 추가할 때는 03_import_month.py 를 사용한다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wq_common as W  # noqa: E402

try:
    from coords import COORDS
except Exception:  # noqa: BLE001
    COORDS = {}


def new_station(i, name, meta):
    addr = meta["주소"]
    note = meta["비고"]
    if "목표지점" in addr:
        note = (note + " " if note else "") + "색도 목표지점"
        addr = addr.replace("_색도 목표지점", "")
    lat, lon = COORDS.get(name, (None, None))
    river = meta["하천명"]
    return {"정렬순서": i, "지점ID": f"S{i:02d}", "하천명": river, "시료번호": name,
            "시군": addr.split()[0] if addr else "", "주소": addr, "위도": lat, "경도": lon,
            "좌표상태": "추정" if lat else "미입력", "좌표출처": "주소 기반 추정" if lat else "", "비고": note}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = sys.argv[1]
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else W.DEFAULT_DB
    rows, stations, order, yearly = W.read_legacy(src)
    meas_years = {int(r["조사연월"][:4]) for r in rows}
    yearly = [y for y in yearly if y["연도"] not in meas_years]
    if out.exists():
        db = W.read_db(out)
        have = {s["시료번호"] for s in db["stations"]}
        nxt = max([int(s.get("정렬순서") or 0) for s in db["stations"]] + [0]) + 1
        for name in order:
            if name not in have:
                db["stations"].append(new_station(nxt, name, stations[name]))
                print(f"[추가] 새 지점: {name}")
                nxt += 1
        db["meas"] = rows
        if yearly:
            db["yearly"] = yearly
    else:
        db = {"meas": rows, "stations": [new_station(i, n, stations[n]) for i, n in enumerate(order, 1)],
              "items": [dict(zip(W.ITEM_COLS, r)) for r in W.ITEM_INFO], "limits": W.default_limits(),
              "yearly": yearly, "settings": [{"설정": k, "값": v, "설명": d} for k, v, d, _ in W.SETTINGS]}
    W.write_db(out, db)
    months = sorted({r["조사연월"] for r in rows})
    print(f"[완료] {out}\n  측정결과 {len(rows)}행 · 지점 {len(db['stations'])}개 · 기간 {months[0]} ~ {months[-1]}")


if __name__ == "__main__":
    main()
