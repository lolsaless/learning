"""
02_build_dashboard.py — 한탄강_수질DB.xlsx → 인터랙티브 대시보드 HTML(단일 파일) 생성 (v2)

사용법
    python 02_build_dashboard.py                       # 같은 폴더 DB → 한탄강_수질대시보드.html
    python 02_build_dashboard.py DB.xlsx 출력.html
    python 02_build_dashboard.py --cdn                 # 라이브러리를 CDN에서 불러오는 가벼운 버전(인터넷 필요)

v2에서 추가된 계산
- 자료 점검(자동): 전월과 같은 값, 지점별 이상값 의심(로버스트 z), 정량한계 미만, 같은 달 중복 채취, 좌표 추정
- 설정 시트(V월드 키, ▲▼ 판정 기준 등)를 HTML에 반영
"""
import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wq_common as W  # noqa: E402

HERE = W.HERE
LIB = HERE / "lib"
CDN = {
    "echarts": "https://cdnjs.cloudflare.com/ajax/libs/echarts/5.5.1/echarts.min.js",
    "leaflet": "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js",
}
VERSION = "2.0"


def build_data(db_path):
    db = W.read_db(db_path)
    cfg = W.settings_dict(db)
    warns = []
    loq_mode = str(cfg.get("정량한계_처리") or "한계값")

    stations = []
    for r in db["stations"]:
        if not r.get("지점명"):
            continue
        stations.append({
            "id": r.get("지점ID") or f"X{len(stations) + 1:02d}", "name": str(r["지점명"]).strip(),
            "river": r.get("하천명") or "", "basin": r.get("수계") or "기타", "sigun": r.get("시군") or "",
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
        st = str(r.get("지점명") or "").strip()
        if not st or not r.get("조사연월"):
            continue
        if st not in names:
            warns.append(f"측정결과 {i}행: 지점정보에 없는 지점명 '{st}' — 건너뜀")
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
                       "note": "좌표 미입력" if s["lat"] is None else "주소 기반 추정 좌표 — 04 좌표 도구(V월드) 실행 권장"})

    yearly, yinfo = defaultdict(dict), {}
    for r in db["yearly"]:
        try:
            st, y, v = str(r["지점명"]).strip(), int(W.to_num(r["연도"])), W.to_num(r["평균색도"])
        except Exception:  # noqa: BLE001
            continue
        if v is not None:
            yearly[st][y] = v
            yinfo.setdefault(st, {"river": r.get("하천명") or "", "addr": r.get("주소") or ""})

    network = [{"name": r.get("지점명"), "basin": r.get("수계"), "sub": r.get("중권역"), "addr": r.get("주소"),
                "spot": r.get("채수지점"), "lat": W.to_num(r.get("위도")), "lon": W.to_num(r.get("경도")),
                "code": r.get("분류번호")} for r in db["network"] if W.to_num(r.get("위도"))]

    geo_path = LIB / "sigungu.geojson"
    data = {
        "version": VERSION, "title": "한탄강 수계 수질 대시보드",
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"), "source": Path(db_path).name,
        "items": items, "limits": limits, "target": target, "stations": stations, "months": months,
        "values": values, "dates": dates, "loq": loq, "qc": qc,
        "yearly": yearly, "yearlyInfo": yinfo, "network": network,
        "geo": json.loads(geo_path.read_text(encoding="utf-8")) if geo_path.exists() else None,
        "settings": {
            "vworldKey": str(cfg.get("VWORLD_KEY") or "").strip(),
            "basemap": str(cfg.get("기본배경지도") or "자동"),
            "item": str(cfg.get("기본항목") or "색도"),
            "band": {"표준편차": "sd", "퍼센트": "pct", "전체": "all"}.get(str(cfg.get("평균대비_판정")), "sd"),
            "k": float(W.to_num(cfg.get("평균대비_k")) or 1), "p": float(W.to_num(cfg.get("평균대비_p")) or 30),
            "loqMode": loq_mode,
        },
    }
    return data, warns


def build_html(data, mode):
    tpl = (HERE / "template.html").read_text(encoding="utf-8")
    css = (LIB / "leaflet.css").read_text(encoding="utf-8")
    if mode == "inline":
        libs = "".join(f"<script>{(LIB / f).read_text(encoding='utf-8')}</script>\n" for f in ("echarts.min.js", "leaflet.js"))
    else:
        libs = "".join(f'<script src="{u}"></script>\n' for u in CDN.values())
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    body = (tpl.replace("/*__LEAFLET_CSS__*/", css).replace("<!--__LIBS__-->", libs)
               .replace("/*__DATA__*/null", payload))
    if mode == "artifact":
        return body
    return ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<meta name="referrer" content="strict-origin-when-cross-origin">\n'
            "</head>\n<body>\n" + body + "\n</body>\n</html>\n")


def main():
    ap = argparse.ArgumentParser(description="한탄강 수질 대시보드 생성")
    ap.add_argument("db", nargs="?", default=str(W.DEFAULT_DB))
    ap.add_argument("out", nargs="?", default=None)
    ap.add_argument("--cdn", action="store_true", help="라이브러리를 CDN에서 불러옴(파일 크기 작음, 인터넷 필요)")
    ap.add_argument("--artifact", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--no-key", action="store_true", help="V월드 인증키를 HTML에 넣지 않음(외부 공유용)")
    a = ap.parse_args()
    if not Path(a.db).exists():
        sys.exit(f"[오류] DB 파일이 없습니다: {a.db}")
    out = Path(a.out) if a.out else Path(a.db).with_name("한탄강_수질대시보드.html")
    data, warns = build_data(a.db)
    if a.no_key:
        data["settings"]["vworldKey"] = ""
    mode = "artifact" if a.artifact else ("cdn" if a.cdn else "inline")
    out.write_text(build_html(data, mode), encoding="utf-8")
    for w in warns:
        print("[확인]", w)
    cnt = defaultdict(int)
    for q in data["qc"]:
        cnt[q["type"]] += 1
    label = {"manual": "검토필요", "repeat": "전월 동일", "outlier": "이상값 의심", "loq": "정량한계 미만",
             "multi": "중복 채취", "coord": "좌표 추정"}
    print(f"[완료] {out}  ({out.stat().st_size / 1024:,.0f} KB)")
    print(f"  지점 {len(data['stations'])}개 · 항목 {len(data['items'])}개 · 기간 "
          f"{data['months'][0] if data['months'] else '-'} ~ {data['months'][-1] if data['months'] else '-'}")
    print("  자료 점검: " + (" · ".join(f"{label[k]} {v}" for k, v in cnt.items()) or "없음"))
    if not data["settings"]["vworldKey"]:
        print("  V월드 인증키 없음 → 지도는 시군 경계만 표시")


if __name__ == "__main__":
    main()
