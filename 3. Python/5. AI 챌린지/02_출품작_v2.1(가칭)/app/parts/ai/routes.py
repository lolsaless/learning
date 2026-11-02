# -*- coding: utf-8 -*-
"""[AI 파트] 화면 주소. 설정·연결 시험은 작업 폴더 없이도 쓸 수 있다."""
from app.parts.ai.part import AiPart


def routes(app):
    holder = {}

    def part():
        ws = getattr(app, "ws", None)
        if ws is not None:
            return ws.ai
        if "p" not in holder:
            holder["p"] = AiPart()
        return holder["p"]

    def get_settings(q):
        return part().settings()

    def save_settings(b):
        s = part().save_settings(b)
        ws = getattr(app, "ws", None)
        if ws is not None and holder.get("p") is not None:
            holder.pop("p")
        return s

    def test(b):
        return part().test()

    def read(b):
        ws = app.need()
        view = ws.ai_read(bool(b.get("on", True)))
        return {"view": view, "claims": (ws.last or {}).get("claims")}

    def claims(q):
        ws = app.need()
        return {"claims": (ws.last or {}).get("claims"), "use_ai": ws.use_ai}

    def summary(b):
        return app.need().ai_summary(bool(b.get("ai")))

    return [
        ("GET", "/api/ai/settings", get_settings),
        ("POST", "/api/ai/settings", save_settings),
        ("POST", "/api/ai/test", test),
        ("POST", "/api/ai/read", read),
        ("GET", "/api/ai/claims", claims),
        ("POST", "/api/ai/summary", summary),
    ]
