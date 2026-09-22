# GC/MS Autotune 자동 판독 - 배포용 앱

기존 `gcms_autotune_ocr_eval.py`(터미널에서 인자 넣어 실행하는 CLI 도구)를
**드래그 앤 드롭으로 쓰는 데스크톱 앱**으로 감싼 버전입니다. 판독 로직 자체는
전혀 건드리지 않았고(`ocr_engine.py` = 원본 스크립트 그대로 + poppler 경로
설정 기능만 추가), 그 위에 화면(웹 UI)과 실행파일 포장만 새로 얹었습니다.

## 사용 방법 (사용자용)

1. `GCMS_Autotune_판독.app`(macOS) 또는 `GCMS_Autotune_판독.exe`(Windows)를
   더블클릭해서 엽니다. 설치 과정 없이 바로 실행됩니다.
2. 창이 뜨면 Autotune 리포트 PDF(또는 PNG/JPG)를 화면 가운데로 끌어다
   놓거나, 클릭해서 파일을 선택합니다.
3. 몇 초 후 판정 결과 표와 종합판정이 화면에 표시됩니다.
4. "평가서 PDF 다운로드" 버튼으로 A4 한 장짜리 평가서를 저장할 수 있습니다.
5. 업로드한 파일은 프로그램 내부(로컬)에서만 처리되며 외부로 전송되지 않습니다.

## 왜 순수 HTML(브라우저) 배포가 아니라 실행파일인가

이 프로그램은 Tesseract(OCR 엔진 실행파일)와 Poppler(PDF 렌더링 실행파일),
OpenCV(표 격자선 제거용 이미지 전처리)에 의존합니다. 전부 OS 네이티브 실행파일/
컴파일된 라이브러리라서 브라우저 WebAssembly 위에서 그대로 돌릴 수 없습니다.
그래서 참고 프로젝트 2(`map_marker.py`, Flask + pywebview 구조)를 따라
로컬 웹서버 + 데스크톱 창으로 만들고, PyInstaller로 실행파일에 포장했습니다.
Tesseract/Poppler 실행파일 자체를 `bin/` 폴더에 함께 넣어 배포하므로,
**사용자 PC에 Tesseract나 Poppler를 별도로 설치할 필요가 없습니다.**

## 파일 구성 (개발자용)

| 파일 | 역할 |
|---|---|
| `ocr_engine.py` | 원본 `gcms_autotune_ocr_eval.py`를 복사한 판독 엔진. **판독 로직을 고칠 때는 이 파일을 수정하세요.** (원본 파일은 상위 폴더에 CLI용으로 그대로 남아있습니다) |
| `app.py` | Flask(로컬 웹서버) + pywebview(데스크톱 창) 진입점. 번들된 tesseract/poppler 경로를 찾아 설정하고, 업로드된 파일을 `ocr_engine.py`로 판독해 결과를 반환합니다. |
| `static/` | 드래그 앤 드롭 업로드 화면 (index.html / style.css / app.js) |
| `bin/mac/`, `bin/windows/` | OS별로 번들할 tesseract, poppler 실행파일 위치. 실행파일에 포함되어 배포됩니다. |
| `build_mac.spec` / `build_mac.sh` | macOS 앱(.app) 빌드 |
| `build_windows.spec` / `build_windows.bat` | Windows 실행파일(.exe) 빌드 |

### 판독 로직을 수정했을 때

1. `ocr_engine.py`를 수정합니다 (ROI 좌표, CRITERIA_NOTE, 판정 로직 등).
2. 아래 "빌드 방법"대로 다시 빌드합니다.
3. `dist/` 안의 결과물을 다시 배포합니다.

개발 중에는 매번 빌드하지 않고 `python3 app.py`로 바로 실행해서 확인할 수
있습니다(이 경우 시스템에 설치된 tesseract/poppler를 사용합니다).

## 빌드 방법

### macOS

이미 이 폴더의 `bin/mac/`에는 테스트를 거쳐 완전히 독립 실행되는 tesseract/
poppler 바이너리가 준비되어 있습니다(Homebrew 등 별도 설치 없이 동작 확인
완료). 코드를 수정한 뒤 다시 빌드하려면:

```bash
pip install -r requirements.txt
./build_mac.sh
```

`dist/GCMS_Autotune_판독.app`이 생성됩니다.

다른 Mac에 새로 `bin/mac/`을 준비해야 한다면(바이너리가 없거나 손상된
경우), 아래 순서로 다시 만들 수 있습니다:

