#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票数据批量导入 API 示例代码

本文件包含所有股票数据批量导入接口的完整示例代码。

使用前请先：
1. 安装依赖: pip install requests
2. 修改 BASE_URL 和 TOKEN 为您的实际值
3. 确保您是高级学员（批量导入功能为高级学员专属）

作者: TradingAgents-CN Pro Team
版本: v1.0.0
最后更新: 2026-01-23
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Any


# ============================================================================
# 配置部分
# ============================================================================

# API 基础 URL（请根据实际情况修改）
BASE_URL = "http://localhost:9706"

# 认证 Token（请替换为您的实际 Token）
TOKEN = "your_auth_token_here"

# 请求头
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}


# ============================================================================
# 辅助函数
# ============================================================================

def print_response(response: requests.Response, operation: str):
    """打印响应结果"""
    print(f"\n{'='*60}")
    print(f"操作: {operation}")
    print(f"{'='*60}")
    
    if response.status_code == 200:
        result = response.json()
        if result.get('success'):
            data = result.get('data', {})
            print(f"✅ 成功: {data.get('saved', 0)}")
            print(f"🔄 更新: {data.get('updated', 0)}")
            print(f"⚠️  跳过: {data.get('skipped', 0)}")
            print(f"❌ 失败: {data.get('failed', 0)}")
            print(f"📊 总计: {data.get('total', 0)}")
            
            if data.get('errors'):
                print(f"\n错误详情:")
                for error in data['errors'][:5]:  # 只显示前5个错误
                    print(f"  - {error}")
        else:
            print(f"❌ 操作失败: {result.get('message')}")
    elif response.status_code == 403:
        print(f"❌ 权限不足: 此功能为高级学员专属")
        print(f"   请在 设置 → 许可证管理 页面激活高级学员权限")
    else:
        print(f"❌ 请求失败 (HTTP {response.status_code})")
        print(f"   {response.text}")
    
    print(f"{'='*60}\n")


# ============================================================================
# 示例 1: 批量导入股票基本信息
# ============================================================================

def example_save_basic_info():
    """批量导入股票基本信息"""
    
    # 准备数据
    data = {
        "stocks": [
            {
                "symbol": "000001",
                "name": "平安银行",
                "full_symbol": "000001.SZ",
                "market": "CN",
                "industry": "银行",
                "area": "深圳",
                "list_date": "1991-04-03",
                "total_mv": 2500.0,
                "pe": 5.2,
                "pb": 0.8
            },
            {
                "symbol": "000002",
                "name": "万科A",
                "full_symbol": "000002.SZ",
                "market": "CN",
                "industry": "房地产",
                "area": "深圳",
                "list_date": "1991-01-29",
                "total_mv": 1800.0,
                "pe": 8.5,
                "pb": 1.2
            },
            {
                "symbol": "600000",
                "name": "浦发银行",
                "full_symbol": "600000.SH",
                "market": "CN",
                "industry": "银行",
                "area": "上海",
                "list_date": "1999-11-10"
            }
        ],
        "data_source": "my_crawler",  # 数据来源标识
        "overwrite": False  # 不覆盖已存在的数据
    }
    
    # 发送请求
    response = requests.post(
        f"{BASE_URL}/api/stock-data/save-basic-info",
        headers=HEADERS,
        json=data
    )
    
    # 打印结果
    print_response(response, "批量导入股票基本信息")
    
    return response


# ============================================================================
# 示例 2: 批量导入实时行情数据
# ============================================================================

def example_save_quotes():
    """批量导入实时行情数据"""

    # 准备数据
    data = {
        "quotes": [
            {
                "symbol": "000001",
                "close": 12.65,
                "open": 12.50,
                "high": 12.80,
                "low": 12.30,
                "pct_chg": 1.61,
                "amount": 1580000000,
                "volume": 125000000,
                "trade_date": datetime.now().strftime("%Y-%m-%d"),
                "current_price": 12.65,
                "change": 0.20
            },
            {
                "symbol": "000002",
                "close": 8.95,
                "open": 8.80,
                "high": 9.10,
                "low": 8.75,
                "pct_chg": 1.70,
                "amount": 980000000,
                "volume": 110000000,
                "trade_date": datetime.now().strftime("%Y-%m-%d")
            }
        ],
        "data_source": "realtime_api",
        "overwrite": True  # 行情数据通常需要覆盖
    }

    # 发送请求
    response = requests.post(
        f"{BASE_URL}/api/stock-data/save-quotes",
        headers=HEADERS,
        json=data
    )

    # 打印结果
    print_response(response, "批量导入实时行情数据")

    return response


# ============================================================================
# 示例 3: 批量导入财务数据
# ============================================================================

