# 주식 기술적 분석기

Yahoo Finance 일봉 데이터로 이동평균, RSI, 볼린저 밴드, MACD, 거래량과
지지·저항 구간을 계산하고 인터랙티브 HTML 차트를 만듭니다.

## 가장 쉬운 실행 방법

1. `settings.txt`를 일반 텍스트 편집기로 엽니다.
2. `종목코드`, `데이터기간`, `처음표시기간` 등의 `=` 오른쪽 값만 수정하고 저장합니다.
3. Finder에서 `실행.command`를 더블클릭합니다.

첫 실행 때는 전용 실행 환경과 필수 패키지를 자동으로 준비합니다. 분석이 끝나면
설정한 HTML 파일이 생성되고 기본 브라우저에서 자동으로 열립니다.

예를 들어 삼성전자는 `settings.txt`에서 다음처럼 입력합니다.

```text
종목코드 = 005930.KS
데이터기간 = 5y
처음표시기간 = 6mo
저장파일 = 삼성전자_기술적분석.html
브라우저자동열기 = 예
```

## 터미널 실행 방법

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python analyze.py
```

기본적으로 5년 데이터를 내려받아 결과를 `RXRX_technical_analysis.html`에 저장하고,
HTML을 처음 열면 최근 6개월을 보여줍니다. HTML 상단의 빠른 기간 버튼 또는
시작일·종료일 입력으로 조회 구간을 즉시 바꿀 수 있습니다. 인터넷 연결 없이도
차트를 열 수 있도록 Plotly 라이브러리를 HTML에 함께 저장합니다.

```bash
python analyze.py RXRX --period 1y --output reports/rxrx.html
python analyze.py 005930.KS --period 2y --initial-range 3mo
```

주요 옵션:

- `--period`: HTML에 포함할 Yahoo Finance 데이터 기간 (기본 `5y`)
- `--initial-range`: HTML을 처음 열 때 표시할 기간 (`1mo`, `3mo`, `6mo`, `ytd`, `1y`, `3y`, `all`)
- `--swing-window`: 로컬 고점·저점 판별 시 양쪽에서 비교할 거래일 수
- `--level-tolerance`: 같은 지지·저항대로 묶을 가격 오차율(%, 기본 1.5)
- `--min-touches`: 주요 가격대로 인정할 최소 반응 횟수(기본 2)
- `--output`: 생성할 HTML 파일 경로

캔들과 거래량은 한국식으로 상승일을 붉은색, 하락일을 파란색으로 표시합니다.
지지·저항은 로컬 고점·저점을 가까운 가격끼리 군집화하고, 여러 번 반응한
가격대를 먼저 채택합니다. 차트의 색 띠는 최근 변동성을 반영한 지지·저항 구간,
삼각형은 실제 반응 지점, 중심선 굵기는 반복 터치 강도를 뜻합니다.

> 기술적 지표는 후행지표입니다. 이 프로그램의 결과는 미래 가격을 보장하지
> 않으며 투자 권유가 아닌 리스크 관리용 참고자료입니다.
