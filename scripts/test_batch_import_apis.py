#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量导入API测试程序

使用 Tushare 获取 000001 和 000002 两只股票的数据，然后通过批量导入 API 导入到数据库中。

测试数据类型：
1. 股票基本信息
2. 实时行情
3. 财务数据
4. 新闻数据
5. 历史K线数据

作者: TradingAgents-CN Pro Team
版本: v1.0.0
创建日期: 2026-01-24
"""

import os
import sys
import asyncio
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 简单的 .env 文件加载器
def load_env_file():
    """简单的 .env 文件加载器"""
    env_path = os.path.join(project_root, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

# 加载环境变量
load_env_file()


# ============================================================================
# 配置部分
# ============================================================================

# API 基础 URL（本地开发环境：前端3000，后端8000）
BASE_URL = "http://localhost:8000"

# 测试股票代码
TEST_SYMBOLS = ["000001", "000002"]

# Tushare 配置
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN")
TUSHARE_ENABLED = os.getenv("TUSHARE_ENABLED", "false").lower() == "true"

# 认证 Token（需要先登录获取）
AUTH_TOKEN = None


# ============================================================================
# 辅助函数
# ============================================================================

def print_section(title: str):
    """打印章节标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_result(success: bool, message: str, data: Any = None):
    """打印结果"""
    icon = "✅" if success else "❌"
    print(f"{icon} {message}")
    if data:
        print(f"   数据: {data}")


async def login_and_get_token(username: str = "admin", password: str = "admin123") -> Optional[str]:
    """登录并获取认证 Token"""
    print_section("步骤 0: 获取认证 Token")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": username, "password": password}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                token = result["data"]["access_token"]
                print_result(True, f"登录成功，Token: {token[:20]}...")
                return token
            else:
                print_result(False, f"登录失败: {result.get('message')}")
        else:
            print_result(False, f"请求失败: {response.status_code}")
    except Exception as e:
        print_result(False, f"登录异常: {str(e)}")
    
    return None


# ============================================================================
# Tushare 数据获取函数
# ============================================================================

async def get_tushare_provider():
    """获取 Tushare 数据提供者"""
    from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
    
    provider = get_tushare_provider()
    
    # 等待连接完成
    max_wait = 5
    elapsed = 0
    while not provider.connected and elapsed < max_wait:
        await asyncio.sleep(0.1)
        elapsed += 0.1
    
    if not provider.connected:
        raise Exception("Tushare 连接失败")
    
    return provider


async def fetch_basic_info(provider, symbols: List[str]) -> List[Dict[str, Any]]:
    """获取股票基本信息"""
    print_section("步骤 1: 获取股票基本信息")
    
    stocks = []
    for symbol in symbols:
        try:
            info = await provider.get_stock_basic_info(symbol)
            if info:
                print_result(True, f"获取 {symbol} 基本信息成功", info.get("name"))
                stocks.append(info)
            else:
                print_result(False, f"获取 {symbol} 基本信息失败")
        except Exception as e:
            print_result(False, f"获取 {symbol} 基本信息异常: {str(e)}")
    
    return stocks


async def fetch_quotes(provider, symbols: List[str]) -> List[Dict[str, Any]]:
    """获取实时行情"""
    print_section("步骤 2: 获取实时行情")
    
    quotes = []
    for symbol in symbols:
        try:
            quote = await provider.get_stock_quotes(symbol)
            if quote:
                print_result(True, f"获取 {symbol} 实时行情成功", f"收盘价: {quote.get('close')}")
                quotes.append(quote)
            else:
                print_result(False, f"获取 {symbol} 实时行情失败")
        except Exception as e:
            print_result(False, f"获取 {symbol} 实时行情异常: {str(e)}")
    
    return quotes


async def fetch_financial_data(provider, symbols: List[str]) -> List[Dict[str, Any]]:
    """获取财务数据"""
    print_section("步骤 3: 获取财务数据")

    financial_data_list = []
    for symbol in symbols:
        try:
            financial_data = await provider.get_financial_data(symbol, limit=1)
            if financial_data:
                print_result(True, f"获取 {symbol} 财务数据成功", f"报告期: {financial_data.get('report_period')}")
                financial_data_list.append(financial_data)
            else:
                print_result(False, f"获取 {symbol} 财务数据失败")
        except Exception as e:
            print_result(False, f"获取 {symbol} 财务数据异常: {str(e)}")

    return financial_data_list


