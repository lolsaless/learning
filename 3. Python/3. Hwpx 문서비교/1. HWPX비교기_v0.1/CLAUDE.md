# CLAUDE.md — HWPX 변경이력 비교기 작업 안내 (Claude 가 가장 먼저 읽는 파일)

> 이 파일만 읽으면 언제 어디서든 작업을 이어갈 수 있게 정리했다.
> **작업을 마치면 맨 아래 「작업 기록」에 한 줄 추가하고, 구조가 바뀌면 「부품 지도」를 고친다.**

## 1. 한 줄 요약

같은 문서의 여러 HWPX 버전을 넣으면(원본 지정 없음) 문서 속 수정일 순으로 줄 세워
**무엇이 바뀌었는지(수정·추가·삭제·서식, 바뀌었다가 되돌아간 곳까지)** 브라우저 대시보드로 보여 주는 도구.

- 현재 버전: **v0.1.0** (최초 모델, 2026-11-02)
- 파이썬이 실제 작업(해석·비교), HTML 대시보드는 진행상황 확인·조정·결과 보기.
- **표준 라이브러리만 사용** (pip 설치 없음, 외부 CDN 없음) — 사용자가 내부망(공공기관)에서 쓰기 때문. 이 원칙은 깨지 않는다.

## 2. 사용자 맥락

- 사용자: 환경 연구(수질·대기·토양) 분석, 환경·행정자료 데이터 분석(Python·VSCode), 임상심리 보고서 작성.
- 대상 문서 예: 「2026년 행정사무감사 예상 쟁점목록」 (본문 + 표 21개, 셀 585개). 사람이 고친 곳을 **빨간 글자**로 표시하는 습관이 있음.
- 화면·주석·문서는 **한국어**, 쉬운 말로. 저장소 규칙: 폴더 `번호. 이름`, 버전 폴더 `N. 프로그램명_vX.Y`.
- 실제 업무 문서(첨부 HWPX)는 저장소에 넣지 않는다 → 시험은 `tests/sample_builder.py` 로 만든 가짜 HWPX 로.

## 3. 실행·시험

```bash
python HWPX비교기.py                         # 대시보드 (브라우저 자동, http://127.0.0.1:8765)
python HWPX비교기.py a.hwpx b.hwpx --report  # 화면 없이 결과 출력 (엔진 확인에 가장 빠름)
python HWPX비교기.py --folder 폴더 --html 결과.html
python -m unittest discover -s tests -v      # 시험 12개 (엔진 9 + 서버 3)
```
- 화면 확인은 Playwright(`chromium.launch()`)로 서버 띄워서 스크린샷. **주의: Playwright `setInputFiles` 에 한글 경로를 주면 파일이 안 들어감** → `{name, mimeType, buffer}` 형식으로 넘길 것.
- 파이썬 3.9 문법 호환 유지 (`ast.parse(..., feature_version=(3,9))` 로 확인).

## 4. 구조 (의존 방향: server → service → compare → hwpx, 거꾸로 부르지 않음)

