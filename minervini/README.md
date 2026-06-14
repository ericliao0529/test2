# Minervini 超級績效趨勢樣板 (Pine Script v6)

Mark Minervini《超級績效》的趨勢樣板 (Trend Template)，8 大條件判斷個股是否進入
第二階段上升趨勢。每支 `.pine` 都是獨立的 TradingView 指標。

## 檔案

| 檔案 | 內容 |
|------|------|
| `00_trend_template_all.pine` | **統整版**：8 指標一次算完，右上角計分表顯示 X/8 |
| `01_price_above_150_200.pine` | 指標 1：股價站上 150MA 與 200MA |
| `02_ma150_above_ma200.pine`   | 指標 2：150MA > 200MA |
| `03_ma200_trending_up.pine`   | 指標 3：200MA 上升中 (預設 22 天) |
| `04_ma50_above_150_200.pine`  | 指標 4：50MA > 150MA 與 200MA |
| `05_price_above_ma50.pine`    | 指標 5：股價 > 50MA |
| `06_above_52w_low.pine`       | 指標 6：高於 52 週低點 30% 以上 |
| `07_near_52w_high.pine`       | 指標 7：距 52 週高點 25% 以內 |
| `08_rs_rating.pine`           | 指標 8：RS 相對強度評級 ≥ 70 |
| `09_score_subwindow.pine`     | 分數子視窗：總分 (0~8) 柱狀圖，會隨圖表移動 |
| `10_trend_template_strategy.pine` | **策略版**：可回測。進場=首次符合8項，出場=停損/賣訊 |

## 計分表 (table) 為什麼拖圖不會動？
`table` 是釘在畫面角落的固定面板，且永遠只顯示「最新一根 K 棒」的結果，這是它的設計。
要看歷史每一根的分數，請用：
- 統整版已內建：把游標移到任一根 K 棒，右側 **Data Window (數據視窗)** 會顯示那一根的分數與各條件。
- 或加掛 `09_score_subwindow.pine`，總分柱狀圖會隨圖表一起移動。
真正會跟著 K 棒移動的還有：背景綠色高亮、三角形標記、均線。

## 使用方式
1. TradingView 開**日線**圖
2. 底部「Pine 編輯器」貼上程式碼 → 「新增至圖表」
3. 平常看盤用 `00_trend_template_all.pine` 即可

## 注意
- 台股請把 RS 比較標的從 `SPX` 改為 `TWSE:TAIEX`。
- 需要約一年歷史資料，上市未滿一年的新股會失真。
- RS 評級為近似值 (個股 vs 大盤近一年報酬百分位)，非 IBD 全市場排名。