async def fetch_news_data(provider, symbols: List[str]) -> List[Dict[str, Any]]:
    """获取新闻数据"""
    print_section("步骤 4: 获取新闻数据")

    all_news = []
    for symbol in symbols:
        try:
            news_list = await provider.get_stock_news(symbol=symbol, limit=5, hours_back=48)
            if news_list:
                print_result(True, f"获取 {symbol} 新闻数据成功", f"数量: {len(news_list)}")
                all_news.extend(news_list)
            else:
                print_result(False, f"获取 {symbol} 新闻数据失败")
        except Exception as e:
            print_result(False, f"获取 {symbol} 新闻数据异常: {str(e)}")

    return all_news


async def fetch_historical_kline(provider, symbols: List[str]) -> Dict[str, Any]:
    """获取历史K线数据"""
    print_section("步骤 5: 获取历史K线数据")

    kline_data = {}
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)

    for symbol in symbols:
        try:
            df = await provider.get_historical_data(
                symbol=symbol,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                period="daily"
            )

            if df is not None and not df.empty:
                print_result(True, f"获取 {symbol} 历史K线成功", f"数量: {len(df)}")
                kline_data[symbol] = df
            else:
                print_result(False, f"获取 {symbol} 历史K线失败")
        except Exception as e:
            print_result(False, f"获取 {symbol} 历史K线异常: {str(e)}")

    return kline_data


# ============================================================================
# 数据转换函数
# ============================================================================

