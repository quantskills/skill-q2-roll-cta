"""Q2 数据层：从 PandaData 拉取商品期货全合约日线，或读取本地 parquet。

数据来源优先级：
1. 调用方通过 input_data 传入 daily / contracts / dominant；
2. config["data_dir"] 指向包含三个 parquet 的目录；
3. 使用 PandaData 额定接口现拉（需要 PANDA_DATA_USERNAME / PANDA_DATA_PASSWORD）。
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterable

import pandas as pd

DEFAULT_PRODUCTS = [
    "RB", "HC", "I", "J", "JM", "CU", "AL", "ZN", "AU", "AG", "RU",
    "M", "Y", "P", "C", "TA", "MA", "FG",
]
DEFAULT_START = "20210101"
DEFAULT_END = "20251231"


def _retry(fn, *args, attempts: int = 4, **kwargs):
    last = None
    for attempt in range(attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise last


def _init_panda_data() -> None:
    import panda_data

    username = os.environ.get("PANDA_DATA_USERNAME")
    password = os.environ.get("PANDA_DATA_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "未配置 PandaData 凭据：请设置 PANDA_DATA_USERNAME / PANDA_DATA_PASSWORD，"
            "或通过 input_data / config['data_dir'] 提供本地数据"
        )
    panda_data.init_token(
        username=username,
        password=password,
        base_url=os.environ.get("PANDA_DATA_BASE_URL", "http://pandadata.pandaaiquant.com"),
    )


def load_local(data_dir: str | Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base = Path(data_dir)
    daily = pd.read_parquet(base / "daily.parquet")
    contracts = pd.read_parquet(base / "contracts.parquet")
    dominant = pd.read_parquet(base / "dominant.parquet")
    return daily, contracts, dominant


def _dominant(products: list[str], start: str, end: str) -> pd.DataFrame:
    import panda_data

    dom = _retry(panda_data.get_future_dominant, underlying_symbol=products,
                 start_date=start, end_date=end)
    dom["date"] = dom["date"].astype(str)
    return dom.sort_values(["underlying_symbol", "date"]).reset_index(drop=True)


def _contract_codes(dom: pd.DataFrame, start: str, end: str) -> dict[str, list[str]]:
    suffix = {}
    for product, grp in dom.groupby("underlying_symbol"):
        suffix[product] = grp["symbol"].iloc[0].split(".")[-1]
    start_year = int(start[:4])
    end_year = int(end[:4])
    out = {}
    for product, sfx in suffix.items():
        codes = [f"{product}{yy % 100:02d}{mm:02d}.{sfx}"
                 for yy in range(start_year, end_year + 2) for mm in range(1, 13)]
        out[product] = codes
    return out


def _fetch_contracts(codes_by_product: dict[str, list[str]]) -> pd.DataFrame:
    import panda_data

    frames = []
    for product, codes in codes_by_product.items():
        for i in range(0, len(codes), 40):
            df = _retry(panda_data.get_future_detail, symbol=codes[i:i + 40], fields=[])
            if df is not None and not df.empty:
                frames.append(df)
            time.sleep(0.2)
    if not frames:
        raise RuntimeError("PandaData 未返回合约信息")
    out = pd.concat(frames, ignore_index=True)
    out["maturity_date"] = pd.to_datetime(out["maturity_date"], errors="coerce")
    out["listed_date"] = pd.to_datetime(out["listed_date"], errors="coerce")
    return out.drop_duplicates("symbol")


def _fetch_daily(symbols: list[str], start: str, end: str) -> pd.DataFrame:
    import panda_data

    frames = []
    for i in range(0, len(symbols), 35):
        df = _retry(panda_data.get_future_daily, symbol=symbols[i:i + 35],
                    start_date=start, end_date=end, fields=[])
        if df is not None and not df.empty:
            frames.append(df)
        time.sleep(0.2)
    if not frames:
        raise RuntimeError("PandaData 未返回合约日线")
    out = pd.concat(frames, ignore_index=True)
    out["date"] = out["date"].astype(str)
    for col in ("open", "high", "low", "close", "settlement", "volume", "open_interest"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.drop_duplicates(["symbol", "date"]).sort_values(["symbol", "date"])


def fetch(products: Iterable[str] | None = None, start: str = DEFAULT_START,
          end: str = DEFAULT_END) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """通过 PandaData 获取全合约日线、合约元信息与主力序列。"""
    products = list(products or DEFAULT_PRODUCTS)
    _init_panda_data()
    dom = _dominant(products, start, end)
    if dom.empty:
        raise RuntimeError("PandaData 未返回主力合约序列")
    detail = _fetch_contracts(_contract_codes(dom, start, end))
    detail = detail[detail["underlying_symbol"].isin(products)]
    detail = detail[(detail["maturity_date"] >= pd.Timestamp(start) - pd.Timedelta(days=220))
                    & (detail["maturity_date"] <= pd.Timestamp(end) + pd.Timedelta(days=220))]
    daily = _fetch_daily(detail["symbol"].tolist(), start, end)
    return daily, detail.reset_index(drop=True), dom
