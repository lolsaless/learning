# -*- coding: utf-8 -*-
"""[화면 연결] 파트에 속하지 않는 공통 주소: 상태·작업 폴더·폴더 탐색·시연·종료."""
import os
import threading

from app import config
from app.web import demo
from app.web.fsbrowse import fs_list, open_in_os


def routes(app):
    def state(q):
        return {"work": app.ws.state() if app.ws else None, "recent": app.recent().get("folders", []),
                "demo": demo.available(), "demo_work": demo.DEMO_WORK,
                "clip": {"available": app.clip.available, "running": app.clip.running,
                         "count": app.clip.count, "error": app.clip.last_error},
                "app_name": config.APP_NAME, "version": config.APP_VERSION,
                "parts": app.parts, "status_names": config.STATUS}

    def mkdir(b):
        os.makedirs(b["path"], exist_ok=True)
        return {"ok": True, "path": os.path.abspath(b["path"])}

    def shutdown(b):
        threading.Thread(target=lambda: (app.clip.stop(), app.server.shutdown()), daemon=True).start()
        return {"ok": True}

    def user(b):
        app.need().set_user(b.get("name"))
        return app.ws.state()

    return [
        ("GET", "/api/ping", lambda q: {"app": config.APP_ID, "name": config.APP_NAME, "version": config.APP_VERSION}),
        ("GET", "/api/state", state),
        ("GET", "/api/fs", lambda q: fs_list(q.get("path", ""), demo.DEMO)),
        ("POST", "/api/work/open", lambda b: app.open_work(b["folder"], b.get("user"))),
        ("POST", "/api/user", user),
        ("POST", "/api/demo/setup", lambda b: demo.setup(app, reset=b.get("reset", False))),
        ("POST", "/api/demo/stage2", lambda b: demo.stage2()),
        ("POST", "/api/demo/restore", lambda b: (demo.restore(), {"ok": True})[1]),
        ("POST", "/api/fs/mkdir", mkdir),
        ("POST", "/api/open", lambda b: open_in_os(b["path"])),
        ("POST", "/api/shutdown", shutdown, "nolock"),
    ]
