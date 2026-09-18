# 실내공기질 출장지 관리 - 지도 마킹 프로그램

엑셀 파일을 불러와 지도에 출장지를 마킹하고, 방문 완료 여부를 관리하는 데스크톱 프로그램.
엑셀 파일이 데이터 원본이며, 완료 처리 시 즉시 같은 파일에 저장된다.

## 실행 (개발용)

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python map_marker.py
```

실행하면 엑셀 파일 선택 창이 뜨고, 이후 프로그램 창이 열린다.

## 사용법

- 좌측 패널: 검색, 시군 필터, 시설군 필터(체크박스), 완료 항목 숨기기, 진행률 표시
- 지도의 마커 클릭 → 팝업에서 "완료 처리" / "완료 취소" 버튼으로 상태 변경
- 상태 변경은 즉시 엑셀 파일에 저장됨 (별도 저장 버튼 없음)
- 엑셀에 없던 시설군이 있으면 자동으로 색상을 배정하고 콘솔에 안내 메시지 출력

## exe(단일 실행 파일)로 빌드하기

```bash
./venv/bin/pip install pyinstaller
./venv/bin/pyinstaller --noconfirm --windowed --name "출장지관리" \
  --add-data "static:static" \
  map_marker.py
```

- macOS에서는 `--add-data "static:static"`, Windows에서는 `--add-data "static;static"` (구분자만 다름)
- 빌드 결과물은 `dist/출장지관리/` 폴더(또는 `--onefile` 옵션 사용 시 단일 실행 파일)에 생성됨
- `dist` 폴더를 원하는 위치로 복사해 두고 실행 파일만 더블클릭하면 실행됨
