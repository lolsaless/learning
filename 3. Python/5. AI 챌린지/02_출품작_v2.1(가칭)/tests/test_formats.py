# -*- coding: utf-8 -*-
"""파일 형식 시험: 형식이 달라도 같은 숫자 표를 읽는가(형식 등록부 → 시트/문서 정규화).

고정 자료(tests/fixtures/formats/): 가상 값으로 만든 xlsx 를 LibreOffice 로 xls·ods 로, 이 프로그램이 만든 docx 를
LibreOffice 로 odt·pdf·docx 로 바꾼 것(다른 프로그램이 만든 파일도 읽는지 확인). hwp 는 시험용 작성기(hwp_fixture.py)로 만든다.
실행: python tests/test_formats.py
"""
import os
import sys
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from app.formats import registry                                   # noqa: E402
from app.formats.hwpx import table_grids                           # noqa: E402
from app.formats.pdf_write import PdfWriter                        # noqa: E402
from app.formats.pdf import read_pdf                               # noqa: E402
from app.formats.hwp import read_hwp, HwpError                     # noqa: E402
from app.formats.text import text_blocks                           # noqa: E402
from app.common.errors import WorkError                            # noqa: E402
import hwp_fixture as HF                                           # noqa: E402

FX = os.path.join(ROOT, "tests", "fixtures", "formats")
TMP = tempfile.mkdtemp(prefix="fmt_test_")
WANT = {1520.0, 1608.0, 980.0, 1022.0, 311.0, 298.0, 2811.0, 2928.0}


def numbers_of(path):
    kind, obj = registry.read_source(path)
    vals = set()
    if kind == "sheet":
        for sh in obj.sheets:
            vals |= {c.v for c in sh.cells.values() if c.kind == "n"}
    else:
        for g in table_grids(obj):
            vals |= {v for v, d in g["cells"].values()}
    return kind, vals


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


class T1SameTableAnyFormat(unittest.TestCase):
    def test_fixtures(self):
        for name, kind in [("가상_실적.xlsx", "sheet"), ("가상_실적.xls", "sheet"), ("가상_실적.ods", "sheet"),
                           ("가상_실적_원본.docx", "doc"), ("가상_실적_LO.docx", "doc"), ("가상_실적_원본.odt", "doc"),
                           ("가상_실적_원본.pdf", "doc")]:
            with self.subTest(name=name):
                k, vals = numbers_of(os.path.join(FX, name))
                self.assertEqual(k, kind)
                self.assertTrue(WANT <= vals, f"{name}: 빠진 숫자 {sorted(WANT - vals)}")

    def test_text_formats(self):
        csv_p = os.path.join(TMP, "실적.csv")
        with open(csv_p, "w", encoding="cp949", newline="") as f:      # 한국어 윈도우 기본 인코딩
            f.write("구분,2025년,2026년\n수질,\"1,520\",1608\n대기,980,1022\n토양,311,298\n합계,2811,2928\n")
        md_p = os.path.join(TMP, "실적.md")
        with open(md_p, "w", encoding="utf-8") as f:
            f.write("# 실적\n\n| 구분 | 2025년 | 2026년 |\n|---|---|---|\n| 수질 | 1,520 | 1,608 |\n| 대기 | 980 | 1,022 |\n"
                    "| 토양 | 311 | 298 |\n| 합계 | 2,811 | 2,928 |\n")
        html_p = os.path.join(TMP, "실적.html")
        with open(html_p, "w", encoding="utf-8") as f:
            f.write("<html><body><p>실적</p><table><tr><th rowspan=2>구분</th><th colspan=2>연도</th></tr>"
                    "<tr><th>2025년</th><th>2026년</th></tr><tr><td>수질</td><td>1,520</td><td>1,608</td></tr>"
                    "<tr><td>대기</td><td>980</td><td>1,022</td></tr><tr><td>토양</td><td>311</td><td>298</td></tr>"
                    "<tr><td>합계</td><td>2,811</td><td>2,928</td></tr></table></body></html>")
        for p in (csv_p, md_p, html_p):
            with self.subTest(p=os.path.basename(p)):
                k, vals = numbers_of(p)
                self.assertTrue(WANT <= vals, f"{p}: {sorted(WANT - vals)}")

    def test_hwp(self):
        body = HF.para("□ 가상 실적") + HF.table([["구분", "2025년", "2026년"], ["수질", "1,520", "1,608"],
                                                 ["대기", "980", "1,022"], ["토양", "311", "298"], ["합계", "2,811", "2,928"]])
        for comp in (True, False):
            p = HF.write_hwp(os.path.join(TMP, f"실적_{comp}.hwp"), body, compressed=comp)
            k, vals = numbers_of(p)
            self.assertEqual(k, "doc")
            self.assertTrue(WANT <= vals)

    def test_hwp_merged_and_errors(self):
        body = HF.table([["구분", "연도", None], ["", "2025년", "2026년"], ["수질", "1,520", "1,608"]],
                        merges={(0, 1): (1, 2), (0, 0): (2, 1)})
        d = read_hwp(HF.write_hwp(os.path.join(TMP, "merge.hwp"), body))
        t = [b for b in d["blocks"] if b["type"] == "table"][0]
        head = next(c for c in t["cells"] if c["r"] == 0 and c["c"] == 1)
        self.assertEqual((head["cs"], head["text"]), (2, "연도"))
        with self.assertRaises(HwpError):
            read_hwp(HF.write_hwp(os.path.join(TMP, "pw.hwp"), body, password=True))
        with self.assertRaises(WorkError):                          # 등록부는 사용자용 오류로 바꾼다
            registry.read_source(os.path.join(TMP, "pw.hwp"))


