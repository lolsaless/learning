"""(v2.0) 병합·고치기·계보·프로젝트 시험.   실행: python -m unittest discover -s tests -v"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hwpxdiff.compare import compare_documents  # noqa: E402
from hwpxdiff.hwpx import load_document  # noqa: E402
from hwpxdiff.lineage import analyze  # noqa: E402
from hwpxdiff.merge.edit import EditError, edit_document  # noqa: E402
from hwpxdiff.merge.engine import apply_merge, plan_merge  # noqa: E402
from hwpxdiff.merge.resources import HeaderMerger, canonical  # noqa: E402
from hwpxdiff.project import Project  # noqa: E402
from hwpxdiff.service import Workspace  # noqa: E402
from sample_builder import make_hwpx  # noqa: E402

PARAS = ["□ 조사 개요", "값은 5명입니다", "세 번째 문단", "끝 문단"]
TABLE = [["구분", "값"], ["가", "1.0"]]


def doc(paras=PARAS, name="base", t="2026-01-01T00:00:00Z", **kw):
    kw.setdefault("table", TABLE)
    return load_document(make_hwpx(paras, modified=t, **kw), name=name)


def texts(d):
    return [b.text for b in d.blocks]


def section(data):
    return zipfile.ZipFile(io.BytesIO(data)).read("Contents/section0.xml")


def header(data):
    return zipfile.ZipFile(io.BytesIO(data)).read("Contents/header.xml")


class MergeTest(unittest.TestCase):
    def setUp(self):
        self.base = doc()
        p1 = list(PARAS)
        p1[1] = [("값은 ", 0), ("4", 3), ("명입니다", 0)]                 # 새 글자모양(3번, 파랑)으로 고침
        self.v1 = doc(p1, "v1", "2026-01-02T00:00:00Z", extra_charprs=[(3, "#0000FF")])
        p2 = list(PARAS) + [[("새로 넣은 문단", 3)]]                         # v2 의 3번(초록) 글자모양 사용
        t2 = [["구분", "값"], ["가", "2.5"]]
        self.v2 = doc(p2, "v2", "2026-01-03T00:00:00Z", table=t2, extra_charprs=[(3, "#00FF00")])

    def run_merge(self, versions, choices=None):
        plan = plan_merge(self.base, versions, compare_documents)
        docs = {d.id: d for d in [self.base] + versions}
        data, rep = apply_merge(self.base, docs, plan, choices or {})
        return plan, data, rep, load_document(data, name="m")

    def test_two_branches_no_conflict(self):
        plan, data, rep, m = self.run_merge([self.v1, self.v2])
        self.assertEqual(plan["counts"]["conflicts"], 0)
        self.assertEqual(len(rep["applied"]), 3)
        self.assertIn("값은 4명입니다", texts(m))
        self.assertIn("새로 넣은 문단", texts(m))
        self.assertIn("2.5", texts(m))
        # 두 버전이 같은 3번에 서로 다른 글자모양을 붙였음 → 받는 쪽에서 3, 4 번으로 따로 들어가야 함
        cps = header(data).count(b"<hh:charPr ")
        self.assertEqual(cps, 3 + 2)
        blue = next(b for b in m.blocks if b.text == "값은 4명입니다")
        colors = {m.styles[r.style]["color"] for r in blue.runs if r.text.strip()}
        self.assertIn("#0000FF", colors)
        green = next(b for b in m.blocks if b.text == "새로 넣은 문단")
        self.assertEqual(m.styles[green.runs[0].style]["color"], "#00FF00")
        # 바뀌지 않은 문단은 원문 바이트 그대로
        self.assertIn(b"<hp:t>\xec\x84\xb8 \xeb\xb2\x88\xec\xa7\xb8 \xeb\xac\xb8\xeb\x8b\xa8</hp:t>", section(data))
        # 각 버전과 비교하면 '다른 버전의 변경'만 남아야 함
        self.assertEqual(compare_documents(self.v1, m)["counts"]["total"], 2)

    def test_conflict_and_choice(self):
        p3 = list(PARAS)
        p3[1] = "값은 9명입니다"
        v3 = doc(p3, "v3", "2026-01-04T00:00:00Z")
        plan, data, rep, m = self.run_merge([self.v1, v3])
        item = next(i for i in plan["items"] if i["conflict"])
        self.assertEqual(item["default"], "base")                       # 충돌은 기본 '원본 유지'
        self.assertIn("값은 5명입니다", texts(m))
        pick = next(o["op_id"] for o in item["options"] if o["vname"] == "v3")
        _, _, _, m2 = self.run_merge([self.v1, v3], {item["key"]: pick})
        self.assertIn("값은 9명입니다", texts(m2))

    def test_same_change_applied_once(self):
        p = list(PARAS)
        p[2] = "세 번째 문단 고침"
        a, b = doc(p, "a", "2026-01-02T00:00:00Z"), doc(p, "b", "2026-01-03T00:00:00Z")
        plan, data, rep, m = self.run_merge([a, b])
        self.assertEqual(plan["counts"]["same"], 1)
        self.assertEqual(texts(m).count("세 번째 문단 고침"), 1)

    def test_delete_paragraph(self):
        p = [x for x in PARAS if x != "세 번째 문단"]
        v = doc(p, "del", "2026-01-02T00:00:00Z")
        _, _, rep, m = self.run_merge([v])
        self.assertNotIn("세 번째 문단", texts(m))
        self.assertEqual(len(rep["applied"]), 1)

    def test_table_paragraph_caption_and_cell(self):
        """표를 품은 문단: 자기 글자(caption)만 바꾸고 표는 그대로 → 표 안 칸 변경과 함께 적용돼야 함."""
        base = doc(caption="표 1. 결과")
        v = doc(caption="표 1. 측정 결과", table=[["구분", "값"], ["가", "3.0"]], name="cap", t="2026-01-02T00:00:00Z")
        self.base = base
        plan, data, rep, m = self.run_merge([v])
        self.assertEqual(plan["counts"]["unsupported"], 0)
        self.assertIn("표 1. 측정 결과", texts(m))
        self.assertIn("3.0", texts(m))
        self.assertEqual(m.stats["tables"], 1)

    def test_unselected_keeps_base(self):
        plan = plan_merge(self.base, [self.v1, self.v2], compare_documents)
        choices = {it["key"]: "base" for it in plan["items"]}
        data, rep = apply_merge(self.base, {d.id: d for d in (self.base, self.v1, self.v2)}, plan, choices)
        self.assertEqual(rep["applied"], [])
        self.assertEqual(section(data), section(self.base.raw))


class HeaderTest(unittest.TestCase):
    def test_default_attr_ignored(self):
        """한글 13 의 textDir="LTR" 처럼 기본값 속성 차이는 같은 모양으로 본다."""
        a = b'<hh:paraPr id="0" condense="0" textDir="LTR"><hh:align horizontal="JUSTIFY"/></hh:paraPr>'
        b = b'<hh:paraPr id="7" condense="0"><hh:align horizontal="JUSTIFY"/></hh:paraPr>'
        self.assertEqual(canonical(a), canonical(b))

    def test_font_appended(self):
        base = doc()
        v = doc(name="f", extra_charprs=[(3, "#FF0000")], fonts=("함초롬바탕", "맑은 고딕"))
        hm = HeaderMerger(header(base.raw))
        src = hm.source(header(v.raw))
        new = src.map("charPr", "3")
        self.assertEqual(new, "3")
        out = hm.build()
        self.assertIn('face="맑은 고딕"'.encode(), out)
        self.assertIn(b'fontCnt="2"', out)
        self.assertIn(b'itemCnt="4"', out)


class EditTest(unittest.TestCase):
    def test_edit_keeps_style_and_marks(self):
        base = doc([[("앞 ", 2), ("값 5", 0)], "그대로"])
        data, rep = edit_document(base, {0: "앞 값 7 추가"}, mark_color="#FF0000")
        m = load_document(data, name="e")
        blk = m.blocks[0]
        self.assertEqual(blk.text, "앞 값 7 추가")
        styles = [(r.text, m.styles[r.style]) for r in blk.runs]
        self.assertTrue(styles[0][1]["bold"])                          # 바뀌지 않은 글자는 원래 서식(굵게)
        red = "".join(t for t, s in styles if s["color"] == "#FF0000")
        self.assertIn("7", red)
        self.assertIn("추가", red)
        self.assertEqual(rep["check_failed"], [])
        self.assertIn("<hp:t>그대로</hp:t>".encode(), section(data))      # 다른 문단은 원문 그대로

    def test_cell_newline_splits_paragraph(self):
        base = doc()
        cell = next(b for b in base.blocks if b.text == "1.0")
        data, _ = edit_document(base, {cell.index: "1.0\n(추정)"})
        m = load_document(data, name="e")
        self.assertIn("1.0\n(추정)", texts(m))
        self.assertEqual(m.stats["cells"], base.stats["cells"])

    def test_refuses_table_paragraph(self):
        base = doc(caption="표 제목")
        blk = next(b for b in base.blocks if b.text == "표 제목")
        with self.assertRaises(EditError):
            edit_document(base, {blk.index: "새 제목"})


class LineageTest(unittest.TestCase):
    def test_branches_and_chain(self):
        o = doc(name="원본")
        a = doc(["□ 조사 개요", "값은 4명입니다", "세 번째 문단", "끝 문단"], "a", "2026-01-02T00:00:00Z",
                extra_charprs=[(3, "#0000FF")])
        b = doc(PARAS + ["추가"], "b", "2026-01-03T00:00:00Z", extra_charprs=[(3, "#00FF00")])
        c = doc(["□ 조사 개요", "값은 4명입니다", "세 번째 문단 수정", "끝 문단"], "c", "2026-01-04T00:00:00Z",
                extra_charprs=[(3, "#0000FF"), (4, "#123456")])
        r = analyze([c, b, a, o], compare_documents)
        names = {d.id: d.name for d in (o, a, b, c)}
        self.assertEqual(names[r["original"]], "원본")
        parent = {n["id"]: [names[p] for p in n["parents"]] for n in r["nodes"]}
        self.assertEqual(parent[a.id], ["원본"])
        self.assertEqual(parent[b.id], ["원본"])                          # a 의 글자모양을 안 가짐 → 형제
        self.assertEqual(parent[c.id], ["a"])                             # a 의 목록을 이어받음 → a 의 자식
        self.assertFalse(r["linear"])


class ProjectTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_final_replaced_and_archived(self):
        p = Project.create(os.path.join(self.dir, "프로젝트"), "시험")
        d1, d2 = doc(name="최종1.hwpx"), doc(["다른"], name="최종2.hwpx")
        p.add(d1.id, d1.name, d1.raw, d1.sha1, "final")
        p.add(d2.id, d2.name, d2.raw, d2.sha1, "final", parents=[d1.id], origin="edit")
        root = p.folder
        self.assertEqual(os.listdir(os.path.join(root, "3_최종본")), ["최종2.hwpx"])
        self.assertEqual(len(os.listdir(os.path.join(root, "4_보관"))), 1)
        q = Project.open(root)
        roles = {e["name"]: e["role"] for e in q.documents}
        self.assertEqual(roles, {"최종1.hwpx": "archived", "최종2.hwpx": "final"})
        self.assertEqual(q.doc(d2.id)["parents"], [d1.id])
        with open(os.path.join(root, "project.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["schema"], "hwpx-project/1")

    def test_workspace_flow(self):
        ws = Workspace()
        o = make_hwpx(PARAS, TABLE, "2026-01-01T00:00:00Z")
        a = make_hwpx(["□ 조사 개요", "값은 4명입니다", "세 번째 문단", "끝 문단"], TABLE, "2026-01-02T00:00:00Z")
        b = make_hwpx(PARAS + ["추가"], TABLE, "2026-01-03T00:00:00Z")
        ids = [ws.submit_bytes(n, d) for n, d in (("o.hwpx", o), ("a.hwpx", a), ("b.hwpx", b))]
        ws.wait()
        self.assertEqual(ws.submit_bytes("o2.hwpx", o), ids[0])        # 같은 파일은 다시 안 들어감
        ws.wait()
        self.assertEqual(len(ws.ready_docs()), 3)
        lin = ws.lineage()
        self.assertEqual(lin["original"], ids[0])
        ws.project_create(os.path.join(self.dir, "p"), "흐름")
        r = ws.merge_save(ids[0], ids[1:], {}, "합친것")
        self.assertTrue(r["path"].endswith(os.path.join("3_최종본", "합친것.hwpx")))
        blk = next(x for x in ws.document(r["id"]).blocks if x.text == "추가")
        e = ws.edit_save(r["id"], {str(blk.index): "추가 고침"})
        self.assertIn("3_최종본", e["path"])                              # 최종본을 고치면 새 최종본
        self.assertEqual(ws.roles[r["id"]], "archived")
        ws2 = Workspace()
        ws2.project_open(os.path.join(self.dir, "p"))
        ws2.wait()
        self.assertEqual(len(ws2.ready_docs()), 5)
        self.assertEqual(ws2.roles[e["id"]], "final")


if __name__ == "__main__":
    unittest.main()
