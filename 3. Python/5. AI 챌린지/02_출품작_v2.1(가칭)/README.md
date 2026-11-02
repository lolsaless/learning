# 취합검증 도우미(가칭) v2.1

**여러 원본을 모아 만든 문서의 모든 숫자를 원본과 대조하고, 다시 받은 원본의 바뀐 곳을 찾고, 문장 속 계산과 AI가 쓴 글의 숫자까지 다시 계산하는 도구**
(이름은 가칭 — `app/config.py` 의 `APP_NAME` 한 줄로 바꿈)

- 형식: HTML 화면 + Python 로컬 서버(표준 라이브러리만, Python 3.8 이상, 패키지 설치 없음, 인터넷 불필요, 127.0.0.1 전용)
- 읽는 파일 14종: **hwpx · hwp · xlsx · xlsm · xls · ods · csv · tsv · docx · odt · pdf · txt · md · html**(고치기는 hwpx, 나머지는 읽기 전용 검증)
- 판정: 규칙·계산. **AI(선택)** 는 문장을 검산식으로 읽기·요약 초안만 하고, 그 답은 프로그램이 검사(지어낸 숫자는 버림). 모델은 설정에서 교체(Ollama·OpenAI 호환)
- 재제출 비교: 다시 받은 원본(이름이 달라도)과 이전 판을 칸 단위로 비교 → 고쳐야 할 문서 칸과 새 값
- 구조: 5개 층(U 화면 · W 화면 연결 · A 조립부 · P 기능 파트 10개 · B 바탕). 파트끼리는 서로 부르지 않는다
- 시험: 자동 시험 47개 + 무작위 시나리오 자동 평가(340개: 심은 오류 3,000개 중 2,999개 검출, 빨강 오탐 0)

## 실행(더블클릭)

| Windows | Mac | 하는 일 |
|---|---|---|
| `실행_Windows.bat` | `실행_Mac.command` | 프로그램 실행 → 브라우저 `http://127.0.0.1:8765` |
| `휴대용Python_넣기_Windows.bat` | — | (인터넷 되는 PC 에서 한 번) `python\` 에 공식 휴대용 Python → Python 없는 PC 에서도 실행 |
| `시연자료_만들기_Windows.bat` | `시연자료_만들기_Mac.command` | 무작위 시연자료 3개 |
| `자동평가_Windows.bat` | `자동평가_Mac.command` | 무작위 20개로 자동 평가 → `평가결과/` |
| `시험_전체실행_Windows.bat` | `시험_전체실행_Mac.command` | 자동 시험 전체 |
| `기본시연자료_다시만들기_Windows.bat` | `python3 tools/make_demo.py` | 고정 시연자료 다시 만들기 |

## 화면

1 작업 준비 · 2 검증 · 3 입력하기 · 4 이력 · 5 시연자료(만들기·채점·자동 평가) · 6 구성도(파트 지도) · 7 설정·도움말(AI 설정)

## 구성(자세히: 6 구성도 탭, `docs/파트지도.md`)

| 층 | 구성요소 |
|---|---|
| U 화면 | `app/ui/` 뼈대 + 페이지 7개(html·js 한 쌍씩) |
| W 화면 연결 | `app/web/` 서버 · 공통 주소 · 평가 주소 · 시연 준비 · 폴더 탐색 · 파트 지도 |
| A 조립부 | `app/workspace.py`(작업) · `app/evaluation.py`(평가) · `app/main.py`(시작점) |
| P 기능 파트 | `app/parts/` 원본 · 문서 · 검증 · 수정·입력 · 이력 · 내보내기 · 클립보드 · **AI** · **재제출 비교** · 가상자료 |
| B 바탕 | `app/config.py` · `common/` · `formats/`(형식 등록부 + 14개 형식) · `store/` |

## 명령줄

```
python tests/run_all.py                                        # 자동 시험 47개 → '전체 통과'
python tools/evaluate.py --n 100 --seed 40000                  # 자동 평가(빨강 오탐이 늘면 안 됨)
python tools/evaluate.py --n 25 --src-mix --target-fmt pdf     # 원본 형식 섞기 + PDF 취합본
python tools/evaluate.py --n 20 --resubmit                     # 재제출 비교 채점
python tools/ai_eval.py --models ollama:exaone3.5:7.8b ollama:qwen2.5:7b   # AI 모델 비교(모델 비종속)
python tools/make_mock.py --count 5 --size 크게 --seed 777      # 무작위 시연자료
python tools/part_map.py                                       # docs/파트지도.md 다시 만들기
python tests/e2e_ui.py · e2e_mock.py · e2e_v21.py               # 화면 시험(서버를 켠 뒤, Playwright 필요)
```

## 문서

| 문서 | 내용 |
|---|---|
| `docs/사용자_매뉴얼.md` | 설치·실행·화면·업무 순서·파일 형식·AI 설정·재제출 비교·시연자료·문제 해결·시연 대본 |
| `docs/유지보수_안내.md` | 층·규칙·고칠 곳 찾기·파트/형식/자료 영역/오류 추가 방법·시험·버전 |
| `docs/설계서_v2.1.md` | 설계 원칙·형식 등록부·AI 검증 구조·재제출 비교·시험 결과·미검증 목록 |
| `docs/심사_검토서.md` | 심사 기준으로 본 v2.0 부족한 점과 v2.1 개선·추정 점수 |
| `docs/파트지도.md` | 구성요소·파일·함수·주소 전체(코드에서 자동 생성) |
| `진행현황.md` | 단계별 진행 기록 |

## 라이선스·자료

- 코드: 표준 라이브러리만 사용(외부 라이브러리 0). 휴대용 Python 을 넣으면 Python Software Foundation License 적용
- 시험 자료: 모두 가상(합성) 값. `tests/fixtures/formats/` 는 가상 값을 LibreOffice 로 형식만 바꾼 파일
