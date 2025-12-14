#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
机器人指数（300024）分析测试脚本

测试目标：
1. 验证自动识别300024为指数
2. 验证指数分析workflow正常执行
3. 将分析结果保存到文件
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置环境变量
os.environ['PYTHONPATH'] = str(project_root)

from app.utils.market_detector import MarketSymbolDetector
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.utils.logging_init import init_logging, get_logger

# 初始化日志
init_logging()
logger = get_logger(__name__)

def test_market_detection():
    """测试1: 市场检测"""
    print("\n" + "="*80)
    print("测试1: 自动检测300024代码")
    print("="*80)
    
    symbol = "300024"
    market_type, analysis_type = MarketSymbolDetector.detect(symbol)
    
    print(f"✅ 代码: {symbol}")
    print(f"✅ 检测到的市场: {market_type}")
    print(f"✅ 检测到的类型: {analysis_type}")
    
    assert market_type == "A股", f"市场类型错误: 期望'A股', 实际'{market_type}'"
    assert analysis_type == "index", f"分析类型错误: 期望'index', 实际'{analysis_type}'"
    
    print("✅ 市场检测测试通过！")
    return market_type, analysis_type

def create_index_config(analysis_type="index"):
    """创建指数分析配置"""
    config = {
        "research_depth": "标准",
        "selected_analysts": [],  # 指数分析不使用个股分析师
        "quick_think_llm": "deepseek-chat",  # 使用DeepSeek快速模型
        "deep_think_llm": "deepseek-reasoner",  # 使用DeepSeek推理模型
        "llm_provider": "deepseek",  # 改为deepseek
        "market_type": "A股",
        "debug": True,
        "enable_memory": True,
        "enable_online_tools": True,
        "analysis_type": analysis_type,
        "project_dir": str(project_root),  # 添加项目根目录
        "cache_dir": str(project_root / "tradingagents" / "dataflows" / "cache" / "data_cache")
    }
    return config

def test_index_analysis():
    """测试2: 指数分析执行"""
    print("\n" + "="*80)
    print("测试2: 执行机器人指数分析")
    print("="*80)
    
    # 创建配置
    config = create_index_config(analysis_type="index")
    
    print(f"✅ 分析配置:")
    print(f"   - 类型: {config['analysis_type']}")
    print(f"   - 市场: {config['market_type']}")
    print(f"   - 分析师: {config['selected_analysts']}")
    print(f"   - 快速模型: {config['quick_think_llm']}")
    print(f"   - 深度模型: {config['deep_think_llm']}")
    
    # 创建分析图
    print("\n🔧 创建TradingAgentsGraph实例...")
    trading_graph = TradingAgentsGraph(
        selected_analysts=config["selected_analysts"],
        debug=config["debug"],
        config=config,
        analysis_type=config["analysis_type"]
    )
    
    print("✅ TradingAgentsGraph创建成功")
    
    # 准备初始状态
    initial_state = AgentState(
        symbol="300024",
        stock_name="机器人指数",
        market_type="A股",
        analysis_date=datetime.now().strftime("%Y-%m-%d"),
        messages=[],
        current_analyst=None,
        analyst_sequence=[],
        completed_analysts=[],
        next_analyst=None,
        research_depth="标准",
        custom_prompt=None,
        enable_sentiment=True,
        enable_risk=True,
        language="zh-CN"
    )
    
    print(f"\n✅ 初始状态:")
    print(f"   - 代码: {initial_state['symbol']}")
    print(f"   - 名称: {initial_state['stock_name']}")
    print(f"   - 市场: {initial_state['market_type']}")
    print(f"   - 日期: {initial_state['analysis_date']}")
    
    # 执行分析
    print("\n🚀 开始执行分析...")
    print("="*80)
    
    try:
        # 增加递归限制以避免GraphRecursionError
        result = trading_graph.graph.invoke(initial_state, config={"recursion_limit": 50})
        print("\n✅ 分析执行完成！")
        return result
        
    except Exception as e:
        print(f"\n❌ 分析执行失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_result_to_file(result, output_dir="./test_results"):
    """保存分析结果到文件"""
    print("\n" + "="*80)
    print("保存分析结果")
    print("="*80)
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. 保存完整结果（JSON格式）
    json_file = os.path.join(output_dir, f"robot_index_300024_result_{timestamp}.json")
    
    # 转换为可序列化的格式
    serializable_result = {}
    for key, value in result.items():
        try:
            json.dumps(value)  # 测试是否可序列化
            serializable_result[key] = value
        except (TypeError, ValueError):
            serializable_result[key] = str(value)
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(serializable_result, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 完整结果已保存: {json_file}")
    
    # 2. 保存可读报告（TXT格式）
    txt_file = os.path.join(output_dir, f"robot_index_300024_report_{timestamp}.txt")
    
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("机器人指数（300024）分析报告\n")
        f.write("="*80 + "\n\n")
        
        f.write(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"代码: {result.get('symbol', 'N/A')}\n")
        f.write(f"名称: {result.get('stock_name', 'N/A')}\n")
        f.write(f"市场: {result.get('market_type', 'N/A')}\n")
        f.write(f"分析日期: {result.get('analysis_date', 'N/A')}\n\n")
        
        f.write("="*80 + "\n")
        f.write("已完成的分析师\n")
        f.write("="*80 + "\n\n")
        
        completed = result.get('completed_analysts', [])
        for i, analyst in enumerate(completed, 1):
            f.write(f"{i}. {analyst}\n")
        
        f.write("\n" + "="*80 + "\n")
        f.write("分析消息\n")
        f.write("="*80 + "\n\n")
        
        messages = result.get('messages', [])
        for msg in messages:
            if hasattr(msg, 'content'):
                f.write(f"{msg.content}\n")
                f.write("-"*80 + "\n")
        
        # 如果有最终报告
        if 'final_report' in result:
            f.write("\n" + "="*80 + "\n")
            f.write("最终报告\n")
            f.write("="*80 + "\n\n")
            f.write(str(result['final_report']))
            f.write("\n")
    
    print(f"✅ 可读报告已保存: {txt_file}")
    
    # 3. 打印摘要
    print("\n" + "="*80)
    print("分析结果摘要")
    print("="*80)
    print(f"代码: {result.get('symbol', 'N/A')}")
    print(f"名称: {result.get('stock_name', 'N/A')}")
    print(f"完成的分析师数量: {len(result.get('completed_analysts', []))}")
    print(f"生成的消息数量: {len(result.get('messages', []))}")
    
    return json_file, txt_file

def main():
    """主测试流程"""
    print("\n" + "="*80)
    print("🤖 机器人指数（300024）分析测试")
    print("="*80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 测试1: 市场检测
        market_type, analysis_type = test_market_detection()
        
        # 测试2: 执行分析
        result = test_index_analysis()
        
        if result is None:
            print("\n❌ 分析失败，无法保存结果")
            return 1
        
        # 保存结果
        json_file, txt_file = save_result_to_file(result)
        
        print("\n" + "="*80)
        print("✅ 所有测试完成！")
        print("="*80)
        print(f"\n📁 结果文件:")
        print(f"   - JSON: {json_file}")
        print(f"   - TXT:  {txt_file}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