class T2Pdf(unittest.TestCase):
    def test_table_across_pages(self):
        w = PdfWriter("긴 표")
        for _ in range(30):
            w.para("가상 문단입니다. " * 6)
        rows = [["구분", "건수", "금액(천원)"]] + [[f"항목{i:02d}", f"{i * 7:,}", f"{i * 1234:,}"] for i in range(1, 41)]
        w.table(rows)
        p = w.save(os.path.join(TMP, "long.pdf"))
        d = read_pdf(p)
        self.assertGreaterEqual(d["pages"], 2)
        tabs = [b for b in d["blocks"] if b["type"] == "table"]
        self.assertEqual(len(tabs), 1, "쪽이 바뀌어도 표 하나로 이어져야 함")
        self.assertEqual(tabs[0]["nrow"], 41)

    def test_ruled_columns(self):
        """테두리선이 있는 표: 긴 숫자가 붙어 있어도 칸을 나눈다."""
        w = PdfWriter("붙은 칸")
        w.table([["사업", "예산", "지출", "잔액"], ["가상사업", "12,345,678,900", "11,111,111,111", "1,234,567,789"]],
                widths=[2, 2, 2, 2], size=11)
        d = read_pdf(w.save(os.path.join(TMP, "ruled.pdf")))
        t = [b for b in d["blocks"] if b["type"] == "table"][0]
        self.assertEqual(t["ncol"], 4)

    def test_wrapped_sentence_joined(self):
        w = PdfWriter("줄바꿈")
        w.para("예산액 기준으로 가상 연구원 시설 유지관리는 2,361,376천원으로 가상 감염병 검사 지원(1,998,464천원)보다 362,912천원 많음")
        d = read_pdf(w.save(os.path.join(TMP, "wrap.pdf")))
        ps = [b["text"] for b in d["blocks"] if b["type"] == "p"]
        self.assertTrue(any("보다" in t and "362,912" in t for t in ps), ps)


class T3Registry(unittest.TestCase):
    def test_registry(self):
        exts = registry.extensions()
        for e in (".hwpx", ".hwp", ".xlsx", ".xls", ".ods", ".csv", ".docx", ".odt", ".pdf", ".txt", ".md", ".html"):
            self.assertIn(e, exts)
        self.assertFalse(registry.supported("a.pptx"))
        self.assertIn(".pptx", registry.HINTS)

    def test_text_blocks(self):
        b = text_blocks("# 제목\n- 항목\n가\t나\n1\t2\n")
        self.assertEqual(b[0]["text"], "□ 제목")
        self.assertEqual(b[1]["text"], "○ 항목")
        self.assertEqual(b[2]["type"], "table")

    def test_read_only_target(self):
        doc = registry.open_target(os.path.join(FX, "가상_실적_원본.pdf"))
        self.assertTrue(doc.read_only)
        self.assertTrue(any(it.raw == "2,928" for it in doc.items))


if __name__ == "__main__":
    unittest.main(verbosity=2)
