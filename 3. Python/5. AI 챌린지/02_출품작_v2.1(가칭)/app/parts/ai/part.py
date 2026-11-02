# -*- coding: utf-8 -*-
"""[AI 파트] 본문 문장 검산(규칙 읽기 + 선택: AI 읽기)과 검증 요약 초안.

원칙: AI 는 '문장을 검산식으로 읽기'와 '요약 글 초안'만 한다. 맞고 틀림은 프로그램 계산이 정한다.
  - 규칙으로 읽은 검산식이 틀리면 → 빨강(calc)
  - AI 가 읽은 검산식이 틀리면   → 노랑(claim: '문장 계산 확인 필요') — AI 가 숫자 역할을 잘못 짝지었을 수 있으므로
  - AI 답에 문장에 없는 숫자·빠진 칸·깨진 JSON 이 있으면 → 버리고 '탈락' 기록(판정에 쓰지 않음)
AI 가 꺼져 있어도 규칙 읽기와 규칙 요약은 늘 동작한다.

입구: settings()/save_settings(), test(), read_doc(doc, use_ai), summarize(요약, 문장검산결과, use_ai)
"""
import json
import os
import re
import time

from app import config
from app.common import numbers as N
from app.parts.ai import claims as C
from app.parts.ai import prompts, summary
from app.parts.ai.providers import make, AiError
from app.parts.ai.reader import rule_read

DEFAULTS = {"provider": "none", "url": "", "model": "", "timeout": 0, "noise": 0}