def example_save_financial_data():
    """批量导入财务数据"""

    # 准备数据
    data = {
        "symbol": "000001",
        "financial_data": [
            {
                "report_period": "20231231",
                "report_type": "annual",
                "ann_date": "2024-03-20",
                "total_assets": 5000000000,
                "total_liabilities": 4000000000,
                "total_equity": 1000000000,
                "revenue": 100000000,
                "net_profit": 20000000,
                "operating_profit": 25000000,
                "roe": 15.5,
                "roa": 3.2,
                "eps": 1.25,
                "bps": 8.50
            },
            {
                "report_period": "20230930",
                "report_type": "quarterly",
                "ann_date": "2023-10-25",
                "revenue": 75000000,
                "net_profit": 15000000,
                "operating_profit": 18000000,
                "eps": 0.95
            },
            {
                "report_period": "20230630",
                "report_type": "semi_annual",
                "ann_date": "2023-08-20",
                "revenue": 50000000,
                "net_profit": 10000000
            }
        ],
        "data_source": "financial_api",
        "overwrite": False
    }

    # 发送请求
    response = requests.post(
        f"{BASE_URL}/api/financial-data/save",
        headers=HEADERS,
        json=data
    )

    # 打印结果
    print_response(response, "批量导入财务数据")

    return response


# ============================================================================
# 示例 4: 批量导入新闻数据
# ============================================================================

def example_save_news_data():
    """批量导入新闻数据"""

    # 准备数据
    data = {
        "symbol": "000001",
        "news_list": [
            {
                "title": "平安银行发布2023年年报",
                "content": "平安银行股份有限公司今日发布2023年年度报告，报告显示全年实现营业收入...",
                "summary": "平安银行2023年净利润同比增长2.6%，资产质量保持稳定",
                "url": "https://example.com/news/20240320/123",
                "source": "证券时报",
                "author": "张三",
                "publish_time": "2024-03-20T09:00:00Z",
                "category": "company_announcement",
                "sentiment": "positive",
                "sentiment_score": 0.75,
                "keywords": ["年报", "净利润", "增长"],
                "importance": "high",
                "symbols": ["000001"]
            },
            {
                "title": "银行业监管政策调整，影响多家上市银行",
                "content": "中国银保监会今日发布最新监管政策...",
                "summary": "新监管政策要求银行提高资本充足率",
                "url": "https://example.com/news/20240321/124",
                "source": "财经网",
                "author": "李四",
                "publish_time": "2024-03-21T10:00:00Z",
                "category": "industry_news",
                "sentiment": "neutral",
                "sentiment_score": 0.50,
                "keywords": ["监管", "政策", "银行"],
                "importance": "medium",
                "symbols": ["000001", "600000", "600036"]
            },
            {
                "title": "平安银行推出新型理财产品",
                "url": "https://example.com/news/20240322/125",
                "source": "金融时报",
                "publish_time": "2024-03-22T14:30:00Z",
                "category": "product_news",
                "sentiment": "positive",
                "importance": "low"
            }
        ],
        "data_source": "news_crawler",
        "overwrite": False
    }

    # 发送请求
    response = requests.post(
        f"{BASE_URL}/api/news-data/save",
        headers=HEADERS,
        json=data
    )

    # 打印结果
    print_response(response, "批量导入新闻数据")

    return response


# ============================================================================
# 示例 5: 获取认证 Token
# ============================================================================

def example_get_token(username: str, password: str) -> str:
    """获取认证 Token"""

    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "username": username,
            "password": password
        }
    )

    if response.status_code == 200:
        result = response.json()
        if result.get('success'):
            token = result['data']['token']
            print(f"✅ 登录成功，Token: {token[:20]}...")
            return token
        else:
            print(f"❌ 登录失败: {result.get('message')}")
    else:
        print(f"❌ 请求失败: {response.status_code}")

    return ""


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主函数：运行所有示例"""

    print("\n" + "="*60)
    print("股票数据批量导入 API 示例")
    print("="*60)

    # 提示：请先修改配置
    if TOKEN == "your_auth_token_here":
        print("\n⚠️  请先修改配置:")
        print("   1. 设置 BASE_URL 为您的 API 地址")
        print("   2. 设置 TOKEN 为您的认证 Token")
        print("   3. 确保您是高级学员（批量导入功能为高级学员专属）\n")
        return

    # 运行所有示例
    try:
        # 示例 1: 批量导入股票基本信息
        example_save_basic_info()

        # 示例 2: 批量导入实时行情数据
        example_save_quotes()

        # 示例 3: 批量导入财务数据
        example_save_financial_data()

        # 示例 4: 批量导入新闻数据
        example_save_news_data()

        print("\n✅ 所有示例运行完成！")

    except Exception as e:
        print(f"\n❌ 运行出错: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


