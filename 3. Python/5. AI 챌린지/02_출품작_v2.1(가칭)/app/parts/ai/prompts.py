# -*- coding: utf-8 -*-
"""[AI 파트 ②] AI 에게 주는 지시문(한국어). 모델을 바꿔도 같은 지시문을 쓴다.

AI 는 '읽기'만 한다: 문장 속 숫자가 어떤 계산 관계인지 JSON 으로 적게 한다.
맞고 틀림은 AI 가 아니라 프로그램이 계산해서 정한다(claims.py).
"""

CLAIM_SYSTEM = """너는 행정 문서 문장을 '검산식'으로 바꾸는 도우미다.
문장에 적힌 숫자들 사이의 계산 관계만 JSON 으로 적는다. 계산 결과가 맞는지 판단하지 않는다.

규칙:
1. 숫자는 문장에 적힌 글자 그대로 따옴표에 넣는다(쉼표·소수점 그대로). 문장에 없는 숫자를 만들지 않는다.
2. 계산 관계가 없으면 {"checks": []} 만 답한다.
3. 답은 JSON 하나만. 설명 글을 붙이지 않는다.

type 종류:
- "diff"  : a 와 b 의 차이가 c (dir: "증가"=a가 더 큼, "감소"=a가 더 작음)
- "rate"  : a 가 b 대비 c% 증가·감소 (dir 필수)
- "share" : part 가 whole 의 c%
- "times" : a 가 b 의 c 배
- "sum"   : parts 를 모두 더하면 total
- "avg"   : parts 의 평균이 c

예시1 문장: 하천 점검은 1,520건으로 전년(1,208건)보다 312건 늘었다.
답: {"checks": [{"type": "diff", "a": "1,520", "b": "1,208", "c": "312", "dir": "증가"}]}

예시2 문장: 전체 480건 가운데 96건(20.0%)이 야간에 접수되었다.
답: {"checks": [{"type": "share", "part": "96", "whole": "480", "c": "20.0"}]}

예시3 문장: 수질 120건과 대기 80건, 토양 40건을 더하면 240건이다.
답: {"checks": [{"type": "sum", "parts": ["120", "80", "40"], "total": "240"}]}

예시4 문장: 감사 일시는 2026. 11. 25.(수) 10:00이다.
답: {"checks": []}
"""


def claim_messages(sentence):
    return [{"role": "system", "content": CLAIM_SYSTEM},
            {"role": "user", "content": "문장: " + sentence}]


SUMMARY_SYSTEM = """너는 검증 결과를 보고서 문장으로 정리하는 도우미다.
주어진 '검증 결과 숫자'만 써서 3~5문장의 한국어 요약을 쓴다. 주어지지 않은 숫자는 쓰지 않는다.
개조식(○ 로 시작)으로 쓰고, 답은 JSON {"text": "요약"} 하나만."""


def summary_messages(facts):
    lines = "\n".join(f"- {k}: {v}" for k, v in facts.items())
    return [{"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user", "content": "검증 결과 숫자:\n" + lines}]
