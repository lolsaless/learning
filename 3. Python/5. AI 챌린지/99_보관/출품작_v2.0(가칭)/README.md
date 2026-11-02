# 취합검증 도우미(가칭) v2.0

**요구자료 취합 문서(hwpx)의 숫자마다 원본 엑셀 출처를 찾아 대조하고, 고친 값과 출처를 이력으로 남기는 도구**
(이름은 가칭 — `app/config.py` 의 `APP_NAME` 한 줄로 바꿈)

- 형식: HTML 화면 + Python 로컬 서버(표준 라이브러리만, Python 3.8 이상, 패키지 설치 없음, 인터넷 불필요, 127.0.0.1 전용)
- 판정: 규칙·계산(AI 판정 없음)
- 구조: 5개 층(U 화면 · W 화면 연결 · A 조립부 · P 기능 파트 8개 · B 바탕). 파트끼리는 서로 부르지 않는다
- 시연자료: 고정 시연(한빛도, 정답표 18개) + **무작위 시연자료 생성기**(가상 기관·공문·참고자료·재제출본·정답표) + **자동 평가**

## 실행(더블클릭)

| Windows | Mac | 하는 일 |
|---|---|---|
| `실행_Windows.bat` | `실행_Mac.command` | 프로그램 실행 → 브라우저 `http://127.0.0.1:8765` |
| `시연자료_만들기_Windows.bat` | `시연자료_만들기_Mac.command` | 무작위 시연자료 3개 |
| `자동평가_Windows.bat` | `자동평가_Mac.command` | 무작위 20개로 자동 평가 → `평가결과/` |
| `시험_전체실행_Windows.bat` | `시험_전체실행_Mac.command` | 자동 시험 전체 |
| `기본시연자료_다시만들기_Windows.bat` | `python3 tools/make_demo.py` | 고정 시연자료 다시 만들기 |

## 화면

1 작업 준비 · 2 검증 · 3 입력하기 · 4 이력 · 5 시연자료(만들기·채점·자동 평가) · 6 구성도(파트 지도) · 7 설정·도움말

## 구성(자세히: 6 구성도 탭, `docs/파트지도.md`)

| 층 | 구성요소 |
|---|---|
| U 화면 | `app/ui/` 뼈대 + 페이지 7개(html·js 한 쌍씩) |
| W 화면 연결 | `app/web/` 서버 · 공통 주소 · 평가 주소 · 시연 준비 · 폴더 탐색 · 파트 지도 |
| A 조립부 | `app/workspace.py`(작업) · `app/evaluation.py`(평가) · `app/main.py`(시작점) |
| P 기능 파트 | `app/parts/` 원본 · 문서 · 검증 · 수정·입력 · 이력 · 내보내기 · 클립보드 · 가상자료 |
| B 바탕 | `app/config.py` · `common/` · `formats/`(hwpx·xlsx·odt) · `store/` |

## 명령줄

```
python tests/run_all.py                                   # 구조 5 + 기능 20 + 가상자료 6 → '전체 통과'
python tools/make_mock.py --count 5 --size 크게 --seed 777 # 무작위 시연자료
python tools/evaluate.py --n 100 --size 보통               # 자동 평가 보고서
python tools/part_map.py                                  # docs/파트지도.md 다시 만들기
python tests/e2e_ui.py · tests/e2e_mock.py                 # 화면 시험(서버를 켠 뒤, Playwright 필요)
```

## 문서

| 문서 | 내용 |
|---|---|
| `docs/사용자_매뉴얼.md` | 설치·실행·화면·업무 순서·시연자료·자동 평가·문제 해결·시연 대본 |
| `docs/유지보수_안내.md` | 층·규칙·고칠 곳 찾기·파트/자료 영역/오류 추가 방법·시험·버전 |
| `docs/파트지도.md` | 구성요소·파일·함수·주소 전체(코드에서 자동 생성) |
| `docs/설계서_v2.0.md` | 설계 원칙·새 파트 설계·일정 |
| `진행현황.md` | 단계별 진행 기록 |
