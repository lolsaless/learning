# -*- coding: utf-8 -*-
"""[원본 파트] 화면 주소. 각 줄: (방식, 주소, 처리 함수). 처리 함수는 요청값(dict)을 받는다."""


def routes(app):
    ws = app.need
    return [
        ("POST", "/api/sources/add", lambda b: dict(ws().add_sources(b["paths"], b.get("role")), state=ws().state())),
        ("POST", "/api/sources/remove", lambda b: (ws().remove_source(b["sid"]), ws().state())[1]),
        ("POST", "/api/sources/role", lambda b: (ws().set_role(b["sid"], b["role"]), ws().state())[1]),
        ("POST", "/api/sources/check", lambda b: ws().check_sources()),
        ("GET", "/api/grid", lambda q: ws().grid(q["sid"], q.get("sheet", ""), int(q.get("r0", 0)), int(q.get("c0", 0)),
                                                 int(q.get("nr", 80)), int(q.get("nc", 30)))),
    ]
