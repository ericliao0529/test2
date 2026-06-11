"""總經情勢評分策略（Macro Regime Score）回測。

策略邏輯
--------
每月底計算 0–6 分的總經評分，每個因子健康記 1 分：
  1. 就業    失業率 < 其 12 個月均值（勞動市場未轉差）
  2. 殖利率曲線  10Y-2Y 利差 > 0（未倒掛）
  3. 通膨    CPI 年增率 < 4%，或正在下降（3 個月前比較）
  4. 貨幣政策  聯邦基金利率 3 個月變化 <= 0（Fed 沒在升息）
  5. 信用市場  高收益債利差 < 其 6 個月均值（信用環境未惡化）
  6. 實體經濟  工業生產年增率 > 0

部位規則（每月底再平衡，無前視偏差）：
  - 純總經策略：評分 >= 門檻 → 持有 S&P 500；否則持有現金（賺聯邦基金利率）
  - 純趨勢策略：S&P > 10 月均線 → 持有（Faber 趨勢法，作為對照）
  - 混合策略：總經與趨勢各佔一半倉位（兩者皆好 100%、其一 50%、皆差 0%）

避免前視偏差的處理
------------------
- 失業率/CPI/工業生產：M 月數據在 M+1 月中上旬才公布 → 訊號一律往後挪 1 個月
  （月底交易時只能看到上上個月的數據）
- 聯邦基金利率：同樣挪 1 個月（保守處理）
- 殖利率曲線/信用利差/股價：市場即時數據，取當月底值，不挪
- 交易成本：每次換倉收 0.1%

已知限制（誠實聲明）
------------------
- Shiller 的 S&P 月資料是「當月日均價」而非月底收盤，報酬序列略為平滑
- 僅含價格報酬、不含股利：策略在場時間 ~70-80%，相對 Buy&Hold 每年
  約少賺 0.3-0.6% 股利差，下方結果未調整此項
"""

import os

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RESULT_DIR = os.path.join(os.path.dirname(__file__), "results")

COST_PER_SWITCH = 0.001   # 換倉成本 0.1%
ENTRY_THRESHOLD = 4       # 評分 >= 4（滿分 6）才持股 —— 事前決定，非事後挑選


# ---------- 資料載入 ----------

def _read_fred(fname: str, value_name: str) -> pd.Series:
    df = pd.read_csv(os.path.join(DATA_DIR, fname))
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["value"].rename(value_name)


def load_monthly_data() -> pd.DataFrame:
    """全部對齊成月頻（月底）資料表。"""
    spx_raw = pd.read_csv(os.path.join(DATA_DIR, "sp500.csv"))
    spx_raw["Date"] = pd.to_datetime(spx_raw["Date"])
    spx = spx_raw.set_index("Date")["SP500"].rename("spx")
    spx.index = spx.index.to_period("M").to_timestamp("M")  # 對齊到月底

    monthly = {
        "unrate": _read_fred("UNRATE.csv", "unrate"),
        "fedfunds": _read_fred("FEDFUNDS.csv", "fedfunds"),
        "cpi": _read_fred("CPIAUCSL.csv", "cpi"),
        "indpro": _read_fred("INDPRO.csv", "indpro"),
    }
    daily = {
        "t10y2y": _read_fred("T10Y2Y.csv", "t10y2y"),
        "hy_spread": _read_fred("HY_SPREAD.csv", "hy_spread"),
    }

    out = pd.DataFrame({"spx": spx})
    for name, s in monthly.items():
        s.index = s.index.to_period("M").to_timestamp("M")
        out[name] = s
    for name, s in daily.items():
        out[name] = s.resample("ME").last()   # 取每月最後一個交易日
    return out


# ---------- 因子與評分 ----------

