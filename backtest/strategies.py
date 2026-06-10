"""Python 版策略訊號（與 Pine 策略 01–04、06 對應，吃 OHLCV 即可）。

每個函式回傳 (entries, exits) 兩個布林 Series。
基本面策略（Pine 05）需要財報資料，請直接在 TradingView 上用 Pine 版回測；
若有匯出的基本面 CSV，可仿照 multifactor 自行加入欄位判斷。
"""

import numpy as np
import pandas as pd


# ---------- 共用指標 ----------

def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss
    return 100 - 100 / (1 + rs)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    atr_n = atr(df, n)
    plus_di = 100 * plus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr_n
    minus_di = 100 * minus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr_n
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff()).fillna(0)
    return (direction * df["volume"]).cumsum()


# ---------- 策略訊號 ----------

def ma_trend_adx(df, fast=20, slow=60, adx_len=14, adx_thresh=20):
    """01 雙均線趨勢 + ADX 濾網"""
    fast_ma, slow_ma = ema(df["close"], fast), ema(df["close"], slow)
    adx_v = adx(df, adx_len)
    cross_up = (fast_ma > slow_ma) & (fast_ma.shift() <= slow_ma.shift())
    entries = cross_up & (adx_v > adx_thresh)
    exits = (df["close"] < slow_ma) & (df["close"].shift() >= slow_ma.shift())
    return entries.fillna(False), exits.fillna(False)


def rsi_bollinger_meanrev(df, bb_len=20, bb_mult=2.0, rsi_len=14,
                          rsi_os=30, rsi_exit=55, trend_len=200):
    """02 RSI + 布林通道均值回歸（含 200MA 多頭濾網）"""
    basis = sma(df["close"], bb_len)
    dev = bb_mult * df["close"].rolling(bb_len).std()
    rsi_v = rsi(df["close"], rsi_len)
    bull = df["close"] > sma(df["close"], trend_len)
    entries = (df["close"] < basis - dev) & (rsi_v < rsi_os) & bull
    exits = (df["close"] > basis) | (rsi_v > rsi_exit)
    return entries.fillna(False), exits.fillna(False)


def volume_breakout(df, hh_len=50, ll_len=20, vol_ma_len=20, vol_mult=2.0):
    """03 爆量突破前高"""
    prev_high = df["high"].rolling(hh_len).max().shift()
    prev_low = df["low"].rolling(ll_len).min().shift()
    rvol = df["volume"] / sma(df["volume"], vol_ma_len)
    entries = (df["close"] > prev_high) & (rvol > vol_mult) & (df["close"] > df["open"])
    exits = df["close"] < prev_low
    return entries.fillna(False), exits.fillna(False)


def obv_accumulation(df, obv_ma_len=30, price_ma_len=50):
    """04 OBV 籌碼累積"""
    obv_v = obv(df)
    obv_ma = sma(obv_v, obv_ma_len)
    cross_up = (obv_v > obv_ma) & (obv_v.shift() <= obv_ma.shift())
    entries = cross_up & (df["close"] > sma(df["close"], price_ma_len))
    exits = (obv_v < obv_ma) & (obv_v.shift() >= obv_ma.shift())
    return entries.fillna(False), exits.fillna(False)


def multifactor_score(df, entry_score=3, exit_score=1, trend_len=100,
                      mom_len=63, vol_ma_len=20, atr_len=14, atr_pct_max=6.0):
    """06 多因子評分（價量四因子版；基本面因子請在 Pine 版使用）"""
    f_trend = (df["close"] > sma(df["close"], trend_len)).astype(int)
    f_mom = (df["close"] > df["close"].shift(mom_len)).astype(int)
    vol_ma = sma(df["volume"], vol_ma_len)
    f_vol = (vol_ma > vol_ma.shift(vol_ma_len)).astype(int)
    f_atr = (atr(df, atr_len) / df["close"] * 100 < atr_pct_max).astype(int)
    score = f_trend + f_mom + f_vol + f_atr
    entries = score >= entry_score
    exits = score <= exit_score
    return entries.fillna(False), exits.fillna(False)


ALL_STRATEGIES = {
    "01_雙均線趨勢+ADX": (ma_trend_adx, {"stop_loss_pct": None}),
    "02_RSI布林均值回歸": (rsi_bollinger_meanrev, {"stop_loss_pct": 0.07}),
    "03_爆量突破前高": (volume_breakout, {"stop_loss_pct": 0.08, "take_profit_pct": 0.25}),
    "04_OBV籌碼累積": (obv_accumulation, {"stop_loss_pct": 0.10}),
    "06_多因子評分": (multifactor_score, {"stop_loss_pct": None}),
}
