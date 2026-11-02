# AI 파트 (`parts/ai`)

## 하는 일
본문 문장 속 계산(차이·비중·배수·합계·평균)을 **검산식**으로 바꾸고, 프로그램이 다시 계산해 맞는지 정한다.
검증 결과 요약 초안(규칙 요약 + 선택: AI 요약)을 만들고, AI 요약의 숫자가 검증 결과에 있는지 검사한다.

원칙: **AI 는 읽기만, 판정은 계산.**
| 읽은 쪽 | 계산이 맞음 | 계산이 틀림 | AI 답이 이상함(지어낸 숫자·빠진 칸·깨진 JSON) |
|---|---|---|---|
| 규칙 읽기 | 초록(ok_calc) | 빨강(calc) | — |
| AI 읽기 | 초록(ok_calc) | 노랑(claim, 확인 필요) | 버림(탈락 기록) |

AI 가 틀린 짝을 지었을 수 있으므로 AI 읽기 결과는 빨강으로 단정하지 않는다.

## 파일
- providers.py — AI 연결(Ollama · OpenAI 호환 · 시험용 모의 AI). 내 컴퓨터(127.0.0.1)만 허용(config.AI_ALLOW_REMOTE)
- prompts.py — AI 에게 주는 지시문(모델을 바꿔도 같음)
- claims.py — 검산식 검사(validate: 숫자가 문장에 글자 그대로 있는가)·계산(compute)
- reader.py — 규칙 읽기(rule_read) · 모의 AI 읽기(mock_read)
- summary.py — 규칙 요약·AI 요약 숫자 검사
- part.py — AiPart(설정·연결 시험·read_doc·summarize) / routes.py — 화면 주소

## 입구
- read_doc(문서, use_ai) → {claims, rejects, stat}
- summarize(검증 요약, 문장검산 통계, use_ai)
- settings()/save_settings(설정), test()

## 출구
- 문장 검산 결과 → 조립부가 검증 파트 `apply_claims` 로 칸 판정에 반영
- 설정 파일: 프로그램 폴더의 `AI설정.json`

## 화면 주소
/api/ai/settings(GET·POST) · /api/ai/test · /api/ai/read · /api/ai/claims · /api/ai/summary

## 모델 바꾸기
설정 화면에서 종류(Ollama/OpenAI 호환)·주소·모델 이름만 바꾼다. 코드 수정 없음.
모델 비교: `python3 tools/ai_eval.py --models ollama:exaone3.5:7.8b ollama:qwen2.5:7b mock`

## 고칠 때 알아 둘 것
- 새 계산 종류: claims.ROLES · NAMES · compute · check_text 에 추가하고 prompts.CLAIM_SYSTEM 에 설명·예시 추가.
- '대비 C% 증가' 증감률 문형은 검증 엔진(common/numbers.change_claims)이 처리 — 여기서 중복하지 않는다.
- 이 파트는 다른 파트를 import 하지 않는다.

## 시험
tests/test_ai.py · tools/ai_eval.py(모델 비교) · tools/evaluate.py --stmt-free --ai mock