def load_settings(path=None):
    path = path or config.AI_SETTINGS_FILE
    s = dict(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as f:
            s.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return s


def parse_json(text):
    """모델 답에서 JSON 객체 하나를 꺼낸다(앞뒤 설명·```json 울타리 허용)."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except ValueError:
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except ValueError:
                return None
    return None


def item_spans(block):
    """문단 블록 → [(시작, 끝, 칸 키)] (block['pieces'] 의 글자 위치)."""
    pos, out = 0, []
    for p in block.get("pieces") or []:
        n = len(p["text"])
        if p.get("item"):
            out.append((pos, pos + n, p["item"]))
        pos += n
    return out


def _is_candidate(text, ruled):
    """AI 에게 물어볼 문장: 데이터 숫자가 3개 이상(또는 %·배 포함 2개 이상)인데 규칙이 못 읽은 문단."""
    if ruled or N.change_claims(text):
        return False
    nums = N.extract_numbers(text)
    if len(nums) >= 3:
        return True
    return len(nums) >= 2 and bool(re.search(r"%|배", text))


class AiPart:
    def __init__(self, ctx=None, settings_path=None, provider=None):
        self.ctx = ctx
        self.path = settings_path or config.AI_SETTINGS_FILE
        self._s = load_settings(self.path)
        self._provider = provider          # 시험에서 직접 넣을 수 있게
        self.last = None

    # ── 설정 ──────────────────────────────────────────
    def settings(self):
        s = dict(self._s)
        s["kinds"] = {"none": "사용 안 함", "ollama": "Ollama(내 컴퓨터)", "openai": "OpenAI 호환 서버(LM Studio 등)",
                      "mock": "시험용 모의 AI(실제 AI 아님)"}
        s["default_url"] = config.AI_DEFAULT_URL
        s["enabled"] = self.enabled()
        return s

    def save_settings(self, d):
        for k in DEFAULTS:
            if k in d:
                self._s[k] = d[k]
        make(self._s)                       # 잘못된 값이면 여기서 오류
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._s, f, ensure_ascii=False, indent=1)
        self._provider = None
        return self.settings()

    def enabled(self):
        return self._provider is not None or (self._s.get("provider") or "none") != "none"

    def provider(self):
        if self._provider is None:
            self._provider = make(self._s)
        return self._provider

    def model_name(self):
        p = self.provider()
        return f"{p.kind}:{p.model}" if p else ""

    def test(self):
        p = self.provider()
        if not p:
            return {"ok": False, "error": "AI 를 '사용 안 함'으로 설정했습니다"}
        t0 = time.time()
        try:
            models = p.models()
            got = self._ask("총 120건 중 30건(25.0%)이 야간 접수였다.", p)
        except AiError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "models": models[:30], "sample": got, "seconds": round(time.time() - t0, 2),
                "model": self.model_name(), "has_model": (p.kind == "mock") or (p.model in models)}

    # ── 문장 검산 ─────────────────────────────────────
    def _ask(self, sentence, p):
        raw = p.chat(prompts.claim_messages(sentence))
        d = parse_json(raw)
        if not isinstance(d, dict) or not isinstance(d.get("checks"), list):
            return {"raw": (raw or "")[:300], "checks": None, "error": "JSON 형식이 아님"}
        return {"raw": (raw or "")[:300], "checks": d["checks"]}

    def read_doc(self, doc, use_ai=False, limit=None):
        limit = limit or config.AI_MAX_SENTENCES
        t0 = time.time()
        p = self.provider() if use_ai else None
        out, rejects = [], []
        calls = 0
        for b in doc.blocks:
            if b.get("type") != "p":
                continue
            text = b["text"]
            spans = item_spans(b)
            ruled = rule_read(text)
            for ck in ruled:
                self._add(out, rejects, ck, text, b, spans, "규칙")
            if p and calls < limit and _is_candidate(text, ruled):
                calls += 1
                try:
                    got = self._ask(text, p)
                except AiError as e:
                    rejects.append({"para": b.get("para"), "text": text[:120], "reason": str(e), "by": self.model_name()})
                    p = None                         # 연결이 끊기면 남은 문장은 규칙만
                    continue
                if got["checks"] is None:
                    rejects.append({"para": b.get("para"), "text": text[:120], "reason": got["error"],
                                    "raw": got["raw"], "by": self.model_name()})
                    continue
                for ck in got["checks"][:5]:
                    self._add(out, rejects, ck, text, b, spans, "AI", self.model_name())
        stat = {"checked": len(out), "wrong": sum(1 for c in out if not c["ok"]),
                "rule": sum(1 for c in out if c["by"] == "규칙"), "ai": sum(1 for c in out if c["by"] == "AI"),
                "rejected": len(rejects), "ai_calls": calls, "seconds": round(time.time() - t0, 2),
                "model": self.model_name() if use_ai else ""}
        self.last = {"claims": out, "rejects": rejects, "stat": stat}
        return self.last

    @staticmethod
    def _add(out, rejects, raw_ck, text, b, spans, by, model=""):
        ck, why = C.validate(raw_ck, text)
        if not ck:
            rejects.append({"para": b.get("para"), "text": text[:120], "reason": why, "by": model or by,
                            "raw": json.dumps(raw_ck, ensure_ascii=False)[:200]})
            return
        res = C.compute(ck)
        if res is None:
            rejects.append({"para": b.get("para"), "text": text[:120], "reason": "0으로 나누는 식", "by": model or by})
            return
        rr = ck[C.result_role(ck["type"])]
        key = next((k for s, e, k in spans if s <= rr["start"] < e), None)
        if any(c["para"] == b.get("para") and c["at"] == rr["start"] for c in out):
            return                               # 같은 숫자를 규칙·AI 가 함께 읽은 경우 하나만
        status = "ok_calc" if res["ok"] else ("calc" if by == "규칙" else "claim")
        out.append({"para": b.get("para"), "at": rr["start"], "key": key, "type": ck["type"], "type_name": C.NAMES[ck["type"]],
                    "check": C.check_text(ck), "by": by, "model": model, "ok": res["ok"], "status": status,
                    "msg": res["msg"], "expected_text": res["expected_text"], "raw": rr["raw"],
                    "text": text[max(0, rr["start"] - 50): rr["end"] + 20]})

    # ── 요약 ──────────────────────────────────────────
    def summarize(self, verify_summary, claim_stat=None, use_ai=False):
        f = summary.facts(verify_summary, claim_stat)
        out = {"facts": f, "rule_text": summary.rule_text(f), "ai_text": None, "ai_bad": [], "error": None}
        if use_ai:
            p = self.provider()
            if not p:
                out["error"] = "AI 를 '사용 안 함'으로 설정했습니다"
                return out
            try:
                raw = p.chat(prompts.summary_messages(f))
            except AiError as e:
                out["error"] = str(e)
                return out
            d = parse_json(raw)
            text = d.get("text") if isinstance(d, dict) else None
            if not isinstance(text, str) or not text.strip():
                text = raw if p.kind != "mock" else summary.rule_text(f)
            out["ai_text"] = text.strip()
            out["ai_bad"] = summary.check_numbers(out["ai_text"], f)
            out["model"] = self.model_name()
        return out


def ai_settings_exists():
    return os.path.exists(config.AI_SETTINGS_FILE)
