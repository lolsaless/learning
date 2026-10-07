# 이미지 변환기 (HEIC → JPG / PNG / WEBP)

iPhone 사진(HEIC/HEIF)을 JPG, PNG, WEBP로 변환하는 도구입니다. 두 가지 방식으로 쓸 수 있습니다.

| 파일 | 용도 |
|---|---|
| `heic_to_jpg.py` | 내 컴퓨터에서 실행하는 Python 스크립트. 폴더 선택 창이 열립니다. |
| `heic_converter.html` | 브라우저에서 쓰는 변환기. 파일/폴더를 드래그해서 변환합니다. 설치가 필요 없습니다. |

---

## 1. HTML 버전 (`heic_converter.html`)

### 실행
- 파일을 더블클릭하거나 브라우저(Chrome, Edge, Safari, Firefox)로 끌어다 놓으면 됩니다.
- 웹 서버에 올려 배포하려면 이 파일 하나만 올리면 됩니다.
- 변환 라이브러리를 CDN에서 불러오므로 **처음 열 때 인터넷 연결이 필요**합니다.
- 사진은 브라우저 안에서만 처리되며 서버로 전송되지 않습니다.

### 사용 순서
1. 파일이나 폴더를 점선 영역으로 드래그합니다. "파일 선택", "폴더 선택" 버튼도 쓸 수 있습니다. 폴더를 넣으면 하위 폴더 안의 이미지까지 읽습니다.
2. 옵션을 고릅니다.
   - **출력 형식**: JPG / PNG(무손실) / WEBP
   - **화질**: 10~100. 낮을수록 용량이 작아집니다. PNG는 무손실이라 비활성화됩니다.
   - **파일당 최대 용량(MB)**: 0이면 제한이 없습니다. 값을 주면 용량 안에 들어올 때까지 화질, 해상도 순으로 줄입니다.
3. **변환 시작**을 누릅니다. 파일마다 진행 상태가 표시됩니다.
4. 결과를 받습니다. 각 줄의 `↓ 용량` 링크로 하나씩 받거나, **ZIP으로 받기**로 한 번에 받습니다.

### 지원 입력 형식
HEIC, HEIF, JPG, PNG, WEBP, GIF, BMP, AVIF. 이미지가 아닌 파일은 목록에 추가되지 않습니다.

### 문제 해결
| 증상 | 원인 / 해결 |
|---|---|
| 상단에 빨간 "라이브러리를 불러오지 못했습니다" 표시 | 인터넷 연결 또는 CDN 차단 문제입니다. 연결을 확인하고 새로고침하세요. |
| 특정 파일이 "실패"로 표시됨 | 파일 아래 빨간 글씨로 원인이 표시됩니다. 파일이 손상됐거나 지원하지 않는 형식일 수 있습니다. |
| WEBP 변환 실패 | 일부 Safari 버전은 WEBP 저장을 지원하지 않습니다. JPG나 PNG를 쓰세요. |
| 큰 파일이 많을 때 느리거나 멈춘 듯함 | 4000×3000 사진 한 장에 1~3초가 걸립니다. 수백 장은 나눠서 변환하세요. 한꺼번에 많이 하면 메모리를 많이 씁니다. |
| PNG 용량이 매우 큼 | PNG는 무손실이라 사진 한 장이 15MB 안팎입니다. 용량이 중요하면 JPG나 WEBP를 쓰세요. |

---

## 2. Python 버전 (`heic_to_jpg.py`)

### 설치 (최초 1회)
```bash
pip install pillow pillow-heif
```
Python 3.9 이상이 필요합니다. 폴더 선택 창은 기본 포함된 tkinter를 씁니다.

### 실행
```bash
# 폴더 선택 창이 열림
python heic_to_jpg.py

# 경로를 직접 지정 (입력 폴더, 출력 폴더)
python heic_to_jpg.py ~/Pictures/trip
python heic_to_jpg.py ~/Pictures/trip ~/Pictures/trip_jpg

# 옵션
python heic_to_jpg.py -f png                  # PNG로 변환
python heic_to_jpg.py -f webp -q 80           # WEBP, 화질 80
python heic_to_jpg.py --max-mb 0              # 용량 제한 없이 변환
python heic_to_jpg.py --max-mb 0.5            # 파일당 500KB 이하로
```

### 옵션
| 옵션 | 기본값 | 설명 |
|---|---|---|
| `src` | 선택 창 | HEIC가 들어 있는 입력 폴더 |
| `dst` | `입력폴더/converted` | 결과 저장 폴더 (없으면 생성) |
| `-f`, `--format` | `jpg` | `jpg`, `png`, `webp` 중 선택 |
| `-q`, `--quality` | `85` | 화질 1~100 (PNG는 무시) |
| `--max-mb` | `1` | 파일당 최대 MB. 0이면 제한 없음 |

### 동작 방식
- 입력 폴더 바로 아래의 `.heic`, `.heif` 파일을 변환합니다. 하위 폴더는 처리하지 않습니다.
- 사진 회전(EXIF)을 반영하고, 파일명은 그대로 두고 확장자만 바꿉니다.
- 용량 제한에 걸리면 화질을 10씩 낮추고, 그래도 크면 해상도를 15%씩 줄입니다.
- 원본 파일은 수정하지 않습니다.

### 문제 해결
| 증상 | 해결 |
|---|---|
| `ModuleNotFoundError: PIL` | `pip install pillow pillow-heif` 실행 |
| 선택 창이 안 뜸 / `No module named tkinter` | Python에 tkinter가 없는 경우입니다. 경로를 직접 지정해 실행하거나, macOS에서는 `brew install python-tk`를 실행하세요. |
| `HEIC/HEIF 파일이 없습니다` | 선택한 폴더 바로 아래에 HEIC 파일이 있는지 확인하세요. 하위 폴더는 검색하지 않습니다. |

---

## 개발 메모: 이전 HTML이 실패한 원인
이전 버전은 `heic2any 0.0.4` 하나에만 의존했습니다. 이 라이브러리는 오래된 libheif를 내장하고 있어서 최신 iPhone 사진에서 `ERR_LIBHEIF format not supported` 오류가 났습니다. Chrome도 HEIC를 기본으로 열지 못해서 대체 경로가 없었고, 화면에는 원인 없이 "실패"만 표시됐습니다.

현재 버전은 이렇게 바뀌었습니다.
- 최신 libheif를 쓰는 `heic-to 1.6.5`를 기본 디코더로 씁니다.
- 실패하면 `heic2any`, 그다음 브라우저 기본 디코더 순으로 시도합니다.
- 확장자가 달라도 파일 헤더로 HEIC를 알아봅니다.
- 실패 원인을 파일 아래에 표시하고, 라이브러리 로드 실패는 상단에 경고로 알려 줍니다.
- Chrome 헤드리스에서 실제 iPhone HEIC(4032×3024)로 JPG, PNG, WEBP, 용량 제한, JPG→PNG, ZIP 생성을 확인했습니다. Python 스크립트도 같은 파일로 확인했습니다. Safari와 Firefox에서는 확인하지 못했습니다.
