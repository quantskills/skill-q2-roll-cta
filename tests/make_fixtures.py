"""从真实 PandaData 导出的小样本生成测试 fixtures（不生成任何模拟行情）。

用法：
    python tests/make_fixtures.py <source_data_dir>

source_data_dir 需包含 daily.parquet / contracts.parquet / dominant.parquet。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PRODUCTS = ["RB", "HC"]
START = "20220101"
END = "20221231"


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("用法: python tests/make_fixtures.py <source_data_dir>")
    src = Path(sys.argv[1])
    out = Path(__file__).resolve().parent / "fixtures"
    out.mkdir(parents=True, exist_ok=True)

    daily = pd.read_parquet(src / "daily.parquet")
    contracts = pd.read_parquet(src / "contracts.parquet")
    dominant = pd.read_parquet(src / "dominant.parquet")
    daily["date"] = daily["date"].astype(str)
    dominant["date"] = dominant["date"].astype(str)

    dom = dominant[dominant["underlying_symbol"].isin(PRODUCTS)
                   & dominant["date"].between(START, END)].copy()
    symbols = set(dom["symbol"])
    sub_daily = daily[daily["symbol"].isin(symbols)
                      & daily["date"].between(START, END)].copy()
    symbols = set(sub_daily["symbol"])
    sub_contracts = contracts[contracts["symbol"].isin(symbols)].copy()

    sub_daily.to_parquet(out / "daily.parquet", index=False)
    sub_contracts.to_parquet(out / "contracts.parquet", index=False)
    dom.to_parquet(out / "dominant.parquet", index=False)
    print("daily", sub_daily.shape, "contracts", sub_contracts.shape,
          "dominant", dom.shape, "->", out)


if __name__ == "__main__":
    main()
