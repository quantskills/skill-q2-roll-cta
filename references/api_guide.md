# Q2 数据接口说明

## 数据源

PandaData（PandaAI data 数据拉取库）：

```python
import panda_data
panda_data.init_token(
    username=os.environ["PANDA_DATA_USERNAME"],
    password=os.environ["PANDA_DATA_PASSWORD"],
    base_url=os.environ.get("PANDA_DATA_BASE_URL", "http://pandadata.pandaaiquant.com"),
)
```

## 额定接口

### get_future_dominant

- 用途：品种主力合约序列
- 入参：`underlying_symbol`（list）、`start_date`、`end_date`
- 关键字段：`underlying_symbol`、`symbol`、`date`

### get_future_detail

- 用途：合约元信息（到期日、合约乘数）
- 入参：`symbol`（list，建议 ≤40 个/次）、`fields`
- 关键字段：`symbol`、`underlying_symbol`、`maturity_date`、`listed_date`、`contract_multiplier`

### get_future_daily

- 用途：具体合约日线
- 入参：`symbol`（list，建议 ≤35 个/次）、`start_date`、`end_date`、`fields`
- 关键字段：`symbol`、`underlying_symbol`、`date`、`open`、`high`、`low`、`close`、`settlement`、`volume`、`open_interest`

## 本地 parquet 模式

`config["data_dir"]` 指向的目录需包含：

| 文件 | 必需字段 |
|---|---|
| `daily.parquet` | symbol, underlying_symbol, date, open, close, volume, open_interest, settlement |
| `contracts.parquet` | symbol, underlying_symbol, maturity_date, contract_multiplier |
| `dominant.parquet` | underlying_symbol, symbol, date |

## 字段口径

- `date` 统一为 `YYYYMMDD` 字符串
- 盈亏只用原始 `open` / `close`，不使用复权价
- `volume < 100` 或 `open_interest <= 0` 视为不可交易
- 距到期 ≤10 天的合约强制换出
- 零成交量行保留供应商原始记录，不插值、不补价

## 调用限制

- 接口按 35–40 个合约一批调用，批次间 sleep，避免触发限流
- 失败自动重试 4 次；仍失败则抛出异常，不静默返回空表
- 凭据只从环境变量读取，不落盘
