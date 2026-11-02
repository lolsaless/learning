# CLAUDE.md — HWPX 비교기 작업 안내 (Claude 가 가장 먼저 읽는 파일)

> 이 파일만 읽으면 언제 어디서든 작업을 이어갈 수 있게 정리했다.
> **작업을 마치면 맨 아래 「작업 기록」에 한 줄 추가하고, 구조가 바뀌면 「부품 지도」를 고친다.**

## 1. 한 줄 요약

같은 문서의 여러 HWPX 버전을 넣으면 **원본·갈래(관계도)를 추정하고, 바뀐 곳을 문서 모양 그대로 보여 주고,
원하는 변경만 골라 깨짐 없이 병합하고, 직접 고쳐서 새 버전을 만들며, 원본/수정본/최종본 폴더와 이력(JSON)으로 관리**하는 도구.

- 현재 버전: **v2.0.0** (2026-11-02) — 위치 `3. Python/3. Hwpx 문서비교/3. HWPX비교기_v2.0/`
  (이전 판 `1. HWPX비교기_v0.1/`, `2. HWPX비교기_v1.1/` 은 보관용, 고치지 않음)
- 파이썬이 실제 작업, HTML 대시보드는 진행상황 확인·조정·결과 보기·고르기.
- **표준 라이브러리만 사용** (pip 설치 없음, 외부 CDN 없음) — 사용자가 내부망(공공기관)에서 쓰기 때문. 이 원칙은 깨지 않는다.
  예외는 **선택 기능**인 pywin32(한글 자동화)뿐이며, 없어도 모든 기능이 동작해야 한다 (`bridge/hangul.py` 가 알아서 끔).

## 2. 사용자 맥락

- 사용자: 환경 연구(수질·대기·토양) 분석, 환경·행정자료 데이터 분석(Python·VSCode), 임상심리 보고서 작성. Windows + 한글 설치됨.
- 대상 문서 예: 「2026년 행정사무감사 예상 쟁점목록」 (본문 + 표 21개, 셀 585개). 사람이 고친 곳을 **빨간 글자**로 표시하는 습관.
- 실제 상황: 원본 하나를 여러 사람이 각자 고침 → **갈래(형제) 버전**이 생김. (첨부 `_1`, `_2` 가 바로 이 경우였다)
- 화면·주석·문서는 **한국어**, 쉬운 말로. 저장소 규칙: 폴더 `번호. 이름`, 버전 폴더 `N. 프로그램명_vX.Y`.
- 실제 업무 문서(첨부 HWPX)는 저장소에 넣지 않는다 → 시험은 `tests/sample_builder.py` 로 만든 가짜 HWPX 로.
- 사용자가 한글에서 직접 열어 확인해 준 것: **v2 병합 결과(문단 갈아 끼우기 방식) — 정상 열림** (2026-11-02).

## 3. 실행·시험

```bash
python HWPX비교기.py                                  # 대시보드 (브라우저 자동, http://127.0.0.1:8765)
python HWPX비교기.py --project D:\업무\감사2026        # 프로젝트 열고 대시보드
python HWPX비교기.py a.hwpx b.hwpx --report           # 화면 없이 결과 출력
python HWPX비교기.py --folder 폴더 --merge 최종.hwpx   # 화면 없이 원본 판정 + 모든 갈래 병합
python -m unittest discover -s tests -v               # 시험 32개 (엔진 9 + 문서보기 6 + 서버 3 + v2 14)
```
- 화면 확인은 Playwright(`chromium.launch()`)로 서버 띄워서 스크린샷. **Playwright `setInputFiles` 에 한글 경로를 주면 파일이 안 들어감**
  → `{name, mimeType, buffer}` 로 넘길 것. 라디오를 고르면 화면이 다시 그려지므로 `check()` 대신 `click()`.
- 이 개발 컨테이너에는 tkinter 가 없어 [찾아보기] 폴더 창은 오류 안내가 정상 (Windows 파이썬에는 있음).
- 파이썬 3.9 문법 호환 유지 (`ast.parse(..., feature_version=(3,9))` 로 확인).

## 4. 구조 (의존 방향: server → service → {project, bridge, render, merge, lineage} → compare → hwpx)

