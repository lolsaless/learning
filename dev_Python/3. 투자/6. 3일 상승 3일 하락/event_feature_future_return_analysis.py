import os
import warnings
from itertools import combinations
from typing import List, Tuple, Dict

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("yfinance가 설치되어 있지 않습니다. `pip install yfinance` 후 다시 실행하세요.")

try:
    from scipy.stats import pearsonr, spearmanr
except ImportError:
    raise SystemExit("scipy가 설치되어 있지 않습니다. `pip install scipy` 후 다시 실행하세요.")

try:
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LinearRegression, Ridge, LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import (
        mean_absolute_error,
        mean_squared_error,
        r2_score,
        accuracy_score,
        roc_auc_score,
        precision_score,
        recall_score,
    )
except ImportError:
    raise SystemExit("scikit-learn이 설치되어 있지 않습니다. `pip install scikit-learn` 후 다시 실행하세요.")


import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

def set_korean_font_mac():
    """
    macOS용 한글 폰트 설정.
    - 1순위: AppleGothic
    - 2순위: Nanum 계열
    - 3순위: Arial Unicode MS
    - 최후: DejaVu Sans
    """
    available_fonts = {f.name for f in fm.fontManager.ttflist}

    preferred_fonts = [
        "AppleGothic",
        "NanumGothic",
        "NanumMyeongjo",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]

    selected_font = None
    for font_name in preferred_fonts:
        if font_name in available_fonts:
            selected_font = font_name
            break

    if selected_font is None:
        print("[경고] 사용 가능한 한글 폰트를 찾지 못했습니다. 그래프 한글이 깨질 수 있습니다.")
    else:
        plt.rcParams["font.family"] = selected_font
        print(f"[INFO] matplotlib 한글 폰트 설정: {selected_font}")

    # 마이너스 기호 깨짐 방지
    plt.rcParams["axes.unicode_minus"] = False


set_korean_font_mac()


# =========================
# 설정값
# =========================
TICKERS = ["RXRX", "SDGR", "TEM", "GLUE", "INTC", "CRSP"]
START_DATE = None  # None이면 yfinance 최대 기간 사용
UP_THRESHOLD = 0.01        # +1.0% 이상 상승일
DOWN_THRESHOLD = -0.01     # -1.0% 이하 하락일
MIN_STREAK = 3             # 최소 연속일수
FUTURE_WINDOWS = [3, 5, 10, 20]
MAX_COMBO_SIZE = 4
MIN_ROWS_FOR_MODEL = 40
TRAIN_RATIO = 0.7
RANDOM_STATE = 42
OUTPUT_DIR = "outputs_event_feature_analysis"

FEATURE_COLUMNS = [
    "rsi14",
    "bb_position",
    "bb_width_pct",
    "ma20_gap",
    "ma60_gap",
    "vol_ratio",
    "streak_len",
    "cum_return_in_streak",
    "event_type",
]

CORE_COMBO_FEATURES = [
    "rsi14",
    "bb_position",
    "ma20_gap",
    "ma60_gap",
    "vol_ratio",
    "event_type",
]

REGRESSION_TARGETS = ["future_return_5d", "future_return_10d"]
CLASSIFICATION_TARGETS = ["future_up_5d", "future_up_10d"]


# =========================
# 유틸
# =========================
def ensure_dirs() -> Dict[str, str]:
    subdirs = {
        "root": OUTPUT_DIR,
        "tables": os.path.join(OUTPUT_DIR, "tables"),
        "charts": os.path.join(OUTPUT_DIR, "charts"),
        "reports": os.path.join(OUTPUT_DIR, "reports"),
        "raw": os.path.join(OUTPUT_DIR, "raw"),
    }
    for path in subdirs.values():
        os.makedirs(path, exist_ok=True)
    return subdirs


def flatten_yf_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def safe_div(a, b):
    return np.where(np.abs(b) < 1e-12, np.nan, a / b)


def add_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def download_price_data(ticker: str) -> pd.DataFrame:
    if START_DATE:
        df = yf.download(ticker, start=START_DATE, auto_adjust=False, progress=False)
    else:
        df = yf.download(ticker, period="max", auto_adjust=False, progress=False)
    if df is None or df.empty:
        raise ValueError(f"{ticker} 데이터를 가져오지 못했습니다.")
    df = flatten_yf_columns(df).copy()
    df = df[[c for c in ["Open", "High", "Low", "Close", "Adj Close", "Volume"] if c in df.columns]]
    if "Adj Close" not in df.columns and "Close" in df.columns:
        df["Adj Close"] = df["Close"]
    df = df.rename(columns={"Adj Close": "Adj_Close"})
    df = df.dropna(subset=["Close"]).copy()
    df.index = pd.to_datetime(df.index)
    return df


