# US Market Support Design

**Date:** 2026-01-19
**Status:** Approved
**Approach:** Multi-market support (CN and US configurable)

## Overview

Add US stock market support while keeping A-share (CN) capability. Market selection via `MARKET` environment variable, defaulting to US.

## Key Decisions

| Decision | Choice |
|----------|--------|
| Migration type | Multi-market (configurable) |
| US data source | YfinanceFetcher only |
| Trading rules | Keep existing logic, skip chip distribution for US |
| Output language | Chinese for both markets |
| Default market | US |

## Architecture Changes

### 1. Configuration & Market Abstraction

**`config.py`:**
- Add `market: str = "US"` field to Config dataclass
- Add market-aware stock code validation:
  - US: 1-5 uppercase letters (e.g., `AAPL`, `TSLA`)
  - CN: 6 digits (e.g., `600519`, `000001`)
- Default stock list: `AAPL,MSFT,GOOGL,NVDA,TSLA`

**`data_provider/base.py`:**
- `DataFetcherManager` initializes different fetcher priorities based on market
- US market: YfinanceFetcher only (priority 0)
- CN market: Keep existing order (Efinance → Akshare → Tushare → Baostock → Yfinance)

### 2. Market Indices & Market Analyzer

**`market_analyzer.py`:**

```python
US_INDICES = {
    '^GSPC': 'S&P 500',
    '^IXIC': 'Nasdaq综合指数',
    '^DJI': '道琼斯工业指数',
    '^RUT': '罗素2000',
}

CN_INDICES = {
    'sh000001': '上证指数',
    'sz399001': '深证成指',
    'sz399006': '创业板指',
    'sh000688': '科创50',
    'sh000016': '上证50',
    'sh000300': '沪深300',
}
```

- `MarketAnalyzer` selects indices based on `config.market`
- Same analysis logic, different index symbols

**`stock_analyzer.py`:**
- No changes to trading logic (MA alignment, bias threshold, etc.)
- Keep Chinese enum values

### 3. Chip Distribution & Data Fetching

**`data_provider/yfinance_fetcher.py`:**
- Market-aware stock code conversion:
  - US: Use symbol directly (`AAPL` → `AAPL`)
  - CN: Keep existing logic (`600519` → `600519.SS`)

**Chip distribution:**
- `get_chip_distribution()` returns `None` for US market
- AI prompts note "筹码数据不适用于美股" when chip data unavailable
- Graceful skip, no code removal

**`analyzer.py`:**
- Remove hardcoded `STOCK_NAME_MAP`
- Fetch names dynamically from yfinance: `yf.Ticker("AAPL").info['shortName']`
- CN stocks: Keep existing map as fallback

### 4. Scheduling & GitHub Actions

**`scheduler.py`:**
- Market-aware default schedule time (both use 18:00 local)
- Configurable via `SCHEDULE_TIME` env var

**`.github/workflows/daily_analysis.yml`:**
```yaml
schedule:
  - cron: '0 23 * * 1-5'  # UTC 23:00 = ET 18:00
env:
  MARKET: ${{ secrets.MARKET || 'US' }}
```

### 5. AI Prompts & Notifications

**`analyzer.py` (AI prompts):**
- Keep all prompts in Chinese
- Add market context: "你正在分析美股市场..." or "你正在分析A股市场..."
- Skip chip distribution section for US stocks

**`notification.py`:**
- Message templates remain Chinese
- Stock code display format:
  - US: `$AAPL (Apple Inc.)`
  - CN: `600519 (贵州茅台)`

**`storage.py`:**
- Add `market: str` column to database schema
- Default value: `"US"`

### 6. Documentation Updates

- `.env.example`: Add `MARKET=US` with explanation
- `CLAUDE.md`: Update with multi-market info
- `README.md`: Add US stock examples

## Files to Modify

| File | Changes |
|------|---------|
| `config.py` | Add `market` field, US default, stock validation |
| `data_provider/base.py` | Market-aware fetcher initialization |
| `data_provider/yfinance_fetcher.py` | Market-aware code conversion |
| `market_analyzer.py` | Add US indices, market selection |
| `analyzer.py` | Dynamic stock names, market-aware prompts |
| `notification.py` | Market-aware message formatting |
| `storage.py` | Add `market` column |
| `scheduler.py` | Market-aware default time |
| `.github/workflows/daily_analysis.yml` | US timezone, MARKET env var |
| `CLAUDE.md` | Documentation updates |
| `README.md` | Documentation updates |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MARKET` | `US` | Market selection: `US` or `CN` |
| `STOCK_LIST` | `AAPL,MSFT,GOOGL,NVDA,TSLA` | Comma-separated stock codes |
| `SCHEDULE_TIME` | `18:00` | Analysis run time (local) |