```
HWPX비교기.py              실행 파일 (경로 설정 → hwpxdiff.cli.main)
설치_pywin32.bat           (선택) 한글 자동화용 pywin32 설치 — vendor/ 의 파일로 오프라인, 없으면 인터넷
vendor/                    받기_pywin32.bat(인터넷 PC 에서 .whl 받기), README.md. *.whl 은 git 에 안 올림
hwpxdiff/
  __init__.py              VERSION, APP_NAME
  config.py                설정값 (포트, 제목 기호, 비교 기본값, 서식 이름, 색 이름)
  cli.py                   명령줄 (대시보드 / --report / --html --csv --json / --merge / --project)
  hwpx/                    ① HWPX 읽기 → Document
    package.py             zip 열기, content.hpf 메타·section 순서, xml_spans(위치 기억 읽기)
    xmlspan.py             (v2) expat 으로 읽으며 요소마다 원문 바이트 위치(시작,끝) 기록 ← 병합·고치기의 바탕
    styles.py              charPr/paraPr/borderFill 해석, 서식 차이 문장
    body.py                section XML → Block 목록 + layout 트리 (+ v2: 블록·노드마다 원문 위치 span)
    model.py               Run / Block(span) / Document(raw 원본 bytes, section_names, layout …)
  compare/                 ② 비교 엔진 (dict 반환) — v1 과 같음
  render/                  ③ 문서 모양 보기 (v1.1) + v2: render_merge(병합 화면), 끼울 글(초록 상자), data-bi(블록 순번)
  merge/                   ④ (v2) 깨짐 없는 HWPX 쓰기
    resources.py           HeaderMerger: 가져온 조각의 모양 번호(글자·문단모양·테두리·탭·스타일·글꼴)를 받는 문서 번호로,
                           없으면 목록 끝에 덧붙임. canonical()=속성 순서·기본값(textDir="LTR") 무시하고 같은 모양 판정
    engine.py              plan_merge(원본, 버전들) → 항목·선택지·충돌 / apply_merge(…, choices) → 새 HWPX bytes
    edit.py                edit_document(문서, {블록: 새 글자}, 표시색) → 새 HWPX (원본 서식 이어받기)
  lineage/__init__.py      ⑤ (v2) analyze(): 원본·최종본 추정(점수·근거), 부모 관계(나무), 갈래 여부, 알림 문장
  project/__init__.py      ⑥ (v2) Project: 폴더(1_원본/2_수정본/3_최종본/4_보관/5_보고서) + project.json
  bridge/                  ⑦ (v2) system.py: 기본 프로그램(한글)으로 열기, 폴더 고르기 창(tkinter 를 별도 프로세스)
                                  hangul.py: pywin32 한글 자동화(다시 저장·PDF) — 없으면 꺼짐
  service/workspace.py     작업공간: 문서(id=SHA-1 앞 12자리)·해석 스레드·로그·캐시 + v2: 역할·부모·계보·병합·고치기·프로젝트·한글
  server/                  로컬 HTTP 서버 (app.py) + API 경로표 (routes.py, v2 경로는 _guard 로 오류를 400/404 로)
  export/reports.py        CSV·HTML 보고서 (프로젝트가 열려 있으면 5_보고서 에도 저장 가능)
web/                       대시보드 (빌드 없음, ES 모듈)
  index.html               화면 틀 (상단 프로젝트 막대·한글 상태, 탭 7개, 대화창·말풍선 자리)
  css/                     base·layout·components·diff·docview-ui + v2.css(프로젝트·대화창·관계도·병합·말풍선·고치기)
  js/main.js               시작점: 탭, 폴링, 결과/관계 다시 계산 시점, 탭 사이 이동 이벤트
  js/api.js                서버 호출 모음 (routes.py 와 짝)
  js/store.js              화면 상태 + on/emit + ensurePair, ROLE_LABEL, nameOf
  js/util.js               이스케이프, 날짜, segHTML, toast, dialog(대화창), ROLE_CLASS
  js/ui/project.js         (v2) 프로젝트 막대: 새로 만들기·열기·닫기·이력, [찾아보기] 폴더 창, 한글 연동 표시
  js/ui/graph.js           (v2) [관계도] SVG: 노드 끌기·화면 이동·확대, 선=비교, 역할 지정·부모 지정·작업 버튼
  js/ui/merge.js           (v2) [병합] 원본 위 표시 + 말풍선(마우스 올리면 버전별 변경·바로 고르기) + 목록 + 미리보기 + 저장
  js/ui/docview.js         [문서 보기·고치기] (v1.1 보기 + v2 고치기 모드: 문단 누르면 대화창, 고친 곳 목록, 수정본 저장)
  js/ui/files.js           파일 넣기·순서 목록 (+ v2 역할 배지, 한글에서 열기, 내려받기)
  js/ui/summary.js         [요약] (+ v2 갈래 알림·관계도/병합 바로가기)
  js/ui/compare.js · history.js · info.js · options.js · progress.js   (v1 과 같음)
tests/                     sample_builder.py(가짜 HWPX: 덧붙인 글자모양·표 제목 문단·글꼴 등), test_engine/render/server/v2.py
```