```bash
brew install tesseract poppler dylibbundler
cp /opt/homebrew/bin/tesseract bin/mac/tesseract
cp /opt/homebrew/bin/pdftoppm bin/mac/poppler/pdftoppm
cp /opt/homebrew/bin/pdfinfo bin/mac/poppler/pdfinfo
cp "$(brew --prefix tesseract)/share/tessdata/eng.traineddata" bin/mac/tessdata/eng.traineddata
chmod +w bin/mac/tesseract bin/mac/poppler/pdftoppm bin/mac/poppler/pdfinfo

dylibbundler -od -b -x bin/mac/tesseract -d bin/mac/libs/ -p @loader_path/libs/
dylibbundler -od -b -x bin/mac/poppler/pdftoppm -d bin/mac/poppler/libs/ -p @loader_path/libs/
dylibbundler -od -b -x bin/mac/poppler/pdfinfo -d bin/mac/poppler/libs/ -p @loader_path/libs/
```

> ⚠️ dylibbundler가 만드는 dylib 파일 이름(예: `libharfbuzz.0.dylib`)이
> PIL/OpenCV가 이미 쓰는 이름과 겹치면 PyInstaller가 서로 다른 버전을
> 하나로 합쳐버려 실행 시 `Symbol not found` 오류가 납니다. 실제로 이
> 프로젝트를 처음 빌드할 때 발생했던 문제이며, `bin/mac/libs/`,
> `bin/mac/poppler/libs/` 안의 파일 이름을 전부 `gcmsbin_` 접두사로 바꾸고
> 그 파일들을 참조하는 install name도 함께 고쳐서 해결했습니다. 새로
> 바이너리를 준비한다면 같은 방식으로 이름을 바꿔주는 것이 안전합니다.

macOS는 서명 인증서 없이 ad-hoc 서명으로 빌드합니다. 다른 Mac으로 옮겨
실행할 때 "확인되지 않은 개발자" 경고가 뜨면 앱을 우클릭 → 열기로 최초
1회 승인하면 됩니다.

### Windows

**PyInstaller는 크로스 컴파일을 지원하지 않으므로 반드시 Windows PC에서
빌드해야 합니다.** (이 문서는 macOS에서 작성되었고, Windows 실행파일은
아직 실제로 빌드/검증되지 않았습니다 — 아래 절차대로 진행한 뒤 꼭 직접
테스트해보세요.)

#### 1) Windows 바이너리 준비

`bin/windows/` 폴더를 아래처럼 구성합니다:

```
bin/windows/
├── tesseract.exe          (+ 함께 필요한 모든 .dll)
├── tessdata/
│   └── eng.traineddata
└── poppler/
    ├── pdftoppm.exe
    ├── pdfinfo.exe
    └── (함께 필요한 모든 .dll)
```

- **Tesseract**: [UB-Mannheim의 Windows용 tesseract 배포판](https://github.com/UB-Mannheim/tesseract/wiki)을
  설치한 뒤, 설치 폴더(보통 `C:\Program Files\Tesseract-OCR\`) 안의
  `tesseract.exe`, 같이 있는 `*.dll` 파일들, `tessdata\eng.traineddata`를
  그대로 복사해오면 됩니다. (설치 프로그램이지만 설치 후 폴더를 그대로
  복사해 옮기면 포터블처럼 쓸 수 있습니다.)
- **Poppler**: pdf2image 공식 문서가 안내하는
  [poppler-windows(oschwartz10612)](https://github.com/oschwartz10612/poppler-windows/releases/)
  릴리즈를 받으면 `Library\bin\` 안에 `pdftoppm.exe`, `pdfinfo.exe`와 필요한
  dll이 모두 들어있습니다. 그 폴더 내용을 `bin/windows/poppler/`에
  복사하세요.

두 프로그램 모두 오픈소스이며 실행파일 그대로 재배포가 허용됩니다(라이선스
고지 파일이 함께 있다면 같이 포함해두는 것을 권장합니다).

#### 2) 빌드

```
pip install -r requirements.txt
build_windows.bat
```

`dist\GCMS_Autotune_판독.exe` (단일 실행파일)가 생성됩니다.

서명되지 않은 exe이므로 처음 실행 시 Windows SmartScreen이 "이 앱이
사용자의 PC를 손상할 수 있습니다" 경고를 띄울 수 있습니다. "추가 정보" →
"실행"으로 진행하면 됩니다.

## 알려진 한계

- 이 프로그램의 OCR 판독은 100% 정확하지 않습니다. '확인필요'로 표시된
  항목은 반드시 원본 리포트와 대조 확인하세요 (`ocr_engine.py` 상단 설명
  참고).
- ROI 좌표는 MassHunter Autotune 표준 인쇄 양식 기준입니다. 양식이 다르면
  `ocr_engine.py`의 `ROI` 딕셔너리를 조정해야 합니다.
- macOS 앱은 OpenCV/NumPy 등을 포함해 배포 용량이 큽니다(약 400MB대).
  실행파일 배포 방식의 특성상 불가피합니다.
