# -*- coding: utf-8 -*-
"""구조 규칙 시험: 파트가 서로 엉키지 않았는지 자동으로 확인한다.

실행: python tests/test_structure.py

  규칙 1. 파트(app/parts/<이름>)는 다른 파트·조립부(workspace)·화면 연결(web)을 import 하지 않는다.
  규칙 2. 공통 도구(common)·파일 형식(formats)·저장소(store)는 파트·조립부·화면 연결을 import 하지 않는다.
  규칙 3. 켜진 파트 폴더에는 __init__.py · part.py · routes.py · README.md 가 있다.
  규칙 4. 화면 주소가 겹치지 않고, 화면(js)이 부르는 주소는 모두 서버에 있다.
  규칙 5. 파이썬 파일 하나는 800줄을 넘지 않는다(넘으면 나눌 때가 된 것).
"""
import os
import re
import ast
import sys
import glob
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
APP = os.path.join(ROOT, "app")

from app import config        # noqa: E402

MAX_LINES = 800


def imports_of(path):
    tree = ast.parse(open(path, encoding="utf-8").read(), path)
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.append(n.module)
            out += [f"{n.module}.{a.name}" for a in n.names]
    return [m for m in out if m == "app" or m.startswith("app.")]


def part_names():
    return sorted(d for d in os.listdir(os.path.join(APP, "parts"))
                  if os.path.isdir(os.path.join(APP, "parts", d)) and not d.startswith("_"))


class TStructure(unittest.TestCase):
    def test_1_parts_do_not_import_each_other(self):
        bad = []
        for p in part_names():
            for f in glob.glob(os.path.join(APP, "parts", p, "**", "*.py"), recursive=True):
                for m in imports_of(f):
                    if m.startswith("app.parts.") and not m.startswith(f"app.parts.{p}"):
                        bad.append(f"{os.path.relpath(f, ROOT)} → {m}")
                    if m.startswith(("app.workspace", "app.web")):
                        bad.append(f"{os.path.relpath(f, ROOT)} → {m}")
        self.assertEqual(bad, [], "파트가 다른 파트를 직접 부르고 있습니다. 조립부(app/workspace.py)에서 연결하세요")

    def test_2_base_layers_are_independent(self):
        bad = []
        for layer in ("common", "formats", "store"):
            for f in glob.glob(os.path.join(APP, layer, "**", "*.py"), recursive=True):
                for m in imports_of(f):
                    if m.startswith(("app.parts", "app.workspace", "app.web")):
                        bad.append(f"{os.path.relpath(f, ROOT)} → {m}")
        self.assertEqual(bad, [])

    def test_3_part_folders_complete(self):
        missing = []
        for p in config.PARTS:
            for f in ("__init__.py", "part.py", "routes.py", "README.md"):
                if not os.path.exists(os.path.join(APP, "parts", p, f)):
                    missing.append(f"parts/{p}/{f}")
        self.assertEqual(missing, [])
        self.assertEqual(sorted(config.PARTS), sorted(set(config.PARTS)), "PARTS 목록에 중복이 있습니다")
        for p in config.PARTS:
            self.assertIn(p, part_names(), f"config.PARTS 의 '{p}' 폴더가 없습니다")

    def test_4_routes_unique_and_ui_paths_exist(self):
        from app.web.server import App
        a = App()                          # 주소가 겹치면 여기서 멈춤
        have = {p for (_, p) in a.table}
        used = set()
        for f in glob.glob(os.path.join(APP, "ui", "**", "*.js"), recursive=True):
            used |= set(re.findall(r"""api\(\s*["'`](/api/[a-z0-9/_]+)""", open(f, encoding="utf-8").read()))
        for f in glob.glob(os.path.join(ROOT, "tests", "e2e*.py")):
            used |= set(re.findall(r"""api\(\s*["'`](/api/[a-z0-9/_]+)""", open(f, encoding="utf-8").read()))
        self.assertTrue(used, "화면에서 부르는 주소를 찾지 못했습니다")
        self.assertEqual(sorted(used - have), [], "화면이 부르는데 서버에 없는 주소")

    def test_5_file_size(self):
        big = []
        for f in glob.glob(os.path.join(ROOT, "app", "**", "*.py"), recursive=True):
            n = sum(1 for _ in open(f, encoding="utf-8"))
            if n > MAX_LINES:
                big.append(f"{os.path.relpath(f, ROOT)} {n}줄")
        self.assertEqual(big, [], f"{MAX_LINES}줄이 넘는 파일은 나눠 주세요")


if __name__ == "__main__":
    unittest.main(verbosity=2)
