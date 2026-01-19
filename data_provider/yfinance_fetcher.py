# -*- coding: utf-8 -*-
"""
===================================
YfinanceFetcher - 兜底数据源 (Priority 4)
===================================

数据来源：Yahoo Finance（通过 yfinance 库）
特点：国际数据源、可能有延迟或缺失
定位：当所有国内数据源都失败时的最后保障

关键策略：
1. 自动将 A 股代码转换为 yfinance 格式（.SS / .SZ）
2. 处理 Yahoo Finance 的数据格式差异
3. 失败后指数退避重试
"""

import logging
from datetime import datetime
from typing import Optional

import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS
from config import get_config

# Import ChipDistribution from akshare_fetcher (only defined there)
try:
    from .akshare_fetcher import ChipDistribution
except ImportError:
    ChipDistribution = None

logger = logging.getLogger(__name__)


class YfinanceFetcher(BaseFetcher):
    """
    Yahoo Finance 数据源实现
    
    优先级：4（最低，作为兜底）
    数据来源：Yahoo Finance
    
    关键策略：
    - 自动转换股票代码格式
    - 处理时区和数据格式差异
    - 失败后指数退避重试
    
    注意事项：
    - A 股数据可能有延迟
    - 某些股票可能无数据
    - 数据精度可能与国内源略有差异
    """
    
    name = "YfinanceFetcher"
    priority = 4
    
    def __init__(self):
        """初始化 YfinanceFetcher"""
        pass
    
    def _convert_stock_code(self, stock_code: str) -> str:
        """
        转换股票代码为 Yahoo Finance 格式（市场感知）

        市场转换规则：
        - US市场：直接使用股票代码（AAPL, TSLA 等无需后缀）
        - CN市场（A股）：
          - 沪市：600519.SS (Shanghai Stock Exchange)
          - 深市：000001.SZ (Shenzhen Stock Exchange)

        Args:
            stock_code: 原始代码，如 '600519', '000001', 'AAPL'

        Returns:
            Yahoo Finance 格式代码，如 '600519.SS', '000001.SZ', 'AAPL'
        """
        config = get_config()
        code = stock_code.strip()

        # US市场：直接使用股票代码，无需后缀
        if config.market == "US":
            return code.upper()

        # CN市场（A股）：需要添加交易所后缀
        # 已经包含后缀的情况
        if '.SS' in code.upper() or '.SZ' in code.upper():
            return code.upper()

        # 去除可能的后缀
        code = code.replace('.SH', '').replace('.sh', '')

        # 根据代码前缀判断市场
        if code.startswith(('600', '601', '603', '688')):
            return f"{code}.SS"
        elif code.startswith(('000', '002', '300')):
            return f"{code}.SZ"
        else:
            logger.warning(f"无法确定股票 {code} 的市场，默认使用深市")
            return f"{code}.SZ"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        从 Yahoo Finance 获取原始数据
        
        使用 yfinance.download() 获取历史数据
        
        流程：
        1. 转换股票代码格式
        2. 调用 yfinance API
        3. 处理返回数据
        """
        import yfinance as yf
        
        # 转换代码格式
        yf_code = self._convert_stock_code(stock_code)
        
        logger.debug(f"调用 yfinance.download({yf_code}, {start_date}, {end_date})")
        
        try:
            # 使用 yfinance 下载数据
            df = yf.download(
                tickers=yf_code,
                start=start_date,
                end=end_date,
                progress=False,  # 禁止进度条
                auto_adjust=True,  # 自动调整价格（复权）
            )
            
            if df.empty:
                raise DataFetchError(f"Yahoo Finance 未查询到 {stock_code} 的数据")
            
            return df
            
        except Exception as e:
            if isinstance(e, DataFetchError):
                raise
            raise DataFetchError(f"Yahoo Finance 获取数据失败: {e}") from e
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化 Yahoo Finance 数据

        yfinance 返回的列名：
        Open, High, Low, Close, Volume（索引是日期）

        注意：yfinance 1.0+ 返回 MultiIndex 列名如 ('Close', 'AAPL')
        需要先展平列名再进行标准化

        需要映射到标准列名：
        date, open, high, low, close, volume, amount, pct_chg
        """
        df = df.copy()

        # 处理 yfinance 1.0+ 的 MultiIndex 列名
        # 例如：('Close', 'AAPL') -> 'Close'
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 重置索引，将日期从索引变为列
        df = df.reset_index()
        
        # 列名映射（yfinance 使用首字母大写）
        column_mapping = {
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
        }
        
        df = df.rename(columns=column_mapping)
        
        # 计算涨跌幅（因为 yfinance 不直接提供）
        if 'close' in df.columns:
            df['pct_chg'] = df['close'].pct_change() * 100
            df['pct_chg'] = df['pct_chg'].fillna(0).round(2)
        
        # 计算成交额（yfinance 不提供，使用估算值）
        # 成交额 ≈ 成交量 * 平均价格
        if 'volume' in df.columns and 'close' in df.columns:
            df['amount'] = df['volume'] * df['close']
        else:
            df['amount'] = 0
        
        # 添加股票代码列
        df['code'] = stock_code
        
        # 只保留需要的列
        keep_cols = ['code'] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]

        return df

    def get_chip_distribution(self, stock_code: str) -> Optional['ChipDistribution']:
        """
        获取筹码分布数据（市场感知）

        注意：
        - US市场：Yahoo Finance 不提供筹码分布数据，直接返回 None
        - CN市场：Yahoo Finance 也不提供筹码分布数据，返回 None

        筹码分布是 A 股特有的概念，需要使用其他数据源（如 AkshareFetcher）

        Args:
            stock_code: 股票代码

        Returns:
            None（Yahoo Finance 不支持筹码分布数据）
        """
        config = get_config()

        # US 市场不支持筹码分布
        if config.market == "US":
            logger.debug(f"[市场限制] US 市场不支持筹码分布数据，跳过 {stock_code}")
            return None

        # CN 市场的 Yahoo Finance 也不提供筹码分布数据
        logger.debug(f"[数据源限制] Yahoo Finance 不支持筹码分布数据，跳过 {stock_code}")
        return None


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)
    
    fetcher = YfinanceFetcher()
    
    try:
        df = fetcher.get_daily_data('600519')  # 茅台
        print(f"获取成功，共 {len(df)} 条数据")
        print(df.tail())
    except Exception as e:
        print(f"获取失败: {e}")
