# -*- coding: utf-8 -*-
"""[검증 엔진 보조] 엑셀 복사 기록(클립보드)을 출처 힌트로 붙인다."""

from app.common import numbers as N
from app.formats.xlsx import ref as a1ref


class ClipHintMixin:
    def _clip_hints(self, doc, results, clips):
        for it in doc.items:
            if it.value is None:
                continue
            r = results.get(it.key)
            if r is None:
                continue
            for cl in clips:
                for (dr, dc), txt in cl.get("cells", {}).items():
                    tok = N.parse_cell(txt)
                    if tok and N.close(tok["value"], it.value, it.dec):
                        r.setdefault("clips", []).append({
                            "at": cl["at"], "path": cl["path"], "sheet": cl["sheet"],
                            "ref": a1ref(cl["r0"] + dr, cl["c0"] + dc), "text": txt})
                        break
                if len(r.get("clips", [])) >= 3:
                    break