```
HWPX비교기.py            실행 파일 (경로 설정 → hwpxdiff.cli.main)
hwpxdiff/
  __init__.py            VERSION, APP_NAME
  config.py              모든 설정값 (포트, 제목 기호, 비교 기본값, 서식 이름, 색 이름)
  cli.py                 명령줄 (대시보드 / --report / --html --csv --json)
  hwpx/                  ① HWPX 읽기 → Document
    package.py           zip 열기, content.hpf 메타·section 순서
    styles.py            header.xml charPr → 실제 속성(글꼴·크기·색·굵게…), 서식 차이 문장
    body.py              section XML → Block 목록 (본문 문단·표 셀·머리말·각주·글상자), 쪽 추정
    model.py             Run / Block / Document 자료형
  compare/               ② 비교 엔진 (화면·서버 모름, dict 반환)
    options.py           CompareOptions (대시보드 옵션과 1:1)
    textutil.py          정규화·토큰화·유사도
    align.py             블록 짝짓기 (difflib + 유사도 DP)
    inline.py            문단 안 글자 차이 조각(segments), 요약 문장
    formatting.py        같은 글자의 서식 변경, 새 글자 서식 안내
    differ.py            compare_documents() → {counts, changes, rows, meta_changes…}
    history.py           order_documents(), build_history() → 버전 흐름·이력 추적표(chains)
  service/workspace.py   ③ 작업공간: 문서 목록·백그라운드 해석 스레드·로그·결과 캐시
  server/                ④ 로컬 HTTP 서버 (http.server)
    app.py               정적 파일 + /api 분배, 127.0.0.1 전용, Origin 검사, 경로 탈출 차단
    routes.py            API 경로표 ROUTES (처리 함수 목록)
  export/reports.py      ⑤ CSV(엑셀 BOM)·HTML 보고서
web/                     대시보드 (빌드 없음, ES 모듈)
  index.html             화면 틀
  css/base.css           색 변수(밝은/어두운), 글꼴
  css/layout.css         배치(상단·왼쪽 패널·결과)
  css/components.css     버튼·목록·탭·로그·표 등 부품
  css/diff.css           삭제/추가 표시, 종류 배지, 나란히 보기, 이력표
  js/main.js             시작점: 탭, 폴링, 결과 재계산 시점
  js/api.js              서버 호출 모음 (routes.py 와 짝)
  js/store.js            화면 상태 + 이벤트(on/emit)
  js/util.js             이스케이프, 날짜, 조각 그리기(segHTML)
  js/ui/files.js         ① 파일 넣기(끌어놓기·폴더 순회) ② 버전 순서 목록
  js/ui/options.js       ③ 비교 옵션 (FIELDS 표)
  js/ui/progress.js      작업 상황(진행 막대·로그)
  js/ui/summary.js       [요약] 탭
  js/ui/compare.js       [두 버전 비교] 탭 (목록/나란히, 거르기·검색)
  js/ui/history.js       [이력 추적표] 탭
  js/ui/info.js          [문서 정보] 탭
tests/                   sample_builder.py(가짜 HWPX), test_engine.py, test_server.py
```

### 데이터 흐름
파일 → `Workspace.submit_*` → 해석 스레드 `load_document()` → `Document(blocks, styles, meta)`
→ (대시보드가 0.6~2.5초마다 `/api/status` 폴링, 완료 문서가 바뀌면) `/api/history` + `/api/compare`
→ `build_history` 가 인접 버전끼리 `compare_documents` (캐시) → rows 의 (ai,bi) 를 이어 chains.

## 5. 부품 지도 — 이런 수정은 여기를

| 하고 싶은 일 | 고칠 곳 |
|---|---|
| 새 비교 옵션 추가 | `config.DEFAULT_OPTIONS` → `compare/options.py` 필드 → 사용하는 엔진 코드 → `web/js/ui/options.js` FIELDS |
| 새 API 추가 | `server/routes.py` 함수 + ROUTES 등록 → `web/js/api.js` 한 줄 |
| 새 탭 추가 | `web/index.html` 탭 버튼·section → `web/js/ui/새탭.js` render 함수 → `main.js` RENDER 표 |
| 그림·도형·차트 안 글자 읽기 | `hwpx/body.py` SHAPES, `_collect()` |
| 구역 제목 인식 기호 | `config.HEADING_MARKERS` |
| 서식 비교 항목(예: 위첨자) | `hwpx/styles.py` parse_char_styles + `config.STYLE_LABELS` |
| 짝짓기 품질(수정↔삭제+추가 판정) | `compare/align.py` `_score`, 옵션 similarity |
| 글자 차이 표시 방식 | `compare/inline.py` (토큰 규칙은 `textutil._TOKEN`) |
| 변경 종류·꼬리표(숫자/표/서식/공백) | `compare/differ.py` `_compare_pair` |
| 되돌림 등 이력 분류 | `compare/history.py` `_classify`, CHAIN_LABELS |
| 보고서 형식 추가(xlsx 등) | `export/reports.py` + `routes.export` + index.html 메뉴 |
| 색·글꼴 | `web/css/base.css` :root 변수 |

## 6. HWPX 형식에서 알아낸 것 (중요)

- 첨부된 실제 파일에는 **한글 '변경 추적' 기록(hp:trackChange 등)이 없었다** → 파일 간 내용 비교 방식을 택함.
  (header.xml 에 `hh:trackchageConfig` 만 있음. 변경 추적을 켠 문서가 생기면 `hhs:` history 네임스페이스 해석 기능을 추가할 것 — 로드맵 참고)
