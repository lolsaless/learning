# -*- coding: utf-8 -*-
"""[내보내기 파트] 출처대장(xlsx)·검증표시본(hwpx)·검증보고(html)를 작업 폴더의 '내보내기'에 만든다.

입구: export(작업) — 작업(조립부)이 가진 folder·doc()·last·db·user 만 읽는다.
출구: {"ledger": 경로, "marked": 경로, "report": 경로, ...}
"""
from app.parts.export import report


class ExportPart:
    def __init__(self, ctx):
        self.ctx = ctx

    def export(self, work):
        return report.export_all(work)
