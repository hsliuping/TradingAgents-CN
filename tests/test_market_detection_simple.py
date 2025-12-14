#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化的市场检测测试脚本

仅测试自动检测功能，不执行完整分析
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.utils.market_detector import MarketSymbolDetector

def test_detection_cases():
    """测试多种代码的检测"""
    test_cases = [
        # (代码, 预期市场, 预期类型, 描述)
        ("300024", "A股", "index", "机器人指数"),
        ("000300", "A股", "index", "沪深300"),
        ("SH000001", "A股", "index", "上证指数"),
        ("SZ399001", "A股", "index", "深证成指"),
        ("000001", "A股", "index", "上证指数（简写）"),
        ("000002", "A股", "stock", "万科A"),
        ("600000", "A股", "stock", "浦发银行"),
        ("300750", "A股", "stock", "宁德时代"),
        ("00700", "港股", "stock", "腾讯控股"),
        ("AAPL", "美股", "stock", "苹果"),
        ("SPX", "美股", "index", "标普500"),
    ]
    
    results = []
    print("\n" + "="*100)
    print("市场检测测试结果")
    print("="*100)
    print(f"{'代码':<15} {'预期市场':<10} {'检测市场':<10} {'预期类型':<10} {'检测类型':<10} {'状态':<10} {'描述':<20}")
    print("-"*100)
    
    passed = 0
    failed = 0
    
    for code, expected_market, expected_type, desc in test_cases:
        detected_market, detected_type = MarketSymbolDetector.detect(code)
        
        market_match = detected_market == expected_market
        type_match = detected_type == expected_type
        status = "✅ 通过" if (market_match and type_match) else "❌ 失败"
        
        if market_match and type_match:
            passed += 1
        else:
            failed += 1
        
        print(f"{code:<15} {expected_market:<10} {detected_market:<10} {expected_type:<10} {detected_type:<10} {status:<10} {desc:<20}")
        
        results.append({
            "code": code,
            "description": desc,
            "expected": {
                "market": expected_market,
                "type": expected_type
            },
            "detected": {
                "market": detected_market,
                "type": detected_type
            },
            "passed": market_match and type_match
        })
    
    print("-"*100)
    print(f"总计: {len(test_cases)} 个测试用例, 通过: {passed}, 失败: {failed}")
    print("="*100)
    
    return results, passed, failed

def save_results(results, passed, failed):
    """保存测试结果"""
    output_dir = "./test_results"
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. 保存JSON格式结果
    json_file = os.path.join(output_dir, f"market_detection_test_{timestamp}.json")
    result_data = {
        "test_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{passed/len(results)*100:.2f}%"
        },
        "test_cases": results
    }
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ JSON结果已保存: {json_file}")
    
    # 2. 保存TXT格式报告
    txt_file = os.path.join(output_dir, f"market_detection_report_{timestamp}.txt")
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write("="*100 + "\n")
        f.write("市场检测功能测试报告\n")
        f.write("="*100 + "\n\n")
        
        f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"测试用例总数: {len(results)}\n")
        f.write(f"通过: {passed}\n")
        f.write(f"失败: {failed}\n")
        f.write(f"通过率: {passed/len(results)*100:.2f}%\n\n")
        
        f.write("="*100 + "\n")
        f.write("详细测试结果\n")
        f.write("="*100 + "\n\n")
        
        for i, result in enumerate(results, 1):
            status_symbol = "✅" if result['passed'] else "❌"
            f.write(f"{i}. {status_symbol} {result['description']} ({result['code']})\n")
            f.write(f"   预期: {result['expected']['market']} - {result['expected']['type']}\n")
            f.write(f"   检测: {result['detected']['market']} - {result['detected']['type']}\n")
            if not result['passed']:
                f.write(f"   ⚠️  不匹配\n")
            f.write("\n")
    
    print(f"✅ TXT报告已保存: {txt_file}")
    
    # 3. 特别测试：机器人指数
    robot_index_file = os.path.join(output_dir, f"robot_index_300024_detection_{timestamp}.txt")
    with open(robot_index_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("机器人指数（300024）自动检测结果\n")
        f.write("="*80 + "\n\n")
        
        code = "300024"
        market, analysis_type = MarketSymbolDetector.detect(code)
        
        f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"输入代码: {code}\n")
        f.write(f"检测到的市场: {market}\n")
        f.write(f"检测到的类型: {analysis_type}\n\n")
        
        f.write("验证结果:\n")
        if market == "A股" and analysis_type == "index":
            f.write("✅ 自动检测成功！\n")
            f.write("✅ 300024 被正确识别为 A股指数\n")
            f.write("✅ 可以直接使用指数分析workflow\n")
        else:
            f.write("❌ 自动检测失败\n")
            f.write(f"   期望: A股 - index\n")
            f.write(f"   实际: {market} - {analysis_type}\n")
    
    print(f"✅ 机器人指数检测结果已保存: {robot_index_file}\n")
    
    return json_file, txt_file, robot_index_file

def main():
    """主测试流程"""
    print("\n" + "="*100)
    print("🤖 市场自动检测功能测试")
    print("="*100)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        # 执行测试
        results, passed, failed = test_detection_cases()
        
        # 保存结果
        json_file, txt_file, robot_file = save_results(results, passed, failed)
        
        print("\n" + "="*100)
        print("✅ 测试完成！")
        print("="*100)
        print(f"\n📁 生成的文件:")
        print(f"   - JSON结果: {json_file}")
        print(f"   - TXT报告: {txt_file}")
        print(f"   - 机器人指数: {robot_file}\n")
        
        return 0 if failed == 0 else 1
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
