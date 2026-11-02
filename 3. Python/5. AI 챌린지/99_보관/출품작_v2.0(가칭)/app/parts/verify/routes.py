# -*- coding: utf-8 -*-
"""[검증 파트] 화면 주소."""


def routes(app):
    ws = app.need
    return [
        ("POST", "/api/verify", lambda b: ws().verify()),
        ("GET", "/api/view", lambda q: ws().view() if ws().last else ws().verify(), "lock"),
        ("GET", "/api/slot", lambda q: ws().slot_detail(q["key"])),
    ]
