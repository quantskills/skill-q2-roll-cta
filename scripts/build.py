"""Q2 换月规则对照 BUILD。

标准入口：
    run(input_data, config=None) -> dict
    validate_input(input_data) -> None

输入：
    input_data: 可选，dict(daily=DataFrame, contracts=DataFrame, dominant=DataFrame)
    config:
        data_dir       本地 parquet 目录（含 daily/contracts/dominant.parquet）
        start_date     回测开始日期 YYYYMMDD，默认 20210101
        end_date       回测结束日期 YYYYMMDD，默认 20251231
        products      品种列表，默认 18 个商品期货
        rules          换月规则，默认 ["fixed", "oi", "gradual"]
        capital_per_product / cost_bps_per_side / momentum_days /
        dead_zone / force_roll_days / gradual_days
        output_dir     可选，写出明细 CSV
        write_production 可选，写出 生产产物/数据库.parquet
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import data as data_layer  # noqa: E402
import engine  # noqa: E402

BUILD_ID = "Q2"
BUILD_NAME = "roll-cta"
RULES = ("fixed", "oi", "gradual")
CONFIG_KEYS = {
    "data_dir", "start_date", "end_date", "products", "rules",
    "capital_per_product", "cost_bps_per_side", "momentum_days",
    "dead_zone", "force_roll_days", "gradual_days",
    "output_dir", "write_production",
}


def validate_input(input_data) -> None:
    """缺字段、空数据、类型错误必须抛出明确异常。"""
    if input_data is None:
        return
    if not isinstance(input_data, dict):
        raise TypeError("input_data 必须是 dict 或 None")
    unknown = set(input_data) - {"daily", "contracts", "dominant"}
    if unknown:
        raise ValueError(f"input_data 含未知字段: {sorted(unknown)}")
    for key, value in input_data.items():
        if not isinstance(value, pd.DataFrame):
            raise TypeError(f"input_data['{key}'] 必须是 pandas.DataFrame")
        if value.empty:
            raise ValueError(f"input_data['{key}'] 为空")
    if input_data:
        engine.validate_frames(input_data["daily"], input_data["contracts"],
                               input_data["dominant"])


def _validate_config(config: dict) -> dict:
    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise TypeError("config 必须是 dict 或 None")
    unknown = set(config) - CONFIG_KEYS
    if unknown:
        raise ValueError(f"config 含未知字段: {sorted(unknown)}")
    cfg = {
        "data_dir": None,
        "start_date": data_layer.DEFAULT_START,
        "end_date": data_layer.DEFAULT_END,
        "products": list(data_layer.DEFAULT_PRODUCTS),
        "rules": list(RULES),
        "capital_per_product": 1_000_000.0,
        "cost_bps_per_side": 1.5,
        "momentum_days": 60,
        "dead_zone": 0.02,
        "force_roll_days": 10,
        "gradual_days": 3,
        "output_dir": None,
        "write_production": False,
    }
    cfg.update(config)

    for key in ("start_date", "end_date"):
        value = str(cfg[key])
        if len(value) != 8 or not value.isdigit():
            raise ValueError(f"{key} 必须是 YYYYMMDD")
        cfg[key] = value
    if cfg["start_date"] > cfg["end_date"]:
        raise ValueError("start_date 不能晚于 end_date")
    if not isinstance(cfg["products"], (list, tuple)) or not cfg["products"]:
        raise ValueError("products 必须是非空列表")
    cfg["products"] = [str(p) for p in cfg["products"]]
    bad_rules = set(cfg["rules"]) - set(RULES)
    if bad_rules or not cfg["rules"]:
        raise ValueError(f"rules 只能取 {RULES} 的子集")
    cfg["rules"] = list(dict.fromkeys(cfg["rules"]))
    for key in ("capital_per_product", "cost_bps_per_side", "dead_zone"):
        if not isinstance(cfg[key], (int, float)) or cfg[key] < 0:
            raise ValueError(f"{key} 必须是非负数")
    for key in ("momentum_days", "force_roll_days", "gradual_days"):
        if not isinstance(cfg[key], int) or cfg[key] <= 0:
            raise ValueError(f"{key} 必须是正整数")
    return cfg


def _resolve_frames(input_data, cfg: dict):
    if input_data:
        return input_data["daily"], input_data["contracts"], input_data["dominant"]
    if cfg["data_dir"]:
        return data_layer.load_local(cfg["data_dir"])
    return data_layer.fetch(cfg["products"], cfg["start_date"], cfg["end_date"])


def _params(cfg: dict) -> engine.Params:
    return engine.Params(
        capital_per_product=float(cfg["capital_per_product"]),
        cost_bps_per_side=float(cfg["cost_bps_per_side"]),
        momentum_days=int(cfg["momentum_days"]),
        dead_zone=float(cfg["dead_zone"]),
        force_roll_days=int(cfg["force_roll_days"]),
        gradual_days=int(cfg["gradual_days"]),
    )


def run(input_data=None, config: dict | None = None) -> dict:
    validate_input(input_data)
    cfg = _validate_config(config)
    daily, contracts, dominant = _resolve_frames(input_data, cfg)
    engine.validate_frames(daily, contracts, dominant)

    params = _params(cfg)
    products = engine.build_products(daily, contracts, dominant, params, cfg["products"])
    all_dates = engine.trading_dates(products)
    dates = [d for d in all_dates if cfg["start_date"] <= d <= cfg["end_date"]]
    if len(dates) < 2:
        raise ValueError("回测区间内交易日不足，请检查 start_date / end_date")

    sig_rows = [
        {"date": d, "product": product, "signal": pdata.signal[d]}
        for product, pdata in products.items() for d in pdata.dates
    ]
    signals = pd.DataFrame(sig_rows).sort_values(["date", "product"]).reset_index(drop=True)

    metric_rows, stress, roll_rows, curves = [], {}, {}, {}
    for rule in cfg["rules"]:
        res = engine.simulate(products, dates, rule, params)
        curves[rule] = res.daily
        metric_rows.append(engine.metrics(res, params, len(products)))
        stress[rule] = engine.stress_months(res).to_dict("records")
        roll_rows[rule] = res.rolls

    data_version = "panda_data:{}..{}:rows={}".format(
        str(daily["date"].min()), str(daily["date"].max()), len(daily))

    result = {
        "metrics": metric_rows,
        "roll_summary": engine.roll_summary(roll_rows),
        "stress_months": stress,
        "signals": signals,
        "daily": curves,
        "data_version": data_version,
        "config": cfg,
    }

    if cfg["output_dir"]:
        _write_outputs(result, Path(cfg["output_dir"]))
    if cfg["write_production"]:
        write_production(result, Path(__file__).resolve().parent.parent / "生产产物")
    return result


def _write_outputs(result: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    result["signals"].to_csv(out / "signals_frozen.csv", index=False)
    pd.DataFrame(result["metrics"]).to_csv(out / "metrics.csv", index=False)
    pd.DataFrame(result["roll_summary"]).to_csv(out / "roll_summary.csv", index=False)
    (out / "stress_months.json").write_text(
        json.dumps(result["stress_months"], ensure_ascii=False, indent=2), encoding="utf-8")
    for rule, frame in result["daily"].items():
        frame.to_csv(out / f"equity_{rule}.csv", index=False)


def to_production(result: dict) -> pd.DataFrame:
    last_date = str(result["signals"]["date"].max())
    update_time = datetime.now().astimezone().isoformat(timespec="seconds")
    roll_by_rule = {row["rule"]: row for row in result["roll_summary"]}
    rows = []
    for metric in result["metrics"]:
        rule = metric["rule"]
        detail = dict(metric)
        detail["roll_summary"] = roll_by_rule.get(rule, {})
        detail["stress_months"] = result["stress_months"].get(rule, [])
        rows.append({
            "trade_date": last_date,
            "build_id": BUILD_ID,
            "build_name": BUILD_NAME,
            "target_id": rule,
            "result_type": "report",
            "result_value": float(metric.get("annual_return") or 0.0),
            "result_json": json.dumps(detail, ensure_ascii=False),
            "data_version": result["data_version"],
            "update_time": update_time,
        })
    return pd.DataFrame(rows)


def write_production(result: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    frame = to_production(result)
    path = out_dir / "数据库.parquet"
    frame.to_parquet(path, index=False)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Q2 换月规则对照 BUILD")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--start", default=data_layer.DEFAULT_START)
    parser.add_argument("--end", default=data_layer.DEFAULT_END)
    parser.add_argument("--products", nargs="*", default=None)
    parser.add_argument("--rules", nargs="*", default=list(RULES))
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--write-production", action="store_true")
    args = parser.parse_args()

    cfg = {
        "start_date": args.start,
        "end_date": args.end,
        "rules": args.rules,
        "output_dir": args.output_dir,
        "write_production": args.write_production,
    }
    if args.data_dir:
        cfg["data_dir"] = args.data_dir
    if args.products:
        cfg["products"] = args.products

    result = run(None, cfg)
    print(pd.DataFrame(result["metrics"]).to_string(index=False))
    print(pd.DataFrame(result["roll_summary"]).to_string(index=False))


if __name__ == "__main__":
    main()
