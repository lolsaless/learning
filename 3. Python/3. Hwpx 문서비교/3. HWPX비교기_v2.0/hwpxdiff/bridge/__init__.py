"""컴퓨터·한글 프로그램 연동 (v2.0).

  open_with_system(path)   기본 프로그램(한글)으로 파일 열기 — 표준 라이브러리만 (Windows/Mac/Linux)
  pick_folder(title)       폴더 고르기 창 — tkinter 를 별도 프로세스로 띄움 (서버 스레드에서도 안전)
  hangul_status()          pywin32 + 한글 자동화 가능 여부
  hangul_resave(path)      한글로 열었다 다시 저장 (미리보기·줄 배치 새로 만들기)  ← pywin32 필요
  hangul_pdf(path, out)    한글로 PDF 저장                                      ← pywin32 필요
"""
from .hangul import hangul_pdf, hangul_resave, hangul_status
from .system import open_with_system, pick_folder

__all__ = ["open_with_system", "pick_folder", "hangul_status", "hangul_resave", "hangul_pdf"]
