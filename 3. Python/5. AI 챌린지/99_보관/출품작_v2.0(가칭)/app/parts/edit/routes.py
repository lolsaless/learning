# -*- coding: utf-8 -*-
"""[수정·입력 파트] 화면 주소."""


def routes(app):
    ws = app.need
    return [
        ("POST", "/api/pending", lambda b: ws().set_pending(b["slot"], b["value"], b.get("method", "직접 입력"),
                                                           b.get("sid"), b.get("ref"), b.get("reason", ""))),
        ("POST", "/api/pending/drop", lambda b: ws().drop_pending(b.get("slot"))),
        ("POST", "/api/fix", lambda b: ws().fix_from_source(b["slot"], b["sid"], b["ref"], b["value"],
                                                           b.get("reason") or "원본 값으로 수정")),
        ("POST", "/api/input", lambda b: ws().input_values(b["sid"], b["sheet"], int(b["r0"]), int(b["c0"]),
                                                          int(b["r1"]), int(b["c1"]), b["slot"], b.get("dec"),
                                                          float(b.get("scale", 1.0)), b.get("comma", True))),
        ("POST", "/api/confirm", lambda b: ws().confirm(b["slot"], b["sid"], b["ref"])),
        ("POST", "/api/unconfirm", lambda b: ws().unconfirm(b["slot"])),
        ("POST", "/api/save", lambda b: ws().save_version(b.get("note", ""))),
    ]
