#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量导入API测试程序

使用 Tushare 获取 000001 和 000002 两只股票的数据，然后通过批量导入 API 导入到数据库中。

功能特性：
- 支持交互式菜单，可选择单项测试或全部测试
- 自动从 Tushare 获取完整字段数据（包括市值、财务比率、股本等）
- 验证 API 数据质量要求（必填字段检查）

测试数据类型：
1. 股票基本信息（包含完整财务数据）
2. 实时行情
3. 财务数据
4. 新闻数据
5. 历史K线数据

使用方法：
1. 确保 .env 文件中配置了 Tushare Token
2. 运行: python scripts/test_batch_import_apis.py
3. 选择要测试的项目（0-5）或退出（q）

作者: TradingAgents-CN Pro Team
版本: v1.1.0
创建日期: 2026-01-24
更新日期: 2026-01-25
"""

import os
import sys
import asyncio
import requests
import json
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

def convert_datetime_to_str(obj: Any) -> Any:
    """递归转换对象中的 datetime 为字符串"""
    if isinstance(obj, datetime):
        return obj.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(obj, dict):
        return {k: convert_datetime_to_str(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime_to_str(item) for item in obj]
    else:
        return obj


def clean_json_data(obj: Any) -> Any:
    """递归清理对象中的 NaN、Infinity 等非 JSON 兼容值"""
    import math

    if isinstance(obj, float):
        # 处理 NaN 和 Infinity
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: clean_json_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_json_data(item) for item in obj]
    else:
        return obj


def round_float_values(obj: Any, decimals: int = 4) -> Any:
    """递归对对象中的浮点数进行四舍五入，保留指定小数位数"""
    if isinstance(obj, float):
        return round(obj, decimals)
    elif isinstance(obj, dict):
        return {k: round_float_values(v, decimals) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [round_float_values(item, decimals) for item in obj]
    else:
        return obj


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

                # 检查用户权限
                user_plan = result["data"].get("user", {}).get("plan", "free")
                print(f"   当前用户计划: {user_plan}")

                if user_plan == "free":
                    print("   ⚠️  当前是初级学员，批量导入功能需要高级学员权限")
                    print("   💡 提示：可以在数据库中手动升级用户为高级学员")

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
    """获取股票基本信息（包含市值、财务比率等完整字段）"""
    print_section("步骤 1: 获取股票基本信息（完整字段）")

    stocks = []

    # 🔥 获取最新交易日期
    try:
        latest_trade_date = await provider.find_latest_trade_date()
        if latest_trade_date:
            # 转换为 YYYYMMDD 格式
            latest_trade_date = latest_trade_date.replace('-', '')
            print(f"   📅 最新交易日期: {latest_trade_date}")
        else:
            print_result(False, "未找到最新交易日期")
    except Exception as e:
        print_result(False, f"获取最新交易日期失败: {str(e)}")
        latest_trade_date = None

    # 🔥 获取 daily_basic 数据（市值、财务比率等）
    daily_data_map = {}
    if latest_trade_date:
        try:
            fields = "ts_code,total_mv,circ_mv,pe,pb,ps,turnover_rate,volume_ratio,pe_ttm,pb_mrq,ps_ttm,total_share,float_share"
            df = await asyncio.to_thread(
                provider.api.daily_basic,
                trade_date=latest_trade_date,
                fields=fields
            )
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    ts_code = row.get('ts_code')
                    if ts_code:
                        daily_data_map[ts_code] = row.to_dict()
                print(f"   ✅ 获取 daily_basic 数据成功: {len(daily_data_map)} 条记录")
        except Exception as e:
            print_result(False, f"获取 daily_basic 数据失败: {str(e)}")

    # 🔥 获取每只股票的基本信息并合并 daily_basic 数据
    for symbol in symbols:
        try:
            info = await provider.get_stock_basic_info(symbol)
            if info:
                # 获取 ts_code
                ts_code = info.get('full_symbol', '')

                # 🔥 合并 daily_basic 数据
                if ts_code in daily_data_map:
                    daily_metrics = daily_data_map[ts_code]

                    # 市值字段（从万元转换为亿元）
                    if 'total_mv' in daily_metrics and daily_metrics['total_mv']:
                        info['total_mv'] = float(daily_metrics['total_mv']) / 10000.0
                    if 'circ_mv' in daily_metrics and daily_metrics['circ_mv']:
                        info['circ_mv'] = float(daily_metrics['circ_mv']) / 10000.0

                    # 财务比率
                    for field in ['pe', 'pb', 'ps', 'pe_ttm', 'pb_mrq', 'ps_ttm']:
                        if field in daily_metrics and daily_metrics[field]:
                            info[field] = daily_metrics[field]

                    # 交易指标
                    for field in ['turnover_rate', 'volume_ratio']:
                        if field in daily_metrics and daily_metrics[field]:
                            info[field] = daily_metrics[field]

                    # 股本字段
                    for field in ['total_share', 'float_share']:
                        if field in daily_metrics and daily_metrics[field]:
                            info[field] = daily_metrics[field]

                print_result(True, f"获取 {symbol} 完整信息成功",
                           f"{info.get('name')} (市值: {info.get('total_mv', 'N/A')}亿)")
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
    """获取历史K线数据（最近3650天，约10年）"""
    print_section("步骤 5: 获取历史K线数据")

    kline_data = {}
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3650)  # 约10年数据

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
    # 转换 datetime 对象为字符串
    stocks = convert_datetime_to_str(stocks)
    # 清理 NaN 和 Infinity 值
    stocks = clean_json_data(stocks)
    # 四舍五入浮点数（保留4位小数）
    stocks = round_float_values(stocks, decimals=4)
    return {
        "stocks": stocks
    }


def transform_quotes(quotes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """转换实时行情为 API 请求格式"""
    # 转换 datetime 对象为字符串
    quotes = convert_datetime_to_str(quotes)
    # 清理 NaN 和 Infinity 值
    quotes = clean_json_data(quotes)
    # 四舍五入浮点数（保留4位小数）
    quotes = round_float_values(quotes, decimals=4)
    return {
        "quotes": quotes
    }


def transform_financial_data(symbol: str, financial_data: Dict[str, Any]) -> Dict[str, Any]:
    """转换财务数据为 API 请求格式"""
    # 转换 datetime 对象为字符串
    financial_data = convert_datetime_to_str(financial_data)
    # 清理 NaN 和 Infinity 值
    financial_data = clean_json_data(financial_data)
    # 四舍五入浮点数（保留4位小数）
    financial_data = round_float_values(financial_data, decimals=4)
    return {
        "symbol": symbol,
        "financial_data": [financial_data]  # API 需要数组格式
    }


def transform_news_data(news_list: List[Dict[str, Any]], symbol: str = None) -> Dict[str, Any]:
    """转换新闻数据为 API 请求格式"""
    # 转换 datetime 对象为字符串
    news_list = convert_datetime_to_str(news_list)
    # 清理 NaN 和 Infinity 值
    news_list = clean_json_data(news_list)
    # 四舍五入浮点数（保留4位小数）
    news_list = round_float_values(news_list, decimals=4)
    return {
        "symbol": symbol,
        "news_list": news_list
    }


def transform_kline_data(symbol: str, df, overwrite: bool = False) -> Dict[str, Any]:
    """转换历史K线数据为 API 请求格式"""
    import pandas as pd

    records = []
    for idx, row in df.iterrows():
        # 🔥 格式化日期为 YYYYMMDD 格式（API 要求）
        if isinstance(idx, pd.Timestamp):
            trade_date = idx.strftime("%Y%m%d")
        elif isinstance(idx, str):
            # 如果是字符串，移除横杠和时间部分
            trade_date = idx.replace("-", "").split(" ")[0]
        else:
            trade_date = str(idx)

        record = {
            "trade_date": trade_date,
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

    # 清理 NaN 和 Infinity 值
    records = clean_json_data(records)
    # 四舍五入浮点数（保留4位小数）
    records = round_float_values(records, decimals=4)

    return {
        "symbol": symbol,
        "period": "daily",
        "records": records,
        "overwrite": overwrite  # 添加 overwrite 参数
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
            # API 返回格式: {"success": True, "data": ..., "message": ...}
            if result.get("success"):
                message = result.get("message", "成功")
                print_result(True, f"{operation}成功: {message}")
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
        "/api/stock-data/save-basic-info",
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
        "/api/stock-data/save-quotes",
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

    # 财务数据API需要按股票分别调用
    success_count = 0
    for financial_data in financial_data_list:
        symbol = financial_data.get("symbol")
        if not symbol:
            print_result(False, "财务数据缺少 symbol 字段")
            continue

        data = transform_financial_data(symbol, financial_data)
        if call_batch_import_api(
            "/api/financial-data/save",
            data,
            token,
            f"导入 {symbol} 财务数据"
        ):
            success_count += 1

    return success_count > 0


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


async def import_historical_kline(kline_data: Dict[str, Any], token: str, overwrite: bool = False) -> bool:
    """导入历史K线数据

    Args:
        kline_data: K线数据字典 {symbol: DataFrame}
        token: 认证令牌
        overwrite: 是否覆盖已存在的数据（默认False，不覆盖）
    """
    print_section("步骤 10: 导入历史K线数据")

    overwrite_text = "覆盖模式" if overwrite else "不覆盖模式"
    print(f"   📝 导入模式: {overwrite_text}")

    if not kline_data:
        print_result(False, "没有历史K线数据可导入")
        return False

    success_count = 0
    for symbol, df in kline_data.items():
        data = transform_kline_data(symbol, df, overwrite=overwrite)
        if call_batch_import_api(
            "/api/historical-data/batch-import",
            data,
            token,
            f"导入 {symbol} 历史K线 ({overwrite_text})"
        ):
            success_count += 1

    return success_count > 0


# ============================================================================
# 主函数
# ============================================================================

def show_menu():
    """显示测试菜单"""
    print("\n" + "="*60)
    print("  批量导入API测试程序")
    print("  测试股票: 000001 (平安银行), 000002 (万科A)")
    print("="*60)
    print("\n请选择测试项目：")
    print("  0. 运行所有测试")
    print("  1. 测试股票基本信息导入")
    print("  2. 测试实时行情导入")
    print("  3. 测试财务数据导入")
    print("  4. 测试新闻数据导入")
    print("  5. 测试历史K线数据导入")
    print("  q. 退出")
    print("="*60)


async def run_all_tests(provider, token):
    """运行所有测试"""
    print_section("运行所有测试")

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


async def run_single_test(test_choice: str, provider, token):
    """运行单项测试"""
    if test_choice == "1":
        # 测试股票基本信息导入
        stocks = await fetch_basic_info(provider, TEST_SYMBOLS)
        await import_basic_info(stocks, token)

    elif test_choice == "2":
        # 测试实时行情导入
        quotes = await fetch_quotes(provider, TEST_SYMBOLS)
        await import_quotes(quotes, token)

    elif test_choice == "3":
        # 测试财务数据导入
        financial_data_list = await fetch_financial_data(provider, TEST_SYMBOLS)
        await import_financial_data(financial_data_list, token)

    elif test_choice == "4":
        # 测试新闻数据导入
        news_list = await fetch_news_data(provider, TEST_SYMBOLS)
        await import_news_data(news_list, token)

    elif test_choice == "5":
        # 测试历史K线数据导入
        kline_data = await fetch_historical_kline(provider, TEST_SYMBOLS)
        await import_historical_kline(kline_data, token)

    print_section("测试完成")
    print_result(True, f"测试项目 {test_choice} 完成！")


async def main():
    """主函数"""
    # 检查 Tushare 配置
    if not TUSHARE_ENABLED or not TUSHARE_TOKEN:
        print("\n" + "="*60)
        print_result(False, "Tushare 未启用或未配置 Token")
        print("   请在 .env 文件中配置:")
        print("   TUSHARE_ENABLED=true")
        print("   TUSHARE_TOKEN=your_token_here")
        print("="*60)
        return

    try:
        # 步骤 0: 登录获取 Token
        print("\n" + "="*60)
        print("  初始化测试环境")
        print("="*60)
        print_result(True, f"Tushare 已配置，Token: {TUSHARE_TOKEN[:20]}...")

        token = await login_and_get_token()
        if not token:
            print_result(False, "无法获取认证 Token，测试终止")
            return

        # 获取 Tushare 提供者
        print_section("初始化 Tushare 数据提供者")
        provider = await get_tushare_provider()
        print_result(True, "Tushare 连接成功")

        # 显示菜单并获取用户选择
        while True:
            show_menu()
            choice = input("\n请输入选项 (0-5 或 q): ").strip().lower()

            if choice == 'q':
                print("\n退出测试程序")
                break
            elif choice == '0':
                await run_all_tests(provider, token)
            elif choice in ['1', '2', '3', '4', '5']:
                await run_single_test(choice, provider, token)
            else:
                print_result(False, "无效的选项，请重新选择")
                continue

            # 询问是否继续
            continue_test = input("\n是否继续测试？(y/n): ").strip().lower()
            if continue_test != 'y':
                print("\n退出测试程序")
                break

    except KeyboardInterrupt:
        print("\n\n用户中断测试")
    except Exception as e:
        print_result(False, f"测试过程中发生异常: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