# =========================
# 지표 계산
# =========================
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ret_1d"] = out["Close"].pct_change()

    out["rsi14"] = add_rsi(out["Close"], 14)

    out["ma20"] = out["Close"].rolling(20).mean()
    out["ma60"] = out["Close"].rolling(60).mean()
    out["ma20_gap"] = safe_div(out["Close"] - out["ma20"], out["ma20"])
    out["ma60_gap"] = safe_div(out["Close"] - out["ma60"], out["ma60"])

    bb_mid = out["Close"].rolling(20).mean()
    bb_std = out["Close"].rolling(20).std(ddof=0)
    out["bb_mid"] = bb_mid
    out["bb_upper"] = bb_mid + 2 * bb_std
    out["bb_lower"] = bb_mid - 2 * bb_std
    band_width = out["bb_upper"] - out["bb_lower"]
    out["bb_position"] = safe_div(out["Close"] - out["bb_lower"], band_width)
    out["bb_width_pct"] = safe_div(band_width, bb_mid)

    out["vol_ma20"] = out["Volume"].rolling(20).mean()
    out["vol_ratio"] = safe_div(out["Volume"], out["vol_ma20"])

    out["volatility_20d"] = out["ret_1d"].rolling(20).std(ddof=0)
    return out


# =========================
# 이벤트 탐지
# =========================
def compute_streak_runs(condition: pd.Series) -> pd.Series:
    values = condition.fillna(False).astype(int).values
    run_lengths = np.zeros(len(values), dtype=int)
    count = 0
    for i, v in enumerate(values):
        if v == 1:
            count += 1
        else:
            count = 0
        run_lengths[i] = count
    return pd.Series(run_lengths, index=condition.index)


