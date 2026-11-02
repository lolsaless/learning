# -*- coding: utf-8 -*-
"""[화면 연결] 파트 지도(구성도): 코드를 직접 읽어 '층 → 구성요소 → 파일 → 함수'를 정리한다.

손으로 적는 목록이 아니라 실행할 때마다 코드에서 다시 읽으므로, 파일을 고치면 지도도 저절로 바뀐다.
  build()        → 화면용 자료(JSON)
  to_markdown()  → docs/파트지도.md (python tools/part_map.py)

구성요소 번호
  U  화면(app/ui)            W  화면 연결(app/web)        A  조립부(workspace·evaluation·main)
  P  기능 파트(app/parts)    B  바탕(config·common·formats·store)
"""
import os
import re
import ast

from app import config

APP = os.path.join(config.PROGRAM_ROOT, "app")

LAYERS = [
    ("U", "화면", "브라우저에 보이는 화면. 페이지마다 모양(html)과 동작(js) 파일이 하나씩 있다."),
    ("W", "화면 연결", "화면 요청을 받아 파트로 넘기는 로컬 서버(127.0.0.1 전용)."),
    ("A", "조립부", "파트를 만들고 서로 연결한다. 계산은 하지 않는다."),
    ("P", "기능 파트", "기능 하나 = 폴더 하나. 파트끼리는 서로 부르지 않는다."),
    ("B", "바탕", "모든 층이 쓰는 설정·공통 도구·파일 형식·저장소. 위층을 모른다."),
]
PART_NAMES = {"sources": "원본", "document": "문서", "verify": "검증", "edit": "수정·입력", "history": "이력",
              "export": "내보내기", "clip": "클립보드", "mockdata": "가상자료"}
BASE_NAMES = {"config.py": "설정", "common": "공통 도구", "formats": "파일 형식", "store": "저장소"}
WEB_NAMES = {"server.py": "서버", "core_routes.py": "공통 주소", "eval_routes.py": "평가 주소", "demo.py": "시연 준비",
             "fsbrowse.py": "폴더 탐색", "partmap.py": "파트 지도"}
PAGE_NAMES = {"뼈대·공통": "뼈대·공통", "prep": "1 작업 준비", "check": "2 검증", "input": "3 입력하기", "hist": "4 이력",
              "mock": "5 시연자료", "map": "6 구성도", "conf": "7 설정·도움말"}
WEB_ORDER = ["server.py", "core_routes.py", "eval_routes.py", "demo.py", "fsbrowse.py", "partmap.py"]
APP_NAMES = {"main.py": "시작점", "workspace.py": "작업 조립부", "evaluation.py": "평가 조립부"}

# 자주 고치는 일 → 볼 곳
FIX_GUIDE = [
    ("프로그램 이름 바꾸기", "B 설정", "app/config.py 의 APP_NAME"),
    ("판정 허용 오차·배율·합계 낱말 바꾸기", "B 설정", "app/config.py (UNIT_SCALES, TOTAL_WORDS, CALC_SLACK …)"),
    ("숫자로 보지 않을 글자 추가(날짜·조문 번호 등)", "B 설정", "app/config.py 의 SKIP_PATTERNS"),
    ("증감률 문장 형태 추가", "B 공통 도구", "app/common/numbers.py 의 CLAIM"),
    ("한글 문서를 못 읽거나 누름틀이 이상함", "B 파일 형식", "app/formats/hwpx/scan.py · fields.py"),
    ("엑셀을 못 읽음", "B 파일 형식", "app/formats/xlsx/read.py"),
    ("출처를 엉뚱한 곳으로 연결함", "P 검증", "app/parts/verify/engine/table_map.py"),
    ("일치·불일치 판정 기준", "P 검증", "app/parts/verify/engine/judge.py · index.py(_relation)"),
    ("합계·비율 재계산", "P 검증", "app/parts/verify/engine/calc.py"),
    ("출처대장·검증표시본 모양", "P 내보내기", "app/parts/export/report.py"),
    ("시연자료에 새 자료 영역 추가", "P 가상자료", "app/parts/mockdata/domains.py 의 DOMAINS"),
    ("시연자료에 새 오류 종류 추가", "P 가상자료", "app/parts/mockdata/errors.py 의 KINDS · e_<종류>()"),
    ("가상 공문 서식", "P 가상자료", "app/parts/mockdata/gongmun.py"),
    ("화면 한 페이지 고치기", "U 화면", "app/ui/pages/<이름>.html + app/ui/js/pages/<이름>.js"),
    ("새 기능 파트 추가", "P·A", "docs/설계서_v2.0.md 7장 순서대로"),
]


def _doc1(s):
    s = (s or "").strip()
    return s.split("\n")[0].strip() if s else ""


