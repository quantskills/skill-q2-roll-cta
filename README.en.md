# Roll-Rule CTA Comparison Skill

**English** | [简体中文](README.md)

> One frozen CTA signal, three roll rules: fixed-date, open-interest-confirmed, and gradual three-day rolls. See how after-cost return, drawdown, and roll-cost share change when only the roll schedule changes.

<p align="center">
  <img alt="roll rules" src="https://img.shields.io/badge/roll_rules-fixed%20%7C%20OI%20%7C%20gradual-blue">
  <img alt="data source" src="https://img.shields.io/badge/data-PandaData-ff69b4">
  <img alt="build" src="https://img.shields.io/badge/BUILD-Q2-7c3aed">
</p>

---

## What it is

`roll-cta` is a **BUILD skill** (Q2). It replays the same 60-day momentum CTA signal on 18 commodity futures products and executes three roll rules on **real contracts**, with T+1 open fills and 1.5 bp per side. Outputs include after-cost return, drawdown, roll-cost share, and a per-roll ledger.

## Roll rules

| Rule | Trigger | Execution |
|---|---|---|
| `fixed` | 15th of each month (or next trading day) | Next open, one-shot roll to the highest-OI contract |
| `oi` | Target contract OI exceeds the held contract for 2 consecutive days | Next open, one-shot roll |
| `gradual` | Same trigger as `oi` | Roll 1/3 per day over the next 3 trading days |

Signal: 60-day momentum of the per-product research series, direction set on the last trading day of each week (+2% / -2% dead zone), executed at the next open. The research series is used only to generate signals, never for PnL.

## Quick start

```bash
pip install -r requirements.txt

# Option 1: fetch from PandaData
export PANDA_DATA_USERNAME=your_phone
export PANDA_DATA_PASSWORD=your_password
export PANDA_DATA_BASE_URL=http://pandadata.pandaaiquant.com
python scripts/build.py --write-production

# Option 2: read local parquet (daily/contracts/dominant.parquet)
python scripts/build.py --data-dir /path/to/data --write-production

# Tests
python scripts/test.py
```

## Production parquet fields

| Field | Description |
|---|---|
| `trade_date` | Result trading date |
| `build_id` | `Q2` |
| `build_name` | `roll-cta` |
| `target_id` | Roll rule (`fixed` / `oi` / `gradual`) |
| `result_type` | `report` |
| `result_value` | Annualized return |
| `result_json` | Full metrics, roll summary, stress months |
| `data_version` | Data version |
| `update_time` | Generation timestamp |

## Data and reproduction

- Default source: PandaData `get_future_dominant` / `get_future_daily` / `get_future_detail`
- PnL uses raw contract open/close prices; adjusted prices are never used
- Costs: 1.5 bp per side on traded notional
- Forced roll within 10 days of maturity; contracts with volume <100 lots are untradable
- `tests/fixtures/` contains a real RB/HC 2022 slice for tests only

## Limitations

- The underlying signal is weak: all three rules lose money in 2023; roll rules change magnitude, not direction
- Results are sensitive to cost, liquidity thresholds, and roll timing
- Fixed product universe and capital; no capacity or market-impact model
- Research and education only, not investment advice

## ⚠️ Disclaimer

- Research and education only. **Not investment advice.** No return is promised.
- Backtests rely on historical data and explicit assumptions; future results may differ materially.
- This is a QuantSkills community project, **not officially endorsed by PandaAI**.
- Verify data, parameters, costs, and risk boundaries before use.

## License

GNU General Public License v3.0. See [LICENSE](LICENSE).
