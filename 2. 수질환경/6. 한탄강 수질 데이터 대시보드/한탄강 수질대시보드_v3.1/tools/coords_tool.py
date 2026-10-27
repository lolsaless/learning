"""
coords_tool.py — V월드로 시료번호 좌표 자동 검색

사용법
    python tools/coords_tool.py [--dry]          # '추정'·'미입력' 좌표만 검색
    python tools/coords_tool.py --all [--dry]    # '확인'을 제외한 모든 좌표 다시 검색

- 좌표상태가 '확인'인 시료번호(현장 확인 좌표)는 바꾸지 않는다.
- 검색 순서: ① 지번 주소 ② 다리·시설 이름(예: 영로교, 율정초등학교). 리·동 중심점 같은 근사 위치는 쓰지 않는다.
- 결과가 주소의 시·군 경계 밖이면 적용하지 않는다.
- 결과는 '좌표보정_결과.csv'로도 저장된다. --dry 는 저장하지 않는다.
- 대시보드 '지점 관리' 화면의 [V월드 검색] 버튼도 이 모듈을 사용한다(tools/serve.py).
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

GEO = json.loads((W.LIBDIR / "sigungu.geojson").read_text(encoding="utf-8"))


class VWorldError(Exception):
    pass


def _pip(x, y, ring):
    c, j = False, len(ring) - 1
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


def vw_get(url, params, key, domain):
    params = dict(params, key=key, format="json")
    if domain:
        params["domain"] = domain
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": "Mozilla/5.0 hantan-wq", **({"Referer": domain} if domain else {})})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise VWorldError(f"V월드 서버에 연결하지 못했습니다({e}). 인터넷·방화벽(api.vworld.kr)을 확인하세요.")
    res = data.get("response", {})
    if res.get("status") == "ERROR":
        txt = res.get("error", {}).get("text") or "V월드 오류"
        raise VWorldError(f"V월드 오류: {txt} (설정 시트의 VWORLD_KEY·VWORLD_DOMAIN 확인)")
    return res


def search_place(q, key, domain):
    res = vw_get("https://api.vworld.kr/req/search", {"service": "search", "request": "search", "version": "2.0",
                 "crs": "EPSG:4326", "size": 10, "page": 1, "query": q, "type": "place", "errorformat": "json"}, key, domain)
    if res.get("status") != "OK":
        return []
    out = []
    for it in res.get("result", {}).get("items", []):
        p, a = it.get("point", {}), it.get("address", {})
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


def candidates(addr, sigun):
    """주소에서 검색어 만들기: ① 지번 주소 ② 다리·시설 이름"""
    full = str(addr or "")
    plain = re.sub(r"\(.*?\)", " ", full).replace("->", " ")
    sigun = str(sigun or (plain.split()[0] if plain.split() else ""))
    out = []
    m = re.search(r"((?:[가-힣]+(?:시|군))\s+(?:[가-힣0-9]+(?:읍|면)\s+)?(?:[가-힣0-9]+(?:리|동)\s+)(?:산\s?)?\d+(?:-\d+)?)", plain)
    if m:
        out.append(("지번", "경기도 " + m.group(1), None))
    for b in re.findall(r"([가-힣0-9]+(?:대교|교|다리))", full):
        if b.endswith("초교"):
            b = b[:-2] + "초등학교"
        out.append(("장소", f"{sigun} {b}", b))
    for b in re.findall(r"([가-힣A-Za-z0-9]{2,})\s*앞", full):
        if not b.endswith(("초교", "교")):
            out.append(("장소", f"{sigun} {b}", b))
    return out, sigun


def find_coords(addr, sigun, key, domain, limit=6):
    """주소로 좌표 후보 찾기 → [{lat, lon, label, kind, inside}] (시군 경계 안 결과를 앞에)."""
    cands, sigun = candidates(addr, sigun)
    hits = []
    for kind, q, word in cands:
        if kind == "지번":
            h = geocode(q, key, domain)
            found = [h] if h else []
        else:
            found = search_place(q, key, domain)
            found = [h for h in found if word in h["name"]] or found
        for h in found[:4]:
            inside = sigun_of(h["lat"], h["lon"]) == sigun
            hits.append({"lat": round(h["lat"], 6), "lon": round(h["lon"], 6), "kind": kind, "inside": inside,
                         "label": f"{kind}: {h['name'] or q}" + (f" · {h['addr']}" if h.get("addr") else ""), "query": q})
    hits.sort(key=lambda h: (not h["inside"], h["kind"] != "지번"))
    return hits[:limit]


def run(db, key, domain, every, dry):
    if not key:
        raise SystemExit("[오류] DB '설정' 시트의 VWORLD_KEY 값이 비어 있습니다.")
    report = []
    for s in db["stations"]:
        st = s.get("좌표상태")
        if st == "확인" or (not every and st not in ("추정", "미입력", None, "")):
            continue
        try:
            hits = [h for h in find_coords(s.get("주소"), s.get("시군"), key, domain) if h["inside"]]
        except VWorldError as e:
            raise SystemExit(f"[중단] {e}")
        old = (s.get("위도"), s.get("경도"))
        if hits:
            h = hits[0]
            d = km(old, (h["lat"], h["lon"]))
            report.append([s["시료번호"], s.get("주소"), h["label"], h["lat"], h["lon"], f"{d:.2f}" if d is not None else ""])
            print(f"[찾음] {s['시료번호']:<10} {h['lat']:.5f},{h['lon']:.5f}  {h['label']}" + (f"  (이전과 {d:.1f}km)" if d is not None else ""))
            if not dry:
                s["위도"], s["경도"], s["좌표상태"], s["좌표출처"] = h["lat"], h["lon"], "브이월드", "V월드 " + h["label"]
        else:
            report.append([s["시료번호"], s.get("주소"), "찾지 못함(기존 좌표 유지)", old[0], old[1], ""])
            print(f"[실패] {s['시료번호']:<10} 검색 결과 없음 → 기존 좌표 유지")
    out = W.ROOT / "좌표보정_결과.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["시료번호", "주소", "결과", "위도", "경도", "이전 좌표와 거리(km)"])
        w.writerows(report)
    ok = sum(1 for r in report if not r[2].startswith("찾지"))
    print(f"[보고서] {out}\n[요약] 대상 {len(report)}개 중 {ok}개 찾음" + (" (--dry: 저장 안 함)" if dry else ""))
    return ok and not dry


def main():
    ap = argparse.ArgumentParser(description="V월드 좌표 자동 검색")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--db", default=str(W.DEFAULT_DB))
    a = ap.parse_args()
    db = W.read_db(a.db)
    cfg = W.settings_dict(db)
    if run(db, str(cfg.get("VWORLD_KEY") or "").strip(), str(cfg.get("VWORLD_DOMAIN") or "").strip(), a.all, a.dry):
        W.write_db(a.db, db)
        print("[완료] 지점정보 좌표를 갱신했습니다. 대시보드를 다시 만드세요.")


if __name__ == "__main__":
    main()
