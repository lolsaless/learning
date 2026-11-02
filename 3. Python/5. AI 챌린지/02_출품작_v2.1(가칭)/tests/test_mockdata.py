# -*- coding: utf-8 -*-
"""가상자료 생성기 시험.  실행: python tests/test_mockdata.py

  1. 시나리오 폴더 구성(공문함·원본·팀제출·취합·참고자료·재제출본·정답표·안내)
  2. 만든 hwpx·odt·xlsx 를 프로그램이 다시 읽을 수 있음
  3. 같은 씨앗값 → 같은 자료(재현성)
  4. 회귀 채점: 정해 둔 씨앗값 10개에서 심은 오류를 모두 찾고 빨강 오탐 0
  5. 재제출본: 정답표의 바뀐 칸이 실제로 바뀌어 있음
"""
import os
import sys
import json
import glob
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.parts.mockdata.scenario import Scenario          # noqa: E402
from app.formats.hwpx import HwpxDoc                     # noqa: E402
from app.formats.odt import read_odt                     # noqa: E402
from app.formats.xlsx import read_xlsx, parse_ref        # noqa: E402
from app import evaluation                               # noqa: E402

TMP = tempfile.mkdtemp(prefix="mock_test_")
REGRESSION_SEEDS = [30000 + i for i in range(10)]        # 2026-10-29 기준 모두 통과(검출 100%, 빨강 오탐 0)


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


class TMock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = Scenario(TMP, seed=4321, size="보통", errors=12).run()
        cls.f = cls.s["folder"]
        cls.key = json.load(open(os.path.join(cls.f, "정답표.json"), encoding="utf-8"))

    def test_1_folders(self):
        base = glob.glob(os.path.join(self.f, "공유폴더(가상)", "*"))[0]
        for sub in ("00_공문함", "01_원본자료", "02_팀제출", "03_취합", "04_참고자료"):
            self.assertTrue(os.listdir(os.path.join(base, sub)), sub)
        self.assertTrue(os.listdir(os.path.join(self.f, "나중에_받은_자료")))
        self.assertTrue(os.path.exists(os.path.join(self.f, "시나리오_안내.md")))
        self.assertEqual(self.s["tables"], 8)
        self.assertGreaterEqual(self.s["errors"], 10)

    def test_2_files_readable(self):
        n = {"hwpx": 0, "odt": 0, "xlsx": 0}
        for p in glob.glob(os.path.join(self.f, "**", "*.*"), recursive=True):
            ext = p.rsplit(".", 1)[-1]
            if ext == "hwpx":
                HwpxDoc(p)
            elif ext == "odt":
                d = read_odt(p)
                self.assertTrue(d["paras"], p)
            elif ext == "xlsx":
                self.assertTrue(read_xlsx(p).sheets, p)
            else:
                continue
            n[ext] += 1
        self.assertTrue(all(v > 0 for v in n.values()), n)
        req = [p for p in glob.glob(os.path.join(self.f, "**", "*요구자료 제출 요청.odt"), recursive=True)]
        d = read_odt(req[0])
        self.assertTrue(any(p.startswith("수신") for p in d["paras"]))
        self.assertTrue(any("끝." in p for p in d["paras"]))

    def test_3_reproducible(self):
        again = Scenario(os.path.join(TMP, "again"), seed=4321, size="보통", errors=12).run()
        k2 = json.load(open(os.path.join(again["folder"], "정답표.json"), encoding="utf-8"))
        self.assertEqual(self.key["항목"], k2["항목"])
        self.assertEqual(self.key["재제출"], k2["재제출"])

    def test_4_regression_scores(self):
        out = os.path.join(TMP, "reg")
        bad = []
        for seed in REGRESSION_SEEDS:
            s = Scenario(out, seed=seed, size="보통", errors=12, gongmun=False, guides=False, form=False, resubmit=False).run()
            r = evaluation.score(s["folder"])
            miss = [x["id"] for x in r["항목"] if not x["ok"] and not x["연쇄"]]
            if miss or r["빨강오탐"]:
                bad.append((seed, miss, r["빨강오탐"]))
        self.assertEqual(bad, [], "회귀: 예전에 다 맞던 시나리오에서 놓침·오탐이 생김")

    def test_5_resubmit(self):
        self.assertEqual(len(self.key["재제출"]), 2)
        for r in self.key["재제출"]:
            new = read_xlsx(os.path.join(self.f, r["수정본"]))
            old = read_xlsx(os.path.join(self.f, r["원본"]))
            for c in r["변경"]:
                rr, cc = parse_ref(c["칸"])
                self.assertNotEqual(new.sheet(c["시트"]).get(rr, cc).v, old.sheet(c["시트"]).get(rr, cc).v)
            self.assertEqual(len(r["영향"]), len(r["변경"]))

    def test_6_forms(self):
        kinds = {f["판정"] for f in self.key["양식"]}
        self.assertIn("작성제출", kinds)
        self.assertIn("참고", kinds)
        self.assertTrue(any(k.startswith("공문") for k in kinds))


if __name__ == "__main__":
    unittest.main(verbosity=2)
