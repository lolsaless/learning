# -*- coding: utf-8 -*-
"""[재제출 비교 파트] 팀이 원본을 고쳐 다시 보냈을 때: 무엇이 바뀌었고, 문서의 어느 칸을 고쳐야 하는지.

  ① 보관: 원본을 등록하거나 내용이 바뀔 때마다 그 판을 작업 폴더 '원본보관/'에 복사(원본 파일은 건드리지 않음)
  ② 비교: 이전 판과 새 판을 칸 단위로 비교(형식이 달라도 됨: xlsx → ods·csv·pdf …)
  ③ 영향: 바뀐 칸을 출처로 쓰던 문서 칸 + 새 값으로 바꾸면 문서에 적힐 값(배율·자릿수 반영)
  ④ 짝 찾기: 이름이 바뀐 새 파일('…(수정).xlsx')이 어느 등록 원본의 새 판인지 이름·내용으로 추정

입구: archive(sid, path, sha), archived(sid, sha), compare_paths(이전, 이후), affected(비교결과, 출처색인),
      match(새 파일, 등록 원본 목록)
"""
import os
import re
import shutil

from app import config
from app.common import numbers as N
from app.common.errors import WorkError
from app.formats import registry
from app.formats.hwpx import table_grids
from app.parts.compare import diff as D


def read_book(path):
    kind, obj = registry.read_source(path)
    if kind == "sheet":
        return {"kind": "sheet", "wb": obj}
    return {"kind": "doc", "grids": table_grids(obj)}


def _stem(name):
    s = os.path.splitext(os.path.basename(name))[0]
    s = re.sub(r"[\(\[（](수정|최종|재제출|보완|변경|정정|v?\d+)[\)\]）]", "", s, flags=re.I)
    s = re.sub(r"[_\-\s]*(수정본?|최종|재제출|보완|v\d+|\d{6,8})$", "", s, flags=re.I)
    return re.sub(r"[\s_\-]+", "", s)


class ComparePart:
    def __init__(self, ctx):
        self.ctx = ctx
        self.dir = ctx.path(config.DIR_ARCHIVE)
        os.makedirs(self.dir, exist_ok=True)

    # ── ① 보관 ────────────────────────────────────────
    def _arch_path(self, sid, sha, ext):
        return os.path.join(self.dir, f"{sid}_{(sha or '')[:12]}{ext}")

    def archive(self, sid, path, sha):
        if not path or not os.path.exists(path):
            return None
        dst = self._arch_path(sid, sha, registry.ext_of(path))
        if not os.path.exists(dst):
            shutil.copy2(path, dst)
        return dst

    def archived(self, sid, sha):
        pre = f"{sid}_{(sha or '')[:12]}"
        for f in os.listdir(self.dir):
            if f.startswith(pre):
                return os.path.join(self.dir, f)
        return None

    # ── ② 비교 ────────────────────────────────────────
    def compare_paths(self, old_path, new_path):
        try:
            a, b = read_book(old_path), read_book(new_path)
        except Exception as e:
            raise WorkError(f"비교할 파일을 읽지 못했습니다: {e}")
        d = D.diff(a, b)
        d["similarity"] = D.similarity(a, b)
        d["old"], d["new"] = os.path.basename(old_path), os.path.basename(new_path)
        d["numeric_changed"] = sum(1 for c in d["changed"] if c["numeric"])
        return d

    # ── ③ 영향 ────────────────────────────────────────
    @staticmethod
    def affected(d, refs):
        """refs: {출처 칸 주소: [{"key","label","raw","scale","dec","comma"}]} (검증 결과에서 조립부가 만듦)."""
        out = []
        for ch in d["changed"]:
            for u in refs.get(ch["ref_old"], []):
                new_doc = None
                if ch["new"] is not None:
                    x = ch["new"] * (u.get("scale") or 1.0)
                    new_doc = N.fmt(x, u.get("dec") or 0, comma=bool(u.get("comma")) or abs(x) >= 1000)
                out.append({"key": u["key"], "label": u["label"], "doc_now": u.get("raw"), "doc_new": new_doc,
                            "src_ref": ch["ref"], "src_old": ch["old_text"], "src_new": ch["new_text"],
                            "same": new_doc == u.get("raw")})
        return out

    # ── ④ 짝 찾기 ─────────────────────────────────────
    def match(self, new_path, sources, books):
        """sources: [{"sid","name","path"}], books: sid → 원본(읽은 것) → 점수순 후보."""
        try:
            nb = read_book(new_path)
        except Exception as e:
            raise WorkError(f"새 파일을 읽지 못했습니다: {e}")
        stem = _stem(new_path)
        cands = []
        for s in sources:
            if os.path.abspath(s["path"]) == os.path.abspath(new_path):
                continue
            b = books.get(s["sid"])
            if not b:
                continue
            name_score = 1.0 if _stem(s["name"]) == stem else (0.5 if stem in _stem(s["name"]) or _stem(s["name"]) in stem else 0)
            sim = D.similarity(b, nb)
            score = round(0.5 * name_score + 0.5 * sim, 3)
            if score >= 0.25:
                cands.append({"sid": s["sid"], "name": s["name"], "score": score, "name_match": name_score, "content": sim})
        cands.sort(key=lambda x: -x["score"])
        return cands[:5]
