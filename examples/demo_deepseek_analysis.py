#!/usr/bin/env python3
"""
DeepSeek V3股票分析演示
展示如何使用DeepSeek V3进行股票投资分析
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# 导入日志模块
import logging
logger = logging.getLogger(__name__)

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv(project_root / ".env", override=True)

def check_deepseek_config():
    """检查DeepSeek配置"""
    logger.debug(f"🔍 检查DeepSeek V3配置...")
    
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    
    if not api_key:
        logger.error(f"❌ 错误：未找到DeepSeek API密钥")
        logger.info(f"\n📝 配置步骤:")
        logger.info(f"1. 访问 https://platform.deepseek.com/")
        logger.info(f"2. 注册DeepSeek账号并登录")
        logger.info(f"3. 进入API Keys页面")
        logger.info(f"4. 创建新的API Key")
        logger.info(f"5. 在.env文件中设置:")
        logger.info(f"   DEEPSEEK_API_KEY=your_api_key")
        logger.info(f"   DEEPSEEK_ENABLED=true")
        return False
    
    logger.info(f"✅ API Key: {api_key[:12]}...")
    logger.info(f"✅ Base URL: {base_url}")
    return True

def demo_simple_chat():
    """演示简单对话功能"""
    logger.info(f"\n🤖 演示DeepSeek V3简单对话...")
    
    try:
        from tradingagents.llm_adapters.deepseek_direct_adapter import create_deepseek_direct_adapter
        
        # 创建DeepSeek模型
        llm = create_deepseek_direct_adapter(
            model="deepseek-chat",
            temperature=0.1,
            max_tokens=500
        )
        
        # 测试对话
        message = """
        请简要介绍股票投资的基本概念，包括：
        1. 什么是股票
        2. 股票投资的风险
        3. 基本的投资策略
        请用中文回答，控制在200字以内。
        """
        
        logger.info(f"💭 正在生成回答...")
        response = llm.invoke(message)
        logger.info(f"🎯 DeepSeek V3回答:\n{response}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 简单对话演示失败: {e}")
        return False

def demo_reasoning_analysis():
    """演示推理分析功能"""
    logger.info(f"\n🧠 演示DeepSeek V3推理分析...")
    
    try:
        from tradingagents.llm_adapters.deepseek_direct_adapter import create_deepseek_direct_adapter
        
        # 创建DeepSeek适配器
        adapter = create_deepseek_direct_adapter(
            model="deepseek-chat",
            temperature=0.1,
            max_tokens=1000
        )
        
        # 复杂推理任务
        complex_query = """
        假设你是一个专业的股票分析师，请分析以下情况：
        
        公司A：
        - 市盈率：15倍
        - 营收增长率：20%
        - 负债率：30%
        - 行业：科技
        
        公司B：
        - 市盈率：25倍
        - 营收增长率：10%
        - 负债率：50%
        - 行业：传统制造
        
        请从投资价值角度分析这两家公司，并给出投资建议。
        """
        
        logger.info(f"💭 正在进行深度分析...")
        response = adapter.invoke(complex_query)
        logger.info(f"🎯 DeepSeek V3分析:\n{response}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 推理分析演示失败: {e}")
        return False

def demo_stock_analysis_with_tools():
    """演示带工具的股票分析"""
    logger.info(f"\n📊 演示DeepSeek V3工具调用股票分析...")
    
    try:
        from tradingagents.llm_adapters.deepseek_direct_adapter import create_deepseek_direct_adapter
        # 移除langchain工具导入以避免兼容性问题
        
        # 定义股票分析工具（简化版本，不使用langchain装饰器）
        def get_stock_info(symbol: str) -> str:
            """获取股票基本信息"""
            stock_data = {
                "AAPL": "苹果公司 - 科技股，主营iPhone、Mac等产品，市值约3万亿美元，P/E: 28.5",
                "TSLA": "特斯拉 - 电动汽车制造商，由马斯克领导，专注新能源汽车，P/E: 65.2",
                "MSFT": "微软 - 软件巨头，主营Windows、Office、Azure云服务，P/E: 32.1",
                "000001": "平安银行 - 中国股份制银行，总部深圳，金融服务业，P/E: 5.8",
                "600036": "招商银行 - 中国领先银行，零售银行业务突出，P/E: 6.2"
            }
            return stock_data.get(symbol, f"股票{symbol}的基本信息")
        
        def get_financial_metrics(symbol: str) -> str:
            """获取财务指标"""
            return f"股票{symbol}的财务指标：ROE 15%，毛利率 35%，净利润增长率 12%"
        
        def get_market_sentiment(symbol: str) -> str:
            """获取市场情绪"""
            return f"股票{symbol}当前市场情绪：中性偏乐观，机构持仓比例65%"
        
        # 创建DeepSeek适配器
        adapter = create_deepseek_direct_adapter(
            model="deepseek-chat",
            temperature=0.1,
            max_tokens=1000
        )
        
        # 测试股票分析
        test_queries = [
            "请全面分析苹果公司(AAPL)的投资价值，包括基本面、财务状况和市场情绪",
            "对比分析招商银行(600036)和平安银行(000001)，哪个更值得投资？"
        ]
        
        for query in test_queries:
            logger.info(f"\n❓ 用户问题: {query}")
            logger.info(f"💭 正在分析...")
            
            # 获取相关股票信息
            if "AAPL" in query:
                stock_info = get_stock_info("AAPL")
                financial_info = get_financial_metrics("AAPL")
                sentiment_info = get_market_sentiment("AAPL")
                context = f"股票信息: {stock_info}\n财务指标: {financial_info}\n市场情绪: {sentiment_info}"
            elif "600036" in query and "000001" in query:
                stock_info_1 = get_stock_info("600036")
                stock_info_2 = get_stock_info("000001")
                context = f"招商银行信息: {stock_info_1}\n平安银行信息: {stock_info_2}"
            else:
                context = "基于一般股票分析原则"
            
            # 构建分析提示
            analysis_prompt = f"""
            你是一个专业的股票分析师，请根据以下信息回答用户问题：
            
            背景信息：
            {context}
            
            用户问题：{query}
            
            请提供专业的分析建议，分析要深入、逻辑清晰，并给出具体的投资建议。
            """
            
            response = adapter.invoke(analysis_prompt)
            logger.info(f"🎯 分析结果:\n{response}")
            logger.info(f"-")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 工具调用演示失败: {e}")
        return False

def demo_trading_system():
    """演示完整的交易分析系统（简化版本）"""
    logger.info(f"\n🎯 演示DeepSeek V3完整交易分析系统...")
    
    try:
        from tradingagents.llm_adapters.deepseek_direct_adapter import create_deepseek_direct_adapter
        
        # 创建DeepSeek适配器
        adapter = create_deepseek_direct_adapter()
        
        # 模拟交易分析查询
        trading_query = "请分析苹果公司(AAPL)的投资价值，包括技术面、基本面和风险评估"
        
        logger.info(f"🏗️ 使用DeepSeek进行交易分析...")
        result = adapter.invoke(trading_query)
        
        logger.info(f"✅ DeepSeek V3交易分析完成！")
        logger.info(f"\n📊 分析结果: {result[:200]}...")
        
        logger.info(f"\n📝 系统特点:")
        logger.info(f"- 🧠 使用DeepSeek V3大模型，推理能力强")
        logger.info(f"- 🛠️ 支持工具调用和智能体协作")
        logger.info(f"- 📊 可进行多维度股票分析")
        logger.info(f"- 💰 成本极低，性价比极高")
        logger.info(f"- 🇨🇳 中文理解能力优秀")
        
        logger.info(f"\n💡 使用建议:")
        logger.info(f"1. 通过Web界面选择DeepSeek模型")
        logger.info(f"2. 输入股票代码进行分析")
        logger.info(f"3. 系统将自动调用多个智能体协作分析")
        logger.info(f"4. 享受高质量、低成本的AI分析服务")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 交易计划演示失败: {e}")
        return False

def main():
    """主演示函数"""
    logger.info(f"🎯 DeepSeek V3股票分析演示")
    logger.info(f"=")
    
    # 检查配置
    if not check_deepseek_config():
        return False
    
    # 运行演示
    demos = [
        ("简单对话", demo_simple_chat),
        ("推理分析", demo_reasoning_analysis),
        ("工具调用分析", demo_stock_analysis_with_tools),
        ("完整交易计划", demo_trading_system),
    ]
    
    success_count = 0
    for demo_name, demo_func in demos:
        logger.info(f"\n{'='*20} {demo_name} {'='*20}")
        try:
            if demo_func():
                success_count += 1
                logger.info(f"✅ {demo_name}演示成功")
            else:
                logger.error(f"❌ {demo_name}演示失败")
        except Exception as e:
            logger.error(f"❌ {demo_name}演示异常: {e}")
    
    # 总结
    logger.info(f"\n")
    logger.info(f"📋 演示总结")
    logger.info(f"=")
    logger.info(f"成功演示: {success_count}/{len(demos)}")
    
    if success_count == len(demos):
        logger.info(f"\n🎉 所有演示成功！")
        logger.info(f"\n🚀 DeepSeek V3已成功集成到TradingAgents！")
        logger.info(f"\n📝 特色功能:")
        logger.info(f"- 🧠 强大的推理和分析能力")
        logger.info(f"- 🛠️ 完整的工具调用支持")
        logger.info(f"- 🤖 多智能体协作分析")
        logger.info(f"- 💰 极高的性价比")
        logger.info(f"- 🇨🇳 优秀的中文理解能力")
        logger.info(f"- 📊 专业的金融分析能力")
        
        logger.info(f"\n🎯 下一步:")
        logger.info(f"1. 在Web界面中选择DeepSeek模型")
        logger.info(f"2. 开始您的股票投资分析之旅")
        logger.info(f"3. 体验高性价比的AI投资助手")
    else:
        logger.error(f"\n⚠️ {len(demos) - success_count} 个演示失败")
        logger.info(f"请检查API密钥配置和网络连接")
    
    return success_count == len(demos)

if __name__ == "__main__":
    success = main()
    logger.error(f"\n{'🎉 演示完成' if success else '❌ 演示失败'}")
    sys.exit(0 if success else 1)
