"""下載總經回測所需資料（來源：GitHub 上的公開資料集 / FRED 鏡像）。

序列一覽：
  S&P 500 月線      datasets/s-and-p-500（Shiller 資料，月均價）
  UNRATE   失業率    FRED 鏡像（月）
  FEDFUNDS 聯邦基金  FRED 鏡像（月）
  CPIAUCSL CPI      FRED 鏡像（月）
  T10Y2Y   殖利率曲線 FRED 鏡像（日）
  BAMLH0A0HYM2 高收益債利差 FRED 鏡像（日）
  INDPRO   工業生產   FRED 鏡像（月）
"""

import os
import urllib.request

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

MIRROR_REF = "bf64e83fa4c2a6e72c37d3883476dc81bd9d2e31"
MIRROR = f"https://raw.githubusercontent.com/maaurocp/Trading_Protocol/{MIRROR_REF}/data/raw"

SOURCES = {
    "sp500.csv": "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv",
    "UNRATE.csv": f"{MIRROR}/fred_UNRATE.csv",
    "FEDFUNDS.csv": f"{MIRROR}/fred_FEDFUNDS.csv",
    "CPIAUCSL.csv": f"{MIRROR}/fred_CPIAUCSL.csv",
    "T10Y2Y.csv": f"{MIRROR}/fred_T10Y2Y.csv",
    "HY_SPREAD.csv": f"{MIRROR}/fred_BAMLH0A0HYM2.csv",
    "INDPRO.csv": f"{MIRROR}/fred_INDPRO.csv",
}


def fetch_all(force: bool = False):
    os.makedirs(DATA_DIR, exist_ok=True)
    for fname, url in SOURCES.items():
        path = os.path.join(DATA_DIR, fname)
        if os.path.exists(path) and not force:
            print(f"已存在，略過：{fname}")
            continue
        print(f"下載 {fname} ...")
        urllib.request.urlretrieve(url, path)
    print("完成。")


if __name__ == "__main__":
    fetch_all()
