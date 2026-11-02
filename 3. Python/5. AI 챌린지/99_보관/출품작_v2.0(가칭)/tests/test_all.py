# -*- coding: utf-8 -*-
"""자동 시험.  실행: python tests/test_all.py   (표준 라이브러리 unittest)"""
import os
import sys
import time
import json
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from app.common import numbers as N                                   # noqa: E402
from app.formats.xlsx import write_xlsx, read_xlsx                  # noqa: E402
from app.formats.hwpx import HwpxDoc, HwpxError                     # noqa: E402
from app.formats.hwpx_build import HwpxBuilder                         # noqa: E402
from app.workspace import Workspace, WorkError                 # noqa: E402
from app.parts.clip.clipwatch import parse_link, parse_text               # noqa: E402
import score_demo                                                   # noqa: E402

TMP = tempfile.mkdtemp(prefix="numjigi_test_")
DEMO = os.path.join(TMP, "시연자료")


def setUpModule():
    sys.argv = ["make_demo", DEMO]
    import importlib
    md = importlib.import_module("tools.make_demo") if os.path.exists(os.path.join(ROOT, "tools", "__init__.py")) else None
    if md is None:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import make_demo as md
    md.Demo(DEMO).run()


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


class T1Numbers(unittest.TestCase):
    def test_extract(self):
        t = "2026. 11. 25.(수) 10:00, 제5조에 따라 요구자료 10. 실적은 총 1,234건으로 전년(1,100건) 대비 12.2% 증가, PM2.5 18.3㎍/㎥"
        vals = [x["raw"] for x in N.extract_numbers(t)]
        self.assertEqual(vals, ["1,234", "1,100", "12.2", "18.3"])

    def test_cell(self):
        self.assertEqual(N.parse_cell("1,234")["value"], 1234)
        self.assertEqual(N.parse_cell("△12.5")["value"], -12.5)
        self.assertEqual(N.parse_cell("79.6%")["dec"], 1)
        self.assertIsNone(N.parse_cell("2025년"))
        self.assertIsNone(N.parse_cell("가온시"))

    def test_close(self):
        self.assertTrue(N.close(2.338, 2.3, 1))
        self.assertTrue(N.close(2.3455, 2.35, 2))
        self.assertFalse(N.close(2.338, 3.2, 1))

    def test_weekday_claim(self):
        w = N.weekday_issues("감사 2026. 11. 25.(목) 및 11. 11.(수)", 2026)
        self.assertEqual(len(w), 1)
        self.assertIn("수요일", w[0]["msg"])
        c = N.change_claims("민원은 312건으로 전년 동기(352건) 대비 15.3% 감소")
        self.assertFalse(c[0]["ok"])
        self.assertEqual(c[0]["expected_text"], "11.4%")
        c2 = N.change_claims("집행률은 83.2%로 전년 동기(67.1%) 대비 16.1%p 상승")
        self.assertTrue(c2[0]["ok"])


