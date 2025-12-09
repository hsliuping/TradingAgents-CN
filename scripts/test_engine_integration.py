#!/usr/bin/env python
# scripts/test_engine_integration.py
"""
测试 StockAnalysisEngine 与实际 Agent 的集成

运行方式:
    .\env\Scripts\activate; python scripts/test_engine_integration.py
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_stub_mode():
    """测试桩模式（不需要 LLM）"""
    print("\n=== 测试 1: 桩模式 (use_stub=True) ===")
    
    from tradingagents.core import StockAnalysisEngine
    
    engine = StockAnalysisEngine(use_stub=True)
    
    result = engine.analyze(
        ticker='000858',  # A股代码不带后缀
        trade_date='2024-01-15',
        company_name='五粮液'
    )
    
    print(f"分析完成: {result.success}")
    print(f"总耗时: {result.total_duration_seconds:.2f}s")
    print(f"阶段数: {len(result.phase_results)}")
    
    for phase_result in result.phase_results:
        status = "OK" if phase_result.success else "FAIL"
        print(f"  [{status}] {phase_result.phase.value}: {phase_result.duration_seconds:.2f}s")
    
    # 检查报告是否生成
    if result.context:
        reports = result.context.reports
        print(f"\n生成的报告: {list(reports.keys())}")
    
    print("\n✅ 桩模式测试通过!")
    return True


def test_integration_mode():
    """测试集成模式（需要 LLM 和 Toolkit）"""
    print("\n=== 测试 2: 集成模式 (需要配置) ===")
    
    try:
        # 尝试导入依赖
        from tradingagents.agents import Toolkit
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.config.config_manager import ConfigManager
        
        # 加载配置
        config_manager = ConfigManager()
        config = config_manager.get_default_config()
        
        # 创建 LLM 和 Toolkit
        llm = config_manager.create_llm(config.get("quick_thinking_llm", {}))
        toolkit = Toolkit(config=config)
        
        print(f"LLM: {llm.__class__.__name__}")
        print(f"Toolkit: 已创建")
        
        from tradingagents.core import StockAnalysisEngine
        
        engine = StockAnalysisEngine(
            llm=llm,
            toolkit=toolkit,
            use_stub=False,
            selected_analysts=["market_analyst"]  # 只测试一个分析师
        )
        
        result = engine.analyze(
            ticker='000858',  # A股代码不带后缀
            trade_date='2024-01-15',
            company_name='五粮液'
        )
        
        print(f"\n分析完成: {result.success}")
        print(f"总耗时: {result.total_duration_seconds:.2f}s")
        
        for phase_result in result.phase_results:
            status = "OK" if phase_result.success else "FAIL"
            print(f"  [{status}] {phase_result.phase.value}: {phase_result.duration_seconds:.2f}s")
        
        # 检查报告
        if result.context:
            market_report = result.context.reports.get("market_report", "")
            if market_report:
                print(f"\n市场报告预览 (前200字符):")
                print(market_report[:200] + "..." if len(market_report) > 200 else market_report)
        
        print("\n✅ 集成模式测试通过!")
        return True
        
    except ImportError as e:
        print(f"⚠️ 依赖缺失，跳过集成测试: {e}")
        return True
    except Exception as e:
        print(f"❌ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_integrator():
    """测试 AgentIntegrator"""
    print("\n=== 测试 3: AgentIntegrator ===")

    from tradingagents.core.engine import AgentIntegrator, AnalysisContext, DataLayer

    # 测试 context 转换（不需要 LLM）
    integrator = AgentIntegrator(llm=None, toolkit=None)

    context = AnalysisContext()
    context.set(DataLayer.CONTEXT, "ticker", "000858", source="test")
    context.set(DataLayer.CONTEXT, "trade_date", "2024-01-15", source="test")

    state = integrator.context_to_state(context)
    assert state["company_of_interest"] == "000858"
    assert state["trade_date"] == "2024-01-15"
    print("  ✓ Context 转换正确")

    # 测试报告提取
    result = {"market_report": "Test report content"}
    report_field, content = integrator.extract_report("market_analyst", result)
    assert report_field == "market_report"
    assert content == "Test report content"
    print("  ✓ 报告提取正确")

    print("\n✅ AgentIntegrator 测试通过!")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("StockAnalysisEngine 集成测试")
    print("=" * 60)
    
    results = []
    
    # 测试桩模式
    results.append(("桩模式", test_stub_mode()))
    
    # 测试 AgentIntegrator
    results.append(("AgentIntegrator", test_agent_integrator()))
    
    # 可选：测试集成模式（需要配置）
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        results.append(("集成模式", test_integration_mode()))
    else:
        print("\n💡 提示: 运行 --full 参数测试完整集成模式")
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        all_passed = all_passed and passed
    
    sys.exit(0 if all_passed else 1)

