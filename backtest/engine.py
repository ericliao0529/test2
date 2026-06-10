"""事件式回測引擎：讀取 TradingView 匯出的 OHLCV CSV，逐棒模擬進出場。

訊號介面：策略函式接收 DataFrame（含 open/high/low/close/volume 欄位），
回傳 entries（布林 Series，當棒收盤產生進場訊號）與 exits（布林 Series）。
成交時點：訊號棒的「下一棒開盤價」成交，避免前視偏差（look-ahead bias）。
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from metrics import compute_metrics


def load_tradingview_csv(path: str) -> pd.DataFrame:
    """讀取 TradingView「匯出圖表資料」產生的 CSV。

    TradingView 匯出格式通常為：time, open, high, low, close, Volume（欄名大小寫不一）。
    time 可能是 ISO 字串或 Unix 秒數，兩種都支援。
    """
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    rename = {}
    for col in df.columns:
        if col.startswith("vol"):
            rename[col] = "volume"
        elif col in ("time", "date", "datetime"):
            rename[col] = "time"
    df = df.rename(columns=rename)

    required = {"time", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV 缺少必要欄位: {missing}，實際欄位: {list(df.columns)}")
    if "volume" not in df.columns:
        df["volume"] = np.nan

    if np.issubdtype(df["time"].dtype, np.number):
        df["time"] = pd.to_datetime(df["time"], unit="s")
    else:
        df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_localize(None)

    df = df.set_index("time").sort_index()
    return df[["open", "high", "low", "close", "volume"]].astype(float)


@dataclass
class BacktestConfig:
    initial_capital: float = 1_000_000.0
    commission_pct: float = 0.001   # 單邊手續費 0.1%（台股費用可自行調整）
    slippage_pct: float = 0.0005    # 滑價 0.05%
    stop_loss_pct: float | None = None    # 例如 0.08 = 跌 8% 停損
    take_profit_pct: float | None = None  # 例如 0.25 = 漲 25% 停利
    position_pct: float = 0.95      # 每次投入資金比例


@dataclass
class BacktestResult:
    name: str
    equity: pd.Series = field(repr=False, default=None)
    trades: pd.DataFrame = field(repr=False, default=None)
    metrics: dict = None


def run_backtest(df: pd.DataFrame, entries: pd.Series, exits: pd.Series,
                 config: BacktestConfig = None, name: str = "策略") -> BacktestResult:
    """逐棒模擬：訊號於收盤產生，下一棒開盤成交；停損／停利以當棒高低價觸發。"""
    cfg = config or BacktestConfig()
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    entry_sig = entries.reindex(df.index).fillna(False).values
    exit_sig = exits.reindex(df.index).fillna(False).values

    cash = cfg.initial_capital
    shares = 0.0
    entry_price = np.nan
    entry_i = -1
    equity = np.empty(len(df))
    trades = []

    def close_position(i: int, price: float, reason: str):
        nonlocal cash, shares, entry_price, entry_i
        proceeds = shares * price * (1 - cfg.commission_pct - cfg.slippage_pct)
        cost = shares * entry_price
        trades.append({
            "entry_time": df.index[entry_i], "exit_time": df.index[i],
            "entry_price": round(entry_price, 4), "exit_price": round(price, 4),
            "pnl_pct": proceeds / cost - 1,
            "hold_days": i - entry_i, "reason": reason,
        })
        cash += proceeds
        shares = 0.0
        entry_price = np.nan
        entry_i = -1

    for i in range(len(df)):
        if shares > 0:
            # 停損／停利：以當棒高低價判斷是否觸發（保守：先看停損）
            if cfg.stop_loss_pct is not None:
                stop = entry_price * (1 - cfg.stop_loss_pct)
                if l[i] <= stop:
                    close_position(i, min(stop, o[i]), "停損")
            if shares > 0 and cfg.take_profit_pct is not None:
                target = entry_price * (1 + cfg.take_profit_pct)
                if h[i] >= target:
                    close_position(i, max(target, o[i]), "停利")
            # 訊號出場：前一棒收盤出訊號，本棒開盤成交
            if shares > 0 and i > 0 and exit_sig[i - 1]:
                close_position(i, o[i], "訊號出場")
        elif i > 0 and entry_sig[i - 1] and not exit_sig[i - 1]:
            buy_price = o[i] * (1 + cfg.commission_pct + cfg.slippage_pct)
            invest = cash * cfg.position_pct
            shares = invest / buy_price
            cash -= invest
            entry_price = buy_price
            entry_i = i

        equity[i] = cash + shares * c[i]

    # 期末強制平倉，讓最後一筆交易納入統計
    if shares > 0:
        close_position(len(df) - 1, c[-1], "期末平倉")
        equity[-1] = cash

    equity_s = pd.Series(equity, index=df.index, name="equity")
    trades_df = pd.DataFrame(trades)
    return BacktestResult(name=name, equity=equity_s, trades=trades_df,
                          metrics=compute_metrics(equity_s, trades_df))


def buy_and_hold(df: pd.DataFrame, config: BacktestConfig = None) -> BacktestResult:
    """基準：第一天買進並持有到最後，用來對照策略是否有超額報酬。"""
    entries = pd.Series(False, index=df.index)
    entries.iloc[0] = True
    exits = pd.Series(False, index=df.index)
    cfg = config or BacktestConfig()
    cfg = BacktestConfig(initial_capital=cfg.initial_capital,
                         commission_pct=cfg.commission_pct,
                         slippage_pct=cfg.slippage_pct,
                         position_pct=cfg.position_pct)  # 不帶停損停利
    return run_backtest(df, entries, exits, cfg, name="Buy & Hold 基準")
