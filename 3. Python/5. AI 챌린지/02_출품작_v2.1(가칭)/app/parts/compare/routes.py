# -*- coding: utf-8 -*-
"""[재제출 비교 파트] 화면 주소."""


def routes(app):
    def check(b):
        return app.need().resubmit_check(b["path"])

    def apply(b):
        return app.need().resubmit_apply(b["sid"], b["path"])

    def diff(b):
        ws = app.need()
        return ws.compare.compare_paths(b["old"], b["new"])

    return [
        ("POST", "/api/resubmit/check", check),
        ("POST", "/api/resubmit/apply", apply),
        ("POST", "/api/compare", diff),
    ]
