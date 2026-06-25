# -*- coding: utf-8 -*-
import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from core.agents.universal import UniversalAgent
from core.agents.config import AgentConfig
from core.llm import get_llm

async def test_valuation_v7():
    print("=== 测试 A股估值分析师 v7 ===")
    print("标的: 贵州茅台 (600519)")
    print()
    
    # 创建LLM
    llm = get_llm()
    print(f"LLM 已初始化: {llm.__class__.__name__}")
    
    # 创建配置
    config = AgentConfig(
        temperature=0.2,
        online_tools=True,
        debug=False,
        timeout=120
    )
    
    # 创建Agent
    agent = UniversalAgent(
        config=config,
        llm=llm,
        agent_id='valuation_analyst_v7',
        agent_name='A股估值分析师 v7',
        agent_description='对A股个股进行纯估值分析',
        output_field='valuation_report'
    )
    
    # 构建state
    state = {
        'symbol': '600519',
        'task_description': '对贵州茅台（600519）进行估值分析，综合PE/PB/PEG/PS/股息率等相对估值指标，结合行业对比，输出估值判断（低估/合理/高估）及关键依据',
        'context': {
            'symbol': '600519',
            'market_type': 'A股',
            'analysis_date': '2026-04-03'
        }
    }
    
    print("开始执行分析...")
    result = agent.execute(state)
    
    print()
    print("=== 分析结果 ===")
    if isinstance(result, dict):
        valuation_report = result.get('valuation_report', '')
        tool_trace = result.get('tool_trace', [])
        
        print(f"工具调用次数: {len(tool_trace)}")
        for i, trace in enumerate(tool_trace):
            print(f"  [{i+1}] {trace.get('tool_name', 'unknown')}: {trace.get('status', 'unknown')}")
        
        print()
        print("=== 估值报告 ===")
        if valuation_report:
            print(valuation_report[:3000] if len(valuation_report) > 3000 else valuation_report)
        else:
            print("未生成估值报告")
        
        # 保存完整结果
        with open('v7_test_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print()
        print("完整结果已保存到: v7_test_result.json")
    else:
        print(result)

if __name__ == '__main__':
    asyncio.run(test_valuation_v7())