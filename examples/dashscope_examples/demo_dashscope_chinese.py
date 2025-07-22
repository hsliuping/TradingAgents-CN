#!/usr/bin/env python3
"""
TradingAgents 中文演示脚本 - 使用阿里百炼大模型
专门针对中文用户优化的股票分析演示
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

from dotenv import load_dotenv
from tradingagents.llm_adapters import ChatDashScope
from langchain_core.messages import HumanMessage, SystemMessage

# 加载 .env 文件
load_dotenv()

def analyze_stock_with_chinese_output(stock_symbol="AAPL", analysis_date="2024-05-10"):
    """使用阿里百炼进行中文股票分析"""
    
    logger.info(f"🚀 TradingAgents 中文股票分析 - 阿里百炼版本")
    logger.info(f"=")
    
    # 检查API密钥
    dashscope_key = os.getenv('DASHSCOPE_API_KEY')
    finnhub_key = os.getenv('FINNHUB_API_KEY')
    
    if not dashscope_key:
        logger.error(f"❌ Error: DASHSCOPE_API_KEY environment variable not found")
        return
    
    if not finnhub_key:
        logger.error(f"❌ Error: FINNHUB_API_KEY environment variable not found")
        return
    
    logger.info(f"✅ DASHSCOPE API key: {dashscope_key[:10]}...")
    logger.info(f"✅ FinnHub API key: {finnhub_key[:10]}...")
    print()
    
    try:
        logger.info(f"🤖 Initializing DASHSCOPE large model...")
        
        # 创建阿里百炼模型实例
        llm = ChatDashScope(
            model="qwen-plus-latest",
            temperature=0.1,
            max_tokens=3000
        )
        
        logger.info(f"✅ Model initialized successfully!")
        print()
        
        logger.info(f"📈 Starting stock analysis: {stock_symbol}")
        logger.info(f"📅 Analysis date: {analysis_date}")
        logger.info(f"⏳ Performing intelligent analysis, please wait...")
        print()
        
        # 构建中文分析提示
        system_prompt = """You are a professional stock analyst with extensive financial market experience. Please analyze in Chinese, ensuring professional, objective, and easy-to-understand content.

Your task is to conduct a comprehensive analysis of the specified stock, including:
1. Technical analysis
2. Fundamental analysis  
3. Market sentiment analysis
4. Risk assessment
5. Investment advice

Please ensure the analysis results:
- Expressed in Chinese
- Content professional and accurate
- Structured clearly
- Include specific data and indicators
- Provide clear investment advice"""

        user_prompt = f"""Please conduct a comprehensive stock analysis for Apple (AAPL).

Analysis requirements:
1. **Technical analysis**:
   - Price trend analysis
   - Key technical indicators (MA, MACD, RSI, Bollinger Bands, etc.)
   - Support and resistance levels
   - Volume analysis

2. **Fundamental analysis**:
   - Company financial status
   - Revenue and profit trends
   - Market position and competitive advantage
   - Future growth prospects

3. **Market sentiment analysis**:
   - Investor sentiment
   - Analyst ratings
   - Institutional holdings
   - Market hot topics

4. **Risk assessment**:
   - Major risk factors
   - Macro-economic impact
   - Industry competition risk
   - Regulatory risk

5. **Investment advice**:
   - Clear buy/hold/sell recommendations
   - Target price
   - Investment time frame
   - Risk control advice

Please write a detailed analysis report in Chinese, ensuring professional and easy-to-understand content."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        # 生成分析报告
        response = llm.invoke(messages)
        
        logger.info(f"🎯 Chinese analysis report:")
        logger.info(f"=")
        print(response.content)
        logger.info(f"=")
        
        print()
        logger.info(f"✅ Analysis completed!")
        print()
        logger.info(f"🌟 DASHSCOPE large model advantages:")
        logger.info(f"  - Strong Chinese understanding and expression ability")
        logger.info(f"  - Rich financial professional knowledge")
        logger.info(f"  - Clear and rigorous analysis logic")
        logger.info(f"  - Suitable for Chinese investor habits")
        
        return response.content
        
    except Exception as e:
        logger.error(f"❌ Error during analysis: {str(e)}")
        import traceback

        logger.error(f"🔍 Detailed error information:")
        traceback.print_exc()
        return None

def compare_models_chinese():
    """比较不同通义千问模型的中文表达能力"""
    logger.info(f"\n🔄 Comparing Chinese analysis capabilities of different Tongyi Qianwen models")
    logger.info(f"=")
    
    models = [
        ("qwen-turbo", "Tongyi Qianwen Turbo"),
        ("qwen-plus", "Tongyi Qianwen Plus"),
        ("qwen-max", "Tongyi Qianwen Max")
    ]
    
    question = "Please summarize the current investment value of Apple Inc. in a few words, including its advantages and risks."
    
    for model_id, model_name in models:
        try:
            logger.info(f"\n🧠 {model_name} analysis:")
            logger.info(f"-")
            
            llm = ChatDashScope(model=model_id, temperature=0.1, max_tokens=500)
            response = llm.invoke([HumanMessage(content=question)])
            
            print(response.content)
            
        except Exception as e:
            logger.error(f"❌ {model_name} analysis failed: {str(e)}")

def main():
    """主函数"""
    # 进行完整的股票分析
    result = analyze_stock_with_chinese_output("AAPL", "2024-05-10")
    
    # 比较不同模型
    compare_models_chinese()
    
    logger.info(f"\n💡 Suggestions:")
    logger.info(f"  1. Tongyi Qianwen Plus is suitable for daily analysis, balancing performance and cost")
    logger.info(f"  2. Tongyi Qianwen Max is suitable for deep analysis, highest quality")
    logger.info(f"  3. Tongyi Qianwen Turbo is suitable for quick queries, fastest response")
    logger.info(f"  4. All models are optimized for Chinese")

if __name__ == "__main__":
    main()
