"""한글(HWP) 프로그램 자동화 — pywin32 가 있는 Windows 에서만 (없으면 기능만 꺼지고 나머지는 정상 동작).

pywin32 설치: 프로그램 폴더의 `설치_pywin32.bat` (vendor 폴더에 받아 둔 파일로 인터넷 없이 설치 가능).
한글 자동화 객체: "HWPFrame.HwpObject" (한글 2010 이상). 파일을 열 때 '접근 허용' 창이 뜨면
보안 모듈(FilePathCheckerModule)을 등록하면 안 뜬다 — 등록되어 있으면 자동으로 쓴다.

COM 은 스레드마다 초기화가 필요해서, 작업마다 새 스레드에서 열고 닫는다 (서버가 멈추지 않게 시간 제한).
"""
from __future__ import annotations

import os
import sys
import threading
from typing import Any, Callable, Dict

TIMEOUT = 120


def _available() -> Dict[str, Any]:
    if not sys.platform.startswith("win"):
        return {"ok": False, "reason": "Windows 에서만 쓸 수 있습니다"}
    try:
        import pythoncom  # noqa: F401
        import win32com.client  # noqa: F401
    except ImportError:
        return {"ok": False, "reason": "pywin32 가 설치되어 있지 않습니다 (설치_pywin32.bat 실행)"}
    return {"ok": True, "reason": ""}


def hangul_status() -> Dict[str, Any]:
    st = _available()
    st["features"] = {"open": True, "resave": st["ok"], "pdf": st["ok"]}
    return st


def _run(job: Callable[[Any], Any]) -> Any:
    st = _available()
    if not st["ok"]:
        raise RuntimeError(st["reason"])
    box: Dict[str, Any] = {}

    def worker():
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        hwp = None
        try:
            hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
            try:
                hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
            except Exception:
                pass
            try:
                hwp.XHwpWindows.Item(0).Visible = False
            except Exception:
                pass
            box["result"] = job(hwp)
        except Exception as e:                          # 한글 쪽 오류를 그대로 전달
            box["error"] = f"{type(e).__name__}: {e}"
        finally:
            try:
                if hwp is not None:
                    hwp.Clear(1)
                    hwp.Quit()
            except Exception:
                pass
            pythoncom.CoUninitialize()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(TIMEOUT)
    if t.is_alive():
        raise RuntimeError("한글 응답이 없습니다 (작업 관리자에서 Hwp.exe 를 확인하세요)")
    if "error" in box:
        raise RuntimeError("한글 자동화 오류: " + box["error"])
    return box.get("result")


def hangul_resave(path: str) -> None:
    """한글로 열어 같은 이름으로 다시 저장 → 미리보기·줄 배치·글자모양 목록이 한글 방식으로 정리된다."""
    path = os.path.abspath(path)

    def job(hwp):
        if not hwp.Open(path, "HWPX", "forceopen:true"):
            raise RuntimeError("한글이 파일을 열지 못했습니다")
        if not hwp.SaveAs(path, "HWPX", ""):
            raise RuntimeError("한글이 저장하지 못했습니다")
    _run(job)


def hangul_pdf(path: str, out: str) -> None:
    path, out = os.path.abspath(path), os.path.abspath(out)

    def job(hwp):
        if not hwp.Open(path, "HWPX", "forceopen:true"):
            raise RuntimeError("한글이 파일을 열지 못했습니다")
        if not hwp.SaveAs(out, "PDF", ""):
            raise RuntimeError("PDF 로 저장하지 못했습니다")
    _run(job)