def py_info(path):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    funcs, classes, deps = [], [], set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_"):
            funcs.append({"name": n.name, "doc": _doc1(ast.get_docstring(n))})
        elif isinstance(n, ast.ClassDef):
            ms = [{"name": m.name, "doc": _doc1(ast.get_docstring(m))} for m in n.body
                  if isinstance(m, ast.FunctionDef) and not m.name.startswith("_")]
            classes.append({"name": n.name, "doc": _doc1(ast.get_docstring(n)), "methods": ms})
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("app"):
            # from app.web import demo → app.web.demo (가져온 이름이 모듈이면 그 모듈, 아니면 앞 모듈)
            for a in n.names:
                deps.add(f"{n.module}|{a.name}")
        elif isinstance(n, ast.Import):
            deps |= {a.name for a in n.names if a.name.startswith("app")}
    rel = os.path.relpath(path, config.PROGRAM_ROOT).replace(os.sep, "/")
    return {"path": rel, "lines": src.count("\n") + 1, "doc": _doc1(ast.get_docstring(tree)), "funcs": funcs,
            "classes": classes, "deps": sorted(deps)}


def _files(folder):
    out = []
    for dp, dns, fs in os.walk(folder):
        dns[:] = sorted(d for d in dns if d != "__pycache__")
        for f in sorted(fs):
            if f.endswith(".py") and not (f == "__init__.py" and os.path.getsize(os.path.join(dp, f)) < 400):
                out.append(py_info(os.path.join(dp, f)))
    return out


def _routes_of(folder):
    p = os.path.join(folder, "routes.py")
    if not os.path.exists(p):
        return []
    return re.findall(r'\("(GET|POST)",\s*"(/api/[^"]+)"', open(p, encoding="utf-8").read())


def _readme(folder):
    p = os.path.join(folder, "README.md")
    if not os.path.exists(p):
        return ""
    t = open(p, encoding="utf-8").read()
    m = re.search(r"## 하는 일\s*\n(.+?)(\n\n|\n#)", t, flags=re.S)
    return m.group(1).strip() if m else ""


def _ui_files():
    out = []
    ui = os.path.join(APP, "ui")
    for dp, dns, fs in os.walk(ui):
        for f in sorted(fs):
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, config.PROGRAM_ROOT).replace(os.sep, "/")
            txt = open(p, encoding="utf-8").read()
            m = re.search(r"/\*\s*(.+?)\n", txt) if f.endswith((".js", ".css")) else None
            api = sorted(set(re.findall(r'api\(\s*["\'`](/api/[a-z0-9/_]+)', txt)))
            out.append({"path": rel, "lines": txt.count("\n") + 1, "doc": m.group(1).strip(" *") if m else "", "api": api})
    return sorted(out, key=lambda x: x["path"])


