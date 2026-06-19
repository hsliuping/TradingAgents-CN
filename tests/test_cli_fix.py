#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试CLI修复 - KeyError: 'stock_symbol' 问题
Test CLI Fix - KeyError: 'stock_symbol' Issue

这个测试验证了CLI中selections字典键名不匹配问题的修复
This test verifies the fix for the selections dictionary key mismatch issue in CLI
"""

import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_selections_dictionary_keys():
    """
    测试selections字典中的键名是否正确
    Test if the keys in selections dictionary are correct
    """
    print("🔍 测试selections字典键名...")
    
    try:
        from cli.main import get_user_selections
        
        # 模拟用户输入
        with patch('typer.prompt') as mock_prompt, \
             patch('cli.main.select_market') as mock_market, \
             patch('cli.main.select_analysts') as mock_analysts, \
             patch('cli.main.select_research_depth') as mock_depth, \
             patch('cli.main.select_llm_provider') as mock_llm, \
             patch('cli.main.select_shallow_thinking_agent') as mock_shallow, \
             patch('cli.main.select_deep_thinking_agent') as mock_deep, \
             patch('cli.main.console.print'):
            
            # 设置模拟返回值
            mock_market.return_value = {
                'name': 'A股',
                'name_en': 'China A-Share',
                'default': '600036',
                'pattern': r'^\d{6}$',
                'data_source': 'china_stock'
            }
            mock_prompt.side_effect = ['600036', '2024-12-01']  # ticker, date
            mock_analysts.return_value = [MagicMock(value='market')]
            mock_depth.return_value = 3
            mock_llm.return_value = ('dashscope', 'http://localhost:8100')
            mock_shallow.return_value = 'qwen-turbo'
            mock_deep.return_value = 'qwen-max'
            
            # 调用函数
            selections = get_user_selections()
            
            # 验证必要的键存在
            required_keys = [
                'ticker',  # 这是正确的键名
                'market',
                'analysis_date',
                'analysts',
                'research_depth',
                'llm_provider',
                'backend_url',
                'shallow_thinker',
                'deep_thinker'
            ]
            
            for key in required_keys:
                assert key in selections, f"缺少必要的键: {key}"
                print(f"✅ 键 '{key}' 存在")
            
            # 确保不存在错误的键名
            assert 'stock_symbol' not in selections, "不应该存在 'stock_symbol' 键"
            print("✅ 确认不存在错误的 'stock_symbol' 键")
            
            print("✅ selections字典键名测试通过")
            return True
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_process_signal_call():
    """
    测试process_signal调用是否使用正确的键名
    Test if process_signal call uses correct key name
    """
    print("\n🔍 测试process_signal调用...")
    
    try:
        # 读取main.py文件内容
        main_file = project_root / 'cli' / 'main.py'
        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否使用了正确的键名
        if "selections['ticker']" in content:
            print("✅ 找到正确的键名 selections['ticker']")
        else:
            print("❌ 未找到 selections['ticker']")
            return False
        
        # 确保不再使用错误的键名
        if "selections['stock_symbol']" in content:
            print("❌ 仍然存在错误的键名 selections['stock_symbol']")
            return False
        else:
            print("✅ 确认不存在错误的键名 selections['stock_symbol']")
        
        print("✅ process_signal调用测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_code_consistency():
    """
    测试代码一致性 - 确保所有地方都使用相同的键名
    Test code consistency - ensure all places use the same key names
    """
    print("\n🔍 测试代码一致性...")
    
    try:
        main_file = project_root / 'cli' / 'main.py'
        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 统计ticker键的使用次数
        ticker_count = content.count("selections['ticker']")
        ticker_double_quote_count = content.count('selections["ticker"]')
        
        total_ticker_usage = ticker_count + ticker_double_quote_count
        
        print(f"📊 'ticker'键使用次数: {total_ticker_usage}")
        
        if total_ticker_usage >= 2:  # 至少应该有2处使用（初始化和process_signal）
            print("✅ ticker键使用次数合理")
        else:
            print("⚠️  ticker键使用次数可能不足")
        
        # 检查是否还有其他可能的键名不一致问题
        potential_issues = [
            "selections['symbol']",
            "selections['stock']",
            "selections['code']"
        ]
        
        for issue in potential_issues:
            if issue in content:
                print(f"⚠️  发现潜在问题: {issue}")
            else:
                print(f"✅ 未发现问题: {issue}")
        
        print("✅ 代码一致性测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    """
    运行所有测试
    Run all tests
    """
    print("🚀 开始CLI修复验证测试...")
    print("=" * 50)
    
    tests = [
        test_selections_dictionary_keys,
        test_process_signal_call,
        test_code_consistency
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！KeyError: 'stock_symbol' 问题已修复")
        return True
    else:
        print("❌ 部分测试失败，需要进一步检查")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)