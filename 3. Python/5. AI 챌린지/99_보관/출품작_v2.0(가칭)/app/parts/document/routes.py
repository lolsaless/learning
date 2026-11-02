# -*- coding: utf-8 -*-
"""[문서 파트] 화면 주소."""


def routes(app):
    ws = app.need
    return [
        ("POST", "/api/target", lambda b: dict(ws().set_target(b["path"]), state=ws().state())),
    ]