def detect_events(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    temp = df.copy()
    temp["up_day"] = temp["ret_1d"] >= UP_THRESHOLD
    temp["down_day"] = temp["ret_1d"] <= DOWN_THRESHOLD

    temp["up_streak"] = compute_streak_runs(temp["up_day"])
    temp["down_streak"] = compute_streak_runs(temp["down_day"])

    up_end = (temp["up_streak"] >= MIN_STREAK) & (~temp["up_day"].shift(-1).fillna(False))
    down_end = (temp["down_streak"] >= MIN_STREAK) & (~temp["down_day"].shift(-1).fillna(False))

    rows = []
    for dt in temp.index[up_end]:
        streak_len = int(temp.at[dt, "up_streak"])
        start_idx = temp.index.get_loc(dt) - streak_len + 1
        start_dt = temp.index[start_idx]
        cum_ret = temp.loc[start_dt:dt, "Close"].iloc[-1] / temp.loc[start_dt:dt, "Close"].iloc[0] - 1
        rows.append({
            "ticker": ticker,
            "event_date": dt,
            "event_type": 1,
            "event_label": "up",
            "streak_len": streak_len,
            "streak_start": start_dt,
            "cum_return_in_streak": cum_ret,
        })

    for dt in temp.index[down_end]:
        streak_len = int(temp.at[dt, "down_streak"])
        start_idx = temp.index.get_loc(dt) - streak_len + 1
        start_dt = temp.index[start_idx]
        cum_ret = temp.loc[start_dt:dt, "Close"].iloc[-1] / temp.loc[start_dt:dt, "Close"].iloc[0] - 1
        rows.append({
            "ticker": ticker,
            "event_date": dt,
            "event_type": 0,
            "event_label": "down",
            "streak_len": streak_len,
            "streak_start": start_dt,
            "cum_return_in_streak": cum_ret,
        })

    events = pd.DataFrame(rows)
    if events.empty:
        return events
    events = events.sort_values("event_date").reset_index(drop=True)
    return events


# =========================
# 이벤트 데이터셋 구축
# =========================
def build_event_dataset(price_df: pd.DataFrame, events: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()

    rows = []
    for _, ev in events.iterrows():
        dt = ev["event_date"]
        if dt not in price_df.index:
            continue
        row = {
            "ticker": ticker,
            "event_date": dt,
            "event_type": ev["event_type"],
            "event_label": ev["event_label"],
            "streak_len": ev["streak_len"],
            "cum_return_in_streak": ev["cum_return_in_streak"],
            "close": price_df.at[dt, "Close"],
        }
        for col in FEATURE_COLUMNS:
            if col in ["streak_len", "cum_return_in_streak", "event_type"]:
                row[col] = row[col]
            else:
                row[col] = price_df.at[dt, col] if col in price_df.columns else np.nan

        idx = price_df.index.get_loc(dt)
        for w in FUTURE_WINDOWS:
            if idx + w < len(price_df):
                future_close = price_df["Close"].iloc[idx + w]
                fut_ret = future_close / price_df["Close"].iloc[idx] - 1
                row[f"future_return_{w}d"] = fut_ret
                row[f"future_up_{w}d"] = int(fut_ret > 0)
            else:
                row[f"future_return_{w}d"] = np.nan
                row[f"future_up_{w}d"] = np.nan
        rows.append(row)

    return pd.DataFrame(rows).sort_values("event_date").reset_index(drop=True)


# =========================
# 단변량 분석
# =========================
def run_univariate_analysis(df: pd.DataFrame, features: List[str], targets: List[str]) -> pd.DataFrame:
    rows = []
    for tgt in targets:
        temp = df.dropna(subset=[tgt]).copy()
        for feat in features:
            pair = temp[[feat, tgt]].dropna()
            if len(pair) < 10:
                continue
            try:
                pr, pp = pearsonr(pair[feat], pair[tgt])
            except Exception:
                pr, pp = np.nan, np.nan
            try:
                sr, sp = spearmanr(pair[feat], pair[tgt])
            except Exception:
                sr, sp = np.nan, np.nan
            rows.append({
                "target": tgt,
                "feature": feat,
                "n": len(pair),
                "pearson_r": pr,
                "pearson_p": pp,
                "spearman_r": sr,
                "spearman_p": sp,
            })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["target", "spearman_r"], ascending=[True, False])
    return out


# =========================
# 시계열 분리
# =========================
def chronological_split(df: pd.DataFrame, train_ratio: float = TRAIN_RATIO) -> Tuple[pd.DataFrame, pd.DataFrame]:
    temp = df.sort_values("event_date").reset_index(drop=True)
    split_idx = max(int(len(temp) * train_ratio), 1)
    split_idx = min(split_idx, len(temp) - 1)
    train_df = temp.iloc[:split_idx].copy()
    test_df = temp.iloc[split_idx:].copy()
    return train_df, test_df


# =========================
# 모델 평가
# =========================
def build_reg_pipeline(model):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", model),
    ])


def build_clf_pipeline(model):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", model),
    ])


def evaluate_regression_combo(df: pd.DataFrame, features: List[str], target: str, model_name: str) -> Dict:
    temp = df[["event_date"] + features + [target]].dropna().copy()
    if len(temp) < MIN_ROWS_FOR_MODEL:
        return {}
    train_df, test_df = chronological_split(temp)
    if len(train_df) < 20 or len(test_df) < 10:
        return {}

    X_train = train_df[features]
    y_train = train_df[target]
    X_test = test_df[features]
    y_test = test_df[target]

    if model_name == "linear":
        model = LinearRegression()
    elif model_name == "ridge":
        model = Ridge(alpha=1.0, random_state=RANDOM_STATE)
    else:
        raise ValueError("지원하지 않는 regression model")

    pipe = build_reg_pipeline(model)
    pipe.fit(X_train, y_train)
    pred = pipe.predict(X_test)

    return {
        "mode": "regression",
        "model": model_name,
        "target": target,
        "features": ", ".join(features),
        "n_total": len(temp),
        "n_train": len(train_df),
        "n_test": len(test_df),
        "r2": r2_score(y_test, pred),
        "mae": mean_absolute_error(y_test, pred),
        "rmse": float(np.sqrt(mean_squared_error(y_test, pred))),
        "pred_mean": float(np.mean(pred)),
        "actual_mean": float(np.mean(y_test)),
    }


