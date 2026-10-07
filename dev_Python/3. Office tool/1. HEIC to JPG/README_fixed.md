# HEIC 변환기 수정본 — 2026-10-08

수정본은 별도 파일입니다. `heic_converter.html`, `heic_to_jpg.py`는 이번 검토를 시작할 때의 내용으로 복원했습니다. HTML에 작업 시작 전부터 있던 미커밋 변경도 보존했습니다. 기존 `README.md`, `create_html.py`는 이번 작업에서 수정하지 않았습니다.

## 실행

- 브라우저: `heic_converter_fixed.html`을 Chrome에서 엽니다. 폴더를 창 안에 놓거나 **폴더 선택** 버튼을 누릅니다. 하위 폴더 이미지도 포함합니다.
- Python: 기존 환경에 `pillow`, `pillow-heif`가 설치되어 있어야 합니다.

```bash
python heic_to_jpg_fixed.py ~/Pictures/trip
python heic_to_jpg_fixed.py ~/Pictures/trip ~/Pictures/trip_jpg -f jpg --max-mb 1
```

Python은 기존처럼 입력 폴더 바로 아래의 HEIC/HEIF만 변환합니다. 기본 출력 폴더는 `입력폴더/converted`입니다.

## 폴더 드롭 실패 원인과 수정

현재 macOS Chrome에서 로컬 HTML을 `file://`로 열고 실제 디스크 폴더를 CDP 드롭 이벤트로 전달했을 때, 기존 `webkitGetAsEntry()` 경로의 `readEntries()`가 `EncodingError`로 실패했습니다. 한글과 영문 폴더 모두에서 재현되어, 한글 이름만의 문제로 볼 수 없습니다. 같은 폴더를 `getAsFileSystemHandle()`로 읽으면 하위 폴더까지 수집됩니다.

수정본은 `getAsFileSystemHandle()`을 우선 사용하고, 지원되지 않거나 실패하면 기존 entry API를 사용합니다. 모든 드롭 항목의 핸들 요청과 대체 entry는 첫 `await` 전에 확보합니다. 이 호출 시점 제약은 [MDN 공식 설명](https://developer.mozilla.org/en-US/docs/Web/API/DataTransferItem/getAsFileSystemHandle)을 따릅니다. 기존 API까지 실패하면 오류 내용과 **폴더 선택** 안내를 표시합니다.

기존 코드는 점선 영역 밖의 드롭에서 브라우저 기본 동작만 차단하고 수집하지 않았습니다. 수정본은 창 전체에서 수집합니다. 외부 라이브러리는 `defer`로 불러와 다운로드가 입력 이벤트 등록을 막지 않도록 했으며, 라이브러리 경고와 입력 상태 안내도 분리했습니다.

## 함께 보완한 오류

| 대상 | 문제 | 수정 |
|---|---|---|
| HTML | 폴더 수집·변환 중 추가 입력으로 목록과 진행률이 달라질 수 있음 | 처리 중 입력 잠금 |
| HTML | 다운로드 URL이 반복 생성되고 해제되지 않음 | 결과별 재사용, 재변환·비우기 때 해제 |
| HTML | 지원되지 않는 출력 형식이 PNG로 저장될 수 있음 | 실제 Blob 형식 검사 |
| HTML | 작은 이미지에서 용량 제한을 초과한 결과도 성공 처리 | 최소 1×1까지 제한 검사, 불가능하면 오류 |
| Python | 음수·NaN·무한대 용량 또는 과도한 축소 | 입력 검사, 최소 1픽셀 유지, 불가능한 제한 안내 |
| Python | 손상 파일 하나로 전체 작업 종료 | 다음 파일 계속 처리, 실패 수와 종료 코드 1 반환 |
| Python | 같은 이름의 결과 파일 덮어쓰기 | `이름 (1).jpg`처럼 새 이름 사용 |
| Python | 잘못된 입력 폴더와 `.heic` 이름의 디렉터리 처리 | 폴더 유효성 확인, 실제 파일만 수집 |

## 검증 범위

- 설치된 Chrome을 헤드리스로 실행하고 CDP 드롭 이벤트에 실제 폴더 경로를 전달했습니다. 한글 이름, 공백, 하위 폴더 포함 이미지 125개 수집과 중복 추가 방지를 확인했습니다.
- HEIC 샘플과 PNG의 JPG·PNG·WEBP 변환, ZIP 생성·다운로드, 폴더 선택 입력을 확인했습니다. HEIC는 Pillow/pillow-heif로 생성한 샘플입니다.
- 새 API 미지원·거부 상태의 안내와, 기존 API의 100개+23개 분할 읽기는 모의 entry로 검증했습니다. 현재 Chrome의 로컬 HTML에서는 기존 API 자체가 실패합니다.
- CDN을 차단해도 파일 입력이 작동하고 라이브러리 경고가 유지되는지 확인했습니다.
- Python의 세 출력 형식, 손상 파일 후 계속 처리, 기존 출력 보존, 잘못된 용량, 폭이 1픽셀인 이미지와 달성 불가능한 용량 제한을 확인했습니다.
- Finder에서 마우스로 직접 드래그하는 조작, Safari·Firefox는 이번 검증 범위에 포함하지 않았습니다.

기존 `create_html.py`는 원래 HTML을 생성하는 별도 스크립트입니다. 수정본을 실행할 때는 위의 `_fixed` 파일을 직접 사용하세요.