### 데이터 흐름
- 넣기: 파일 → `Workspace._enqueue`(id=SHA-1) → 해석 스레드 `load_document()` → `Document(blocks+span, layout+span, raw)`
  → 프로젝트가 열려 있으면 `Project.add` 로 2_수정본 에 복사.
- 관계: `/api/lineage` → `lineage.analyze(docs, compare, 지정 부모, 지정 역할)` → nodes/edges/notes (캐시).
- 병합: `/api/merge/plan` → `plan_merge`(버전마다 compare(원본, 버전) → 행(row)마다 선택지; 같은 원본 자리 = 같은 항목)
  → 화면에서 choices → `/api/merge/preview|save` → `apply_merge`: 원본 section 바이트에 갈아 끼우기(splice) + `HeaderMerger.build()`.
- 고치기: `/api/edit/save {doc, edits:{블록: 글자}}` → `edit_document` → 새 문서(부모=고친 문서, 최종본을 고쳤으면 새 최종본).

### 병합 방식 (가장 중요 — 바꿀 때 반드시 시험 + 한글 확인)
| 변경 | 방식 (mode) |
|---|---|
| 문단 수정 (안에 표·글상자 없음) | `element`: 원본 `<hp:p>…</hp:p>` 를 버전 것으로 통째 교체 |
| 표 칸 수정·비우기·채우기 | `cell`: 칸 안 첫 문단 시작~마지막 문단 끝을 교체 (표 번호는 짝지어진 칸들의 투표로 대응) |
| 표를 품은 문단의 글자 | `own`: run 을 '글자 run 묶음(gap)'과 '고정 run(anchor: 표·필드·컨트롤)'으로 나눠 **gap 만 교체** |
| 문단 삭제 | `delete` (안에 표가 있으면 `own` 으로 글자만 지움) |
| 새 문단 | `insert`: 바로 앞 짝지어진 블록의 **본문 최상위 문단 끝**에 버전의 최상위 문단을 끼움 |
| 그림 든 조각, 머리말·각주 안 새 글 등 | `unsupported` (이유 표시, 한글에서 직접) |
- 같은 원본 자리를 두 버전이 **다르게** 고치면 충돌(기본 원본 유지), **똑같이** 고치면 same(한 번만).
- 바깥 칸 교체가 안쪽 변경을 포함하면 안쪽은 `includes` 로 흡수(중복 적용 방지).
- 원본 파일의 다른 부분은 한 바이트도 바꾸지 않는다. Preview/* 도 그대로(한글로 저장하면 새로 생김). ModifiedDate 만 지금 시각으로.

## 5. 부품 지도 — 이런 수정은 여기를

| 하고 싶은 일 | 고칠 곳 |
|---|---|
| 새 비교 옵션 | `config.DEFAULT_OPTIONS` → `compare/options.py` → 엔진 → `web/js/ui/options.js` FIELDS |
| 새 API | `server/routes.py` 함수(+`@_guard`) + ROUTES → `web/js/api.js` |
| 새 탭 | `index.html` 탭·section → `web/js/ui/새탭.js` → `main.js` RENDER·showTab |
| 원본·부모 추정 규칙(점수) | `lineage/__init__.py` analyze (근거 문장 reasons 도 함께) |
| 병합 가능한 변경 종류 늘리기 (예: 그림 복사) | `merge/engine.py` `_options_for_version` + `_op_splices` (+ BinData·manifest 복사) |
| 병합 시 같은 모양 판정이 어긋남(모양 중복 추가) | `merge/resources.py` `IGNORABLE_DEFAULTS`, `canonical` |
| 모양 번호 종류 추가 (numbering·bullet 등) | `merge/resources.py` KINDS, REF_RE |
| 고치기 허용 범위 (특수 요소) | `merge/edit.py` `_items_of_unit` (anchor 규칙), SIMPLE |
| 고친 글자 서식 규칙 | `merge/edit.py` `_rebuild` (앞 글자 이어받기, color_cid) |
| 프로젝트 폴더 이름·json 형식 | `project/__init__.py` FOLDERS, SCHEMA (형식 바꾸면 SCHEMA 버전 올리고 open 에서 변환) |
| 한글 자동화 동작 | `bridge/hangul.py` (HWPFrame.HwpObject, RegisterModule) |
| 관계도 모양·배치 | `web/js/ui/graph.js` W,H,GX,GY, autoLayout, drawNodes / `css/v2.css` .gr-* |
| 병합 화면·말풍선 | `web/js/ui/merge.js` (itemHTML, optionsHTML, showPop) / `render/__init__.py` render_merge |
| 문서 모양 재현 | `render/document_view.py` (_pcss, _ccss, _table) |
| 그 밖의 v1 항목 | 비교(`compare/*`), 보고서(`export/reports.py`), 색(`css/base.css`) |

## 6. HWPX 형식에서 알아낸 것 (중요)

- 첨부 실제 파일에는 **한글 '변경 추적' 기록이 없었다** → 파일끼리 내용 비교. (`hh:trackchageConfig` 만 있음)
- **charPr 번호는 파일마다 다르다.** 고치면 새 글자모양이 **목록 끝에** 붙는다. **한글은 안 쓰는 글자모양도 지우지 않는다**
  (원본에 미사용 30개 존재) → 목록의 '앞부분 일치(접두)'로 조상 관계를 추정할 수 있다 (lineage 근거 ①).
  첨부 `_1`·`_2` 는 둘 다 원본 112개 뒤에 112번을 붙였는데 **내용이 서로 달라**(11pt 빨강 굵게 / 15pt 빨강) 형제로 판정.
- **한글 13 과 12 는 같은 문단모양을 다르게 쓴다**: 13 은 paraPr 에 `textDir="LTR"` 를 쓰고 12 는 생략 → 바이트 비교 금지, `canonical` 로.
- XML 을 ElementTree 로 읽고 다시 쓰면 접두어(hp:)가 ns0: 로 바뀌어 위험 → **원문 바이트 갈아 끼우기**만 한다 (`xmlspan`).
  expat 은 스스로 닫힌 요소(`<a/>`)의 끝 위치를 '다음 토큰' 으로 알려 준다 → 시작 태그가 `/>` 로 끝나는지로 판별.
- 한글은 수정한 곳에서 run 을 쪼갠다 → 문단 단위로 글자를 합친 뒤 비교. 바뀌지 않은 곳에서도 lineseg vertpos·`fieldBegin metaTag=""`
  같은 잡음이 바뀐다 → 의미 단위(글자·서식)로만 비교.
- 수식 칸: `<hp:run><hp:ctrl><hp:fieldBegin type="FORMULA"/></hp:ctrl><hp:t>24</hp:t><hp:ctrl><hp:fieldEnd/></hp:ctrl></hp:run>`
  처럼 글자와 컨트롤이 한 run 에 섞임 → 고치기에서는 컨트롤을 같은 글자모양의 별도 run(anchor)으로 떼어 제자리 고정.
- 첫 문단에는 `hp:secPr`(용지)·`hp:colPr` 컨트롤 run 이 있다 → anchor 로 보존.
- 고친 문단은 `hp:linesegarray`(줄 배치 캐시)를 빼서 한글이 다시 계산하게 함 — **한글 확인 대기 중** (작업 기록 참고).
- 메타(content.hpf): `ModifiedDate`(UTC), `lastsaveby`, `creator`, `CreatedDate`(같으면 같은 문서 가족). version.xml 에 한글 버전.
- paraPr 여백은 `hp:switch` 안 `hp:case`(정상 값) / `hp:default`(옛 프로그램용 2배 값) → case 사용.
- 단위: HWPUNIT = 1/7200 인치 → px = 값/75. height 1000 = 10pt. A4 = 59528×84188.
- 표: `hp:tr` 에는 실제 칸만, 합침은 `hp:cellSpan`. 테두리·배경 = `borderFillIDRef` → `hh:borderFill`.

## 7. 알려진 한계 (v2.0)

- HWP(5.0 .hwp) 못 읽음 → 한글에서 HWPX 로 저장.
- 병합: 그림이 든 변경, 머리말·각주 안 새 글·삭제, 문단↔표 칸 종류 변경, 표 구조(행·열 추가) 변경은 자동 적용 안 함(이유 표시).
  새 문단 앞뒤의 '빈 줄'은 옮기지 않음. 문단모양만 바뀐 변경은 감지하지 않음(글자·글자 서식만).
- 고치기: 표·글상자를 품은 문단은 불가. 한 문단 안 여러 수정 중 일부만 고르기는 병합에서 불가(문단 단위).
- 관계 추정은 근거 기반 '추정' — 화면에서 직접 지정하면 그것을 따른다(프로젝트에 기록).
- 쪽 번호는 추정값. 문서 보기는 그림을 [그림] 글자로만.

## 8. 다음 할 일 (로드맵 후보)

1. 고치기 결과 한글 확인 후: 확인되면 이 줄 지우기 / 문제 있으면 linesegarray 를 남기는 방식으로 바꾸기(`merge/edit.py`)
2. 병합 시 그림(BinData) 복사, 표 행 추가·삭제 병합
3. 한 문단 안 변경 조각 단위 고르기 (inline segments 를 run 으로 재구성)
4. 문단모양(정렬·들여쓰기) 변경 감지·병합
5. 엑셀(xlsx) 보고서, 숫자 변경만 모아 보기 (환경 측정값·예산)
6. 실행 파일(.exe) — PyInstaller (pywin32 포함 가능)
7. 한글 변경 추적(track change)·메모가 든 문서 해석

## 9. 작업 규칙

- 엔진(hwpx/compare/merge/lineage)은 화면을 모른다: dict/bytes 만 돌려준다. 새 기능은 엔진 → 서비스 → 라우트 → 화면 순서.
- **HWPX 를 쓰는 코드를 바꾸면**: `tests/test_v2.py` 통과 + 실제 문서로 만든 결과를 사용자에게 한글로 열어 확인받는다.
- 기능을 바꾸면 `tests/` 에 시험 추가, `python -m unittest discover -s tests` 통과 확인.
- 버전 올리기: `hwpxdiff/__init__.py` VERSION + `문서/변경이력.md` + 이 파일. 기능 추가는 새 폴더(`4. HWPX비교기_v2.1` 등)로 복사 후 작업,
  상위 `3. Hwpx 문서비교/CLAUDE.md`·`README.md` 의 '최신 버전' 과 저장소 최상위 README 폴더 안내도 고친다.
- 커밋 메시지·문서에 모델 이름을 쓰지 않는다.

## 10. 작업 기록 (최신이 위)

- 2026-11-02 v2.0.0 관계도·병합·고치기·프로젝트·한글 연동.
  · 위치 기억 XML 읽기(xmlspan) + 블록/배치 노드 원문 위치(span) → 바이트 갈아 끼우기 병합(engine) — 첨부 3개 병합 결과가
    사용자가 한글에서 정상 열림을 확인한 시험 파일과 section·header 가 **바이트 단위로 동일**함을 확인.
  · 모양 번호 맞추기(HeaderMerger, 한글 13/12 textDir 차이 처리), 직접 고치기(edit, 610/612 블록 가능, 수식 필드 보존),
    계보 분석(lineage: 첨부 `_1`·`_2` = 원본의 형제 갈래로 판정 → v1.1 의 '되돌림 4곳' 해석은 잘못이었음),
    프로젝트(폴더 5개 + project.json, 최종본 교체 시 이전 것 4_보관), 한글 연동(기본 열기 + pywin32 다시 저장·PDF, 설치_pywin32.bat).
  · 화면: [관계도](끌어서 옮기기·확대·역할/부모 지정), [병합](마우스 올리면 버전별 변경 말풍선·바로 고르기·미리보기·저장),
    [문서 보기·고치기], 프로젝트 막대, 파일 목록 역할 배지·한글 열기·내려받기, 요약 갈래 알림. CLI --merge/--project. 시험 32개.
  · 사용자 확인 대기: 고치기 시험 파일(고친 문단의 줄 배치를 한글이 다시 계산하는지).
- 2026-11-02 v1.1.0 원본 문서 모양 보기 ([문서 보기] 탭, render/ 패키지, 문서 모양 보고서). 시험 18개.
- 2026-11-02 v0.1.0 최초: 해석·비교·이력 추적·대시보드·보고서. 시험 12개.
