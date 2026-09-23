# 브라우저 실행판

## 사용자

1. Chrome 또는 Edge에서 `index.html`을 연다.
2. 처음 실행할 때는 인터넷에 연결한다.
3. 실험노트와 조회통계 `.xlsx` 파일을 선택한다.
4. 검증 결과를 확인한 뒤 최종 통합 Excel을 다운로드한다.

업로드한 Excel은 브라우저 내부에서 처리되며 앱 서버로 전송하지 않는다. 다만 최초
실행 시 stlite, Python 런타임, 필요 패키지를 CDN에서 받기 때문에 인터넷이 필요하다.

## 개발자

처리 규칙이나 화면을 수정한 뒤에는 반드시 `index.html`을 다시 생성한다.

```powershell
python build.py
```

`build.py`는 다음 소스를 하나의 HTML에 포함한다.

- 생성된 `app.py` 진입점
- `../src/ui.py`
- `../src/processor.py`

`index.html`의 stlite 버전을 변경할 때는 브라우저 테스트와 샘플 Excel 회귀 테스트를 다시 실행한다.