def evaluate_classification_combo(df: pd.DataFrame, features: List[str], target: str, model_name: str) -> Dict:
    temp = df[["event_date"] + features + [target]].dropna().copy()
    if len(temp) < MIN_ROWS_FOR_MODEL:
        return {}
    if temp[target].nunique() < 2:
        return {}

    train_df, test_df = chronological_split(temp)
    if len(train_df) < 20 or len(test_df) < 10:
        return {}
    if train_df[target].nunique() < 2 or test_df[target].nunique() < 2:
        return {}

    X_train = train_df[features]
    y_train = train_df[target].astype(int)
    X_test = test_df[features]
    y_test = test_df[target].astype(int)

    if model_name == "logistic":
        model = LogisticRegression(max_iter=2000, random_state=RANDOM_STATE)
        pipe = build_clf_pipeline(model)
    elif model_name == "random_forest":
        pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", RandomForestClassifier(
                n_estimators=300,
                max_depth=4,
                min_samples_leaf=4,
                random_state=RANDOM_STATE,
            )),
        ])
    else:
        raise ValueError("지원하지 않는 classification model")

    pipe.fit(X_train, y_train)
    pred = pipe.predict(X_test)

    if hasattr(pipe.named_steps["model"], "predict_proba"):
        proba = pipe.predict_proba(X_test)[:, 1]
    else:
        proba = pred.astype(float)

    return {
        "mode": "classification",
        "model": model_name,
        "target": target,
        "features": ", ".join(features),
        "n_total": len(temp),
        "n_train": len(train_df),
        "n_test": len(test_df),
        "accuracy": accuracy_score(y_test, pred),
        "roc_auc": roc_auc_score(y_test, proba),
        "precision": precision_score(y_test, pred, zero_division=0),
        "recall": recall_score(y_test, pred, zero_division=0),
        "base_rate_test": float(np.mean(y_test)),
        "pred_positive_rate": float(np.mean(pred)),
    }


# =========================
# 조합 탐색
# =========================
def generate_feature_combos(features: List[str], max_size: int = MAX_COMBO_SIZE) -> List[Tuple[str, ...]]:
    combos = []
    for k in range(1, max_size + 1):
        combos.extend(combinations(features, k))
    return combos


