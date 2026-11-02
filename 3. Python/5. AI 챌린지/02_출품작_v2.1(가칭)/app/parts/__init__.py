# -*- coding: utf-8 -*-
"""기능 파트 모음. 폴더 하나 = 파트 하나.

파트 규칙(tests/test_structure.py 가 자동으로 검사한다)
  1. 파트는 다른 파트를 import 하지 않는다. 필요한 값은 조립부(app/workspace.py)가 넘겨 준다.
  2. 파트가 쓸 수 있는 것: app.config, app.common, app.formats, app.store, 파이썬 표준 라이브러리
  3. 파트 폴더에는 README.md(역할·입구·출구·시험), part.py(기능), routes.py(화면 주소) 가 있다.
  4. 켜고 끄기는 app/config.py 의 PARTS 목록으로 한다.
"""
