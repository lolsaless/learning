"""
04_coords_tool.py — 지점 좌표 도구

사용법
    python 04_coords_tool.py network 측정망좌표.hwpx     # 국가수질측정망 좌표표(hwpx) 가져오기 + 같은 지점 좌표 적용
    python 04_coords_tool.py vworld [--dry]             # V월드로 '추정'·'미입력' 지점 좌표 자동 검색
    python 04_coords_tool.py vworld --all [--dry]       # '확인'을 제외한 모든 지점 다시 검색

- 좌표상태가 '확인'인 지점(현장 확인 좌표)은 절대 바꾸지 않는다.
- V월드 검색 결과가 지점 주소의 시·군 경계 밖이면 적용하지 않는다.
- 결과는 '좌표보정_결과.csv'로도 저장된다. --dry 는 저장하지 않고 결과만 보여준다.
- V월드 인증키는 DB '설정' 시트의 VWORLD_KEY 값을 사용한다(인터넷 필요).
"""
import argparse
import csv
import json
import math
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wq_common as W  # noqa: E402
import hwpx_coords  # noqa: E402

GEO = json.loads((W.HERE / "lib" / "sigungu.geojson").read_text(encoding="utf-8"))


def _pip(x, y, ring):
    c = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def sigun_of(lat, lon):
    for f in GEO["features"]:
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        if any(_pip(lon, lat, p[0]) for p in polys):
            return f["properties"]["name"]
    return None


def km(a, b):
    if None in (a[0], a[1], b[0], b[1]):
        return None
    return 6371 * math.hypot(math.radians(a[0] - b[0]), math.radians(a[1] - b[1]) * math.cos(math.radians(a[0])))


# ── 국가측정망 ───────────────────────────────────────────
def cmd_network(db, hwpx):
    pts = hwpx_coords.read(hwpx)
    if not pts:
        raise SystemExit("[오류] hwpx 파일에서 좌표 표를 찾지 못했습니다.")
    db["network"] = pts
    print(f"[가져옴] 국가수질측정망 {len(pts)}개 지점 → '측정망지점' 시트")
    n = 0
    for s in db["stations"]:
        if s.get("좌표상태") == "확인":
            continue
        addr, sigun = str(s.get("주소") or ""), str(s.get("시군") or "")
        for p in pts:
            bridge = re.sub(r"\(.*?\)|아래|하류.*$", "", p["채수지점"]).strip()
            if bridge and bridge in addr and sigun and sigun in p["주소"]:
                d = km((s.get("위도"), s.get("경도")), (p["위도"], p["경도"]))
                s["위도"], s["경도"], s["좌표상태"] = p["위도"], p["경도"], "측정망"
                s["좌표출처"] = f"국가수질측정망 {p['지점명']}({p['분류번호']}) {p['채수지점']}"
                print(f"[적용] {s['지점명']} ← 측정망 {p['지점명']} {p['채수지점']}" + (f" (기존 위치와 {d:.1f}km 차이)" if d else ""))
                n += 1
                break
    print(f"[완료] 측정망 좌표를 적용한 지점 {n}개")


# ── V월드 ────────────────────────────────────────────────
def vw_get(url, params, key, domain):
    params = dict(params, key=key, format="json")
    if domain:
        params["domain"] = domain
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": "Mozilla/5.0 hantan-wq", **({"Referer": domain} if domain else {})})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    res = data.get("response", {})
    if res.get("status") == "ERROR":
        raise RuntimeError(res.get("error", {}).get("text") or "V월드 오류")
    return res


def search_place(q, key, domain):
    res = vw_get("https://api.vworld.kr/req/search", {"service": "search", "request": "search", "version": "2.0",
                 "crs": "EPSG:4326", "size": 10, "page": 1, "query": q, "type": "place", "errorformat": "json"}, key, domain)
    if res.get("status") != "OK":
        return []
    out = []
    for it in res.get("result", {}).get("items", []):
        p = it.get("point", {})
        a = it.get("address", {})
        out.append({"lat": float(p["y"]), "lon": float(p["x"]), "name": it.get("title", ""),
                    "addr": a.get("parcel") or a.get("road") or ""})
    return out


def geocode(addr, key, domain, typ="parcel"):
    res = vw_get("https://api.vworld.kr/req/address", {"service": "address", "request": "getcoord", "version": "2.0",
                 "crs": "epsg:4326", "address": addr, "refine": "true", "simple": "false", "type": typ}, key, domain)
    if res.get("status") != "OK":
        return None
    p = res["result"]["point"]
    return {"lat": float(p["y"]), "lon": float(p["x"]), "name": "", "addr": res.get("refined", {}).get("text", addr)}


