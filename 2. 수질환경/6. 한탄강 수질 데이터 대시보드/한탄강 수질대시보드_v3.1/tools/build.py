"""
build.py — 부품(소스/)을 합쳐 한탄강_수질대시보드.html 한 파일로 만든다.

사용법 (프로그램 폴더에서)
    python tools/build.py              # 데이터(DB 엑셀) 읽기 → 부품 조립 → 검사 → HTML 저장
    python tools/build.py --check      # 검사만(파일을 만들지 않음)
    python tools/build.py --watch      # 부품·DB를 저장할 때마다 자동으로 다시 빌드(Ctrl+C로 멈춤)
    python tools/build.py --cache      # DB를 읽지 않고 지난번 데이터(빌드결과/_data.js)로 조립(디자인만 고칠 때)
    python tools/build.py --no-key     # V월드 키를 뺀 공유용 HTML (기본 이름: 한탄강_수질대시보드_공유용.html)
    python tools/build.py --out 파일.html --db 다른DB.xlsx
    (Mac은 python 대신 python3)

빌드가 하는 일
1. 소스/빌드목록.txt 순서대로 부품을 읽는다.
     .css → <style> 한 곳 / .html → 화면 / 10_외부라이브러리 .js → 따로 <script> / 나머지 .js → 한 <script>
   각 부품 앞에 /* ===== 부품: 경로 ===== */ 표시를 넣어 브라우저 오류(F12)에서 부품을 찾을 수 있게 한다.
2. 검사한다. 오류가 하나라도 있으면 HTML을 만들지 않고 기존 파일을 그대로 둔다.
3. 이전 HTML은 빌드결과/이전/ 에 보관(최근 5개), 문서/부품지도.md 를 새로 만든다.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import wq_common as W  # noqa: E402

ROOT, SRC, LIB, OUTDIR = W.ROOT, W.SRC, W.LIBDIR, W.OUTDIR
LIST_FILE = SRC / "빌드목록.txt"
VERSION_FILE = SRC / "버전.txt"
FIX_FILE = SRC / "자주하는수정.txt"
DATA_CACHE = OUTDIR / "_data.js"
PARTMAP = ROOT / "문서" / "부품지도.md"
CHANGELOG = ROOT / "문서" / "변경이력.md"
NOT_PARTS = {"빌드목록.txt", "버전.txt", "자주하는수정.txt"}
ALLOWED_HOSTS = ("api.vworld.kr", "www.vworld.kr", "localhost", "127.0.0.1", "www.w3.org")
CDN = {"echarts.min.js": "https://cdnjs.cloudflare.com/ajax/libs/echarts/5.5.1/echarts.min.js",
       "leaflet.js": "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"}
HEAD_META = ('<meta charset="utf-8">\n'
             '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
             '<meta name="referrer" content="strict-origin-when-cross-origin">\n')


class BuildError(Exception):
    pass


# ── 부품 목록 ─────────────────────────────────────────────
def read_list():
    if not LIST_FILE.exists():
        raise BuildError(f"빌드목록이 없습니다: {LIST_FILE}")
    parts = []
    for ln in LIST_FILE.read_text(encoding="utf-8").splitlines():
        ln = ln.split("#", 1)[0].strip()
        if ln:
            parts.append(ln.replace("\\", "/"))
    return parts


def kind_of(path):
    if path.endswith(".css"):
        return "css"
    if path.endswith(".html"):
        return "head" if path.startswith("00_틀/01_") else "html"
    if path.endswith(".geojson"):
        return "geo"
    if path.endswith(".js"):
        return "lib" if path.startswith("10_외부라이브러리/") else "js"
    return "unknown"


def read_header(text):
    """부품 머리말: [경로] 제목 / 하는 일 / 주요 이름 / 이럴 때 고침"""
    m = re.search(r"\[([^\]]+)\]\s*(.*?)\n\s*하는 일\s*:\s*(.*?)\n\s*주요 이름\s*:\s*(.*?)\n\s*이럴 때 고침\s*:\s*(.*?)\n", text[:1500])
    if not m:
        return None
    return {"title": m.group(2).strip(), "does": m.group(3).strip(), "names": m.group(4).strip(), "fix": m.group(5).strip()}


# ── 조립 ─────────────────────────────────────────────────
def data_script(db_path, use_cache, no_key, version, warns):
    """데이터(D) 스크립트 한 줄. DB를 읽거나(기본) 지난번 데이터를 쓴다(--cache, DB 없음)."""
    if use_cache or not Path(db_path).exists():
        if not DATA_CACHE.exists():
            raise BuildError(f"DB 파일이 없고 지난번 데이터도 없습니다: {db_path}")
        if not use_cache:
            warns.append(f"DB 파일이 없어 지난번 데이터(빌드결과/_data.js)로 조립했습니다: {db_path}")
        line = DATA_CACHE.read_text(encoding="utf-8").strip()
        if no_key:
            line = re.sub(r'"vworldKey":"[^"]*"', '"vworldKey":""', line)
            line = re.sub(r'(\{"key":"VWORLD_KEY","value":)"[^"]*"', r'\1""', line)
        return line, None
    import data_builder  # noqa: WPS433 (필요할 때만 읽음: openpyxl 필요)
    data, dwarns = data_builder.build_data(db_path)
    warns.extend(dwarns)
    full = "const D = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";"
    OUTDIR.mkdir(exist_ok=True)
    DATA_CACHE.write_text(full + "\n", encoding="utf-8")
    if no_key:
        data["settings"]["vworldKey"] = ""
        for r in data["settingsRaw"]:
            if r["key"] == "VWORLD_KEY":
                r["value"] = ""
        return "const D = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";", data
    return full, data


def assemble(parts, data_line, mode="inline", version="?"):
    """부품 → HTML 글자. 간단 빌드(tools/build_simple.*)도 같은 규칙으로 만든다."""
    head, css, html, libs, js = [], [], [], [], []
    js_map = []  # (시작 줄, 부품) — 문법 오류 위치 찾기용
    for p in parts:
        text = (SRC / p).read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")
        k = kind_of(p)
        if k == "head":
            head.append(text)
        elif k == "css":
            css.append(f"/* ===== 부품: {p} ===== */\n{text}")
        elif k == "html":
            html.append(f"<!-- ===== 부품: {p} ===== -->\n{text}")
        elif k == "geo":
            libs.append(f"<script>window.GEO_SIGUNGU = {text};</script>")
        elif k == "lib":
            name = Path(p).name
            libs.append(f'<script src="{CDN[name]}"></script>' if mode != "inline" and name in CDN else f"<script>{text}</script>")
        elif k == "js":
            js_map.append((sum(c.count("\n") + 2 for c in js) + 2, p))
            js.append(f"/* ===== 부품: {p} ===== */\n{text}")
    app = '"use strict";\n' + "\n\n".join(js)
    body = ("\n".join(html) + "\n" + "\n".join(libs) + '\n<script>window.APP_VERSION = "' + version + '";\n' + data_line +
            "</script>\n<script>\n" + app + "\n</script>\n")
    style = "<style>\n" + "\n\n".join(css) + "\n</style>\n"
    if mode == "artifact":
        return "\n".join(head) + "\n" + style + body, app, js_map
    out = ('<!doctype html>\n<html lang="ko">\n<head>\n' + HEAD_META + "\n".join(head) + "\n" + style +
           "</head>\n<body>\n" + body + "</body>\n</html>\n")
    return out, app, js_map


# ── 검사 ─────────────────────────────────────────────────
DECL = re.compile(r"^(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)|^(?:const|let|var|class)\s+([A-Za-z_$][\w$]*)")


def top_names(text):
    names = []
    for ln in text.split("\n"):
        m = DECL.match(ln)
        if not m:
            continue
        names.append(m.group(1) or m.group(2))
        mm = re.match(r"^(?:let|var)\s+([\w$\s,]+?)\s*(?:=|;|$)", ln)
        if mm and "," in mm.group(1):
            names += [x.strip() for x in mm.group(1).split(",")[1:] if re.fullmatch(r"[A-Za-z_$][\w$]*", x.strip())]
        m2 = re.match(r'^const\s+[\w$]+\s*=\s*"[^"]*"\s*,\s*([\w$]+)\s*=', ln)
        if m2:
            names.append(m2.group(1))
    return names


def check(parts, app, js_map, html_out):
    errs, warns = [], []
    # 1) 목록·파일
    for p in parts:
        if not (SRC / p).exists():
            errs.append(f"목록에 있지만 파일이 없음: 소스/{p}")
        elif kind_of(p) == "unknown":
            errs.append(f"알 수 없는 파일 종류(.html/.css/.js/.geojson만 가능): 소스/{p}")
    listed = set(parts)
    for f in sorted(SRC.rglob("*")):
        rel = f.relative_to(SRC).as_posix()
        if f.is_file() and rel not in listed and f.name not in NOT_PARTS and not f.name.startswith("."):
            warns.append(f"목록에 없는 부품(빌드에 안 들어감): 소스/{rel} → 쓰려면 소스/빌드목록.txt에 한 줄 추가")
    if errs:
        return errs, warns
    # 2) 이름 중복
    seen = {}
    for p in parts:
        if kind_of(p) != "js":
            continue
        for n in top_names((SRC / p).read_text(encoding="utf-8")):
            if n in seen and seen[n] != p:
                errs.append(f'이름 "{n}" 이(가) 두 부품에 있음: {seen[n]} / {p}')
            seen.setdefault(n, p)
    # 3) </script
    for p in parts:
        if kind_of(p) == "js" and "</script" in (SRC / p).read_text(encoding="utf-8").lower():
            errs.append(f'"</script" 글자가 있으면 화면이 깨집니다 → <\\/script 로 쓰세요: {p}')
    # 4) 문법(Node.js가 있을 때)
    node = shutil.which("node")
    if node:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
            t.write(app)
        r = subprocess.run([node, "--check", t.name], capture_output=True, text=True, encoding="utf-8")
        Path(t.name).unlink(missing_ok=True)
        if r.returncode != 0:
            # 어느 부품인지: 부품을 하나씩 따로 검사해서 처음 실패하는 부품과 그 줄을 알려 준다
            found = False
            for p in parts:
                if kind_of(p) != "js":
                    continue
                with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
                    t.write((SRC / p).read_text(encoding="utf-8"))
                r2 = subprocess.run([node, "--check", t.name], capture_output=True, text=True, encoding="utf-8")
                Path(t.name).unlink(missing_ok=True)
                if r2.returncode != 0:
                    m = re.search(r":(\d+)\n", r2.stderr)
                    msg = [x for x in r2.stderr.splitlines() if "Error" in x][:1]
                    errs.append(f"문법 오류 → 부품 {p} 의 {m.group(1) if m else '?'}번째 줄 근처: {msg[0] if msg else ''}"
                                " (괄호·따옴표·쉼표 확인)")
                    found = True
                    break
            if not found:
                msg = [x for x in r.stderr.splitlines() if "Error" in x][:1]
                errs.append(f"문법 오류(부품 사이 연결 문제): {msg[0] if msg else r.stderr.strip()[:200]}")
    else:
        warns.append("Node.js가 없어 문법 검사를 건너뜁니다(나머지 검사는 했습니다).")
    # 5) id 검사: 화면(HTML) 부품의 id 중복, 스크립트가 찾는 id가 화면에 있는지
    html_ids = []
    for p in parts:
        if kind_of(p) in ("html", "head"):
            body = re.sub(r"<!--.*?-->", "", (SRC / p).read_text(encoding="utf-8"), flags=re.S)
            html_ids += re.findall(r'\bid="([^"$]+)"', body)
    dup = sorted({i for i in html_ids if html_ids.count(i) > 1})
    if dup:
        errs.append("화면 부품에 같은 id가 두 번 있음: " + ", ".join(dup))
    made_in_js = set(re.findall(r'id="([A-Za-z][\w-]*)"', app)) | set(re.findall(r'id=\\"([A-Za-z][\w-]*)\\"', app))
    asked = set(re.findall(r'\$\("([A-Za-z][\w-]*)"\)', app))
    missing = sorted(asked - set(html_ids) - made_in_js)
    if missing:
        warns.append("스크립트가 찾지만 화면에 없는 id(동적으로 만드는 것이면 무시): " + ", ".join(missing))
    # 5-2) 화면 등록(registerView) ↔ 화면 자리(<section id="v-○○">) 짝
    for vid in re.findall(r'registerView\(\{\s*id:\s*"([\w-]+)"', app):
        if "v-" + vid not in html_ids:
            errs.append(f'화면 "{vid}" 을(를) 등록했지만 화면 자리(<section id="v-{vid}">)가 없음 → 02_화면 부품이 빌드목록에 있는지 확인')
    for hid in html_ids:
        if hid.startswith("v-") and not re.search(r'registerView\(\{\s*id:\s*"' + re.escape(hid[2:]) + '"', app):
            warns.append(f'화면 자리 <section id="{hid}"> 는 있지만 등록(registerView)한 동작 부품이 없음 → 탭이 안 생김')
    # 6) 외부 링크(행정망에서 막힘)
    for p in parts:
        if kind_of(p) in ("html", "css", "js", "head") and not p.startswith("10_외부라이브러리/"):
            for u in set(re.findall(r"https?://([^/\"'`\s)]+)", (SRC / p).read_text(encoding="utf-8"))):
                if not u.split(":")[0].endswith(ALLOWED_HOSTS):
                    warns.append(f"외부 주소({u})가 있음 — 행정망에서는 열리지 않습니다: {p}")
    # 7) 버전
    ver = VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else "?"
    if CHANGELOG.exists():
        m = re.search(r"^##\s*v?([\d.]+)", CHANGELOG.read_text(encoding="utf-8"), re.M)
        if m and m.group(1) != ver:
            warns.append(f"버전 표기가 다름: 소스/버전.txt = {ver}, 문서/변경이력.md 맨 위 = {m.group(1)}")
    # 8) 자주하는수정 표의 부품이 있는지
    for row in read_fixes():
        for f in re.findall(r"[0-9]{2}_[^ ,()]+?\.(?:js|css|html)", row[1]):
            if "새화면" not in f and f not in listed and not any(x.endswith(f) for x in listed):
                warns.append(f"자주하는수정.txt 에 있는 부품이 목록에 없음: {f}")
    return errs, warns


def read_fixes():
    rows = []
    if FIX_FILE.exists():
        for ln in FIX_FILE.read_text(encoding="utf-8").splitlines():
            if ln.strip() and not ln.startswith("#") and ln.count("|") >= 2:
                rows.append([x.strip() for x in ln.split("|")[:3]])
    return rows


# ── 부품지도 ─────────────────────────────────────────────
GROUPS = [("00_틀", "화면 틀(HTML)"), ("01_디자인", "디자인(CSS)"), ("02_화면", "화면별 자리(HTML)"),
          ("10_외부라이브러리", "외부 라이브러리 — 고치지 않음"), ("20_공통", "공통 — 상태·통계·색·그래프"),
          ("30_틀동작", "틀 동작 — 탭·왼쪽 패널·요약 카드"), ("40_화면", "화면별 동작"), ("90_시작", "시작·버튼 연결")]


def write_partmap(parts):
    ver = VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else "?"
    out = [f"# 부품지도 v{ver} (자동 생성 — tools/build.py 가 빌드할 때마다 고쳐 씀, 직접 고치지 말 것)", "",
           "고칠 내용이 생기면 **이 표에서 부품을 찾아 그 파일만** 고친 뒤 빌드한다. 자세한 방법은 `문서/수정방법.md`.",
           "부품 설명은 각 파일 맨 위 머리말(하는 일·주요 이름·이럴 때 고침)에서 가져온다. 머리말을 고치면 이 표도 바뀐다.", "",
           "## 자주 하는 수정 → 고칠 부품", "", "| 이런 수정 | 고칠 부품 (소스/…) | 찾을 이름 |", "|---|---|---|"]
    for a, b, c in read_fixes():
        out.append(f"| {a} | `{b}` | {c} |")
    out += ["", "_이 표는 `소스/자주하는수정.txt` 에서 만든다(한 줄에 `수정 | 부품 | 이름`)._", ""]
    for g, title in GROUPS:
        rows = [p for p in parts if p.startswith(g + "/")]
        if not rows:
            continue
        out += [f"## {title}", "", "| 파일 | 줄 | 하는 일 | 주요 이름 | 이럴 때 고침 |", "|---|---|---|---|---|"]
        for p in rows:
            f = SRC / p
            text = f.read_text(encoding="utf-8") if f.exists() else ""
            n = text.count("\n") + 1
            if g == "10_외부라이브러리":
                out.append(f"| `{p}` | - | 공개 라이브러리 원본(ECharts 5.5.1·Leaflet 1.9.4·시군 경계) | - | 고치지 않음 |")
                continue
            h = read_header(text) or {"does": "(머리말 없음)", "names": "", "fix": ""}
            out.append(f"| `{p}` | {n} | {h['does']} | {h['names']} | {h['fix']} |")
        out.append("")
    PARTMAP.parent.mkdir(exist_ok=True)
    PARTMAP.write_text("\n".join(out), encoding="utf-8")


# ── 실행 ─────────────────────────────────────────────────
def build(db=None, out=None, check_only=False, use_cache=False, no_key=False, mode="inline", quiet=False):
    """빌드 1회. (성공 여부, 출력 경로, 오류 목록, 주의 목록) 반환 — serve.py 에서도 씀"""
    t0 = time.time()
    db = Path(db) if db else W.DEFAULT_DB
    out = Path(out) if out else ROOT / (W.HTML_NAME.replace(".html", "_공유용.html") if no_key else W.HTML_NAME)
    warns = []
    try:
        parts = read_list()
        ver = VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else "?"
        missing = [p for p in parts if not (SRC / p).exists()]
        if missing:
            raise BuildError("목록에 있지만 파일이 없음: " + ", ".join("소스/" + p for p in missing))
        data_line, data = data_script(db, use_cache, no_key, ver, warns)
        html, app, js_map = assemble(parts, data_line, mode, ver)
        errs, w2 = check(parts, app, js_map, html)
        warns += w2
    except BuildError as e:
        errs = [str(e)]
    except W.DBLocked as e:
        errs = [str(e)]
    if not quiet:
        for w in warns:
            print("[주의]", w)
        for e in errs:
            print("[오류]", e)
    if errs:
        if not quiet:
            print(f"[실패] 오류 {len(errs)}건 — HTML을 만들지 않았습니다(기존 파일 그대로).")
        return False, out, errs, warns
    if check_only:
        print(f"[검사 통과] 부품 {len(parts)}개 · 주의 {len(warns)}건")
        return True, out, [], warns
    if out.exists():
        prev = OUTDIR / "이전"
        prev.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out, prev / f"{out.stem}_{datetime.now():%Y%m%d_%H%M%S}{out.suffix}")
        olds = sorted(prev.glob(f"{out.stem}_*{out.suffix}"))
        for o in olds[:-5]:
            o.unlink()
    out.write_text(html, encoding="utf-8", newline="\n")
    write_partmap(parts)
    if not quiet:
        print(f"[완료] {out.name}  ({out.stat().st_size / 1024:,.0f} KB · 부품 {len(parts)}개 · {time.time() - t0:.1f}초)")
        if data:
            from collections import Counter
            c = Counter(q["type"] for q in data["qc"])
            lab = {"manual": "검토필요", "repeat": "전월 동일", "outlier": "이상값 의심", "loq": "정량한계 미만",
                   "multi": "중복 채취", "coord": "좌표 추정"}
            print(f"  시료번호 {len(data['stations'])}개 · 기간 {data['months'][0] if data['months'] else '-'} ~ "
                  f"{data['months'][-1] if data['months'] else '-'} · 자료 점검: " +
                  (" · ".join(f"{lab.get(k, k)} {v}" for k, v in c.items()) or "없음"))
    return True, out, [], warns


def src_mtime():
    return max([f.stat().st_mtime for f in SRC.rglob("*") if f.is_file()] + [0])


def watch(**kw):
    print("[자동 빌드] 소스/ 또는 DB를 저장하면 다시 빌드합니다. 멈추려면 Ctrl+C")
    last = 0
    while True:
        try:
            m = max(src_mtime(), W.DEFAULT_DB.stat().st_mtime if W.DEFAULT_DB.exists() else 0)
            if m > last:
                last = m
                print(f"\n── {datetime.now():%H:%M:%S} 빌드 ──")
                build(**kw)
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n[자동 빌드] 멈춤")
            return


def main():
    ap = argparse.ArgumentParser(description="부품 → 한탄강_수질대시보드.html")
    ap.add_argument("--check", action="store_true", help="검사만")
    ap.add_argument("--watch", action="store_true", help="저장할 때마다 자동 빌드")
    ap.add_argument("--cache", action="store_true", help="DB를 읽지 않고 지난번 데이터로 조립")
    ap.add_argument("--no-key", action="store_true", help="V월드 키를 뺀 공유용")
    ap.add_argument("--cdn", action="store_true", help="라이브러리를 인터넷(CDN)에서 불러옴")
    ap.add_argument("--artifact", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--db", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    kw = dict(db=a.db, out=a.out, check_only=a.check, use_cache=a.cache, no_key=a.no_key,
              mode="artifact" if a.artifact else ("cdn" if a.cdn else "inline"))
    if a.watch:
        watch(**kw)
        return
    ok, *_ = build(**kw)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