class T2Xlsx(unittest.TestCase):
    def test_roundtrip(self):
        p = os.path.join(TMP, "rt.xlsx")
        write_xlsx(p, [{"name": "가", "rows": [["이름", "값", "날짜"], ["a", {"v": 1.2345, "fmt": "0.00"}, {"v": 46000, "fmt": "yyyy-mm-dd"}],
                                              ["b", 1000, "글자 <&>"]]}])
        wb = read_xlsx(p)
        s = wb.sheets[0]
        self.assertEqual(s.get(1, 1).v, 1.2345)
        self.assertEqual(s.get(1, 1).text, "1.23")
        self.assertEqual(s.get(1, 2).kind, "d")
        self.assertEqual(s.get(2, 2).text, "글자 <&>")

    def test_openpyxl_opens(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl 없음")
        for dp, _, fs in os.walk(DEMO):
            for f in fs:
                if f.endswith(".xlsx"):
                    openpyxl.load_workbook(os.path.join(dp, f))


class T3Hwpx(unittest.TestCase):
    def test_fields_roundtrip(self):
        src = os.path.join(DEMO, "공유폴더(가상)", "2026 행정사무감사", "03_취합", "2026_행정사무감사_요구자료_취합본.hwpx")
        d = HwpxDoc(src)
        before = [(i.key, i.raw) for i in d.items]
        n = d.make_fields()
        self.assertEqual(n, len([i for i in d.items if i.editable]))
        p = os.path.join(TMP, "f.hwpx")
        d.save(p)
        d2 = HwpxDoc(p)
        self.assertEqual(before, [(i.key, i.raw) for i in d2.items])
        self.assertTrue(all(i.field for i in d2.items))
        k = d2.items[10].key
        d2.set_field(k, "123.4")
        d2.mark(k, "red")
        d2.save(p)
        d3 = HwpxDoc(p)
        self.assertEqual(d3.item(k).raw, "123.4")
        import zipfile
        with zipfile.ZipFile(p) as z:
            self.assertEqual(z.infolist()[0].filename, "mimetype")
            self.assertEqual(z.infolist()[0].compress_type, zipfile.ZIP_STORED)
            h = z.read("Contents/header.xml").decode()
            import re
            cnt = int(re.search(r'<hh:charProperties itemCnt="(\d+)"', h).group(1))
            self.assertEqual(cnt, h.count("<hh:charPr "))

    def test_blank_form(self):
        f = os.path.join(DEMO, "공유폴더(가상)", "2026 행정사무감사", "03_취합", "2026_행정사무감사_요구자료_작성틀(수질·대기).hwpx")
        d = HwpxDoc(f)
        self.assertEqual(len([i for i in d.items if i.empty]), 57)
        d.make_fields()
        p = os.path.join(TMP, "form.hwpx")
        d.save(p)
        d2 = HwpxDoc(p)
        d2.set_field(d2.items[0].key, "2.0")
        d2.save(p)
        self.assertEqual(HwpxDoc(p).items[0].raw, "2.0")

    def test_bad_files(self):
        p0 = os.path.join(TMP, "zero.hwpx")
        open(p0, "wb").close()
        with self.assertRaises(HwpxError):
            HwpxDoc(p0)
        p1 = os.path.join(TMP, "old.hwpx")
        open(p1, "wb").write(b"\xd0\xcf\x11\xe0" + b"\x00" * 100)
        with self.assertRaises(HwpxError) as cm:
            HwpxDoc(p1)
        self.assertIn("구형", str(cm.exception))


class T4Engine(unittest.TestCase):
    def test_answer_key_stage1(self):
        ok, n, bad, noise, out = score_demo.score(DEMO, stage=1, verbose=False)
        self.assertEqual(ok, n, f"틀린 항목: {bad}")
        self.assertEqual(noise, [], "정답표 밖에서 빨강·노랑 표시가 나오면 안 됨")

    def test_answer_key_stage2(self):
        d2 = os.path.join(TMP, "demo2")
        shutil.copytree(DEMO, d2)
        shutil.copy2(os.path.join(d2, "나중에_받은_자료", "하천수질_측정결과_2026.xlsx"),
                     os.path.join(d2, "공유폴더(가상)", "2026 행정사무감사", "01_원본자료", "수질분석팀", "하천수질_측정결과_2026.xlsx"))
        ok, n, bad, noise, out = score_demo.score(d2, stage=2, verbose=False)
        self.assertEqual(ok, n, f"틀린 항목: {bad}")
        self.assertEqual(noise, [])


class T5Workspace(unittest.TestCase):
    def setUp(self):
        self.base = os.path.join(DEMO, "공유폴더(가상)", "2026 행정사무감사")
        self.wdir = tempfile.mkdtemp(prefix="ws_", dir=TMP)
        self.ws = Workspace(self.wdir, "시험자")
        self.ws.set_target(os.path.join(self.base, "03_취합", "2026_행정사무감사_요구자료_취합본.hwpx"))

    def tearDown(self):
        self.ws.db.close()

    def test_flow(self):
        r = self.ws.add_sources([os.path.join(self.base, "01_원본자료"), os.path.join(self.base, "02_팀제출")])
        self.assertEqual(len(r["added"]), 17)
        r2 = self.ws.add_sources([os.path.join(self.base, "01_원본자료")])
        self.assertEqual(len(r2["added"]), 0)                    # 중복 등록 안 됨
        v = self.ws.verify()
        self.assertEqual(v["summary"]["mismatch"], 4)
        d = self.ws.slot_detail("표2_은하천하류_BOD")
        o = d["sources"][0]
        self.assertEqual(o["role"], "원본")                        # 엑셀 원본을 먼저 보여 줌
        self.ws.fix_from_source("표2_은하천하류_BOD", o["sid"], o["ref"], d["result"]["fix"])
        self.ws.set_pending("P18_3", "11.4", "직접 입력", reason="재계산")
        s = self.ws.save_version("시험")
        self.assertEqual(s["ver"], 2)
        doc = self.ws.doc(fresh=True)
        self.assertEqual(doc.item("표2_은하천하류_BOD").raw, "2.3")
        ev = self.ws.db.events("표2_은하천하류_BOD")
        self.assertEqual(ev[0]["method"], "원본 값으로 수정")
        self.assertTrue(ev[0]["source_sha"])
        v2 = self.ws.verify()
        self.assertEqual(v2["items"]["표2_은하천하류_BOD"]["status"], "ok_user")
        files = self.ws.export()
        for k in ("ledger", "marked", "report"):
            self.assertTrue(os.path.exists(files[k]))
        wb = read_xlsx(files["ledger"])
        self.assertEqual([s.name for s in wb.sheets], ["검증결과", "값 이력", "원본 목록", "원본 변경 기록", "작업본 버전"])

    def test_input_values(self):
        self.ws.add_sources([os.path.join(self.base, "01_원본자료", "수질분석팀")])
        sid = [s["sid"] for s in self.ws.db.sources() if s["name"].startswith("하천수질")][0]
        # 연평균 시트 HB-02 행(5행)의 BOD(E열)~TOC(G열) → 문서 칸 BOD부터 3칸
        r = self.ws.input_values(sid, "연평균", 4, 4, 4, 6, "표2_은하천중류_BOD", dec=1)
        self.assertEqual(r["count"] + r["same"], 3)
        p = {x["slot"]: x for x in self.ws.db.pending()}
        self.assertIn("표2_은하천중류_TOC", p)                     # 원본 COD 값이 TOC 칸에 들어가는 '모양 그대로' 입력
        self.assertEqual(p["표2_은하천중류_TOC"]["source_ref"], "연평균!F5")

    def test_manual_edit_detected(self):
        path = self.ws.current_path()
        d = HwpxDoc(path)
        d.set_field("표1_합계_2025년", "8,713")
        d.save(path)                                            # 한글에서 고친 것처럼
        time.sleep(0.01)
        v = self.ws.verify()
        self.assertEqual(len(v["edits"]), 1)
        ev = self.ws.db.events("표1_합계_2025년")
        self.assertEqual(ev[0]["method"], "한글에서 직접 수정")

    def test_bad_sources_do_not_stop(self):
        bad = os.path.join(self.wdir, "..", "bad_src")
        os.makedirs(bad, exist_ok=True)
        open(os.path.join(bad, "빈파일.xlsx"), "wb").close()
        with open(os.path.join(bad, "깨짐.hwpx"), "wb") as f:
            f.write(b"PK\x03\x04broken")
        open(os.path.join(bad, "~$잠금.xlsx"), "wb").write(b"x")
        shutil.copy2(os.path.join(self.base, "01_원본자료", "운영지원팀", "인력현황_2026-09.xlsx"), bad)
        r = self.ws.add_sources([bad])
        self.assertEqual(len(r["added"]), 1)
        self.assertEqual(len(r["failed"]), 2)
        self.assertTrue(any(x["why"] == "임시 파일" for x in r["skipped"]))
        v = self.ws.verify()                                      # 실패한 원본이 있어도 검증은 돌아감
        self.assertGreater(v["summary"]["total"], 100)

    def test_source_change_and_missing(self):
        src = os.path.join(self.wdir, "..", "chg.xlsx")
        shutil.copy2(os.path.join(self.base, "01_원본자료", "운영지원팀", "인력현황_2026-09.xlsx"), src)
        self.ws.add_sources([src])
        self.ws.verify()
        write_xlsx(src, [{"name": "직렬별", "rows": [["직렬", "정원"], ["환경연구사", 40]]}])
        c = self.ws.check_sources()
        self.assertEqual(len(c["changed"]), 1)
        self.assertTrue(c["changed"][0]["affected"])
        os.remove(src)
        c2 = self.ws.check_sources()
        self.assertEqual(len(c2["missing"]), 1)

    def test_reject_hwp_and_second_target(self):
        with self.assertRaises(WorkError):
            self.ws.set_target(os.path.join(self.base, "03_취합", "2026_행정사무감사_요구자료_작성틀(수질·대기).hwpx"))
        p = os.path.join(TMP, "x.hwp")
        open(p, "wb").write(b"\xd0\xcf\x11\xe0")
        w2 = Workspace(tempfile.mkdtemp(dir=TMP))
        with self.assertRaises(WorkError):
            w2.set_target(p)
        w2.db.close()

    def test_clip_hint(self):
        self.ws.add_sources([os.path.join(self.base, "01_원본자료", "대기환경팀")])
        self.ws.record_clip({"path": r"C:\공유\대기측정망_월보_2026.xlsx", "sheet": "요약", "r0": 3, "c0": 1, "nrows": 1, "ncols": 2,
                             "cells": {(0, 0): "35.3", (0, 1): "17.8"}})
        v = self.ws.verify()
        d = self.ws.slot_detail("표3_PM10평균_가온동")
        self.assertTrue(d["clips"])
        self.assertEqual(d["clips"][0]["ref"], "B4")


class T6Clip(unittest.TestCase):
    def test_parse(self):
        raw = b"Excel\x00C:\\work\\[data.xlsx]Sheet1\x00R2C3:R4C5\x00\x00"
        p = parse_link(raw)
        self.assertEqual(p["path"], "C:\\work\\data.xlsx")
        self.assertEqual(p["sheet"], "Sheet1")
        self.assertEqual((p["r0"], p["c0"], p["nrows"], p["ncols"]), (1, 2, 3, 3))
        self.assertIsNone(parse_link(b"Word\x00x\x00y\x00\x00"))
        c = parse_text("1\t2\r\n3\t\r\n")
        self.assertEqual(c, {(0, 0): "1", (0, 1): "2", (1, 0): "3"})


class T7Perf(unittest.TestCase):
    def test_large_source(self):
        p = os.path.join(TMP, "big.xlsx")
        import random
        rnd = random.Random(1)
        rows = [["번호"] + [f"항목{j}" for j in range(20)]]
        for i in range(10000):
            rows.append([i] + [round(rnd.uniform(0, 1000), 2) for _ in range(20)])
        write_xlsx(p, [{"name": "자료", "rows": rows}])
        t = time.time()
        wb = read_xlsx(p)
        t_read = time.time() - t
        tgt = os.path.join(DEMO, "공유폴더(가상)", "2026 행정사무감사", "03_취합", "2026_행정사무감사_요구자료_취합본.hwpx")
        srcdir = os.path.join(DEMO, "공유폴더(가상)", "2026 행정사무감사")
        res = []
        for extra in ([], [p]):
            w = Workspace(tempfile.mkdtemp(dir=TMP))
            w.set_target(tgt)
            w.add_sources([os.path.join(srcdir, "01_원본자료"), os.path.join(srcdir, "02_팀제출")] + extra)
            t = time.time()
            v = w.verify()
            res.append((time.time() - t, {k: v["items"][k]["status"] for k in v["items"]}))
            w.db.close()
        t_ver = res[1][0]
        print(f"\n  [성능] 20만 칸 엑셀 읽기 {t_read:.1f}초 / 원본 18개(20만 칸 추가) 검증 {t_ver:.1f}초")
        self.assertLess(t_ver, 60)
        diff = {k: (a, res[1][1][k]) for k, a in res[0][1].items() if res[1][1][k] != a}
        bad = {k: d for k, d in diff.items() if d[1] in ("mismatch", "unit", "calc", "conflict")}
        self.assertEqual(bad, {}, "무작위 큰 원본이 섞여도 빨강·충돌 판정이 새로 생기면 안 됨")


if __name__ == "__main__":
    unittest.main(verbosity=2)
