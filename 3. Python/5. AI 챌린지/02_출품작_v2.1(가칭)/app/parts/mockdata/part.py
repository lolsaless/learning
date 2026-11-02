# -*- coding: utf-8 -*-
"""[가상자료 파트] 무작위 시연자료(가상 기관 하나의 요구자료 작성 상황)를 만들고 목록을 보여 준다.

작업 폴더와 무관한 '프로그램 전체' 파트라서 Context 대신 저장 위치(out_root)를 받는다.

입구: generate(씨앗값, 크기, 오류 수, 오류 종류, 공문, 참고자료, 작성틀, 재제출본, 형식), list(), info(이름)
출구: 시나리오 요약 {name, folder, seed, org, tables, errors, kinds, files, target}
"""
import os
import json

from app import config
from app.common.errors import WorkError
from app.parts.mockdata.scenario import Scenario, SIZES, DEFAULTS, TARGET_FORMATS
from app.parts.mockdata.errors import KINDS, KIND_NAMES
from app.parts.mockdata.domains import DOMAIN_TITLES


class MockDataPart:
    def __init__(self, out_root=None):
        self.root = out_root or os.path.join(config.PROGRAM_ROOT, config.DIR_MOCK)

    def options(self):
        return {"sizes": list(SIZES), "kinds": [{"key": k, "name": KIND_NAMES[k]} for k in KINDS],
                "domains": DOMAIN_TITLES, "target_formats": list(TARGET_FORMATS) + ["mix"], "defaults": {k: v for k, v in DEFAULTS.items() if k != "kinds"},
                "root": self.root}

    def generate(self, **opts):
        if opts.get("errors") is not None and not (0 <= int(opts["errors"]) <= 30):
            raise WorkError("오류 수는 0~30 사이로 정해 주세요")
        if opts.get("size") and opts["size"] not in SIZES:
            raise WorkError("크기는 작게·보통·크게 중 하나입니다")
        kinds = [k for k in (opts.get("kinds") or KINDS) if k in KINDS]
        opts["kinds"] = kinds or list(KINDS)
        os.makedirs(self.root, exist_ok=True)
        return Scenario(self.root, **opts).run()

    def list(self):
        out = []
        if not os.path.isdir(self.root):
            return out
        for name in sorted(os.listdir(self.root)):
            f = os.path.join(self.root, name, "정답표.json")
            if not os.path.isfile(f):
                continue
            try:
                with open(f, encoding="utf-8") as fh:
                    k = json.load(fh)
            except (OSError, ValueError):
                continue
            s = k.get("시나리오", {})
            out.append({"name": name, "folder": os.path.join(self.root, name), "org": s.get("기관"), "seed": s.get("씨앗값"),
                        "size": s.get("크기"), "domains": s.get("자료영역", []),
                        "errors": sum(1 for a in k.get("항목", []) if not a.get("정상") and not a.get("연쇄")),
                        "resubmit": len(k.get("재제출", [])), "docs": len(k.get("양식", [])),
                        "mtime": os.path.getmtime(f)})
        out.sort(key=lambda x: -x["mtime"])
        return out

    def folder(self, name):
        p = os.path.join(self.root, os.path.basename(name))
        if not os.path.isfile(os.path.join(p, "정답표.json")):
            raise WorkError("시연자료를 찾을 수 없습니다")
        return p
