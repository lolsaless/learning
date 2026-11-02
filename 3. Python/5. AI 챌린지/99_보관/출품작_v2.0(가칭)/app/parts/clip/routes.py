# -*- coding: utf-8 -*-
"""[클립보드 파트] 화면 주소. 감시기는 프로그램 전체에 하나(app.clip)."""


def routes(app):
    def toggle(b):
        if b.get("on"):
            app.need()
            ok = app.clip.start()
            return {"ok": ok, "error": app.clip.last_error}
        app.clip.stop()
        return {"ok": True}

    def clips(q):
        return {"clips": [dict(c, cells={f"{k[0]},{k[1]}": v for k, v in c["cells"].items()})
                          for c in app.need().clip.clips(100)]}

    return [
        ("POST", "/api/clip", toggle),
        ("GET", "/api/clips", clips),
    ]
