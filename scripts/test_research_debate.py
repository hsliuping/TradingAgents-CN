#!/usr/bin/env python
"""测试 ResearchDebatePhase 集成"""

import sys
sys.path.insert(0, '.')

from tradingagents.core.engine.stock_analysis_engine import StockAnalysisEngine
from tradingagents.core.engine.data_contract import DataLayer
from core.workflow.builder import LegacyDependencyProvider

def main():
    print("=" * 60)
    print("测试 ResearchDebatePhase 集成")
    print("=" * 60)

    # 创建依赖
    print("\n[1/3] 创建 LLM 和 Toolkit...")
    provider = LegacyDependencyProvider.get_instance()
    llm = provider.get_llm("quick")
    toolkit = provider.get_toolkit()
    print(f"  ✓ LLM: {type(llm).__name__}")
    print(f"  ✓ Toolkit: 已创建")
    
    # 创建引擎（启用 Memory 支持）
    print("\n[2/3] 创建 StockAnalysisEngine (启用 Memory)...")
    engine = StockAnalysisEngine(
        llm=llm,
        toolkit=toolkit,
        selected_analysts=['market_analyst'],  # 只运行市场分析师，加快测试
        memory_enabled=True  # 启用 Memory 功能
    )
    print("  ✓ 引擎创建完成")
    print("  ✓ Memory 功能已启用")
    
    # 分析
    print("\n[3/3] 执行分析...")
    print("  股票: 000858 (五粮液)")
    print("  日期: 2024-01-15")
    print("  分析师: market_analyst")
    print("\n  开始分析（预计需要 2-3 分钟）...")
    
    result = engine.analyze(
        ticker='000858',
        trade_date='2024-01-15',
        company_name='五粮液'
    )
    
    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)
    
    status = "✅ 成功" if result.success else "❌ 失败"
    print(f"状态: {status}")
    print(f"总耗时: {result.total_duration_seconds:.2f}s")
    
    print("\n阶段执行情况:")
    for pr in result.phase_results:
        status_icon = '✅' if pr.success else '❌'
        print(f"  {status_icon} {pr.phase.value}: {pr.duration_seconds:.2f}s")
        if pr.error:
            print(f"     错误: {pr.error}")
    
    # 检查投资建议
    if result.context:
        investment_plan = result.context.get(DataLayer.DECISIONS, 'investment_plan')
        if investment_plan:
            plan_str = str(investment_plan)
            print(f"\n📝 投资建议长度: {len(plan_str)} 字符")
            print("\n" + "=" * 60)
            print("投资建议预览 (前500字符)")
            print("=" * 60)
            print(plan_str[:500] + "..." if len(plan_str) > 500 else plan_str)
        else:
            print("\n⚠️ 未生成投资建议")

        # 检查辩论状态
        debate_state = result.context.get(DataLayer.DECISIONS, 'investment_debate_state')
        if debate_state:
            print("\n" + "=" * 60)
            print("辩论状态")
            print("=" * 60)
            print(f"  辩论轮数: {debate_state.get('count', 0)}")
            bull_len = len(debate_state.get('bull_history', ''))
            bear_len = len(debate_state.get('bear_history', ''))
            print(f"  多头历史长度: {bull_len} 字符")
            print(f"  空头历史长度: {bear_len} 字符")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()

