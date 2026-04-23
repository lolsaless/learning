# Pairs Trading Pro v3

## 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 포함 기능
- 2~5개 종목 입력
- 모든 pairwise 조합 스캔
- 공적분 / ADF / KPSS / 반감기 / Hurst 진단
- 워크포워드 단일 페어 백테스트
- 상위 페어 기반 동일가중 포트폴리오 백테스트
- 파라미터 민감도 heatmap
- 사용법 / 해석 / 한계 설명 탭 내장

## 주의
- 연구/검증용입니다.
- 실전 체결용 실시간 시스템이 아닙니다.
- 브로커 API, 슬리피지 모델, 공매도 가능성, 세금, 생존편향, 이벤트 리스크는 별도 검토가 필요합니다.