def build():
    comps = []
    ui = _ui_files()
    pages = {}
    for f in ui:
        m = re.search(r"pages/(\w+)\.(html|js)$", f["path"])
        key = m.group(1) if m else ("뼈대·공통" if "pages" not in f["path"] else f["path"])
        pages.setdefault(key, []).append(f)
    n = 0
    order = list(PAGE_NAMES)
    for k, fs in sorted(pages.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 99):
        n += 1
        comps.append({"id": f"U{n}", "layer": "U", "name": PAGE_NAMES.get(k, k), "role": next((x["doc"] for x in fs if x["doc"]), ""),
                      "files": fs, "routes": sorted({a for x in fs for a in x["api"]})})
    n = 0
    webfs = [f for f in os.listdir(os.path.join(APP, "web")) if f.endswith(".py") and f != "__init__.py"]
    for f in sorted(webfs, key=lambda x: WEB_ORDER.index(x) if x in WEB_ORDER else 99):
        if True:
            n += 1
            info = py_info(os.path.join(APP, "web", f))
            comps.append({"id": f"W{n}", "layer": "W", "name": WEB_NAMES.get(f, f), "role": info["doc"], "files": [info],
                          "routes": [r[1] for r in _routes_of_file(os.path.join(APP, "web", f))]})
    n = 0
    for f in ("main.py", "workspace.py", "evaluation.py"):
        p = os.path.join(APP, f)
        if os.path.exists(p):
            n += 1
            info = py_info(p)
            comps.append({"id": f"A{n}", "layer": "A", "name": APP_NAMES[f], "role": info["doc"], "files": [info], "routes": []})
    parts_dir = os.path.join(APP, "parts")
    n = 0
    allp = [d for d in os.listdir(parts_dir) if os.path.isdir(os.path.join(parts_dir, d)) and not d.startswith("_")]
    for p in sorted(allp, key=lambda d: config.PARTS.index(d) if d in config.PARTS else 99):
        n += 1
        folder = os.path.join(parts_dir, p)
        comps.append({"id": f"P{n}", "layer": "P", "key": p, "name": PART_NAMES.get(p, p), "on": p in config.PARTS,
                      "role": _readme(folder), "files": _files(folder), "routes": [r[1] for r in _routes_of(folder)]})
    n = 0
    for key in ("config.py", "common", "formats", "store"):
        p = os.path.join(APP, key)
        n += 1
        files = [py_info(p)] if key.endswith(".py") else _files(p)
        role = files[0]["doc"] if key.endswith(".py") else next((x["doc"] for x in files if x["doc"]), "")
        comps.append({"id": f"B{n}", "layer": "B", "name": BASE_NAMES[key], "role": role, "files": files, "routes": []})
    # 구성요소끼리 쓰는 관계(파일 import 로 계산)
    owner = {}
    for c in comps:
        for f in c["files"]:
            mod = f["path"][:-3].replace("/", ".") if f["path"].endswith(".py") else None
            if mod:
                owner[mod] = c["id"]
                if mod.endswith(".__init__"):
                    owner[mod[:-9]] = c["id"]
    for c in comps:
        uses = set()
        for f in c["files"]:
            for d in f.get("deps", []):
                mod, _, name = d.partition("|")
                tgt = owner.get(f"{mod}.{name}") or owner.get(mod) or \
                    (next((owner[m] for m in owner if m.startswith(mod + ".")), None) if mod != "app" else None)
                if tgt and tgt != c["id"]:
                    uses.add(tgt)
        c["uses"] = sorted(uses)
        c["lines"] = sum(f["lines"] for f in c["files"])
    # 화면 페이지는 import 대신 화면 주소(/api/…)로 파트를 부른다 → 주소 주인과 연결
    route_owner = {r: c["id"] for c in comps if c["layer"] != "U" for r in c["routes"]}
    for c in comps:
        if c["layer"] == "U":
            c["uses"] = sorted({route_owner[r] for r in c["routes"] if r in route_owner})
    return {"app": config.APP_NAME, "version": config.APP_VERSION, "layers": [dict(zip(("id", "name", "role"), x)) for x in LAYERS],
            "components": comps, "fix_guide": [dict(zip(("task", "where", "file"), x)) for x in FIX_GUIDE],
            "total_lines": sum(c["lines"] for c in comps), "total_files": sum(len(c["files"]) for c in comps)}


def _routes_of_file(path):
    return re.findall(r'\("(GET|POST)",\s*"(/api/[^"]+)"', open(path, encoding="utf-8").read())


def to_markdown(m=None):
    m = m or build()
    L = [f"# 파트 지도 — {m['app']} v{m['version']}", "",
         "> 이 문서는 `python tools/part_map.py` 가 코드를 읽어 자동으로 만든다. 손으로 고치지 말 것.", "",
         f"구성요소 {len(m['components'])}개 · 파일 {m['total_files']}개 · 코드 {m['total_lines']:,}줄", "",
         "## 1. 한눈에 보기", "", "```"]
    for lay in m["layers"]:
        cs = [c for c in m["components"] if c["layer"] == lay["id"]]
        L.append(f"[{lay['id']}] {lay['name']}")
        L.append("    " + "  ".join(f"{c['id']}:{c['name']}" for c in cs))
    L += ["```", "", "위층은 아래층을 쓰고, 아래층은 위층을 모른다. 기능 파트(P)끼리는 서로 부르지 않는다.", "",
          "## 2. 고칠 곳 찾기", "", "| 하고 싶은 일 | 구성요소 | 볼 곳 |", "|---|---|---|"]
    for g in m["fix_guide"]:
        L.append(f"| {g['task']} | {g['where']} | `{g['file']}` |")
    for lay in m["layers"]:
        L += ["", f"## {lay['id']}. {lay['name']}", "", lay["role"], ""]
        for c in [c for c in m["components"] if c["layer"] == lay["id"]]:
            off = "" if c.get("on", True) else " (꺼짐)"
            L += [f"### {c['id']} {c['name']}{off}", "", c["role"] or "", "",
                  f"- 파일 {len(c['files'])}개 · {c['lines']:,}줄" + (f" · 쓰는 구성요소: {', '.join(c['uses'])}" if c["uses"] else ""),
                  *( [f"- 화면 주소: {', '.join('`' + r + '`' for r in c['routes'])}"] if c["routes"] else []), "",
                  "| 파일 | 줄 | 하는 일 |", "|---|---|---|"]
            for f in c["files"]:
                L.append(f"| `{f['path']}` | {f['lines']} | {f['doc']} |")
                for k in f.get("classes", []):
                    L.append(f"| └ class `{k['name']}` | | {k['doc']} |")
                for fn in f.get("funcs", [])[:12]:
                    L.append(f"| └ `{fn['name']}()` | | {fn['doc']} |")
            L.append("")
    return "\n".join(L) + "\n"


def routes(app):
    return [("GET", "/api/partmap", lambda q: build())]
