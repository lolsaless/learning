"""
03_import_month.py — 월별 결과 엑셀(YYYYMM 시트)을 DB '측정결과'에 추가

사용법
    python 03_import_month.py 결과파일.xlsx [결과파일2.xlsx ...] [--db DB.xlsx]

- 파일 안의 YYYYMM 시트(예: 202610)를 모두 읽는다. 시트가 여러 개여도 된다.
- DB에 이미 같은 달이 있으면 그 달 자료를 새 값으로 바꾼다(다시 가져와도 중복되지 않음).
- 지점정보에 없는 지점은 새 지점으로 추가하고 안내한다(좌표는 비어 있음).
- 저장 전 기존 DB는 '백업' 폴더에 복사된다.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wq_common as W  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--db", default=str(W.DEFAULT_DB))
    a = ap.parse_args()
    db = W.read_db(a.db)
    names = {s["시료번호"] for s in db["stations"]}
    nxt = max([int(s.get("정렬순서") or 0) for s in db["stations"]] + [0]) + 1
    added_total = 0
    for f in a.files:
        f = f.strip().strip('"')
        rows, stations, order, _ = W.read_legacy(f)
        if not rows:
            print(f"[건너뜀] {f}: YYYYMM 이름의 시트가 없습니다.")
            continue
        months = sorted({r["조사연월"] for r in rows})
        before = len(db["meas"])
        db["meas"] = [r for r in db["meas"] if W.norm_month(r.get("조사연월")) not in months]
        replaced = before - len(db["meas"])
        db["meas"].extend(rows)
        for n in order:
            if n not in names:
                m = stations[n]
                db["stations"].append({"정렬순서": nxt, "지점ID": f"S{nxt:02d}", "하천명": m["하천명"], "시료번호": n,
                                       "시군": (m["주소"].split() or [""])[0],
                                       "주소": m["주소"], "위도": None, "경도": None, "좌표상태": "미입력",
                                       "좌표출처": "", "비고": m["비고"]})
                names.add(n)
                nxt += 1
                print(f"[새 시료번호] {n} — 지점정보에 추가했습니다. 대시보드 '지점 관리'에서 주소·좌표를 입력하세요.")
        added_total += len(rows)
        print(f"[가져옴] {Path(f).name}: {', '.join(months)} · {len(rows)}행" + (f" (기존 {replaced}행 교체)" if replaced else ""))
    if added_total:
        W.write_db(a.db, db)
        print(f"[완료] {a.db} 저장. 이제 대시보드를 다시 만드세요.")


if __name__ == "__main__":
    main()
