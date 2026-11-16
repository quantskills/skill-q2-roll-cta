---
name: roll-cta-production
description: 生产环境的换月规则对照结果读取。从标准 Parquet 读取三种换月规则的扣费后指标、换月汇总与压力月份，供研究/监控 agent 查询。
tags: [quant, build, production, futures, roll]
---

# 换月规则对照（生产）

## 结果文件

`生产产物/数据库.parquet`

## 主键

- `trade_date`
- `build_id`
- `target_id`
- `result_type`

## 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `trade_date` | string | 结果所属交易日（YYYYMMDD） |
| `build_id` | string | `Q2` |
| `build_name` | string | `roll-cta` |
| `target_id` | string | 换月规则：`fixed` / `oi` / `gradual` |
| `result_type` | string | `report` |
| `result_value` | float | 年化收益（小数） |
| `result_json` | string | 完整指标、换月汇总、压力月份 JSON |
| `data_version` | string | 数据版本 |
| `update_time` | string | 生成时间（ISO 8601） |

## 读取规则

```python
import json
import pandas as pd

df = pd.read_parquet("生产产物/数据库.parquet")
latest = df[df["trade_date"] == df["trade_date"].max()]
fixed = latest[latest["target_id"] == "fixed"].iloc[0]
detail = json.loads(fixed["result_json"])
print(fixed["result_value"], detail["sharpe"], detail["roll_summary"])
```

1. 先按 `trade_date` 取最新有效交易日。
2. 再按 `target_id` 取需要的规则。
3. `result_value` 只作核心指标；完整口径以 `result_json` 为准。
4. 结果缺失时说明数据日期，不允许用开发脚本临时重算替代生产结果。

## 禁止行为

- 不得把 `result_value` 当作收益承诺或交易建议
- 不得修改 `result_json` 的结构后回写
- 不得在缺少 `trade_date` / `build_id` / `target_id` 的情况下合并数据
