# -*- coding: utf-8 -*-
"""[클립보드 파트] (Windows 전용) 엑셀에서 Ctrl+C 할 때 파일·시트·칸 위치를 기록해 출처 힌트로 쓴다.

감시기(ClipWatcher)는 프로그램 전체에 하나이고(app/web/server.py 가 가짐),
기록은 열린 작업의 장부에 저장한다.

입구: record(복사 정보), clips(개수)
"""
from app.parts.clip.clipwatch import ClipWatcher, parse_link, parse_text   # noqa: F401  (밖에서 쓰도록 내보냄)


class ClipPart:
    def __init__(self, ctx):
        self.db = ctx.db

    def record(self, clip):
        return self.db.add_clip(clip["path"], clip["sheet"], clip["r0"], clip["c0"], clip["nrows"], clip["ncols"],
                                {f"{r},{c}": t for (r, c), t in clip["cells"].items()})

    def clips(self, limit=500):
        return self.db.clips(limit)
