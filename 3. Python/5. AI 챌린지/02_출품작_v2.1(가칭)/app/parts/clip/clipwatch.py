# -*- coding: utf-8 -*-
"""클립보드 출처 기록(Windows 전용, 표준 라이브러리 ctypes 사용).

엑셀에서 Ctrl+C를 하면 클립보드에 값과 함께 'Link' 형식 정보
("Excel\\0C:\\폴더\\[파일.xlsx]시트\\0R2C3:R5C6\\0\\0")가 들어간다.
이 정보를 읽어 '어느 파일 어느 시트 어느 칸을 복사했는지'를 이력 장부에 남긴다.
 · 켜져 있을 때만 기록한다(화면의 [복사 기록] 스위치).
 · 엑셀에서 복사한 것만 기록한다(다른 프로그램의 복사 내용은 보지 않음).
 · 기록은 이 PC의 작업 폴더 안에만 저장한다(밖으로 보내지 않음).
"""
import re
import sys
import time
import threading

from app import config

CF_UNICODETEXT = 13


def parse_link(raw):
    parts = raw.split(b"\x00")
    if len(parts) < 3:
        return None
    try:
        app = parts[0].decode("mbcs" if sys.platform == "win32" else "utf-8", "replace")
        topic = parts[1].decode("mbcs" if sys.platform == "win32" else "utf-8", "replace")
        item = parts[2].decode("mbcs" if sys.platform == "win32" else "utf-8", "replace")
    except LookupError:
        app, topic, item = (p.decode("utf-8", "replace") for p in parts[:3])
    if app.lower() != "excel":
        return None
    m = re.match(r"^(.*)\[(.+)\](.+)$", topic)
    if m:
        path, sheet = m.group(1) + m.group(2), m.group(3)
    else:
        path, sheet = topic, ""
    m2 = re.match(r"^R(\d+)C(\d+)(?::R(\d+)C(\d+))?$", item.strip())
    if not m2:
        return None
    r0, c0 = int(m2.group(1)) - 1, int(m2.group(2)) - 1
    r1 = int(m2.group(3)) - 1 if m2.group(3) else r0
    c1 = int(m2.group(4)) - 1 if m2.group(4) else c0
    return {"path": path, "sheet": sheet, "r0": r0, "c0": c0, "nrows": r1 - r0 + 1, "ncols": c1 - c0 + 1}


def parse_text(text, max_cells=None):
    max_cells = max_cells or config.CLIP_MAX_CELLS
    cells = {}
    lines = (text or "").replace("\r\n", "\n").rstrip("\n").split("\n")
    for r, line in enumerate(lines):
        for c, t in enumerate(line.split("\t")):
            if t.strip():
                cells[(r, c)] = t.strip()
            if len(cells) >= max_cells:
                return cells
    return cells


class ClipWatcher:
    def __init__(self, on_clip):
        self.on_clip = on_clip
        self.available = sys.platform == "win32"
        self.running = False
        self.count = 0
        self.last_error = None
        self._th = None

    def start(self):
        if not self.available:
            self.last_error = "Windows에서만 사용할 수 있습니다"
            return False
        if self.running:
            return True
        self.running = True
        self._th = threading.Thread(target=self._loop, daemon=True)
        self._th.start()
        return True

    def stop(self):
        self.running = False

    def _loop(self):
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        k = ctypes.windll.kernel32
        u.GetClipboardSequenceNumber.restype = wintypes.DWORD
        u.GetClipboardData.restype = ctypes.c_void_p
        u.GetClipboardData.argtypes = [wintypes.UINT]
        u.RegisterClipboardFormatW.restype = wintypes.UINT
        u.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
        u.OpenClipboard.argtypes = [wintypes.HWND]
        k.GlobalLock.restype = ctypes.c_void_p
        k.GlobalLock.argtypes = [ctypes.c_void_p]
        k.GlobalUnlock.argtypes = [ctypes.c_void_p]
        k.GlobalSize.restype = ctypes.c_size_t
        k.GlobalSize.argtypes = [ctypes.c_void_p]
        fmt_link = u.RegisterClipboardFormatW("Link")
        last = u.GetClipboardSequenceNumber()
        while self.running:
            time.sleep(config.CLIP_POLL_SEC)
            try:
                seq = u.GetClipboardSequenceNumber()
                if seq == last:
                    continue
                last = seq
                if not u.IsClipboardFormatAvailable(fmt_link):
                    continue
                opened = False
                for _ in range(10):
                    if u.OpenClipboard(None):
                        opened = True
                        break
                    time.sleep(0.05)
                if not opened:
                    continue
                try:
                    raw = b""
                    h = u.GetClipboardData(fmt_link)
                    if h:
                        p = k.GlobalLock(h)
                        if p:
                            raw = ctypes.string_at(p, k.GlobalSize(h))
                            k.GlobalUnlock(h)
                    text = ""
                    h2 = u.GetClipboardData(CF_UNICODETEXT)
                    if h2:
                        p2 = k.GlobalLock(h2)
                        if p2:
                            text = ctypes.wstring_at(p2)
                            k.GlobalUnlock(h2)
                finally:
                    u.CloseClipboard()
                info = parse_link(raw)
                if not info:
                    continue
                info["cells"] = parse_text(text)
                self.count += 1
                self.on_clip(info)
            except Exception as e:      # 기록 실패가 프로그램을 멈추지 않게
                self.last_error = str(e)