- **charPr 번호는 파일마다 다르다.** 고친 글자에 새 번호(112~115)가 생기고 header.xml 개수가 달라짐 → 번호가 아니라 해석된 속성으로 비교 (`styles.style_key`).
- 한글은 수정한 곳에서 run 을 쪼갠다(`<hp:t>임유진 등</hp:t>` + `<hp:t> 4</hp:t>` + …) → 문단 단위로 글자를 합친 뒤 비교.
- 바뀌지 않은 곳에서도 `hp:lineseg vertpos`, `fieldBegin metaTag=""` 같은 배치·속성 잡음이 바뀐다 → XML 통째 비교는 쓸모없음, 의미 단위(글자·서식)로만 비교.
- 메타정보(content.hpf): `ModifiedDate`(UTC, 버전 순서 기준), `lastsaveby`, `creator`, `CreatedDate`. version.xml 에 한글 버전.
- 표 셀 위치: `hp:cellAddr colAddr/rowAddr` (0부터). 병합 셀은 `hp:cellSpan`.
- 쪽 번호: 줄 배치 `vertpos` 가 줄어들면 새 쪽으로 추정 (참고값, 화면에 '약 n쪽'/'추정' 표기).

## 7. 알려진 한계 (v0.1)

- HWP(5.0 바이너리 .hwp) 는 못 읽음 → 한글에서 HWPX 로 저장해서 넣어야 함.
- 문단 서식(정렬·들여쓰기·줄간격), 표 구조(행 추가·셀 병합 변화), 그림 내용 바뀜은 비교하지 않음 (그림 추가/삭제는 `[그림]` 표시로 잡힘).
- 같은 글자가 여러 번 나오는 큰 표에서 행을 끼워 넣으면 짝짓기가 어긋날 수 있음 (align.py REGION_LIMIT, 셀 위치 가산점으로 일부 완화).
- 쪽 번호는 추정값.
- 결과는 메모리에만 있음 (서버를 끄면 사라짐).

## 8. 다음 할 일 (로드맵 후보 — 사용자와 우선순위 정하기)

1. 원본 문서 모양으로 보기: section XML → 간이 HTML 렌더(표 모양 유지) 후 바뀐 곳 표시
2. 표 구조 비교: 행·열 추가/삭제를 '표 3에 2행 추가'로 요약
3. 한글 변경 추적(track change)·메모 해석 (있으면 작성자·시각까지)
4. 작업 저장/불러오기 (작업공간 JSON), 비교 결과 메모·확인 체크
5. 엑셀(xlsx) 보고서 — 표준 라이브러리로 zip+XML 직접 작성 (공문추출기 방식 참고)
6. 숫자 변경 강조 보고서 (환경 측정값·예산 수치 등 '숫자만' 모아 보기)
7. 실행 파일(.exe) 배포 — PyInstaller (`*.spec`, build/, dist/ 는 .gitignore 처리됨)

## 9. 작업 규칙

- 엔진(hwpx/, compare/)은 화면을 모른다: dict/JSON 으로만 돌려준다. 새 기능은 엔진 → 서비스 → 라우트 → 화면 순서.
- 기능을 바꾸면 `tests/` 에 시험 추가, `python -m unittest discover -s tests` 통과 확인.
- 버전 올리기: `hwpxdiff/__init__.py` VERSION + `문서/변경이력.md`. 큰 변경은 새 폴더 `2. HWPX비교기_v0.2` 로 복사 후 작업(저장소 관례).
- 커밋 메시지·문서에 모델 이름을 쓰지 않는다.

## 10. 작업 기록 (최신이 위)

- 2026-11-02 v0.1.0 최초 작성: HWPX 해석(본문·표·머리말·각주·글상자, 글자모양 해석), 블록 짝짓기, 글자/서식 비교,
  다중 버전 이력(되돌림 탐지), 로컬 서버 + 대시보드(요약·두 버전 비교·이력 추적표·문서 정보), CSV/HTML 보고서, 시험 12개.
  첨부 3개 파일(행정사무감사 쟁점목록 원본·1·2)로 확인: v1→v2 수정 4건(빨간 글자), v2→v3 수정 6·추가 1, 전체 이력 되돌림 4곳.
