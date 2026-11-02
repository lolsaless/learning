# -*- coding: utf-8 -*-
"""[화면 연결] 폴더·파일 고르기 창과 '파일 열기' (이 PC의 파일만 다룸)."""
import os
import sys
import string
import subprocess

from app.common.errors import WorkError

SHOW_EXT = (".hwpx", ".xlsx", ".xlsm", ".hwp", ".xls")


def fs_list(path, demo_dir=None):
    if not path:
        roots = []
        if sys.platform == "win32":
            for d in string.ascii_uppercase:
                if os.path.exists(f"{d}:\\"):
                    roots.append({"name": f"{d}:\\", "path": f"{d}:\\", "dir": True})
        else:
            roots.append({"name": "/", "path": "/", "dir": True})
        home = os.path.expanduser("~")
        quick = [{"name": "홈 폴더", "path": home, "dir": True}]
        for nm in ("Desktop", "바탕 화면", "Documents", "문서", "Downloads", "다운로드"):
            p = os.path.join(home, nm)
            if os.path.isdir(p):
                quick.append({"name": nm, "path": p, "dir": True})
        if demo_dir and os.path.isdir(demo_dir):
            quick.insert(0, {"name": "시연자료(이 프로그램 폴더)", "path": demo_dir, "dir": True})
        return {"path": "", "parent": None, "entries": quick + roots}
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        raise WorkError("폴더가 아닙니다")
    out = []
    try:
        names = sorted(os.listdir(path), key=lambda s: s.lower())
    except OSError as e:
        raise WorkError(f"폴더를 열 수 없습니다: {e}")
    for n in names:
        if n.startswith(".") or n.startswith("~$"):
            continue
        p = os.path.join(path, n)
        isd = os.path.isdir(p)
        if isd or n.lower().endswith(SHOW_EXT):
            out.append({"name": n, "path": p, "dir": isd, "size": None if isd else os.path.getsize(p)})
    parent = os.path.dirname(path)
    return {"path": path, "parent": parent if parent != path else "", "entries": out}


def open_in_os(path):
    if not os.path.exists(path):
        raise WorkError("파일이 없습니다")
    if sys.platform == "win32":
        os.startfile(path)                                       # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
    return {"ok": True}