def candidates(s):
    """주소에서 검색어 만들기: ① 지번 주소 ② 다리·시설 이름 (리·동 중심점 같은 근사 위치는 쓰지 않음)"""
    full = str(s.get("주소") or "")
    addr = re.sub(r"\(.*?\)", " ", full).replace("->", " ")
    sigun = str(s.get("시군") or (addr.split()[0] if addr.split() else ""))
    out = []
    m = re.search(r"((?:[가-힣]+(?:시|군))\s+(?:[가-힣0-9]+(?:읍|면)\s+)?(?:[가-힣0-9]+(?:리|동)\s+)(?:산\s?)?\d+(?:-\d+)?)", addr)
    if m:
        out.append(("지번", "경기도 " + m.group(1), None))
    for b in re.findall(r"([가-힣0-9]+(?:대교|교|다리))", full):
        if b.endswith("초교"):
            b = b[:-2] + "초등학교"
        out.append(("장소", f"{sigun} {b}", b))
    for b in re.findall(r"([가-힣A-Za-z0-9]{2,})\s*앞", full):
        if not b.endswith(("초교", "교")):
            out.append(("장소", f"{sigun} {b}", b))
    return out


def cmd_vworld(db, key, domain, every, dry):
    if not key:
        raise SystemExit("[오류] DB '설정' 시트의 VWORLD_KEY 값이 비어 있습니다.")
    report = []
    for s in db["stations"]:
        st = s.get("좌표상태")
        if st == "확인" or (not every and st not in ("추정", "미입력", None, "")):
            continue
        sigun = str(s.get("시군") or "")
        found, how = None, ""
        for kind, q, bridge in candidates(s):
            try:
                if kind == "장소":
                    hits = [h for h in search_place(q, key, domain) if sigun[:2] in h["addr"] or sigun[:2] in h["name"]]
                    hits = [h for h in hits if bridge in h["name"]] or hits
                    hit = hits[0] if hits else None
                elif kind == "지번":
                    hit = geocode(q, key, domain)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                raise SystemExit(f"[중단] V월드 서버에 연결하지 못했습니다({e}). 인터넷·방화벽(api.vworld.kr)을 확인하세요.")
            except Exception as e:  # noqa: BLE001
                print(f"[오류] {s['지점명']} '{q}': {e}")
                if "INVALID_KEY" in str(e).upper() or "인증" in str(e):
                    raise SystemExit("[중단] 인증키 오류입니다. 설정 시트의 VWORLD_KEY / VWORLD_DOMAIN을 확인하세요.")
                continue
            if hit and sigun_of(hit["lat"], hit["lon"]) == sigun:
                found, how = hit, f"V월드 {kind}검색: {q}" + (f" → {hit['name']}" if hit["name"] else "")
                break
        old = (s.get("위도"), s.get("경도"))
        if found:
            d = km(old, (found["lat"], found["lon"]))
            report.append([s["지점명"], s.get("주소"), how, found["lat"], found["lon"], f"{d:.2f}" if d is not None else ""])
            print(f"[찾음] {s['지점명']:<10} {found['lat']:.5f},{found['lon']:.5f}  {how}" + (f"  (이전과 {d:.1f}km)" if d is not None else ""))
            if not dry:
                s["위도"], s["경도"] = round(found["lat"], 6), round(found["lon"], 6)
                s["좌표상태"], s["좌표출처"] = "브이월드", how
        else:
            report.append([s["지점명"], s.get("주소"), "찾지 못함(기존 좌표 유지)", old[0], old[1], ""])
            print(f"[실패] {s['지점명']:<10} 검색 결과 없음 → 기존 좌표 유지")
    out = W.HERE / "좌표보정_결과.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["지점명", "주소", "결과", "위도", "경도", "이전 좌표와 거리(km)"])
        w.writerows(report)
    print(f"[보고서] {out}")
    ok = sum(1 for r in report if not r[2].startswith("찾지"))
    print(f"[요약] 대상 {len(report)}개 중 {ok}개 찾음" + (" (--dry: 저장 안 함)" if dry else ""))
    return ok and not dry


def main():
    ap = argparse.ArgumentParser(description="지점 좌표 도구")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("network")
    n.add_argument("hwpx")
    v = sub.add_parser("vworld")
    v.add_argument("--all", action="store_true")
    v.add_argument("--dry", action="store_true")
    ap.add_argument("--db", default=str(W.DEFAULT_DB))
    a = ap.parse_args()
    db = W.read_db(a.db)
    if a.cmd == "network":
        cmd_network(db, a.hwpx.strip('"'))
        W.write_db(a.db, db)
    else:
        cfg = W.settings_dict(db)
        if cmd_vworld(db, str(cfg.get("VWORLD_KEY") or "").strip(), str(cfg.get("VWORLD_DOMAIN") or "").strip(), a.all, a.dry):
            W.write_db(a.db, db)
            print("[완료] 지점정보 좌표를 갱신했습니다. 대시보드를 다시 만드세요.")


if __name__ == "__main__":
    main()
