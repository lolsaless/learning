# Pairs Trading Lab

## 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 기능
- 2~5개 티커 입력
- pairwise 공적분/ADF/반감기/Hurst 스캔
- 선택 페어의 스프레드/Z-score 모니터링
- 간단한 mean-reversion 백테스트

## 주의
- 연구/교육용 예시입니다.
- yfinance 데이터는 연구·교육 목적 사용이 권장됩니다.
- 실전 적용 전 체결비용, 공매도 제약, 슬리피지, 생존편향, 리밸런싱 규칙을 별도로 점검해야 합니다.
