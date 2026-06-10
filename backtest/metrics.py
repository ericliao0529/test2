"""績效指標計算：給定每日權益曲線與交易紀錄，輸出完整績效報告。"""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def compute_metrics(equity: pd.Series, trades: pd.DataFrame) -> dict:
    """equity: 以日期為索引的權益曲線；trades: 每筆交易的紀錄（含 pnl_pct 欄位）。"""
    returns = equity.pct_change().dropna()
    n_days = len(equity)
    years = n_days / TRADING_DAYS

    total_return = equity.iloc[-1] / equity.iloc[0] - 1
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else np.nan

    ann_vol = returns.std() * np.sqrt(TRADING_DAYS)
    sharpe = (returns.mean() * TRADING_DAYS) / ann_vol if ann_vol > 0 else np.nan

    downside = returns[returns < 0]
    downside_vol = downside.std() * np.sqrt(TRADING_DAYS)
    sortino = (returns.mean() * TRADING_DAYS) / downside_vol if downside_vol > 0 else np.nan

    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    max_dd = drawdown.min()
    calmar = cagr / abs(max_dd) if max_dd < 0 else np.nan

    if len(trades) > 0:
        wins = trades[trades["pnl_pct"] > 0]
        losses = trades[trades["pnl_pct"] <= 0]
        win_rate = len(wins) / len(trades)
        avg_win = wins["pnl_pct"].mean() if len(wins) else 0.0
        avg_loss = losses["pnl_pct"].mean() if len(losses) else 0.0
        gross_profit = wins["pnl_pct"].sum()
        gross_loss = abs(losses["pnl_pct"].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf
        avg_hold = trades["hold_days"].mean()
    else:
        win_rate = avg_win = avg_loss = profit_factor = avg_hold = np.nan

    return {
        "總報酬率 %": round(total_return * 100, 2),
        "年化報酬 CAGR %": round(cagr * 100, 2),
        "年化波動 %": round(ann_vol * 100, 2),
        "Sharpe": round(sharpe, 2),
        "Sortino": round(sortino, 2),
        "最大回撤 %": round(max_dd * 100, 2),
        "Calmar": round(calmar, 2),
        "交易次數": len(trades),
        "勝率 %": round(win_rate * 100, 1) if len(trades) else np.nan,
        "平均獲利 %": round(avg_win * 100, 2) if len(trades) else np.nan,
        "平均虧損 %": round(avg_loss * 100, 2) if len(trades) else np.nan,
        "獲利因子": round(profit_factor, 2) if len(trades) else np.nan,
        "平均持有天數": round(avg_hold, 1) if len(trades) else np.nan,
    }


def format_report(name: str, metrics: dict) -> str:
    lines = [f"\n=== {name} ==="]
    for k, v in metrics.items():
        lines.append(f"  {k:<14} {v}")
    return "\n".join(lines)
