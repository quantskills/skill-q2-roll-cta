---
name: roll-cta
description: "Commodity-futures roll-rule comparison BUILD: replays the same frozen 60-day momentum CTA signal under fixed-date, open-interest-confirmed, and gradual three-day rolls, then reports after-cost return, drawdown, roll cost share, and roll-ledger statistics. Use when an agent needs to compare futures roll rules, audit roll cost and roll gaps, reproduce a CTA roll ledger, or explain how roll timing changes real contract PnL rather than paper returns."
license: GPL-3.0-only
metadata:
  organization: QuantSkills
  organization_url: https://github.com/quantskills
  repository: skill-q2-roll-cta
  repository_url: https://github.com/quantskills/skill-q2-roll-cta
  project_type: skill
  collection: futures-roll-cta
  creator: fuzijun
  maintainer: fuzijun
quantSkills:
  project_type: skill
  category: tooling
  tags:
    - futures
    - roll
    - cta
    - backtest
    - pandadata
  platforms:
    - claude-code
    - codex
    - openclaw
    - cursor
  status: draft
  requires:
    - skill-pandadata-api
  validation_level: runnable
  maintainer_type: community
  summary_zh: "商品期货换月规则对照：同一冻结 CTA 信号下，比较固定日期、持仓量确认与渐进换月的扣费后收益、回撤与换月成本。"
  summary_en: "Commodity-futures roll-rule comparison: replays one frozen CTA signal under fixed-date, OI-confirmed, and gradual rolls, with after-cost return, drawdown, and roll-cost attribution."
---

# 换月规则怎样影响 CTA 的真实收益与风险

Use this skill to compare futures roll rules on the same frozen CTA signal, using real contract open/close prices and explicit cost accounting.

## 工具定位
- 工具类型：研究/回测型 BUILD（结果型）
- 解决问题：换月规则对扣费后收益、回撤和换月成本的影响，量化到具体合约的换月账本
- 使用对象：agent / Alpha / 人工分析

## 适用场景
- 需要比较固定日期、持仓量确认、渐进换月三种规则
- 需要核对换月成本占毛利、换月价差、低流动性换月次数
- 需要为 CTA/Alpha 研究提供可复现的冻结信号与实合约盈亏基线

## 输入
| 字段 | 类型 | 说明 |
|---|---|---|
| input_data | dict / None | 可选，`daily`、`contracts`、`dominant` 三个 DataFrame |
| config.data_dir | str | 本地 parquet 目录，含 daily/contracts/dominant.parquet |
| config.start_date / end_date | str | 回测区间，YYYYMMDD |
| config.products | list[str] | 品种列表，默认 18 个商品期货 |
| config.rules | list[str] | `fixed` / `oi` / `gradual` 的子集 |
| config.capital_per_product | float | 每品种名义资金，默认 1,000,000 |
| config.cost_bps_per_side | float | 单边成本，默认 1.5bp |
| config.momentum_days | int | 冻结信号动量窗口，默认 60 |
| config.dead_zone | float | 动量死区，默认 0.02 |
| config.force_roll_days | int | 到期前强制换月天数，默认 10 |
| config.gradual_days | int | 渐进换月天数，默认 3 |
| config.write_production | bool | 是否写 `生产产物/数据库.parquet` |

## 输出
`run()` 返回：

| 字段 | 类型 | 说明 |
|---|---|---|
| metrics | list[dict] | 每种规则的收益、波动、Sharpe、回撤、换月成本占比、换手 |
| roll_summary | list[dict] | 换月次数、价差中位数、P90、低流动性换月次数 |
| stress_months | dict | 每种规则最差 6 个自然月 |
| signals | DataFrame | 冻结信号（date / product / signal） |
| daily | dict[str, DataFrame] | 每种规则的逐日净值、盈亏、成本、分品种盈亏 |
| data_version | str | 数据版本标识 |
| config | dict | 生效配置 |

## 调用方式
```python
from scripts.build import run, validate_input

validate_input(None)
result = run(None, {
    "data_dir": r"path/to/data",
    "start_date": "20210101",
    "end_date": "20251231",
    "rules": ["fixed", "oi", "gradual"],
})
print(result["metrics"])
```

## 可被 Alpha 调用
- 是
- 调用限制：只输出研究/回测结果，不产生交易指令
- 依赖数据：PandaData `get_future_dominant` / `get_future_daily` / `get_future_detail`

## 是否需要生产结果
- 是，生成 `生产产物/数据库.parquet`（每种规则一行标准 BUILD 结果）

## 数据来源
- PandaData 额定接口（默认），或调用方传入的标准结构化数据
- 不使用随机数、模拟价格或复权价格计算盈亏

## 依赖
- pandas、numpy、pyarrow、panda_data
