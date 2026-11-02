# -*- coding: utf-8 -*-
"""[내보내기 파트] 화면 주소."""


def routes(app):
    return [
        ("POST", "/api/export", lambda b: app.need().export()),
    ]
