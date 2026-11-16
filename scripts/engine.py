"""Q2 换月账本：同一冻结 CTA 下三种换月规则的实合约收益对照。

规则：
  fixed    每月 15 日（或其后首个交易日）换到持仓量最大的合约
  oi       目标合约持仓量连续 2 日超过当前合约后，次日开盘一次换完
  gradual  同一触发，分 3 个交易日各换 1/3

信号冻结：品种连续研究序列的 60 日动量，每周最后一个交易日定方向，次日开盘执行。
盈亏只用具体合约的原始开收盘价计算，不使用复权价格。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Params:
    capital_per_product: float = 1_000_000.0
    cost_bps_per_side: float = 1.5
    momentum_days: int = 60
    dead_zone: float = 0.02
    force_roll_days: int = 10
    gradual_days: int = 3


@dataclass
class ProductData:
    bars: dict[tuple[str, str], dict]
    dates: list[str]
    contracts: dict[str, dict]
    signal: dict[str, int]


@dataclass
class Trade:
    date: str
    product: str
    contract: str
    lots: float
    price: float
    mult: float
    kind: str
    cost: float

    @property
    def notional(self) -> float:
        return abs(self.lots) * self.price * self.mult


@dataclass
class SimResult:
    name: str
    daily: pd.DataFrame
    trades: list[Trade] = field(default_factory=list)
    rolls: list[dict] = field(default_factory=list)


class defaultdict_int(dict):
    def __missing__(self, key):
        self[key] = 0
        return 0


def _normalise_dates(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    df = df.copy()
    df[col] = df[col].astype(str)
    return df


def validate_frames(daily: pd.DataFrame, contracts: pd.DataFrame,
                    dominant: pd.DataFrame) -> None:
    required_daily = {"symbol", "underlying_symbol", "date", "open", "close",
                      "volume", "open_interest", "settlement"}
    required_contracts = {"symbol", "underlying_symbol", "maturity_date",
                          "contract_multiplier"}
    required_dominant = {"underlying_symbol", "symbol", "date"}
    missing = required_daily - set(daily.columns)
    if missing:
        raise ValueError(f"daily 缺少字段: {sorted(missing)}")
    missing = required_contracts - set(contracts.columns)
    if missing:
        raise ValueError(f"contracts 缺少字段: {sorted(missing)}")
    missing = required_dominant - set(dominant.columns)
    if missing:
        raise ValueError(f"dominant 缺少字段: {sorted(missing)}")
    if daily.empty or contracts.empty or dominant.empty:
        raise ValueError("行情数据为空，无法计算换月账本")


def build_products(daily: pd.DataFrame, contracts: pd.DataFrame,
                   dominant: pd.DataFrame, params: Params | None = None,
                   products: Iterable[str] | None = None) -> dict[str, ProductData]:
    params = params or Params()
    daily = _normalise_dates(daily)
    dominant = _normalise_dates(dominant)
    wanted = set(products) if products else None
    products_out: dict[str, ProductData] = {}
    meta_all = contracts.set_index("symbol").to_dict("index")

    for product, dom in dominant.groupby("underlying_symbol"):
        if wanted is not None and product not in wanted:
            continue
        dom = dom.sort_values("date")
        sub = daily[daily["underlying_symbol"] == product]
        if sub.empty or dom.empty:
            continue
        bars: dict[tuple[str, str], dict] = {}
        for row in sub.itertuples(index=False):
            m = meta_all.get(row.symbol, {})
            bars[(row.symbol, row.date)] = {
                "open": float(row.open), "close": float(row.close),
                "volume": float(row.volume), "oi": float(row.open_interest),
                "settle": float(row.settlement),
                "maturity": m.get("maturity_date"),
                "mult": float(m.get("contract_multiplier") or 1.0),
            }
        dates = sorted(dom["date"].unique().tolist())
        moves, prev_c, prev_close = [], None, None
        for d in dates:
            c = dom.loc[dom["date"] == d, "symbol"].iloc[0]
            row = bars.get((c, d))
            if row is None:
                moves.append(0.0)
                prev_c, prev_close = c, None
                continue
            moves.append(row["close"] / prev_close - 1 if prev_c == c and prev_close else 0.0)
            prev_c, prev_close = c, row["close"]
        index = (1 + pd.Series(moves, index=dates)).cumprod()
        mom = index / index.shift(params.momentum_days) - 1

        weekly: dict[str, int] = {}
        last = 0
        cal = pd.to_datetime(dates).isocalendar()
        keys = list(zip(cal.year.tolist(), cal.week.tolist()))
        for key in dict.fromkeys(keys):
            idx = [i for i, k in enumerate(keys) if k == key][-1]
            value = float(mom.iloc[idx])
            if value > params.dead_zone:
                last = 1
            elif value < -params.dead_zone:
                last = -1
            weekly[dates[idx]] = last
        signal: dict[str, int] = {}
        cur = 0
        for d in dates:
            cur = weekly.get(d, cur)
            signal[d] = cur

        contracts_p = {c: m for c, m in meta_all.items()
                       if m.get("underlying_symbol") == product}
        products_out[product] = ProductData(bars=bars, dates=dates,
                                            contracts=contracts_p, signal=signal)
    if not products_out:
        raise ValueError("没有可用的品种数据，请检查 products / 日期区间")
    return products_out


def trading_dates(products: dict[str, ProductData]) -> list[str]:
    return sorted({d for p in products.values() for d in p.dates})


def tradable(row: dict | None, date: str, force_roll_days: int = 10) -> bool:
    if not row or not row.get("open") or row.get("volume", 0) < 100 or row.get("oi", 0) <= 0:
        return False
    maturity = row.get("maturity")
    if maturity is not None and not pd.isna(maturity):
        if (pd.Timestamp(maturity) - pd.Timestamp(date)).days <= force_roll_days:
            return False
    return True


def pick_target(p: ProductData, date: str, params: Params) -> str | None:
    best, best_oi = None, -1.0
    for c in p.contracts:
        row = p.bars.get((c, date))
        if not tradable(row, date, params.force_roll_days):
            continue
        if row["oi"] > best_oi:
            best, best_oi = c, row["oi"]
    return best


def simulate(products: dict[str, ProductData], dates: list[str], rule: str,
             params: Params | None = None) -> SimResult:
    params = params or Params()
    if rule not in {"fixed", "oi", "gradual"}:
        raise ValueError(f"未知换月规则: {rule}")
    holdings: dict[str, dict[str, float]] = {p: {} for p in products}
    lots_by_product: dict[str, float] = {}
    pending: dict[str, dict] = {}
    oi_streak: dict[str, int] = defaultdict_int()
    fixed_month: dict[str, str] = {}
    last_close: dict[str, float] = {}
    total_capital = params.capital_per_product * len(products)
    equity = total_capital
    curve, trades, rolls = [], [], []

    for d in dates:
        pnl = 0.0
        cost_day = 0.0
        product_daily = {p: 0.0 for p in products}

        for product, pos in holdings.items():
            p = products[product]
            for c, q in list(pos.items()):
                row = p.bars.get((c, d))
                pc = last_close.get(c)
                if row and pc:
                    move = q * row["mult"] * (row["open"] - pc)
                    pnl += move
                    product_daily[product] += move

        for product, pos in holdings.items():
            plan = pending.get(product)
            if not plan:
                continue
            p = products[product]
            target = plan["target"]
            row_new = p.bars.get((target, d))
            if not row_new or not row_new["open"]:
                continue
            sign = plan.get("sign", 0) or 1
            lots = lots_by_product.get(product)
            if lots is None:
                lots = max(1.0, math.floor(
                    params.capital_per_product / (row_new["open"] * row_new["mult"])))
                lots_by_product[product] = lots

            for c, q in list(pos.items()):
                if c == target and plan["kind"] != "flip":
                    continue
                row_old = p.bars.get((c, d))
                if not row_old:
                    del pos[c]
                    continue
                exit_price = row_old["open"]
                if row_old["volume"] <= 0 and last_close.get(c):
                    exit_price = last_close[c]
                if plan["kind"] == "gradual":
                    if "slice" not in plan:
                        plan["slice"] = lots / params.gradual_days
                    exit_q = q if plan.get("remaining", params.gradual_days) <= 1 else min(q, plan["slice"])
                else:
                    exit_q = q
                cost = abs(exit_q) * exit_price * row_old["mult"] * params.cost_bps_per_side / 10000
                cost_day += cost
                pnl -= cost
                product_daily[product] -= cost
                pos[c] = q - exit_q
                if abs(pos[c]) < 1e-9:
                    del pos[c]
                trades.append(Trade(d, product, c, -exit_q, exit_price,
                                    row_old["mult"], "roll_out", cost))
                rolls.append({
                    "date": d, "product": product, "rule": rule, "from": c, "to": target,
                    "from_open": exit_price, "to_open": row_new["open"],
                    "gap_bps": (row_new["open"] - exit_price) / exit_price * 10000,
                    "from_volume": row_old["volume"], "to_volume": row_new["volume"],
                    "from_oi": row_old["oi"], "to_oi": row_new["oi"], "lots": abs(exit_q),
                    "kind": plan["kind"],
                })

            want = sign * lots
            have = pos.get(target, 0.0)
            if plan["kind"] == "gradual":
                if "slice" not in plan:
                    plan["slice"] = lots / params.gradual_days
                delta = min(plan["slice"], want - have)
            else:
                delta = want - have
            if abs(delta) > 1e-9:
                cost = abs(delta) * row_new["open"] * row_new["mult"] * params.cost_bps_per_side / 10000
                cost_day += cost
                pnl -= cost
                product_daily[product] -= cost
                pos[target] = have + delta
                trades.append(Trade(d, product, target, delta, row_new["open"],
                                    row_new["mult"], "roll_in", cost))
            if plan["kind"] == "gradual":
                plan["remaining"] = plan.get("remaining", params.gradual_days) - 1
                if plan["remaining"] <= 0:
                    pending.pop(product, None)
            else:
                pending.pop(product, None)

        for product, pos in holdings.items():
            p = products[product]
            for c, q in pos.items():
                row = p.bars.get((c, d))
                if row:
                    move = q * row["mult"] * (row["close"] - row["open"])
                    pnl += move
                    product_daily[product] += move

        equity += pnl
        curve.append({"date": d, "equity": equity, "pnl": pnl, "cost": cost_day, **product_daily})
        for product, pos in holdings.items():
            p = products[product]
            for c in pos:
                row = p.bars.get((c, d))
                if row:
                    last_close[c] = row["close"]

        for product, p in products.items():
            if d not in p.dates or product in pending:
                continue
            pos = holdings[product]
            held = next(iter(pos), None)
            target = pick_target(p, d, params)
            if not target:
                continue
            sig = p.signal.get(d, 0)

            if held:
                row_h = p.bars.get((held, d))
                force = not row_h or row_h["volume"] < 100
                if row_h and not pd.isna(row_h.get("maturity")):
                    force = force or (pd.Timestamp(row_h["maturity"]) - pd.Timestamp(d)).days <= params.force_roll_days
                if force and target != held:
                    pending[product] = {"target": target, "sign": sig, "kind": "force", "frac": 1.0}
                    continue

            if not held:
                if sig != 0:
                    pending[product] = {"target": target, "sign": sig, "kind": "entry", "frac": 1.0}
                continue

            signed = sum(pos.values())
            if sig != 0 and np.sign(signed) != sig:
                pending[product] = {"target": target, "sign": sig, "kind": "flip", "frac": 1.0}
                continue

            if rule == "fixed":
                if pd.Timestamp(d).day >= 15 and fixed_month.get(product) != d[:6]:
                    fixed_month[product] = d[:6]
                    if target != held:
                        pending[product] = {"target": target, "sign": sig, "kind": "fixed", "frac": 1.0}
            else:
                if target != held:
                    row_h = p.bars.get((held, d))
                    row_t = p.bars.get((target, d))
                    if row_h and row_t and row_t["oi"] > row_h["oi"]:
                        oi_streak[product] += 1
                    else:
                        oi_streak[product] = 0
                    if oi_streak[product] >= 2:
                        pending[product] = {
                            "target": target, "sign": sig,
                            "kind": "gradual" if rule == "gradual" else "oi",
                            "frac": 1 / params.gradual_days if rule == "gradual" else 1.0,
                            "remaining": params.gradual_days,
                        }
                        oi_streak[product] = 0
                else:
                    oi_streak[product] = 0

    daily = pd.DataFrame(curve)
    if daily.empty:
        raise ValueError("模拟结果为空，请检查日期区间与数据覆盖")
    daily["ret"] = daily["pnl"] / total_capital
    return SimResult(rule, daily, trades, rolls)


def metrics(res: SimResult, params: Params | None = None,
            product_count: int | None = None) -> dict:
    params = params or Params()
    d = res.daily.set_index("date")
    ret = d["ret"]
    years = len(ret) / 252
    total = float(d["equity"].iloc[-1] / d["equity"].iloc[0] - 1)
    ann = total / years if years > 0 else 0.0
    vol = ret.std() * math.sqrt(252)
    curve = d["equity"]
    mdd = (curve / curve.cummax() - 1).min()
    gross = d["pnl"].sum() + d["cost"].sum()
    notional = sum(t.notional for t in res.trades)
    n_products = product_count or 18
    return {
        "rule": res.name,
        "years": round(float(years), 3),
        "total_return": round(total, 4),
        "annual_return": round(float(ann), 4),
        "annual_vol": round(float(vol), 4),
        "sharpe": round(float(ret.mean() * 252 / vol), 3) if vol else None,
        "max_drawdown": round(float(mdd), 4),
        "calmar": round(float(ann / abs(mdd)), 3) if mdd else None,
        "total_cost": round(float(d["cost"].sum()), 2),
        "cost_share_of_gross": round(float(d["cost"].sum() / gross), 4) if gross else None,
        "roll_count": len(res.rolls),
        "roll_events": len({(r["date"][:4], r["product"], r["from"], r["to"]) for r in res.rolls}),
        "trade_count": len(res.trades),
        "turnover_x": round(float(notional / (params.capital_per_product * n_products) / years), 2),
    }


def stress_months(res: SimResult) -> pd.DataFrame:
    d = res.daily.copy()
    d["month"] = d["date"].str[:6]
    m = d.groupby("month").agg(ret=("ret", lambda x: (1 + x).prod() - 1), cost=("cost", "sum"))
    return m.sort_values("ret").head(6).reset_index()


def roll_summary(rolls_by_rule: dict[str, list[dict]]) -> list[dict]:
    rows = []
    for rule, rolls in rolls_by_rule.items():
        if not rolls:
            continue
        df = pd.DataFrame(rolls)
        rows.append({
            "rule": rule, "rolls": len(df),
            "median_abs_gap_bps": round(float(df["gap_bps"].abs().median()), 2),
            "p90_abs_gap_bps": round(float(df["gap_bps"].abs().quantile(0.9)), 2),
            "low_liquidity_rolls": int(((df["from_volume"] < 5000) | (df["to_volume"] < 5000)).sum()),
        })
    return rows