def run_combo_search(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    reg_rows = []
    clf_rows = []
    combos = generate_feature_combos(CORE_COMBO_FEATURES, MAX_COMBO_SIZE)

    for target in REGRESSION_TARGETS:
        for combo in combos:
            for model_name in ["linear", "ridge"]:
                result = evaluate_regression_combo(df, list(combo), target, model_name)
                if result:
                    reg_rows.append(result)

    for target in CLASSIFICATION_TARGETS:
        for combo in combos:
            for model_name in ["logistic", "random_forest"]:
                result = evaluate_classification_combo(df, list(combo), target, model_name)
                if result:
                    clf_rows.append(result)

    reg_df = pd.DataFrame(reg_rows)
    clf_df = pd.DataFrame(clf_rows)

    if not reg_df.empty:
        reg_df = reg_df.sort_values(["target", "r2", "mae"], ascending=[True, False, True]).reset_index(drop=True)
    if not clf_df.empty:
        clf_df = clf_df.sort_values(["target", "roc_auc", "accuracy"], ascending=[True, False, False]).reset_index(drop=True)
    return reg_df, clf_df


# =========================
# 분위수 분석
# =========================
def quantile_analysis(df: pd.DataFrame, feature: str, target: str, q: int = 5) -> pd.DataFrame:
    temp = df[[feature, target]].dropna().copy()
    if len(temp) < 20:
        return pd.DataFrame()
    try:
        temp["quantile"] = pd.qcut(temp[feature], q=q, duplicates="drop")
    except Exception:
        return pd.DataFrame()
    out = temp.groupby("quantile", observed=False)[target].agg(["count", "mean", "median", "std"]).reset_index()
    out.insert(0, "feature", feature)
    out.insert(1, "target", target)
    return out


# =========================
# 시각화
# =========================
def plot_correlation_heatmap(univariate_df: pd.DataFrame, out_path: str):
    if univariate_df.empty:
        return
    pivot = univariate_df.pivot(index="feature", columns="target", values="spearman_r")
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(pivot.values, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("Spearman Correlation Heatmap")
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.iloc[i, j]
            txt = "nan" if pd.isna(val) else f"{val:.2f}"
            ax.text(j, i, txt, ha="center", va="center", fontsize=9)
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_quantile_bar(df_quant: pd.DataFrame, out_path: str):
    if df_quant.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 5))
    labels = [str(x) for x in df_quant["quantile"]]
    ax.bar(labels, df_quant["mean"])
    ax.set_title(f"{df_quant['feature'].iloc[0]} vs {df_quant['target'].iloc[0]} by Quantile")
    ax.set_ylabel("Mean future return")
    ax.set_xlabel("Quantile")
    plt.xticks(rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_top_regression(reg_df: pd.DataFrame, out_path: str, top_n: int = 10):
    if reg_df.empty:
        return
    temp = reg_df.groupby("target", as_index=False).head(top_n).copy()
    temp["label"] = temp["target"] + " | " + temp["model"] + " | " + temp["features"]
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh(temp["label"], temp["r2"])
    ax.set_title("Top Regression Combos by Test R²")
    ax.set_xlabel("R²")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_top_classification(clf_df: pd.DataFrame, out_path: str, top_n: int = 10):
    if clf_df.empty:
        return
    temp = clf_df.groupby("target", as_index=False).head(top_n).copy()
    temp["label"] = temp["target"] + " | " + temp["model"] + " | " + temp["features"]
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.barh(temp["label"], temp["roc_auc"])
    ax.set_title("Top Classification Combos by Test ROC AUC")
    ax.set_xlabel("ROC AUC")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# =========================
# 리포트 생성
# =========================
def make_interpretation(event_df: pd.DataFrame, univariate_df: pd.DataFrame, reg_df: pd.DataFrame, clf_df: pd.DataFrame) -> str:
    lines = []
    lines.append("[이벤트-미래수익률 연결 분석 요약]\n")
    lines.append(f"총 이벤트 수: {len(event_df)}")
    if not event_df.empty:
        lines.append(f"상승 이벤트 수: {int((event_df['event_type'] == 1).sum())}")
        lines.append(f"하락 이벤트 수: {int((event_df['event_type'] == 0).sum())}")
        lines.append("")

    if not univariate_df.empty:
        lines.append("[단변량 상관 상위 결과: Spearman 기준]")
        for tgt in REGRESSION_TARGETS:
            temp = univariate_df[univariate_df["target"] == tgt].sort_values("spearman_r", ascending=False).head(5)
            if not temp.empty:
                lines.append(f"- {tgt}")
                for _, r in temp.iterrows():
                    lines.append(
                        f"  · {r['feature']}: spearman={r['spearman_r']:.3f}, p={r['spearman_p']:.4g}, n={int(r['n'])}"
                    )
        lines.append("")

    if not reg_df.empty:
        lines.append("[회귀모델 상위 조합: 테스트 R² 기준]")
        for tgt in REGRESSION_TARGETS:
            temp = reg_df[reg_df["target"] == tgt].head(5)
            if not temp.empty:
                lines.append(f"- {tgt}")
                for _, r in temp.iterrows():
                    lines.append(
                        f"  · {r['model']} | {r['features']} | R²={r['r2']:.4f}, MAE={r['mae']:.4f}, RMSE={r['rmse']:.4f}"
                    )
        lines.append("")

    if not clf_df.empty:
        lines.append("[분류모델 상위 조합: 테스트 ROC AUC 기준]")
        for tgt in CLASSIFICATION_TARGETS:
            temp = clf_df[clf_df["target"] == tgt].head(5)
            if not temp.empty:
                lines.append(f"- {tgt}")
                for _, r in temp.iterrows():
                    lines.append(
                        f"  · {r['model']} | {r['features']} | ROC AUC={r['roc_auc']:.4f}, ACC={r['accuracy']:.4f}, Precision={r['precision']:.4f}, Recall={r['recall']:.4f}"
                    )
        lines.append("")

    lines.append("[해석 시 주의점]")
    lines.append("1. 이 결과는 이벤트 시점 지표와 이후 수익률의 연결 강도를 본 것이다. 인과를 증명하지 않는다.")
    lines.append("2. R²가 낮더라도 방향성 분류에서 ROC AUC가 의미 있게 나올 수 있다. 회귀와 분류 결과를 분리해서 봐야 한다.")
    lines.append("3. RSI, 볼린저 위치, 이동평균 이격률은 상호 상관이 높을 수 있다. 상위 조합 해석 시 중복정보 가능성을 경계해야 한다.")
    lines.append("4. 종목별 구조가 다르므로 전체 통합 결과와 티커별 결과를 따로 확인하는 것이 바람직하다.")
    return "\n".join(lines)


# =========================
# 메인 실행
# =========================
def main():
    paths = ensure_dirs()

    all_event_frames = []
    download_log = []

    for ticker in TICKERS:
        try:
            price = download_price_data(ticker)
            price = add_indicators(price)
            price.to_csv(os.path.join(paths["raw"], f"{ticker}_price_with_indicators.csv"), encoding="utf-8-sig")

            events = detect_events(price, ticker)
            event_df = build_event_dataset(price, events, ticker)
            if not event_df.empty:
                event_df.to_csv(os.path.join(paths["raw"], f"{ticker}_event_dataset.csv"), index=False, encoding="utf-8-sig")
                all_event_frames.append(event_df)

            download_log.append({
                "ticker": ticker,
                "rows": len(price),
                "events": 0 if event_df.empty else len(event_df),
                "start": price.index.min(),
                "end": price.index.max(),
            })
            print(f"[완료] {ticker}: 가격행 {len(price)}, 이벤트 {0 if event_df.empty else len(event_df)}")

        except Exception as e:
            print(f"[실패] {ticker}: {e}")
            download_log.append({
                "ticker": ticker,
                "rows": 0,
                "events": 0,
                "start": None,
                "end": None,
                "error": str(e),
            })

    log_df = pd.DataFrame(download_log)
    log_df.to_csv(os.path.join(paths["tables"], "download_log.csv"), index=False, encoding="utf-8-sig")

    if not all_event_frames:
        raise SystemExit("유효한 이벤트 데이터가 생성되지 않았습니다. 임계값 또는 티커를 점검하세요.")

    event_df = pd.concat(all_event_frames, ignore_index=True)
    event_df = event_df.sort_values(["event_date", "ticker"]).reset_index(drop=True)
    event_df.to_csv(os.path.join(paths["tables"], "event_dataset.csv"), index=False, encoding="utf-8-sig")

    all_targets = [f"future_return_{w}d" for w in FUTURE_WINDOWS] + [f"future_up_{w}d" for w in FUTURE_WINDOWS]
    univariate_df = run_univariate_analysis(event_df, FEATURE_COLUMNS, [f"future_return_{w}d" for w in FUTURE_WINDOWS])
    univariate_df.to_csv(os.path.join(paths["tables"], "univariate_analysis.csv"), index=False, encoding="utf-8-sig")

    reg_df, clf_df = run_combo_search(event_df)
    reg_df.to_csv(os.path.join(paths["tables"], "regression_combo_results.csv"), index=False, encoding="utf-8-sig")
    clf_df.to_csv(os.path.join(paths["tables"], "classification_combo_results.csv"), index=False, encoding="utf-8-sig")

    quant_frames = []
    for feat in ["rsi14", "bb_position", "ma20_gap", "vol_ratio"]:
        for tgt in ["future_return_5d", "future_return_10d"]:
            qdf = quantile_analysis(event_df, feat, tgt, q=5)
            if not qdf.empty:
                quant_frames.append(qdf)
                plot_quantile_bar(
                    qdf,
                    os.path.join(paths["charts"], f"quantile_{feat}_{tgt}.png"),
                )
    if quant_frames:
        pd.concat(quant_frames, ignore_index=True).to_csv(
            os.path.join(paths["tables"], "quantile_analysis.csv"),
            index=False,
            encoding="utf-8-sig",
        )

    plot_correlation_heatmap(univariate_df, os.path.join(paths["charts"], "correlation_heatmap.png"))
    plot_top_regression(reg_df, os.path.join(paths["charts"], "top_regression_combos.png"))
    plot_top_classification(clf_df, os.path.join(paths["charts"], "top_classification_combos.png"))

    interpretation = make_interpretation(event_df, univariate_df, reg_df, clf_df)
    with open(os.path.join(paths["reports"], "interpretation.txt"), "w", encoding="utf-8") as f:
        f.write(interpretation)

    print("\n분석 완료")
    print(f"결과 폴더: {OUTPUT_DIR}")
    print("주요 파일:")
    print("- tables/event_dataset.csv")
    print("- tables/univariate_analysis.csv")
    print("- tables/regression_combo_results.csv")
    print("- tables/classification_combo_results.csv")
    print("- charts/correlation_heatmap.png")
    print("- charts/top_regression_combos.png")
    print("- charts/top_classification_combos.png")
    print("- reports/interpretation.txt")


if __name__ == "__main__":
    main()
