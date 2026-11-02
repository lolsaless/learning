# -*- coding: utf-8 -*-
"""[화면 연결] 시연 기능: 가상 자료로 작업을 자동 준비하고, '원본이 나중에 바뀐' 상황을 재현한다."""
import os
import shutil

from app.common.errors import WorkError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEMO = os.path.join(ROOT, "시연자료")
DEMO_WORK = os.path.join(DEMO, "작업(시연)")
DEMO_BASE = os.path.join(DEMO, "공유폴더(가상)", "2026 행정사무감사")
CHANGED = os.path.join(DEMO, "나중에_받은_자료", "하천수질_측정결과_2026.xlsx")
KEEP = os.path.join(DEMO, "나중에_받은_자료", "_처음_원본_보관", "하천수질_측정결과_2026.xlsx")
TARGET_IN_SHARE = os.path.join(DEMO_BASE, "01_원본자료", "수질분석팀", "하천수질_측정결과_2026.xlsx")


def available():
    return os.path.isdir(DEMO_BASE)


def setup(app, reset=False):
    if not available():
        raise WorkError("시연자료 폴더가 없습니다. 먼저 '시연자료_다시만들기'를 실행하세요")
    if reset and os.path.isdir(DEMO_WORK):
        if app.ws and os.path.normcase(app.ws.folder) == os.path.normcase(DEMO_WORK):
            app.close_work()
        shutil.rmtree(DEMO_WORK)
    restore()
    app.open_work(DEMO_WORK)
    ws = app.ws
    if not ws.db.versions():
        ws.set_target(os.path.join(DEMO_BASE, "03_취합", "2026_행정사무감사_요구자료_취합본.hwpx"))
    if not ws.db.sources():
        ws.add_sources([os.path.join(DEMO_BASE, "01_원본자료")], "원본")
        ws.add_sources([os.path.join(DEMO_BASE, "02_팀제출")], "팀제출")
    return ws.state()


def stage2():
    shutil.copy2(CHANGED, TARGET_IN_SHARE)
    os.utime(TARGET_IN_SHARE, None)
    return {"ok": True, "msg": "수질분석팀이 수정한 엑셀로 공유폴더의 원본을 바꿨습니다(시연)"}


def restore():
    if os.path.exists(KEEP):
        with open(KEEP, "rb") as a, open(TARGET_IN_SHARE, "rb") as b:
            if a.read() == b.read():
                return
        shutil.copy2(KEEP, TARGET_IN_SHARE)
        os.utime(TARGET_IN_SHARE, None)


def setup_scenario(app, folder, reset=False):
    """무작위 시연자료(정답표.json 이 있는 폴더)로 작업을 준비한다: 작업 폴더 = <시나리오>/작업(시연)."""
    import json
    with open(os.path.join(folder, "정답표.json"), encoding="utf-8") as f:
        key = json.load(f)
    target = os.path.join(folder, key["대상"])
    base = os.path.dirname(os.path.dirname(target))
    work = os.path.join(folder, "작업(시연)")
    if reset and os.path.isdir(work):
        if app.ws and os.path.normcase(app.ws.folder) == os.path.normcase(work):
            app.close_work()
        shutil.rmtree(work)
    app.open_work(work)
    ws = app.ws
    if not ws.db.versions():
        ws.set_target(target)
    if not ws.db.sources():
        ws.add_sources([os.path.join(base, "01_원본자료")], "원본")
        ws.add_sources([os.path.join(base, "02_팀제출")], "팀제출")
    return ws.state()
