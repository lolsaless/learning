"""운영체제 기능 — 파일을 기본 프로그램으로 열기, 폴더 고르기 창 (표준 라이브러리만)."""
from __future__ import annotations

import os
import subprocess
import sys

_PICK_CODE = r"""
import sys, tkinter as tk
from tkinter import filedialog
root = tk.Tk(); root.withdraw()
try: root.attributes('-topmost', True)
except Exception: pass
path = filedialog.askdirectory(title=sys.argv[1], initialdir=sys.argv[2] or None, mustexist=False)
sys.stdout.write(path or '')
"""


def open_with_system(path: str) -> None:
    """한글이 .hwpx 기본 프로그램이면 한글로 열린다."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    if sys.platform.startswith("win"):
        os.startfile(path)                                   # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def pick_folder(title: str = "폴더 고르기", initial: str = "") -> str:
    """폴더 고르기 창을 띄우고 고른 경로를 돌려준다 (취소하면 ''). 창을 못 띄우면 RuntimeError."""
    try:
        out = subprocess.run([sys.executable, "-c", _PICK_CODE, title, initial or ""],
                             capture_output=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"폴더 고르기 창을 띄우지 못했습니다: {e}")
    if out.returncode != 0:
        msg = out.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or ["알 수 없는 오류"]
        raise RuntimeError(f"폴더 고르기 창을 띄우지 못했습니다 ({msg[0]}) — 경로를 직접 입력해 주세요")
    return out.stdout.decode("utf-8", "replace").strip()
