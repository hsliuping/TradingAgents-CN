#!/usr/bin/env python3
"""
沪深300指数分析Mock测试脚本
使用预设的mock数据,跳过LLM调用,快速验证工作流逻辑
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置环境变量
os.environ["TUSHARE_TOKEN"] = "2876ea85cb005fb5fa17c809a98174f2d5aae8b1f830110a5ead6211"

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s'
)
logger = logging.getLogger(__name__)


# Mock LLM响应数据
MOCK_RESPONSES = {
    "macro_report": """```json
{
  "economic_cycle": "扩张",
  "liquidity": "宽松",
  "key_indicators": ["GDP增速5.0%", "CPI同比2.3%", "PMI=51.2"],
  "analysis_summary": "当前宏观经济处于温和扩张阶段,流动性环境相对宽松,有利于权益市场表现",
  "confidence": 0.75,
  "sentiment_score": 0.6
}```""",
    
    "policy_report": """```json
{
  "policy_stance": "积极",
  "industry_policy": ["半导体", "新能源", "人工智能"],
  "key_events": ["科技创新支持政策出台", "新能源补贴延续"],
  "analysis_summary": "政策面整体积极,重点支持科技创新和新兴产业,对成长股形成利好",
  "confidence": 0.8,
  "sentiment_score": 0.7
}```""",
    
    "sector_report": """```json
{
  "top_sectors": ["半导体", "新能源车", "人工智能"],
  "bottom_sectors": ["房地产", "煤炭", "钢铁"],
  "rotation_trend": "价值→成长",
  "hot_themes": ["AI应用", "芯片自主可控", "新能源"],
  "analysis_summary": "资金持续流入科技成长板块,传统周期板块资金流出明显,市场呈现明显的成长风格",
  "confidence": 0.85,
  "sentiment_score": 0.75
}```""",
    
    "strategy_report": """```json
{
  "market_outlook": "谨慎乐观",
  "recommended_position": 0.65,
  "key_risks": ["外部地缘政治风险", "流动性收紧预期"],
  "opportunity_sectors": ["半导体", "新能源", "人工智能"],
  "rationale": "综合宏观、政策和板块分析,当前市场处于结构性行情,建议适度增配科技成长板块,控制整体仓位在65%左右",
  "final_sentiment_score": 0.68,
  "confidence": 0.78
}```"""
}


def create_mock_llm():
    """创建Mock LLM,返回预设的响应"""
    
    call_count = {'macro': 0, 'policy': 0, 'sector': 0, 'strategy': 0}
    
    def mock_invoke(messages, *args, **kwargs):
        """Mock invoke方法"""
        # 从消息中判断是哪个分析师
        content = str(messages)
        
        response = MagicMock()
        response.tool_calls = []  # 默认无工具调用
        
        if '宏观' in content or 'macro' in content.lower():
            call_count['macro'] += 1
            if call_count['macro'] == 1:
                # 第一次调用:返回工具调用请求
                response.tool_calls = [MagicMock(
                    name="fetch_macro_data",
                    args={"query_date": "2025-12-14"}
                )]
                response.content = "我将获取宏观数据"
            else:
                # 第二次调用:返回分析结果
                response.content = MOCK_RESPONSES['macro_report']
                
        elif '政策' in content or 'policy' in content.lower():
            call_count['policy'] += 1
            if call_count['policy'] == 1:
                response.tool_calls = [MagicMock(
                    name="fetch_policy_news",
                    args={"lookback_days": 7}
                )]
                response.content = "我将获取政策新闻"
            else:
                response.content = MOCK_RESPONSES['policy_report']
                
        elif '板块' in content or 'sector' in content.lower():
            call_count['sector'] += 1
            if call_count['sector'] == 1:
                response.tool_calls = [MagicMock(
                    name="fetch_sector_rotation",
                    args={"trade_date": "2024-12-27"}
                )]
                response.content = "我将获取板块数据"
            else:
                response.content = MOCK_RESPONSES['sector_report']
                
        elif '策略' in content or 'strategy' in content.lower():
            response.content = MOCK_RESPONSES['strategy_report']
        else:
            response.content = "Mock response"
            
        return response
    
    mock_llm = MagicMock()
    mock_llm.invoke = mock_invoke
    mock_llm.model_name = "mock-model"
    
    return mock_llm


def test_index_analysis_mock():
    """使用Mock数据测试指数分析流程"""
    
    print("\n" + "="*80)
    print("🎯 沪深300指数分析 Mock 测试")
    print("="*80 + "\n")
    
    try:
        # 1. 创建指数分析图
        logger.info("📊 步骤1: 创建指数分析图实例(Mock模式)...")
        config = DEFAULT_CONFIG.copy()
        
        graph = TradingAgentsGraph(
            selected_analysts=[],
            debug=True,
            config=config,
            analysis_type="index"
        )
        
        # 替换LLM为Mock对象
        mock_llm = create_mock_llm()
        graph.quick_thinking_llm = mock_llm
        graph.deep_thinking_llm = mock_llm
        
        # 重新设置graph(使用mock llm)
        graph.graph_setup.quick_thinking_llm = mock_llm
        graph.graph_setup.deep_thinking_llm = mock_llm
        graph.graph = graph.graph_setup.setup_graph(analysis_type="index")
        
        logger.info("✅ Mock LLM已配置\n")
        
        # 2. 执行分析
        index_code = "sh000300"
        trade_date = datetime.now().strftime("%Y-%m-%d")
        
        logger.info(f"📋 步骤2: 执行Mock分析...")
        logger.info(f"   - 指数代码: {index_code}")
        logger.info(f"   - 分析日期: {trade_date}")
        logger.info(f"   - 模式: Mock (不调用真实LLM)\n")
        
        start_time = datetime.now()
        
        final_state, decision = graph.propagate(
            company_name=index_code,
            trade_date=trade_date
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"\n✅ Mock分析完成! 耗时: {duration:.2f}秒\n")
        
        # 3. 验证结果
        print("\n" + "="*80)
        print("📊 Mock测试验证")
        print("="*80 + "\n")
        
        checks = {
            "is_index标志": final_state.get("is_index") == True,
            "宏观报告存在": bool(final_state.get("macro_report")),
            "政策报告存在": bool(final_state.get("policy_report")),
            "板块报告存在": bool(final_state.get("sector_report")),
            "策略报告存在": bool(final_state.get("strategy_report")),
            "决策类型正确": decision.get("analysis_type") == "index",
            "无final_trade_decision": "final_trade_decision" not in final_state,
        }
        
        all_passed = True
        for check_name, check_result in checks.items():
            status = "✅ 通过" if check_result else "❌ 失败"
            print(f"{status} - {check_name}")
            if not check_result:
                all_passed = False
        
        # 4. 显示报告摘要
        if all_passed:
            print("\n" + "="*80)
            print("📝 报告摘要预览")
            print("="*80 + "\n")
            
            for report_name, report_key in [
                ("宏观分析", "macro_report"),
                ("政策分析", "policy_report"),
                ("板块分析", "sector_report"),
                ("策略建议", "strategy_report")
            ]:
                content = final_state.get(report_key, "")
                if content:
                    preview = content[:200] if len(content) > 200 else content
                    print(f"\n📌 {report_name}:")
                    print(f"{preview}...")
        
        print(f"\n{'='*80}")
        if all_passed:
            print("✅ 所有测试通过!")
        else:
            print("❌ 部分测试失败,请检查!")
        print(f"{'='*80}\n")
        
        return all_passed
        
    except Exception as e:
        logger.error(f"❌ Mock测试失败: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════════╗
║              沪深300指数分析 Mock 测试                              ║
║                                                                    ║
║  模式: Mock模式 (不调用真实LLM,使用预设数据)                       ║
║  目的: 快速验证工作流逻辑,节省Token消耗                            ║
║  预计耗时: < 10秒                                                  ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    
    result = test_index_analysis_mock()
    sys.exit(0 if result else 1)
