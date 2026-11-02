# -*- coding: utf-8 -*-
"""작업 맥락(Context): 작업 폴더 하나에 대해 모든 파트가 함께 쓰는 값 묶음.

파트는 서로를 직접 부르지 않는다. 대신 조립부(app/workspace.py)가 이 묶음을 만들어
각 파트에 똑같이 넘겨 준다. 파트가 알 수 있는 것은 이 묶음과 공통 도구뿐이다.

  folder : 작업 폴더 경로
  db     : 이력 장부(app/store/ledger.py 의 Ledger)
  user   : 작업자 이름
  lock   : 동시에 두 작업이 겹치지 않게 하는 잠금
"""
import threading


class Context:
    def __init__(self, folder, db, user):
        self.folder = folder
        self.db = db
        self.user = user
        self.lock = threading.RLock()

    def path(self, *names):
        import os
        return os.path.join(self.folder, *names)
