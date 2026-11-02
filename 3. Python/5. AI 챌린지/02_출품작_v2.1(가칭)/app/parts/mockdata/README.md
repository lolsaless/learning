# 가상자료 파트 (`parts/mockdata`)

## 하는 일
무작위 가상 기관 하나의 '요구자료 작성 상황'을 통째로 만든다: 원본 엑셀(배치·머리글·단위가 문서와 다름), 팀 답변서, 오류를 심은 취합본, 작성틀, 공문(hwpx·odt), 참고자료, 재제출본, 정답표. 자동 평가(app/evaluation.py)가 이 정답표로 검증 엔진을 채점한다.

## 파일(만드는 순서)
| 번호 | 파일 | 하는 일 |
|---|---|---|
| ① | vocab.py | 가상 사전(기관·시군·하천·측정소·사람 이름·주소·하단 문구) |
| ② | model.py | 요구자료 표 하나(DataTable): 진짜 값·표시 자릿수·합계·비율·원본 머리글·배율 |
| ③ | domains.py | 자료 영역 12종(하천 수질·대기·예산·실적·민원 …). 표시값으로 다시 계산해도 맞는 정상 표만 만든다 |
| ④ | sources.py | 원본 엑셀 배치 변형(뒤집기·섞기·열/행 더하기·합계 유무·사용안내·세부기록·월별 시트) + 칸 위치 기록 |
| ⑤ | errors.py | 오류 9종 심기 + 연쇄 표시 + 정상 사례 → 정답표 항목 |
| ⑥ | render.py | 문서 모형 → hwpx·odt 파일 |
| ⑦ | reports.py | 팀 답변서·취합본·작성틀 문서 모형 |
| ⑧ | gongmun.py | 가상 공문(요구·검사 의뢰·결과 알림·협조 요청) |
| ⑨ | guides.py | 참고자료(시험법 요약본·장비 점검 매뉴얼·작성 지침) |
| ⑩ | resubmit.py | 재제출본(같은 이름·바뀐 이름)과 바뀐 칸 정답 |
| ⑪ | scenario.py | 위를 모두 조립해 시나리오 폴더 하나를 만든다 |
| | part.py | MockDataPart — 만들기·목록 |
| | routes.py | 화면 주소 |

## 입구(다른 곳에서 부르는 기능)
- MockDataPart().generate(seed, size, errors, kinds, gongmun, guides, form, resubmit, fmt) — 시나리오 하나 만들기
- MockDataPart().list() — 만든 시나리오 목록
- Scenario(저장 위치, …).run() — 명령줄(tools/make_mock.py)·자동 평가에서 직접 사용

## 출구(내놓는 것)
- `<프로그램 폴더>/시연자료_무작위/<도이름>_<씨앗값>/` 폴더와 그 안의 `정답표.json`, `시나리오_안내.md`

## 화면 주소
/api/mock/options · /api/mock/list · /api/mock/generate

## 고칠 때 알아 둘 것
- 새 자료 영역: domains.py 에 make_<이름>() 를 만들고 DOMAINS 와 DOMAIN_TITLES 에 넣는다.
- 새 오류 종류: errors.py 의 KINDS·KIND_NAMES·EXPECT 에 넣고 Injector.e_<종류>() 를 만든다.
- 같은 씨앗값이면 같은 자료가 나온다(난수 순서를 바꾸면 예전 씨앗값의 자료가 달라짐 — 평가 기록과 비교할 때 주의).
- 실제 공문·설명서에서는 서식의 '틀'만 참고했다. 실제 이름·주소·번호를 넣지 않는다(대회 규칙).
- 이 파트는 다른 파트를 import 하지 않는다. 채점은 app/evaluation.py(평가 조립부)가 한다.

## 시험
tests/test_mockdata.py(생성·정답표·재현성·평가) · tests/test_structure.py(구조 규칙)
