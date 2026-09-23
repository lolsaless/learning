# Windows 데스크톱 배포

이 폴더는 Python과 Streamlit을 설치하지 않은 Windows PC에서 실행할 수 있는
설치 프로그램을 만든다. Python 처리 코드와 필요 라이브러리는 앱에 포함된다.

## 빌드 환경

- Windows 10/11
- Python 3.11 이상
- Node.js 22 LTS 이상

## 설치 파일 생성

```powershell
npm install
npm run dist
```

완료되면 `dist/IndoorAirQualityReport-1.0.0-Setup.exe`가 생성된다.

`src/processor.py` 또는 `src/ui.py`를 수정한 뒤에는 `npm run dist`를
다시 실행하면 최신 소스가 자동으로 복사된다.

## 배포 전 확인

- 조직의 코드 서명 인증서로 `.exe`에 서명하는 것을 권장한다.
- 폐쇄망용으로 배포할 때는 인터넷을 차단한 PC에서 실행 테스트한다.
- 빌드 산출물은 소스 관리에 포함하지 않고 릴리스 파일로 배포한다.
