# -*- coding: utf-8 -*-
"""[이력 파트] 화면 주소."""


def routes(app):
    return [
        ("GET", "/api/history", lambda q: app.need().history(q.get("slot"))),
    ]
