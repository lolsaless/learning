# -*- coding: utf-8 -*-
"""AI 파트(문장 검산)·재제출 비교 파트 시험. 실제 AI 없이 '시험용 모의 AI'로 흐름을 확인한다.
실행: python tests/test_ai_compare.py
"""
import os
import sys
import json
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.parts.ai.part import AiPart, parse_json                    # noqa: E402
from app.parts.ai.providers import Mock, make, AiError               # noqa: E402
from app.parts.ai import claims as C, summary as S                  # noqa: E402
from app.parts.compare import diff as D                             # noqa: E402
from app.parts.compare.part import read_book, _stem                 # noqa: E402
from app.formats.xlsx import write_xlsx                             # noqa: E402
from app.parts.mockdata.scenario import Scenario                    # noqa: E402
from app.workspace import Workspace                                 # noqa: E402
from app import config                                              # noqa: E402

TMP = tempfile.mkdtemp(prefix="ai_cmp_test_")
NOFILE = os.path.join(TMP, "없음.json")


class _Doc:
    def __init__(self, texts):
        self.blocks = [{"type": "p", "para": i, "text": t, "pieces": [{"text": t}]} for i, t in enumerate(texts)]


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


class T1Claims(unittest.TestCase):
    def test_rule_reading_and_judgement(self):
        d = _Doc(["A동은 1,520건으로 B동(1,208건)보다 312건 많음",
                  "전체 480건 중 야간 접수가 96건(20.0%)으로 집계됨",
                  "수질 120건, 대기 80건, 토양 40건을 합하여 총 250건임",
                  "A반(360건)은 B반(120건)의 3.0배 수준임",
                  "감사 일시는 2026. 11. 25.(수) 10:00임"])
        r = AiPart(settings_path=NOFILE).read_doc(d)
        got = {c["type"]: c["status"] for c in r["claims"]}
        self.assertEqual(got, {"diff": "ok_calc", "share": "ok_calc", "sum": "calc", "times": "ok_calc"})
        self.assertEqual(r["stat"]["ai_calls"], 0)

    def test_ai_reading_is_yellow_and_hallucination_rejected(self):
        d = _Doc(["지원은 1,520건을 기록해 1,208건에 그친 본청을 320건 앞섰음"])
        r = AiPart(settings_path=NOFILE, provider=Mock()).read_doc(d, use_ai=True)
        self.assertEqual([(c["by"], c["status"]) for c in r["claims"]], [("AI", "claim")])   # AI 읽기 틀림 = 노랑
        bad = {"type": "diff", "a": "1,520", "b": "1,208", "c": "9,876", "dir": "증가"}
        ck, why = C.validate(bad, d.blocks[0]["text"])
        self.assertIsNone(ck)
        self.assertIn("문장에 없는 숫자", why)
        r2 = AiPart(settings_path=NOFILE, provider=Mock(noise=1.0, seed=2)).read_doc(d, use_ai=True)
        self.assertEqual(r2["stat"]["ai"], 0)                     # 이상한 답은 판정에 쓰지 않음
        self.assertEqual(r2["stat"]["rejected"], 1)

    def test_parse_json_and_settings(self):
        self.assertEqual(parse_json('설명\n```json\n{"checks": []}\n```'), {"checks": []})
        self.assertIsNone(parse_json("JSON 아님"))
        self.assertIsNone(make({"provider": "none"}))
        with self.assertRaises(AiError):
            make({"provider": "ollama", "url": "http://10.0.0.5:11434", "model": "x"})   # 다른 컴퓨터 차단
        with self.assertRaises(AiError):
            make({"provider": "ollama", "model": "exaone"}).chat([{"role": "user", "content": "x"}])  # 서버 없음
        p = os.path.join(TMP, "AI설정.json")
        a = AiPart(settings_path=p)
        a.save_settings({"provider": "mock", "model": "모의AI"})
        self.assertEqual(json.load(open(p, encoding="utf-8"))["provider"], "mock")
        self.assertTrue(AiPart(settings_path=p).test()["ok"])

    def test_summary_numbers_checked(self):
        f = S.facts({"total": 120, "ok": 100, "mismatch": 3, "unknown": 2})
        self.assertEqual(S.check_numbers(S.rule_text(f), f), [])
        bad = S.check_numbers("○ 숫자 120개 중 불일치 7개", f)
        self.assertEqual([b["raw"] for b in bad], ["7"])


class T2Diff(unittest.TestCase):
    def test_inserted_row_and_change(self):
        a = os.path.join(TMP, "v1.xlsx")
        b = os.path.join(TMP, "v2.xlsx")
        write_xlsx(a, [{"name": "자료", "rows": [["구분", "건수"], ["가", 10], ["나", 20], ["다", 30]]}])
        write_xlsx(b, [{"name": "자료", "rows": [["구분", "건수"], ["가", 10], ["새행", 5], ["나", 21], ["다", 30]]}])
        d = D.diff(read_book(a), read_book(b))
        self.assertEqual([(c["ref_old"], c["ref"], c["old"], c["new"]) for c in d["changed"]], [("자료!B3", "자료!B4", 20.0, 21.0)])
        self.assertEqual(d["added_rows"], [{"sheet": "자료", "row": 3}])
        self.assertEqual(_stem("대기측정망_월보(수정).xlsx"), _stem("대기측정망_월보.xlsx"))


class T3Workspace(unittest.TestCase):
    def test_resubmit_flow(self):
        s = Scenario(os.path.join(TMP, "mock"), seed=4242, gongmun=False, guides=False, form=False, resubmit=True).run()
        folder = s["folder"]
        key = json.load(open(os.path.join(folder, "정답표.json"), encoding="utf-8"))
        base = os.path.dirname(os.path.dirname(os.path.join(folder, key["대상"])))
        ws = Workspace(os.path.join(TMP, "ws"), "시험자")
        try:
            ws.set_target(os.path.join(folder, key["대상"]))
            ws.add_sources([os.path.join(base, "01_원본자료"), os.path.join(base, "02_팀제출")])
            self.assertTrue(os.listdir(os.path.join(ws.folder, config.DIR_ARCHIVE)))        # 원본 보관
            ws.verify()
            rs = next(x for x in key["재제출"] if not x["같은이름"])
            r = ws.resubmit_check(os.path.join(folder, rs["수정본"]))
            self.assertEqual(ws.sources.info(r["sid"])["name"], os.path.basename(rs["원본"]))   # 이름이 달라도 짝 찾음
            self.assertEqual(r["diff"]["numeric_changed"], len(rs["변경"]))
            self.assertEqual(len(r["impact"]), len(rs["영향"]))
            ws.resubmit_apply(r["sid"], os.path.join(folder, rs["수정본"]))
            v = ws.verify()
            keys = {x["key"] for x in r["impact"]}
            self.assertTrue(all(v["items"][k]["status"] in ("mismatch", "conflict") for k in keys))
            # 같은 이름으로 덮어쓴 경우: 원본 변경 확인이 이전 판과 비교한다
            rs2 = next(x for x in key["재제출"] if x["같은이름"])
            shutil.copy2(os.path.join(folder, rs2["수정본"]), os.path.join(folder, rs2["원본"]))
            chk = ws.check_sources()
            ch = next(c for c in chk["changed"] if c["name"] == os.path.basename(rs2["원본"]))
            self.assertEqual(ch["diff"]["numeric_changed"], len(rs2["변경"]))
            self.assertEqual(len(ch["impact"]), len(rs2["영향"]))
        finally:
            ws.db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
