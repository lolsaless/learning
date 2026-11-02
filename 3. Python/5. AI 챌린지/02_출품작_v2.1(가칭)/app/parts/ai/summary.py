# -*- coding: utf-8 -*-
"""[AI 파트 ⑤] 검증 결과 요약 — 규칙 요약(항상) + AI 요약 초안(선택)과 그 숫자 검사.

AI 가 쓴 요약의 숫자가 모두 '검증 결과 숫자'에 있는지 프로그램이 확인한다.
없는 숫자가 있으면 '근거 없는 숫자'로 표시하고 규칙 요약을 쓰라고 안내한다.
"""
from app.common import numbers as N

LABELS = [("total", "검사한 숫자"), ("ok", "원본과 일치"), ("ok_calc", "계산으로 확인"), ("single", "값 일치(위치 추정)"),
          ("ok_user", "사용자 확정"), ("mismatch", "불일치"), ("unit", "단위 다름"), ("calc", "계산 오류"),
          ("conflict", "출처 간 충돌"), ("unknown", "출처 미확인"), ("multi", "후보 여러 개"), ("claim", "문장 계산 확인 필요"),
          ("text_issues", "요일 오류")]


def facts(summary, claims_stat=None):
    s = summary or {}
    out = {}
    for k, lab in LABELS:
        if s.get(k):
            out[lab] = int(s[k])
    red = sum(int(s.get(k) or 0) for k in ("mismatch", "unit", "calc", "text_issues"))
    yel = sum(int(s.get(k) or 0) for k in ("conflict", "unknown", "multi", "claim"))
    out["빨강(고칠 것) 합계"] = red
    out["노랑(확인할 것) 합계"] = yel
    if claims_stat:
        out["문장 검산 건수"] = int(claims_stat.get("checked") or 0)
        if claims_stat.get("wrong"):
            out["문장 검산 틀림"] = int(claims_stat["wrong"])
    return out


def rule_text(f):
    lines = [f"○ 문서 속 숫자 {f.get('검사한 숫자', 0):,}개를 원본 자료와 대조함"]
    good = sum(f.get(k, 0) for k in ("원본과 일치", "계산으로 확인", "값 일치(위치 추정)", "사용자 확정"))
    lines.append(f"○ 일치·확인 {good:,}개, 고칠 것(빨강) {f['빨강(고칠 것) 합계']:,}개, 확인할 것(노랑) {f['노랑(확인할 것) 합계']:,}개")
    det = [f"{lab} {f[lab]:,}개" for lab in ("불일치", "단위 다름", "계산 오류", "요일 오류") if f.get(lab)]
    if det:
        lines.append("○ 고칠 것 내역: " + ", ".join(det))
    if f.get("문장 검산 건수"):
        lines.append(f"○ 본문 문장의 계산 {f['문장 검산 건수']:,}건을 다시 계산함" +
                     (f"(틀림 {f['문장 검산 틀림']:,}건)" if f.get("문장 검산 틀림") else ""))
    return "\n".join(lines)


def check_numbers(text, f):
    """요약 글의 숫자 중 검증 결과에 없는 것(= 근거 없는 숫자) 목록."""
    allowed = set(float(v) for v in f.values())
    good = sum(f.get(k, 0) for k in ("원본과 일치", "계산으로 확인", "값 일치(위치 추정)", "사용자 확정"))
    allowed.add(float(good))
    bad = []
    for tk in N.extract_numbers(text or ""):
        if tk["value"] not in allowed:
            bad.append({"raw": tk["raw"], "start": tk["start"], "end": tk["end"]})
    return bad
