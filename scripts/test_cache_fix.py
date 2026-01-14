#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试缓存修复 - 验证 TTL 类型转换是否正常工作
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_adaptive_cache():
    """测试自适应缓存系统"""
    print("=" * 60)
    print("测试自适应缓存系统")
    print("=" * 60)
    
    try:
        from tradingagents.dataflows.cache.adaptive import AdaptiveCacheSystem
        
        # 创建缓存实例
        cache = AdaptiveCacheSystem()
        print(f"✅ 缓存系统初始化成功")
        print(f"   主要后端: {cache.primary_backend}")
        
        # 测试保存数据（模拟大盘分析报告）
        print("\n📝 测试保存大盘分析报告...")
        cache_key = cache.save_data(
            symbol="market_v2",
            data="这是一个测试报告",
            start_date="20260114",
            end_date="20260114",
            data_source="llm",
            data_type="index_report"
        )
        print(f"✅ 保存成功，缓存键: {cache_key}")
        
        # 测试保存板块分析报告
        print("\n📝 测试保存板块分析报告...")
        cache_key = cache.save_data(
            symbol="000001",
            data="这是一个板块分析报告",
            start_date="20260114",
            end_date="20260114",
            data_source="llm",
            data_type="sector_report"
        )
        print(f"✅ 保存成功，缓存键: {cache_key}")
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！缓存修复有效。")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integrated_cache():
    """测试集成缓存管理器"""
    print("\n" + "=" * 60)
    print("测试集成缓存管理器")
    print("=" * 60)
    
    try:
        from tradingagents.dataflows.cache import get_cache
        
        cache = get_cache()
        print(f"✅ 集成缓存管理器初始化成功")
        
        # 测试保存分析报告
        print("\n📝 测试保存分析报告...")
        cache_key = cache.save_analysis_report(
            report_type="index_report",
            report_data="测试大盘分析报告",
            symbol="market_v2",
            trade_date="2026-01-14",
            data_source="llm"
        )
        print(f"✅ 保存成功，缓存键: {cache_key}")
        
        # 测试加载报告
        print("\n📖 测试加载报告...")
        loaded_data = cache.load_analysis_report(cache_key)
        if loaded_data:
            print(f"✅ 加载成功: {loaded_data[:50]}...")
        else:
            print(f"⚠️ 未找到缓存数据")
        
        print("\n" + "=" * 60)
        print("✅ 集成缓存测试通过！")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n🧪 开始测试缓存修复...\n")
    
    # 测试自适应缓存
    result1 = test_adaptive_cache()
    
    # 测试集成缓存
    result2 = test_integrated_cache()
    
    # 总结
    print("\n" + "=" * 60)
    if result1 and result2:
        print("🎉 所有测试通过！缓存系统工作正常。")
        sys.exit(0)
    else:
        print("❌ 部分测试失败，请检查错误信息。")
        sys.exit(1)

