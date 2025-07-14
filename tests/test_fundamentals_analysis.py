#!/usr/bin/env python3
"""
基本面分析功能测试
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv(project_root / ".env", override=True)

def test_fundamentals_report_generation():
    """测试基本面报告生成"""
    print("🧪 测试基本面报告生成...")
    
    try:
        from tradingagents.dataflows.tdx_utils import get_china_stock_data
        from tradingagents.dataflows.optimized_china_data import OptimizedChinaDataProvider
        from datetime import datetime, timedelta
        
        # 创建分析器实例
        analyzer = OptimizedChinaDataProvider()
        
        # 测试股票
        test_stocks = [
            ("000001", "平安银行"),
            ("600519", "贵州茅台"),
        ]
        
        results = []
        
        # 计算日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        for ticker, expected_name in test_stocks:
            print(f"\n📊 测试 {ticker} ({expected_name})")
            
            try:
                # 获取真实股票数据
                real_stock_data = get_china_stock_data(
                    ticker,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d')
                )
                
                if not real_stock_data or "获取失败" in real_stock_data:
                    print(f"   ⚠️ 跳过 {ticker}，数据获取失败")
                    continue
                
                # 生成基本面报告
                report = analyzer._generate_fundamentals_report(ticker, real_stock_data)
                
                # 检查报告质量
                expected_keywords = [
                    "财务数据分析",
                    "估值指标",
                    "市盈率",
                    "投资建议",
                    "基本面评分"
                ]
                
                found_keywords = [k for k in expected_keywords if k in report]
                
                print(f"   ✅ 报告生成成功，长度: {len(report)}")
                print(f"   📊 关键词匹配: {len(found_keywords)}/{len(expected_keywords)}")
                
                success = len(found_keywords) >= 3
                results.append((ticker, success))
                
            except Exception as e:
                print(f"   ❌ 测试失败: {e}")
                results.append((ticker, False))
        
        # 总结结果
        passed = sum(1 for _, success in results if success)
        print(f"\n📊 测试结果: {passed}/{len(results)} 通过")
        
        return passed > 0
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_chinese_investment_advice():
    """测试中文投资建议"""
    print("\n🧪 测试中文投资建议...")
    
    try:
        from tradingagents.dataflows.optimized_china_data import OptimizedChinaDataProvider
        
        analyzer = OptimizedChinaDataProvider()
        
        # 测试投资建议生成
        financial_estimates = {
            "fundamental_score": 7.5,
            "valuation_score": 8.0,
            "growth_score": 6.5,
            "risk_level": "中等"
        }
        
        industry_info = {
            "industry": "银行业",
            "analysis": "测试分析"
        }
        
        advice = analyzer._generate_investment_advice(financial_estimates, industry_info)
        
        # 检查是否包含中文投资建议
        chinese_actions = ['买入', '卖出', '持有']
        english_actions = ['buy', 'sell', 'hold', 'BUY', 'SELL', 'HOLD']
        
        has_chinese = any(action in advice for action in chinese_actions)
        has_english = any(action in advice for action in english_actions)
        
        print(f"   包含中文建议: {'✅' if has_chinese else '❌'}")
        print(f"   包含英文建议: {'❌' if has_english else '✅'}")
        
        return has_chinese and not has_english
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🧪 基本面分析功能测试")
    print("=" * 50)
    
    tests = [
        ("基本面报告生成", test_fundamentals_report_generation),
        ("中文投资建议", test_chinese_investment_advice),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
            results.append((test_name, False))
    
    # 总结结果
    print("\n" + "="*50)
    print("📋 测试结果总结:")
    print("="*50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{len(results)} 项测试通过")
    
    return passed >= len(results) // 2

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
