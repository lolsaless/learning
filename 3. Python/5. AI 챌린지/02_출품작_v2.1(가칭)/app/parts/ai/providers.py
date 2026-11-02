# -*- coding: utf-8 -*-
"""[AI 파트 ①] AI 연결(모델 교체 가능): Ollama · OpenAI 호환 서버 · 시험용 모의 AI.

  make(설정) → 연결 객체.  연결.chat(메시지들) → 글자(모델 답)
  연결.models() → 서버에 있는 모델 이름 목록

- 기본은 내 컴퓨터(127.0.0.1)에서 도는 AI 만 허용한다(config.AI_ALLOW_REMOTE=False). 문서 내용이 밖으로 나가지 않게.
- 모델 이름은 설정에서 바꾼다(예: exaone3.5:7.8b, qwen2.5:7b, llama3.1:8b). 코드에 모델 이름을 박지 않는다.
- 표준 라이브러리(urllib)만 쓴다.
"""
import json
import urllib.parse
import urllib.request

from app import config


class AiError(Exception):
    pass


LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1", "[::1]")


def _check_url(url):
    u = urllib.parse.urlparse(url or "")
    if u.scheme not in ("http", "https") or not u.hostname:
        raise AiError(f"AI 주소가 올바르지 않습니다: {url}")
    if not config.AI_ALLOW_REMOTE and u.hostname not in LOCAL_HOSTS:
        raise AiError("보안 설정상 내 컴퓨터(127.0.0.1)의 AI 만 쓸 수 있습니다(config.AI_ALLOW_REMOTE)")
    return url.rstrip("/")


def _post(url, body, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                    # 연결 거부·시간 초과·HTTP 오류 모두
        raise AiError(f"AI 서버에 연결하지 못했습니다({url}): {e}")


def _get(url, timeout):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise AiError(f"AI 서버에 연결하지 못했습니다({url}): {e}")


class Ollama:
    kind = "ollama"

    def __init__(self, url, model, timeout):
        self.url, self.model, self.timeout = _check_url(url), model, timeout

    def chat(self, messages, json_mode=True):
        body = {"model": self.model, "messages": messages, "stream": False,
                "options": {"temperature": 0, "seed": 7}}
        if json_mode:
            body["format"] = "json"
        d = _post(self.url + "/api/chat", body, self.timeout)
        if "error" in d:
            raise AiError(f"AI 오류: {d['error']}")
        return (d.get("message") or {}).get("content", "")

    def models(self):
        return [m.get("name") for m in _get(self.url + "/api/tags", 5).get("models", [])]


class OpenAICompat:
    """LM Studio · llama.cpp server · vLLM 등 '/v1/chat/completions' 를 주는 서버."""
    kind = "openai"

    def __init__(self, url, model, timeout):
        self.url, self.model, self.timeout = _check_url(url), model, timeout

    def chat(self, messages, json_mode=True):
        body = {"model": self.model, "messages": messages, "temperature": 0}
        d = _post(self.url + "/v1/chat/completions", body, self.timeout)
        try:
            return d["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise AiError(f"AI 답 형식이 예상과 다릅니다: {str(d)[:200]}")

    def models(self):
        return [m.get("id") for m in _get(self.url + "/v1/models", 5).get("data", [])]


class Mock:
    """시험용 모의 AI(실제 AI 아님). 정해진 문장 틀을 읽는 흉내만 낸다.

    noise(0~1): 일부러 틀린 답(지어낸 숫자·깨진 JSON)을 섞는 비율 — 프로그램 검증이 걸러 내는지 시험할 때.
    """
    kind = "mock"

    def __init__(self, url="", model="모의AI", timeout=0, noise=0.0, seed=1):
        import random
        self.model, self.noise, self.rng = model, noise, random.Random(seed)

    def chat(self, messages, json_mode=True):
        from app.parts.ai.reader import mock_read          # 같은 파트 안
        text = messages[-1]["content"].split("문장:", 1)[-1].strip()
        checks = mock_read(text)
        if self.noise and self.rng.random() < self.noise:
            k = self.rng.randrange(3)
            if k == 0:
                return "죄송합니다. 계산식을 만들 수 없습니다"                   # JSON 아님
            if k == 1 and checks:
                c = dict(checks[0])
                key = "c" if "c" in c else "total"
                c[key] = "9,876"                                              # 문장에 없는 숫자(환각)
                return json.dumps({"checks": [c] + checks[1:]}, ensure_ascii=False)
            return json.dumps({"checks": [{"type": "rate", "a": "1", "b": "2"}]})   # 칸 빠짐
        return json.dumps({"checks": checks}, ensure_ascii=False)

    def models(self):
        return [self.model]


KINDS = {"ollama": Ollama, "openai": OpenAICompat, "mock": Mock}


def make(settings):
    kind = settings.get("provider") or "none"
    if kind == "none":
        return None
    cls = KINDS.get(kind)
    if not cls:
        raise AiError(f"모르는 AI 종류: {kind}")
    if kind == "mock":
        return Mock(model=settings.get("model") or "모의AI", noise=float(settings.get("noise") or 0))
    if not settings.get("model"):
        raise AiError("AI 모델 이름을 설정하세요(예: exaone3.5:7.8b)")
    return cls(settings.get("url") or config.AI_DEFAULT_URL[kind], settings["model"],
               int(settings.get("timeout") or config.AI_TIMEOUT_SEC))
