TICKER = "RXRX"
START_DATE = "2023-01-01"
END_DATE = None

RSI_PERIOD = 14
PRICE_DROP_WINDOW = 5
VOLUME_MA_WINDOW = 20
HIGH_WINDOW = 20

# 점수 가중치
WEIGHT_PRICE = 0.40
WEIGHT_VOLUME = 0.15
WEIGHT_RSI = 0.35
WEIGHT_DRAWDOWN = 0.10

# 점수 해석 기준
LABEL_THRESHOLDS = {
    "normal": 30,
    "weak_oversold": 60,
    "meaningful_oversold": 80
}

# CSV 저장 설정
OUTPUT_DIR = "output"
SAVE_FULL_DATA_CSV = True
SAVE_SCORE_TABLE_CSV = True
SAVE_BACKTEST_CSV = True

# 백테스트 설정
BACKTEST_ENABLED = True
ENTRY_SCORE_THRESHOLD = 70.0     # 진입 기준
EXIT_SCORE_THRESHOLD = 45.0      # 점수 하락 시 조기 청산에 사용 가능
MAX_HOLD_DAYS = 10               # 최대 보유일
STOP_LOSS_PCT = -5.0             # 손절
TAKE_PROFIT_PCT = 8.0            # 익절
USE_EXIT_SCORE = False           # True면 Oversold_Score <= EXIT_SCORE_THRESHOLD일 때 청산