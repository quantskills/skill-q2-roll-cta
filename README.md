# 换月规则 CTA 对照 Skill

**简体中文** | [English](README.en.md)

> 同一份冻结 CTA 信号，只改换月规则：固定日期、持仓量确认、渐进换月——扣费后到底差多少，换月成本吃掉了多少毛利，一次跑清。

<p align="center">
  <img alt="roll rules" src="https://img.shields.io/badge/roll_rules-fixed%20%7C%20OI%20%7C%20gradual-blue">
  <img alt="data source" src="https://img.shields.io/badge/data-PandaData-ff69b4">
  <img alt="build" src="https://img.shields.io/badge/BUILD-Q2-7c3aed">
</p>

---

## 这是什么

`roll-cta` 是一个 **BUILD 技能**（Q2）：在 18 个商品期货品种上复现同一份 60 日动量 CTA 信号，分别用三种换月规则在**具体合约**上撮合，按 T+1 开盘成交、双边 1.5bp 计成本，输出扣费后的收益、回撤、换月成本占比与换月账本。

## 三种换月规则

| 规则 | 触发 | 执行 |
|---|---|---|
| `fixed` | 每月 15 日（或其后首个交易日） | 次日开盘一次性换到当日持仓量最大的合约 |
| `oi` | 目标合约持仓量连续 2 个交易日高于当前合约 | 次日开盘一次性换完 |
| `gradual` | 同 `oi` | 次日开始连续 3 个交易日，每天平/开 1/3 |

信号冻结：品种连续研究序列的 60 日动量，每周最后一个交易日定方向（>+2% 做多、<-2% 做空），下一交易日开盘执行。研究序列只用于生成信号，不用于计算盈亏。

## 快速开始

```bash
pip install -r requirements.txt

# 方式一：PandaData 现拉（需要凭据）
export PANDA_DATA_USERNAME=your_phone
export PANDA_DATA_PASSWORD=your_password
export PANDA_DATA_BASE_URL=http://pandadata.pandaaiquant.com
python scripts/build.py --write-production

# 方式二：读取本地 parquet（目录含 daily/contracts/dominant.parquet）
python scripts/build.py --data-dir /path/to/data --write-production

# 测试
python scripts/test.py
```

### 自定义参数

```python
from scripts.build import run

result = run(None, {
    "data_dir": "/path/to/data",
    "start_date": "20210101",
    "end_date": "20251231",
    "products": ["RB", "HC", "I", "J", "JM", "CU", "AL", "ZN",
                 "AU", "AG", "RU", "M", "Y", "P", "C", "TA", "MA", "FG"],
    "rules": ["fixed", "oi", "gradual"],
    "capital_per_product": 1_000_000,
    "cost_bps_per_side": 1.5,
})
print(result["metrics"])
```

## 输出字段（生产 parquet）

| 字段 | 说明 |
|---|---|
| `trade_date` | 结果所属交易日（区间最后一天） |
| `build_id` | `Q2` |
| `build_name` | `roll-cta` |
| `target_id` | 换月规则（`fixed` / `oi` / `gradual`） |
| `result_type` | `report` |
| `result_value` | 年化收益 |
| `result_json` | 该规则完整指标、换月汇总与压力月份 |
| `data_version` | 数据版本 |
| `update_time` | 生成时间 |

## 目录结构

```
skill-q2-roll-cta/
├── SKILL.md                    # 技能入口
├── skill.json                  # 技能元数据
├── scripts/
│   ├── build.py                # BUILD 入口（run / validate_input）
│   ├── data.py                 # PandaData / 本地 parquet 数据层
│   ├── engine.py               # 换月回测引擎
│   └── test.py                 # 单元测试
├── tests/
│   ├── make_fixtures.py        # 从真实数据切小样本
│   └── fixtures/               # 真实数据切片（RB/HC 2022）
├── references/
│   └── api_guide.md            # 数据接口说明
├── agents/                     # 多平台入口
├── 生产产物/
│   ├── SKILL.md
│   └── 数据库.parquet
└── README.md / README.en.md / INSTALL.md / LICENSE / requirements.txt
```

## 数据来源与复现

- 默认数据源：PandaData `get_future_dominant` / `get_future_daily` / `get_future_detail`
- 盈亏只用具体合约的原始开收盘价，不使用复权价格
- 成本：双边各 1.5bp（手续费 + 滑点），按成交名义金额计
- 临期保护：距到期 ≤10 天强制换月；成交量 <100 手视为不可交易
- 零成交量行、临近交割的远月合约按供应商原始记录处理，不做插值
- 仓库内 `tests/fixtures/` 是从真实数据切出的 RB/HC 2022 子样本，仅用于测试

## 局限

- 信号本身偏弱：三种规则 2023 年均为负收益，换月规则只改变幅度，不改变信号方向
- 结果对成本假设、流动性阈值和换月时点敏感
- 品种池、资金规模与保证金约束固定，未做容量与冲击成本建模
- 研究用途，不构成投资建议

## ⚠️ 免责声明

- 本项目仅供研究与教育用途，**不构成任何投资建议**，不承诺收益。
- 回测结果基于历史数据与明确假设，未来表现可能显著不同。
- 本项目是 QuantSkills 社区项目，**非 PandaAI 官方背书**，也不代表任何机构认证。
- 使用前请自行核对数据、参数、成本与风险边界。

## 许可证

GNU General Public License v3.0，见 [LICENSE](LICENSE)。
