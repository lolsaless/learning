# -*- coding: utf-8 -*-
"""[이력 파트] 값 이력·작업본 버전·원본 변경·검증 실행 기록을 꺼내 보여 준다(읽기 전용).

입구: history(칸=None)
출구: {"events", "versions", "source_events", "runs"}
"""


class HistoryPart:
    def __init__(self, ctx):
        self.db = ctx.db

    def history(self, slot=None, runs=30):
        return {"events": self.db.events(slot), "versions": self.db.versions(),
                "source_events": self.db.source_events(), "runs": self.db.runs()[:runs]}

    def slot_events(self, slot):
        return self.db.events(slot)
