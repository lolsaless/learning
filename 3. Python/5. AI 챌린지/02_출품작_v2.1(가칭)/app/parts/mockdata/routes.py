# -*- coding: utf-8 -*-
"""[가상자료 파트] 화면 주소. 생성은 시간이 걸릴 수 있어 잠금 안에서 하나씩 실행한다."""
from app.parts.mockdata.part import MockDataPart


def routes(app):
    part = MockDataPart()
    app.mock = part
    return [
        ("GET", "/api/mock/options", lambda q: part.options()),
        ("GET", "/api/mock/list", lambda q: {"items": part.list(), "root": part.root}),
        ("POST", "/api/mock/generate", lambda b: part.generate(
            seed=b.get("seed") or None, size=b.get("size"), errors=b.get("errors"), kinds=b.get("kinds"),
            gongmun=b.get("gongmun", True), guides=b.get("guides", True), form=b.get("form", True),
            resubmit=b.get("resubmit", True), fmt=b.get("fmt", "both"), src_mix=bool(b.get("src_mix")),
            target_fmt=b.get("target_fmt") or "hwpx", stmt_free=bool(b.get("stmt_free")))),
    ]
