"""(v1.1) 문서 모양 보기 시험 — 배치 트리, 문단·표 그리기, 바뀐 곳 표시."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hwpxdiff.compare import CompareOptions, compare_documents  # noqa: E402
from hwpxdiff.hwpx import load_document  # noqa: E402
from hwpxdiff.render import render_plain, render_view  # noqa: E402
from sample_builder import make_hwpx  # noqa: E402


def doc(paras, table=None, name="a.hwpx"):
    return load_document(make_hwpx(paras, table), name=name)


def text_of(html):
    return re.sub(r"<[^>]+>", "", html)


class LayoutTest(unittest.TestCase):
    def test_layout_tree(self):
        d = doc(["첫 문단", "", "셋째"], [["가", "나"], ["다", ""]])
        tops = [n for n in d.layout if n["t"] == "p"]
        self.assertEqual([n["b"] for n in tops[:3]], [0, None, 1])     # 빈 문단은 블록 없음
        tbl = tops[3]["items"][0]
        self.assertEqual(tbl["t"], "tbl")
        self.assertEqual(len(tbl["rows"]), 2)
        self.assertIsNone(tbl["rows"][1][1]["b"])                        # 빈 셀

    def test_plain_render(self):
        d = doc([[("굵은", 2), (" 빨강", 1)]], [["가", "나"]])
        html = render_plain(d)["html"]
        self.assertIn('class="dv-sheet"', html)
        self.assertIn("font-weight:700", html)
        self.assertIn("color:#FF0000", html)
        self.assertIn("<table", html)
        self.assertEqual(html.count("<td"), 2)


class MarkTest(unittest.TestCase):
    def setUp(self):
        self.a = doc(["머리 문단", "값은 5명입니다", "지울 문단", "끝 문단"], name="a")
        self.b = doc(["머리 문단", [("값은 ", 0), ("4", 1), ("명입니다", 0)], "끝 문단", "새 문단"], name="b")
        self.res = compare_documents(self.a, self.b)

    def test_merged(self):
        v = render_view(self.a, self.b, self.res, "merged")
        html = v["html"]
        self.assertIn('class="dv-ghost"', html)                          # 지운 문단 끼워 넣기
        self.assertIn("지울 문단", text_of(html))
        self.assertLess(html.index("지울 문단"), html.index("끝 문단"))   # 제자리(다음 문단 앞)
        self.assertRegex(html, r'class="dv-gdel"[^>]*>5</del>')          # 지운 글자
        self.assertRegex(html, r'class="dv-ins"[^>]*>4</span>')          # 넣은 글자
        self.assertIn("dv-added", html)                                  # 새 문단
        self.assertEqual(sorted(v["order"]), [c["id"] for c in self.res["changes"]])

    def test_pair(self):
        v = render_view(self.a, self.b, self.res, "pair")
        self.assertRegex(v["html_a"], r'class="dv-del"[^>]*>5</span>')
        self.assertIn("dv-deleted", v["html_a"])
        self.assertNotIn("dv-gdel", v["html_b"])                         # 나란히 보기 B 쪽엔 지운 글자 없음
        self.assertRegex(v["html_b"], r'class="dv-ins"[^>]*>4</span>')

    def test_whitespace_alignment_on_a_side(self):
        """공백 무시 비교에서도 A 쪽 글자 위치가 어긋나지 않아야 한다."""
        a = doc(["가나   다라 3.2 끝"])
        b = doc(["가나 다라 2.2 끝"])
        res = compare_documents(a, b, CompareOptions(ignore_whitespace=True))
        v = render_view(a, b, res, "pair")
        self.assertEqual(text_of(v["html_a"]).replace(" ", ""), "가나   다라 3.2 끝")
        self.assertRegex(v["html_a"], r'class="dv-del"[^>]*>3.2</span>')

    def test_format_mark(self):
        a = doc(["같은 글자"])
        b = doc([[("같은 ", 0), ("글자", 2)]])
        res = compare_documents(a, b)
        html = render_view(a, b, res, "merged")["html"]
        self.assertIn("dv-format", html)
        self.assertIn("dv-fmtc", html)


if __name__ == "__main__":
    unittest.main()
