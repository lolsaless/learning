# 실내공기질 실적 정리

실험노트와 조회통계 Excel을 검증·병합하여 다중이용시설과 공동주택 실적을 생성한다.

## 폴더 구성

```text
app.py              Streamlit 실행 진입점
src/                검증·집계 로직과 UI
samples/            회귀 테스트용 Excel
tests/              자동 테스트
browser/            단일 HTML 배포판
desktop/            Windows 설치 파일 빌드
requirements.txt    Python 버전 고정
```

## 로컬 실행

Python 3.11 이상을 사용한다.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

macOS/Linux에서는 `.venv\Scripts\Activate.ps1` 대신 `source .venv/bin/activate`를 사용한다.

## 사용자 배포

- 브라우저용: `browser/index.html`을 배포한다. 최초 실행에 인터넷이 필요하다.
- Windows 설치형: `desktop/README.md`에 따라 `.exe`를 생성한다.

## 출력

`실내공기질_실적_통합.xlsx`에 다음 시트를 생성한다.

- `처리요약`
- `다중이용시설`
- `기존신축공동주택`
- `검증결과`

입력 접수번호가 중복되거나 두 파일 간에 불일치하면 조용히 누락시키지 않고 처리를 중단한다.
주소·부적합항목 등이 집계 그룹 내에서 다르면 고유값을 모두 보존하고 `검증결과`에 남긴다.
`불검출`은 현재 규칙에 따라 평균에서 제외하고 건수를 경고한다.

## 테스트

```powershell
python -m unittest discover -s tests -v
python browser/build.py
```
