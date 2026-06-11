# TradingView 量化策略回測工具組

利用 TradingView Pro 會員的資料（價量、成交量、財報基本面）進行個股策略回測。
包含兩條路線，互相搭配使用：

| 路線 | 用途 | 資料來源 |
|------|------|----------|
| **Pine Script 策略庫** (`strategies/pine/`) | 直接在 TradingView 上回測，可使用基本面財報資料 | TradingView 內建（你的 Pro 帳號） |
| **Python 回測引擎** (`backtest/`) | 深入統計分析、批次比較多策略、輸出交易明細 | TradingView 匯出的 CSV |

---

## 一、Pine Script 策略庫（建議從這裡開始）

### 使用方式
> **做美股的話，先看 [`strategies/美股策略分類指南.md`](strategies/美股策略分類指南.md)** ——
> 按股票類型（權值股/動能股/題材股/防禦股/ETF）分類好的策略對照表與調參建議。
> 所有策略預設：初始資金 $50,000、手續費 0、滑價 0。

1. 在 TradingView 開啟想測的個股圖表（建議日線）
2. 開啟「Pine 編輯器」（圖表下方）
3. 貼上 `strategies/pine/` 任一支策略的完整內容 → 點「新增至圖表」
4. 開啟「策略測試器」分頁查看：淨利、勝率、最大回撤、獲利因子、每筆交易明細
5. 點策略名稱旁的齒輪調整參數，做敏感度測試

### 策略總覽

| 檔案 | 策略 | 因子類型 | 適合標的 |
|------|------|----------|----------|
| `01_ma_trend_adx.pine` | 雙均線趨勢 + ADX 濾網 + ATR 移動停損 | 價格趨勢 | 趨勢明顯的股票/指數 |
| `02_rsi_bollinger_meanrev.pine` | RSI 超賣 + 布林下軌低接，回均值出場 | 均值回歸 | 大型權值股、震盪市 |
| `03_volume_breakout.pine` | 爆量（RVOL > 2）突破 50 日前高 | 量價 | 中小型成長股、題材股 |
| `04_obv_vwap_accumulation.pine` | OBV 籌碼累積 + MFI 資金流確認 | 量能/籌碼 | 主力吸籌型標的 |
| `05_fundamental_momentum.pine` | EPS/營收年增 + ROE 濾網 + 價格動能 | **基本面**+動能 | 基本面成長股 |
| `06_multifactor_score.pine` | 六因子評分（趨勢/動能/量能/波動/EPS/營收） | **多因子綜合** | 全市場通用 |
| `07_macro_regime.pine` | 總經情勢評分濾網（FRED 數據：就業/曲線/通膨/Fed/信用/生產） | **總經** | 任何個股（套用總經風險開關） |

> 策略 05、06 使用 `request.financial()` 抓財報資料（EPS、營收、ROE），
> 這正是 Pro 會員資料的優勢。若標的在 TradingView 上沒有財務數據，
> 06 可關閉「計入基本面因子」選項。

### 回測注意事項（避免常見陷阱）
- 所有策略已內建 **0.1% 手續費 + 滑價**，台股請依實際費率調整（手續費 0.1425% + 賣出證交稅 0.3%）
- 訊號都在 **收盤確認、下一棒成交**，沒有前視偏差
- 用「回測起始日/結束日」參數切分 **樣本內優化 / 樣本外驗證**，避免過度擬合
- 同一組參數至少測 5–10 檔不同產業的股票，確認不是只對單一股票有效

---

## 二、Python 回測引擎

### 安裝
```bash
pip install pandas numpy matplotlib
```

### 從 TradingView 匯出資料
圖表右上角「⋯」→「匯出圖表資料」→ 下載 CSV（Pro 會員可匯出完整歷史資料）。

### 執行
```bash
cd backtest

# 先用合成資料確認流程
python run_backtest.py --demo

# 跑你匯出的個股資料（一次比較全部策略 + Buy&Hold 基準）
python run_backtest.py ~/Downloads/TSMC_1D.csv

# 只跑單一策略、自訂資金與費率
python run_backtest.py data.csv --strategy 03_爆量突破前高 --capital 500000 --commission 0.001425
```

### 輸出
- 終端機：各策略 vs **Buy & Hold 基準** 的完整比較表（CAGR、Sharpe、Sortino、最大回撤、Calmar、勝率、獲利因子…）
- `results/summary.csv`：績效比較表
- `results/equity_curves.png`：權益曲線圖
- `results/<策略>_trades.csv`：每筆交易明細（進出場時間/價格/損益/出場原因）

### 架構
```
backtest/
├── engine.py        # 事件式回測引擎（下一棒開盤成交、停損停利、手續費滑價）
├── strategies.py    # 策略訊號（與 Pine 01-04、06 對應）
├── metrics.py       # 績效指標計算
└── run_backtest.py  # CLI 入口
```

要加自己的策略：在 `strategies.py` 寫一個回傳 `(entries, exits)` 布林 Series 的函式，
加進 `ALL_STRATEGIES` 字典即可。

---

## 三、總經策略回測（`backtest/macro/`）

用真實總經數據（FRED：失業率、殖利率曲線、CPI、聯邦基金利率、高收益債利差、工業生產）
建立 0–6 分「總經情勢評分」，已對 S&P 500 完成 1998–2025 實證回測：

```bash
cd backtest/macro
python fetch_data.py      # 下載總經數據（GitHub 公開鏡像）
python macro_strategy.py  # 回測 + 預測力檢驗 + 樣本外驗證 + 敏感度分析
```

主要結論（詳見 `results/`）：
- 評分有單調預測力：6 分時下月上漲機率 79%、平均 +1.5%；2 分以下平均為負
- 總經濾網的價值在**降風險**：最大回撤 -51% → -30%，Sharpe 0.62 → 0.76
- 多頭年代會落後 Buy & Hold（保險成本）；與價格趨勢搭配效果最佳
- 已處理數據公布延遲（shift 1 個月），無前視偏差

Pine 版為 `07_macro_regime.pine`，可在 TradingView 直接套用到任何個股。

---

## 建議的研究流程

1. **選股池**：先用 TradingView 篩選器挑 10–20 檔候選股（基本面 + 流動性條件）
2. **Pine 快速掃描**：每檔套用策略 06 多因子評分，看哪些股票對哪類因子有反應
3. **深入測試**：對有潛力的「股票 × 策略」組合，匯出 CSV 用 Python 引擎跑完整統計
4. **樣本外驗證**：參數用 2018–2022 優化，2023 之後驗證；績效衰退過多就放棄
5. **檢查穩健性**：參數微調 ±20% 績效不應劇變；勝率/獲利因子要看交易次數是否足夠（< 30 筆參考價值低）
