# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

股票智能分析系统（支持美股/A股）- An AI-powered stock analysis system supporting both US and Chinese markets. Generates daily stock decision dashboards and market reviews, with multi-channel push notifications.

**Core Functionality:**
- **Multi-market support**: US stocks (default) and A-shares/H-shares
- Individual stock analysis with AI-generated "decision dashboards"
- Daily market review (大盘复盘) for major indices
- Multi-channel notifications: WeChat Work, Feishu, Telegram, Email, Custom Webhooks
- Zero-cost deployment via GitHub Actions

## Commands

### Running the Application
```bash
# Full analysis (stocks + market review)
python main.py

# Debug mode with detailed logging
python main.py --debug

# Dry-run: fetch data only, skip AI analysis
python main.py --dry-run

# Analyze specific stocks (US stocks)
python main.py --stocks AAPL,TSLA,NVDA

# Analyze specific stocks (A-shares)
python main.py --stocks 600519,000001,300750

# Market review only
python main.py --market-review

# Skip market review (stocks only)
python main.py --no-market-review

# Start local WebUI for configuration
python main.py --webui

# Single stock notification mode (push after each stock)
python main.py --single-notify

# Enable scheduled task mode
python main.py --schedule
```

### Dependencies
```bash
pip install -r requirements.txt
```

### Code Quality (configured in pyproject.toml)
```bash
# Format code
black . --line-length 120

# Sort imports
isort . --profile black --line-length 120

# Security scan
bandit -r . --exclude tests
```

## Architecture

### Data Flow
```
DataFetcherManager (Strategy Pattern)
    ├── EfinanceFetcher (Priority 0)
    ├── AkshareFetcher (Priority 1)
    ├── TushareFetcher (Priority 2)
    ├── BaostockFetcher (Priority 3)
    └── YfinanceFetcher (Priority 4)
         ↓ (auto-failover)
    storage.py (SQLite via SQLAlchemy)
         ↓
    StockTrendAnalyzer (technical analysis)
         ↓
    SearchService (Bocha/Tavily/SerpAPI - multi-key load balancing)
         ↓
    GeminiAnalyzer / OpenAI API (AI analysis)
         ↓
    NotificationService (multi-channel push)
```

### Key Modules

| Module | Responsibility |
|--------|---------------|
| `main.py` | Main orchestrator - `StockAnalysisPipeline` coordinates the entire flow |
| `config.py` | Singleton configuration from `.env` with validation |
| `data_provider/` | Strategy pattern for data sources with auto-failover |
| `data_provider/base.py` | `BaseFetcher` abstract class and `DataFetcherManager` |
| `analyzer.py` | `GeminiAnalyzer` with system prompt for decision dashboard format |
| `stock_analyzer.py` | `StockTrendAnalyzer` - technical analysis based on trading philosophy |
| `market_analyzer.py` | `MarketAnalyzer` - daily market review generation |
| `search_service.py` | Multi-provider news search with key rotation |
| `notification.py` | Multi-channel notifications with platform-specific formatting |
| `storage.py` | SQLite storage with SQLAlchemy ORM |

### Trading Philosophy (Embedded in AI Prompts)

The system enforces specific trading rules:
1. **No chasing highs**: Bias ratio > 5% from MA5 = "Danger"
2. **Trend trading**: Only buy when MA5 > MA10 > MA20 (bullish alignment)
3. **Chip structure**: Monitor profit ratio and concentration
4. **Buy points**: Prefer pullbacks to MA5/MA10 support

### AI Analysis Output Format

The `GeminiAnalyzer` is prompted to return a structured "Decision Dashboard" JSON containing:
- `core_conclusion`: One-sentence verdict with position advice
- `data_perspective`: Trend status, price position, volume, chip analysis
- `intelligence`: News alerts, risk warnings, catalysts
- `battle_plan`: Sniper points (buy/stop-loss/target prices), action checklist

## Configuration

All configuration via environment variables or `.env` file. Key settings:

### Market Selection
- `MARKET`: Market to analyze - `US` (default) or `CN`
  - `MARKET=US` - US stocks (e.g., `AAPL,MSFT,GOOGL,NVDA,TSLA`)
  - `MARKET=CN` - A-shares/H-shares (e.g., `600519,000001,300750`)

### Core Settings
- `STOCK_LIST`: Comma-separated stock codes
  - US examples: `AAPL,MSFT,GOOGL,NVDA,TSLA`
  - CN examples: `600519,000001,300750`
- `GEMINI_API_KEY` / `OPENAI_API_KEY`: AI provider (at least one required)
- `BOCHA_API_KEYS` / `TAVILY_API_KEYS` / `SERPAPI_API_KEYS`: News search (comma-separated for load balancing)
- Notification channels: `WECHAT_WEBHOOK_URL`, `FEISHU_WEBHOOK_URL`, `TELEGRAM_BOT_TOKEN`+`TELEGRAM_CHAT_ID`, `EMAIL_SENDER`+`EMAIL_PASSWORD`

## GitHub Actions

The workflow `.github/workflows/daily_analysis.yml` runs at 18:00 Beijing time (10:00 UTC) on weekdays. Configure secrets in repository settings.

Manual dispatch supports three modes: `full`, `market-only`, `stocks-only`.

## Code Style

- Python 3.10+
- Line length: 120 characters
- Chinese comments and docstrings are common throughout
- Dataclasses used extensively for structured data
- Type hints on function signatures
