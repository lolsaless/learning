# -*- coding: utf-8 -*-
"""프로그램 시작점.  실행: python app/main.py   (Windows는 '실행_Windows.bat' 더블클릭)
  --no-browser : 브라우저를 자동으로 열지 않음
  --fresh      : 최근 작업 폴더를 자동으로 열지 않음
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.web.server import main          # noqa: E402

if __name__ == "__main__":
    main()
