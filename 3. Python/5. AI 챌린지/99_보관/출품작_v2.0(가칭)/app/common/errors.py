# -*- coding: utf-8 -*-
"""모든 파트가 같이 쓰는 오류 종류.

WorkError: 사용자에게 그대로 보여 줄 수 있는 오류(예: "먼저 작업 폴더를 여세요").
           화면에는 빨간 알림으로 나오고 프로그램은 계속 동작한다.
"""


class WorkError(Exception):
    pass
