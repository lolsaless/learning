# -*- coding: utf-8 -*-
"""[한글 파일] 검증표시본용 색 표시(불일치 빨간 굵은 글씨, 확인 필요 노란 배경)."""
import re

from app import config
from app.formats.hwpx.base import T


class MarkMixin:
    def _color_charpr(self, base_id, color=None, shade=None):
        h = self.header_raw
        key = f"{base_id}|{color}|{shade}"
        if not hasattr(self, "_cp_cache"):
            self._cp_cache = {}
        if key in self._cp_cache:
            return self._cp_cache[key]
        m = re.search(r'<hh:charPr id="%s"[\s\S]*?</hh:charPr>' % re.escape(str(base_id)), h)
        if not m:
            return None
        ids = [int(x) for x in re.findall(r'<hh:charPr id="(\d+)"', h)]
        new_id = max(ids) + 1
        x = m.group(0)
        x = re.sub(r'id="\d+"', f'id="{new_id}"', x, count=1)
        if color:
            x = re.sub(r'textColor="[^"]*"', f'textColor="{color}"', x, count=1)
        if shade:
            x = re.sub(r'shadeColor="[^"]*"', f'shadeColor="{shade}"', x, count=1)
        if color and "<hh:bold/>" not in x:
            x = re.sub(r'(<hh:charPr [^>]*>)', r'\1<hh:bold/>', x, count=1)
        h = h.replace("</hh:charProperties>", x + "</hh:charProperties>", 1)
        h = re.sub(r'<hh:charProperties itemCnt="(\d+)"', lambda mm: f'<hh:charProperties itemCnt="{int(mm.group(1)) + 1}"', h, count=1)
        self.header_raw = h
        self._header_changed = True
        self._cp_cache[key] = str(new_id)
        return str(new_id)

    def mark(self, key, level):
        """level: 'red'(불일치·오류) | 'yellow'(확인 필요)"""
        it = self.item(key)
        if it is None:
            return False
        run = None
        if it.field:
            tl = self._field_texts(it.field)
            if tl:
                run = tl[0][1]
        elif it._t is not None and not isinstance(it._t, tuple):
            run = self._parent.get(it._t)
        if run is None or run.tag != T["run"]:
            return False
        base = run.get("charPrIDRef", "0")
        if level == "red":
            nid = self._color_charpr(base, color=config.MARK_RED)
        else:
            nid = self._color_charpr(base, shade=config.MARK_YELLOW_SHADE)
        if nid:
            run.set("charPrIDRef", nid)
            return True
        return False