def build_factors(df: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(index=df.index)

    # 月頻官方數據：公布延遲 1 個月 → shift(1)
    unrate = df["unrate"].shift(1)
    cpi = df["cpi"].shift(1)
    fedfunds = df["fedfunds"].shift(1)
    indpro = df["indpro"].shift(1)

    cpi_yoy = cpi.pct_change(12) * 100
    indpro_yoy = indpro.pct_change(12) * 100

    f["f_employment"] = (unrate < unrate.rolling(12).mean()).astype(float)
    f["f_yieldcurve"] = (df["t10y2y"] > 0).astype(float)
    f["f_inflation"] = ((cpi_yoy < 4.0) | (cpi_yoy < cpi_yoy.shift(3))).astype(float)
    f["f_fed"] = (fedfunds.diff(3) <= 0).astype(float)
    f["f_credit"] = (df["hy_spread"] < df["hy_spread"].rolling(6).mean()).astype(float)
    f["f_indpro"] = (indpro_yoy > 0).astype(float)

    f["score"] = f.sum(axis=1)

    # 對照用：純價格趨勢（10 月均線，Faber）
    f["trend"] = (df["spx"] > df["spx"].rolling(10).mean()).astype(float)
    return f


# ---------- 回測 ----------

def backtest_weights(df: pd.DataFrame, weights: pd.Series, cost: float = COST_PER_SWITCH) -> pd.Series:
    """weights: 每月底決定的下月持股比例（0~1）。其餘部位賺聯邦基金利率。
    回傳每月報酬序列。"""
    spx_ret = df["spx"].pct_change()
    cash_ret = (df["fedfunds"].shift(1) / 100) / 12   # 上月底已知的利率水準
    w = weights.shift(1)                              # 月底決定 → 下月生效
    turnover_cost = w.diff().abs().fillna(0) * cost
    ret = w * spx_ret + (1 - w) * cash_ret.fillna(0) - turnover_cost
    return ret.dropna()


def perf_stats(ret: pd.Series, name: str) -> dict:
    equity = (1 + ret).cumprod()
    years = len(ret) / 12
    cagr = equity.iloc[-1] ** (1 / years) - 1
    vol = ret.std() * np.sqrt(12)
    sharpe = ret.mean() * 12 / vol if vol > 0 else np.nan
    dd = (equity / equity.cummax() - 1).min()
    worst_month = ret.min()
    return {
        "策略": name,
        "CAGR %": round(cagr * 100, 2),
        "年化波動 %": round(vol * 100, 2),
        "Sharpe": round(sharpe, 2),
        "最大回撤 %": round(dd * 100, 2),
        "Calmar": round(cagr / abs(dd), 2) if dd < 0 else np.nan,
        "最差單月 %": round(worst_month * 100, 2),
        "期末淨值(1元)": round(equity.iloc[-1], 2),
    }


def conditional_returns(df: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    """評分 vs 下月 S&P 報酬：檢驗評分有沒有預測力（策略有效性的核心證據）。"""
    nxt = df["spx"].pct_change().shift(-1) * 100
    score = factors["score"]
    buckets = pd.cut(score, bins=[-0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5],
                     labels=["0-1分", "2分", "3分", "4分", "5分", "6分"])
    g = nxt.groupby(buckets, observed=True)
    out = pd.DataFrame({
        "月數": g.count(),
        "下月平均報酬 %": g.mean().round(2),
        "下月報酬中位數 %": g.median().round(2),
        "上漲機率 %": (g.apply(lambda x: (x > 0).mean()) * 100).round(1),
        "下月最差 %": g.min().round(2),
    })
    return out


def main():
    os.makedirs(RESULT_DIR, exist_ok=True)
    df = load_monthly_data()
    factors = build_factors(df)

    # 信用利差 1997 年才有 → 評分自 1998 年起完整
    start = "1998-01-31"
    df = df.loc[start:].copy()
    factors = factors.loc[start:].copy()
    # 截到股價與評分都齊的最後一個月
    valid = df["spx"].notna() & factors["score"].notna()
    df, factors = df[valid], factors[valid]
    print(f"回測期間：{df.index[0].date()} ~ {df.index[-1].date()}（{len(df)} 個月）\n")

    # ===== 各策略權重 =====
    w_macro = (factors["score"] >= ENTRY_THRESHOLD).astype(float)
    w_trend = factors["trend"]
    w_combo = (w_macro + w_trend) / 2
    w_hold = pd.Series(1.0, index=df.index)

    strategies = {
        "Buy & Hold": w_hold,
        "純總經評分(>=4分)": w_macro,
        "純價格趨勢(10月線)": w_trend,
        "總經+趨勢混合": w_combo,
    }

    rows, equity_curves, ret_map = [], {}, {}
    for name, w in strategies.items():
        ret = backtest_weights(df, w)
        rows.append(perf_stats(ret, name))
        equity_curves[name] = (1 + ret).cumprod()
        ret_map[name] = ret

    summary = pd.DataFrame(rows).set_index("策略")
    pd.set_option("display.unicode.east_asian_width", True)
    pd.set_option("display.width", 200)
    print("========== 績效比較（1998–2025，月頻） ==========")
    print(summary.to_string())

    # ===== 有效性檢驗 1：評分 vs 下月報酬 =====
    cond = conditional_returns(df, factors)
    print("\n========== 評分預測力：不同評分下的「下個月」S&P 表現 ==========")
    print(cond.to_string())

    # ===== 有效性檢驗 2：樣本內 / 樣本外 =====
    split = "2012-12-31"
    print("\n========== 樣本切分穩健性 ==========")
    sub_rows = []
    for name, ret in ret_map.items():
        for label, r in [("前半 1998-2012", ret[:split]), ("後半 2013-2025", ret[split:])]:
            s = perf_stats(r, f"{name} | {label}")
            sub_rows.append(s)
    print(pd.DataFrame(sub_rows).set_index("策略").to_string())

    # ===== 有效性檢驗 3：門檻敏感度（避免剛好挑到幸運參數） =====
    print("\n========== 門檻敏感度（評分 >= N 才持股） ==========")
    sens_rows = []
    for th in range(1, 7):
        ret = backtest_weights(df, (factors["score"] >= th).astype(float))
        s = perf_stats(ret, f"門檻 {th} 分")
        s["在場時間 %"] = round((factors["score"] >= th).mean() * 100, 1)
        sens_rows.append(s)
    print(pd.DataFrame(sens_rows).set_index("策略").to_string())

    # ===== 輸出 =====
    summary.to_csv(os.path.join(RESULT_DIR, "macro_summary.csv"), encoding="utf-8-sig")
    cond.to_csv(os.path.join(RESULT_DIR, "macro_score_predictive.csv"), encoding="utf-8-sig")
    factors.assign(spx=df["spx"]).to_csv(os.path.join(RESULT_DIR, "macro_factors.csv"), encoding="utf-8-sig")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 1, figsize=(13, 9), sharex=True,
                                 gridspec_kw={"height_ratios": [3, 1]})
        for name, eq in equity_curves.items():
            axes[0].plot(eq.index, eq, label=name, linewidth=1.4)
        axes[0].set_yscale("log")
        axes[0].set_title("Macro Regime Strategy vs Buy & Hold (S&P 500, monthly, 1998-2025)")
        axes[0].legend(["Buy & Hold", "Macro score (>=4)", "Trend (10m MA)", "Macro + Trend"])
        axes[0].grid(alpha=0.3)
        axes[0].set_ylabel("Growth of $1 (log)")
        axes[1].fill_between(factors.index, factors["score"], color="tab:blue", alpha=0.5, step="mid")
        axes[1].axhline(ENTRY_THRESHOLD - 0.5, color="red", linestyle="--", linewidth=1)
        axes[1].set_ylabel("Macro score (0-6)")
        axes[1].grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(RESULT_DIR, "macro_strategy.png"), dpi=130)
        print(f"\n圖表已輸出：{os.path.join(RESULT_DIR, 'macro_strategy.png')}")
    except Exception as e:
        print(f"（繪圖略過：{e}）")


if __name__ == "__main__":
    main()
