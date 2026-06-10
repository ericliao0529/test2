"""一鍵跑完所有策略並輸出比較報告。

用法：
  python run_backtest.py <TradingView匯出的CSV>            # 跑全部策略
  python run_backtest.py <CSV> --strategy 03_爆量突破前高   # 只跑一支
  python run_backtest.py --demo                            # 用合成資料示範

輸出：
  - 終端機：各策略 vs Buy&Hold 的完整績效比較表
  - results/equity_curves.png：權益曲線圖
  - results/<策略>_trades.csv：每筆交易明細
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

from engine import BacktestConfig, buy_and_hold, load_tradingview_csv, run_backtest
from strategies import ALL_STRATEGIES


def make_demo_data(n_days: int = 1500, seed: int = 42) -> pd.DataFrame:
    """合成日線資料（幾何布朗運動 + 趨勢段），僅供驗證流程用。"""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=n_days)
    drift = np.concatenate([
        np.full(n_days // 3, 0.0008),   # 多頭
        np.full(n_days // 3, -0.0005),  # 空頭
        np.full(n_days - 2 * (n_days // 3), 0.0010),
    ])
    ret = drift + rng.normal(0, 0.018, n_days)
    close = 100 * np.exp(np.cumsum(ret))
    high = close * (1 + np.abs(rng.normal(0, 0.008, n_days)))
    low = close * (1 - np.abs(rng.normal(0, 0.008, n_days)))
    open_ = np.roll(close, 1) * (1 + rng.normal(0, 0.004, n_days))
    open_[0] = 100
    volume = rng.lognormal(13, 0.6, n_days) * (1 + 3 * (ret > 0.02))
    return pd.DataFrame({"open": open_, "high": high, "low": low,
                         "close": close, "volume": volume}, index=dates)


def main():
    parser = argparse.ArgumentParser(description="TradingView CSV 回測工具")
    parser.add_argument("csv", nargs="?", help="TradingView 匯出的 OHLCV CSV 路徑")
    parser.add_argument("--demo", action="store_true", help="使用合成資料示範")
    parser.add_argument("--strategy", help="只跑指定策略（名稱見 strategies.py）")
    parser.add_argument("--capital", type=float, default=1_000_000, help="初始資金")
    parser.add_argument("--commission", type=float, default=0.001, help="單邊手續費率")
    args = parser.parse_args()

    if args.demo:
        df = make_demo_data()
        label = "DEMO（合成資料）"
    elif args.csv:
        df = load_tradingview_csv(args.csv)
        label = os.path.basename(args.csv)
    else:
        parser.error("請提供 CSV 路徑，或加上 --demo 用合成資料示範")

    print(f"資料：{label}  |  {df.index[0].date()} ~ {df.index[-1].date()}  共 {len(df)} 根 K 棒")

    strategies = ALL_STRATEGIES
    if args.strategy:
        if args.strategy not in strategies:
            sys.exit(f"找不到策略 {args.strategy}，可選：{list(strategies)}")
        strategies = {args.strategy: strategies[args.strategy]}

    os.makedirs("results", exist_ok=True)
    results = [buy_and_hold(df, BacktestConfig(initial_capital=args.capital,
                                               commission_pct=args.commission))]
    for name, (fn, risk) in strategies.items():
        entries, exits = fn(df)
        cfg = BacktestConfig(initial_capital=args.capital,
                             commission_pct=args.commission, **risk)
        res = run_backtest(df, entries, exits, cfg, name=name)
        results.append(res)
        if len(res.trades) > 0:
            res.trades.to_csv(f"results/{name}_trades.csv", index=False, encoding="utf-8-sig")

    # 比較表
    table = pd.DataFrame({r.name: r.metrics for r in results}).T
    pd.set_option("display.unicode.east_asian_width", True)
    pd.set_option("display.width", 200)
    print("\n========== 績效比較 ==========")
    print(table.to_string())
    table.to_csv("results/summary.csv", encoding="utf-8-sig")

    # 權益曲線圖
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
        # 盡量找出可顯示中文的字型，找不到就退回英文標籤
        zh_font = next((f.name for f in font_manager.fontManager.ttflist
                        if any(k in f.name for k in ("CJK", "Hei", "Ming", "Song", "WenQuanYi"))), None)
        if zh_font:
            plt.rcParams["font.family"] = zh_font
        fig, ax = plt.subplots(figsize=(12, 6))
        for r in results:
            ax.plot(r.equity.index, r.equity / r.equity.iloc[0], label=r.name, linewidth=1.2)
        ax.set_title(f"Equity Curves — {label}")
        ax.set_ylabel("Normalized Equity")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig("results/equity_curves.png", dpi=130)
        print("\n已輸出：results/equity_curves.png、results/summary.csv、results/*_trades.csv")
    except Exception as e:  # 繪圖失敗不影響回測結果
        print(f"\n（繪圖略過：{e}）")


if __name__ == "__main__":
    main()