def transform_basic_info(stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """转换股票基本信息为 API 请求格式"""
    return {
        "stocks": stocks
    }


def transform_quotes(quotes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """转换实时行情为 API 请求格式"""
    return {
        "quotes": quotes
    }


def transform_financial_data(financial_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """转换财务数据为 API 请求格式"""
    return {
        "financial_data": financial_data_list
    }


def transform_news_data(news_list: List[Dict[str, Any]], symbol: str = None) -> Dict[str, Any]:
    """转换新闻数据为 API 请求格式"""
    return {
        "symbol": symbol,
        "news_list": news_list
    }


def transform_kline_data(symbol: str, df) -> Dict[str, Any]:
    """转换历史K线数据为 API 请求格式"""
    import pandas as pd

    records = []
    for idx, row in df.iterrows():
        record = {
            "trade_date": str(idx),  # 索引是日期
            "open": float(row.get("open", 0)),
            "high": float(row.get("high", 0)),
            "low": float(row.get("low", 0)),
            "close": float(row.get("close", 0)),
            "volume": float(row.get("volume", 0)),
        }

        # 可选字段
        if "amount" in row and pd.notna(row["amount"]):
            record["amount"] = float(row["amount"])
        if "pre_close" in row and pd.notna(row["pre_close"]):
            record["pre_close"] = float(row["pre_close"])
        if "change" in row and pd.notna(row["change"]):
            record["change"] = float(row["change"])
        if "pct_chg" in row and pd.notna(row["pct_chg"]):
            record["pct_chg"] = float(row["pct_chg"])

        records.append(record)

    return {
        "symbol": symbol,
        "period": "daily",
        "records": records
    }


# ============================================================================
# API 调用函数
# ============================================================================

def call_batch_import_api(endpoint: str, data: Dict[str, Any], token: str, operation: str) -> bool:
    """调用批量导入 API"""
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.post(
            f"{BASE_URL}{endpoint}",
            headers=headers,
            json=data
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 200:
                print_result(True, f"{operation}成功", result.get("data"))
                return True
            else:
                print_result(False, f"{operation}失败: {result.get('message')}")
        else:
            print_result(False, f"{operation}失败: HTTP {response.status_code}")
            print(f"   响应: {response.text[:200]}")
    except Exception as e:
        print_result(False, f"{operation}异常: {str(e)}")

    return False


async def import_basic_info(stocks: List[Dict[str, Any]], token: str) -> bool:
    """导入股票基本信息"""
    print_section("步骤 6: 导入股票基本信息")

    if not stocks:
        print_result(False, "没有股票基本信息可导入")
        return False

    data = transform_basic_info(stocks)
    return call_batch_import_api(
        "/api/stocks/batch-import-basic-info",
        data,
        token,
        "导入股票基本信息"
    )


async def import_quotes(quotes: List[Dict[str, Any]], token: str) -> bool:
    """导入实时行情"""
    print_section("步骤 7: 导入实时行情")

    if not quotes:
        print_result(False, "没有实时行情可导入")
        return False

    data = transform_quotes(quotes)
    return call_batch_import_api(
        "/api/stocks/batch-import-quotes",
        data,
        token,
        "导入实时行情"
    )


async def import_financial_data(financial_data_list: List[Dict[str, Any]], token: str) -> bool:
    """导入财务数据"""
    print_section("步骤 8: 导入财务数据")

    if not financial_data_list:
        print_result(False, "没有财务数据可导入")
        return False

    data = transform_financial_data(financial_data_list)
    return call_batch_import_api(
        "/api/financial-data/batch-import",
        data,
        token,
        "导入财务数据"
    )


async def import_news_data(news_list: List[Dict[str, Any]], token: str) -> bool:
    """导入新闻数据"""
    print_section("步骤 9: 导入新闻数据")

    if not news_list:
        print_result(False, "没有新闻数据可导入")
        return False

    data = transform_news_data(news_list)
    return call_batch_import_api(
        "/api/news-data/save",
        data,
        token,
        "导入新闻数据"
    )


async def import_historical_kline(kline_data: Dict[str, Any], token: str) -> bool:
    """导入历史K线数据"""
    print_section("步骤 10: 导入历史K线数据")

    if not kline_data:
        print_result(False, "没有历史K线数据可导入")
        return False

    success_count = 0
    for symbol, df in kline_data.items():
        data = transform_kline_data(symbol, df)
        if call_batch_import_api(
            "/api/historical-data/batch-import",
            data,
            token,
            f"导入 {symbol} 历史K线"
        ):
            success_count += 1

    return success_count > 0


# ============================================================================
# 主函数
# ============================================================================

async def main():
    """主函数"""
    print("\n" + "="*60)
    print("  批量导入API测试程序")
    print("  测试股票: 000001 (平安银行), 000002 (万科A)")
    print("="*60)

    # 检查 Tushare 配置
    if not TUSHARE_ENABLED or not TUSHARE_TOKEN:
        print_result(False, "Tushare 未启用或未配置 Token")
        print("   请在 .env 文件中配置:")
        print("   TUSHARE_ENABLED=true")
        print("   TUSHARE_TOKEN=your_token_here")
        return

    print_result(True, f"Tushare 已配置，Token: {TUSHARE_TOKEN[:20]}...")

    try:
        # 步骤 0: 登录获取 Token
        token = await login_and_get_token()
        if not token:
            print_result(False, "无法获取认证 Token，测试终止")
            return

        # 获取 Tushare 提供者
        print_section("初始化 Tushare 数据提供者")
        provider = await get_tushare_provider()
        print_result(True, "Tushare 连接成功")

        # 步骤 1-5: 获取数据
        stocks = await fetch_basic_info(provider, TEST_SYMBOLS)
        quotes = await fetch_quotes(provider, TEST_SYMBOLS)
        financial_data_list = await fetch_financial_data(provider, TEST_SYMBOLS)
        news_list = await fetch_news_data(provider, TEST_SYMBOLS)
        kline_data = await fetch_historical_kline(provider, TEST_SYMBOLS)

        # 步骤 6-10: 导入数据
        await import_basic_info(stocks, token)
        await import_quotes(quotes, token)
        await import_financial_data(financial_data_list, token)
        await import_news_data(news_list, token)
        await import_historical_kline(kline_data, token)

        # 完成
        print_section("测试完成")
        print_result(True, "所有数据导入测试完成！")

    except Exception as e:
        print_result(False, f"测试过程中发生异常: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

