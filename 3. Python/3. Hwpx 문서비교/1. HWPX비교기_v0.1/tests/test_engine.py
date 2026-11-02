"""엔진 시험 (해석·비교·이력).   실행: python -m unittest discover -s tests -v"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hwpxdiff.compare import CompareOptions, build_history, compare_documents, order_documents  # noqa: E402
from hwpxdiff.hwpx import HwpxError, load_document  # noqa: E402
from sample_builder import make_hwpx  # noqa: E402

BASE = ["□ 조사 개요", " ○ (조사 목적) 경기북부 주요 하천의 생태독성 확인", "   - 효촌천: 0.8~3.2 TU", "삭제될 문단"]
TABLE = [["연번", "요구의원"], ["1", "임유진 등 5명"]]


def doc(paras, table=TABLE, modified="2026-01-01T00:00:00Z", name="a.hwpx"):
    return load_document(make_hwpx(paras, table, modified), name=name)


class ParserTest(unittest.TestCase):
    def test_blocks_and_locations(self):
        d = doc(BASE)
        self.assertEqual(d.stats["paragraphs"], 4)
        self.assertEqual(d.stats["tables"], 1)
        cell = [b for b in d.blocks if b.kind == "cell"][-1]
        self.assertEqual((cell.table, cell.row, cell.col), (1, 2, 2))
        self.assertEqual(cell.location, "표 1 · 2행 2열")
        self.assertEqual(d.blocks[1].context, "□ 조사 개요")          # 제목 문단 인식
        self.assertEqual(d.meta["ModifiedDate"], "2026-01-01T00:00:00Z")

    def test_styles_resolved(self):
        d = doc([[("검정", 0), ("빨강", 1)]], table=None)
        props = [d.styles[r.style] for r in d.blocks[0].runs]
        self.assertEqual([p["color"] for p in props], ["#000000", "#FF0000"])

    def test_not_hwpx(self):
        with self.assertRaises(HwpxError):
            load_document(b"not a zip", name="x.hwpx")


class CompareTest(unittest.TestCase):
    def setUp(self):
        self.a = doc(BASE)
        new = list(BASE)
        new[1] = [(" ○ (조사 목적) 경기", 0), ("남", 1), ("부 주요 하천의 생태독성 확인", 0)]
        new[2] = "   - 효촌천: 0.8~2.2 TU"
        new[3:] = ["새로 넣은 문단"]
        table = [["연번", "요구의원"], ["1", "임유진 등 4명"]]
        self.b = doc(new, table, "2026-01-02T00:00:00Z", "b.hwpx")
        self.r = compare_documents(self.a, self.b)

    def test_counts(self):
        c = self.r["counts"]
        self.assertEqual((c["modified"], c["added"], c["deleted"]), (3, 1, 1))

    def test_inline_and_tags(self):
        by_loc = {c["location"]: c for c in self.r["changes"]}
        self.assertEqual(by_loc["본문 2번째 문단"]["summary"], "‘북’ → ‘남’")
        self.assertIn("서식", by_loc["본문 2번째 문단"]["tags"])        # 빨간 글자로 바꿈
        self.assertEqual(by_loc["본문 3번째 문단"]["summary"], "‘3.2’ → ‘2.2’")
        self.assertIn("숫자", by_loc["본문 3번째 문단"]["tags"])
        self.assertIn("표", by_loc["표 1 · 2행 2열"]["tags"])

    def test_format_only(self):
        a = doc(["같은 글자 문단"], table=None)
        b = doc([[("같은 ", 0), ("글자", 2), (" 문단", 0)]], table=None)
        r = compare_documents(a, b)
        self.assertEqual(r["counts"]["format"], 1)
        self.assertIn("굵게", r["changes"][0]["format"][0]["details"][0])
        r2 = compare_documents(a, b, CompareOptions(include_format=False))
        self.assertEqual(r2["counts"]["total"], 0)

    def test_whitespace_option(self):
        a, b = doc(["가나다 라마"], table=None), doc(["가나다   라마"], table=None)
        self.assertEqual(compare_documents(a, b)["counts"]["total"], 0)
        self.assertEqual(compare_documents(a, b, CompareOptions(ignore_whitespace=False))["counts"]["modified"], 1)

    def test_identical(self):
        r = compare_documents(self.a, doc(BASE))
        self.assertEqual(r["counts"]["total"], 0)
        self.assertTrue(r["identical_file"])


class HistoryTest(unittest.TestCase):
    def test_revert_detected_and_ordered(self):
        v1 = doc(["값은 5명", "그대로"], None, "2026-01-01T00:00:00Z", "v1.hwpx")
        v2 = doc(["값은 4명", "그대로"], None, "2026-01-02T00:00:00Z", "v2.hwpx")
        v3 = doc(["값은 5명", "그대로", "추가 문단"], None, "2026-01-03T00:00:00Z", "v3.hwpx")
        ordered = order_documents([v3, v1, v2])                  # 넣은 순서와 무관하게 수정일 순
        self.assertEqual([d.name for d in ordered], ["v1.hwpx", "v2.hwpx", "v3.hwpx"])
        h = build_history(ordered, compare_documents)
        kinds = {c["kind"] for c in h["chains"]}
        self.assertEqual(kinds, {"reverted", "added"})
        rev = next(c for c in h["chains"] if c["kind"] == "reverted")
        self.assertEqual(rev["texts"], ["값은 5명", "값은 4명", "값은 5명"])
        self.assertEqual(len(h["steps"]), 2)


if __name__ == "__main__":
    unittest.main()
