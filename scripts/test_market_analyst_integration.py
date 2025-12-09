#!/usr/bin/env python
# scripts/test_market_analyst_integration.py
"""
测试 StockAnalysisEngine 集成市场分析师

运行方式:
    .\env\Scripts\activate; python scripts/test_market_analyst_integration.py
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_market_analyst():
    """测试市场分析师集成"""
    print("\n" + "=" * 60)
    print("测试 StockAnalysisEngine 集成市场分析师")
    print("=" * 60)

    # 1. 使用 LegacyDependencyProvider 创建依赖
    # 不传入 config，让它自动从数据库获取 dashscope/qwen-plus 配置
    print("\n[1/3] 创建 LLM 和 Toolkit (从数据库获取配置)...")
    from core.workflow.builder import LegacyDependencyProvider

    provider = LegacyDependencyProvider()  # 自动从数据库获取配置
    llm = provider.get_llm("quick")
    toolkit = provider.get_toolkit()

    print(f"  ✓ LLM: {llm.__class__.__name__}")
    print("  ✓ Toolkit: 已创建")

    # 2. 创建引擎
    print("\n[2/3] 创建 StockAnalysisEngine...")
    from tradingagents.core import StockAnalysisEngine
    
    # 可配置的分析师列表
    import sys
    if len(sys.argv) > 1:
        selected_analysts = sys.argv[1].split(",")
    else:
        selected_analysts = ["market_analyst"]  # 默认只测试市场分析师

    engine = StockAnalysisEngine(
        llm=llm,
        toolkit=toolkit,
        use_stub=False,
        selected_analysts=selected_analysts
    )
    print("  ✓ 引擎创建完成")

    # 3. 执行分析
    print("\n[3/3] 执行分析...")
    print("  股票: 000858 (五粮液)")  # A股代码不带后缀
    print("  日期: 2024-01-15")
    print(f"  分析师: {', '.join(selected_analysts)}")
    print("\n  开始分析（可能需要 30-60 秒）...")

    result = engine.analyze(
        ticker='000858',  # A股代码不带后缀，前后端统一
        trade_date='2024-01-15',
        company_name='五粮液'
    )
    
    # 5. 输出结果
    print("\n" + "=" * 60)
    print("分析结果")
    print("=" * 60)
    
    print(f"\n分析状态: {'✅ 成功' if result.success else '❌ 失败'}")
    print(f"总耗时: {result.total_duration_seconds:.2f}s")

    print("\n阶段执行情况:")
    for phase_result in result.phase_results:
        status = "✅" if phase_result.success else "❌"
        print(f"  {status} {phase_result.phase.value}: {phase_result.duration_seconds:.2f}s")
        if phase_result.error:
            print(f"     错误: {phase_result.error}")
    
    # 检查市场报告
    if result.context:
        market_report = result.context.reports.get("market_report", "")
        if market_report:
            print(f"\n{'=' * 60}")
            print("市场分析报告")
            print("=" * 60)
            # 只显示前 1000 字符
            if len(market_report) > 1000:
                print(market_report[:1000])
                print(f"\n... (共 {len(market_report)} 字符，已截断)")
            else:
                print(market_report)
        else:
            print("\n⚠️ 未生成市场报告")
    
    return result.success


if __name__ == "__main__":
    try:
        success = test_market_analyst()
        print("\n" + "=" * 60)
        if success:
            print("✅ 测试完成！")
        else:
            print("❌ 测试失败！")
        print("=" * 60)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

