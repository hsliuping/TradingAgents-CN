#!/usr/bin/env python3
"""
TradingAgents 演示脚本 - 使用 OpenAI 模型
这个脚本展示了如何使用 OpenAI 模型运行 TradingAgents 框架
"""

import os
import sys
from pathlib import Path

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('default')

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG


def main():
    """主函数"""
    logger.info(f"🚀 TradingAgents 演示 - OpenAI 版本")
    logger.info(f"=")
    
    # 检查API密钥
    openai_key = os.getenv('OPENAI_API_KEY')
    finnhub_key = os.getenv('FINNHUB_API_KEY')
    
    if not openai_key:
        logger.error(f"❌ 错误: 未找到 OPENAI_API_KEY 环境变量")
        logger.info(f"请设置您的 OpenAI API 密钥:")
        logger.info(f"  Windows: set OPENAI_API_KEY=your_api_key")
        logger.info(f"  Linux/Mac: export OPENAI_API_KEY=your_api_key")
        logger.info(f"  或创建 .env 文件")
        return
    
    if not finnhub_key:
        logger.error(f"❌ 错误: 未找到 FINNHUB_API_KEY 环境变量")
        logger.info(f"请设置您的 FinnHub API 密钥:")
        logger.info(f"  Windows: set FINNHUB_API_KEY=your_api_key")
        logger.info(f"  Linux/Mac: export FINNHUB_API_KEY=your_api_key")
        logger.info(f"  或创建 .env 文件")
        return
    
    logger.info(f"✅ OpenAI API 密钥: {openai_key[:10]}...")
    logger.info(f"✅ FinnHub API 密钥: {finnhub_key[:10]}...")
    print()
    
    # 创建 OpenAI 配置
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "openai"
    config["backend_url"] = "https://api.openai.com/v1"
    config["deep_think_llm"] = "gpt-4o-mini"  # 使用更经济的模型
    config["quick_think_llm"] = "gpt-4o-mini"
    config["max_debate_rounds"] = 1  # 减少辩论轮次以降低成本
    config["online_tools"] = True
    
    logger.info(f"📊 配置信息:")
    logger.info(f"  LLM 提供商: {config['llm_provider']}")
    logger.info(f"  深度思考模型: {config['deep_think_llm']}")
    logger.info(f"  快速思考模型: {config['quick_think_llm']}")
    logger.info(f"  最大辩论轮次: {config['max_debate_rounds']}")
    logger.info(f"  在线工具: {config['online_tools']}")
    print()
    
    try:
        logger.info(f"🤖 正在初始化 TradingAgents...")
        ta = TradingAgentsGraph(debug=True, config=config)
        logger.info(f"✅ TradingAgents 初始化成功!")
        print()
        
        # 分析股票
        stock_symbol = "AAPL"  # 苹果公司
        analysis_date = "2024-05-10"
        
        logger.info(f"📈 开始分析股票: {stock_symbol}")
        logger.info(f"📅 分析日期: {analysis_date}")
        logger.info(f"⏳ 正在进行多智能体分析，请稍候...")
        print()
        
        # 执行分析
        state, decision = ta.propagate(stock_symbol, analysis_date)
        
        logger.info(f"🎯 分析结果:")
        logger.info(f"=")
        print(decision)
        print()
        
        logger.info(f"✅ 分析完成!")
        logger.info(f"💡 提示: 您可以修改 stock_symbol 和 analysis_date 来分析其他股票")
        
    except Exception as e:
        logger.error(f"❌ 运行时错误: {str(e)}")
        print()
        logger.info(f"🔧 可能的解决方案:")
        logger.info(f"1. 检查API密钥是否正确")
        logger.info(f"2. 检查网络连接")
        logger.info(f"3. 确认API账户有足够的额度")
        logger.error(f"4. 查看详细错误信息进行调试")

if __name__ == "__main__":
    main()
