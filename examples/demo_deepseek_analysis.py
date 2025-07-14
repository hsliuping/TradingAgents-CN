#!/usr/bin/env python3
"""
DeepSeek V3股票分析演示
展示如何使用DeepSeek V3进行股票投资分析
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv(project_root / ".env", override=True)

def check_deepseek_config():
    """检查DeepSeek配置"""
    print("🔍 检查DeepSeek V3配置...")
    
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    
    if not api_key:
        print("❌ 错误：未找到DeepSeek API密钥")
        print("\n📝 配置步骤:")
        print("1. 访问 https://platform.deepseek.com/")
        print("2. 注册DeepSeek账号并登录")
        print("3. 进入API Keys页面")
        print("4. 创建新的API Key")
        print("5. 在.env文件中设置:")
        print("   DEEPSEEK_API_KEY=your_api_key")
        print("   DEEPSEEK_ENABLED=true")
        return False
    
    print(f"✅ API Key: {api_key[:12]}...")
    print(f"✅ Base URL: {base_url}")
    return True

def demo_simple_chat():
    """演示简单对话功能"""
    print("\n🤖 演示DeepSeek V3简单对话...")
    
    try:
        from langchain_openai import ChatOpenAI
        from langchain.schema import HumanMessage
        
        # 创建DeepSeek模型
        try:
            # 尝试新版本参数
            llm = ChatOpenAI(
                model="deepseek-chat",
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                temperature=0.1,
                max_tokens=500
            )
        except Exception:
            # 回退到旧版本参数
            llm = ChatOpenAI(
                model="deepseek-chat",
                openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
                openai_api_base=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                temperature=0.1,
                max_tokens=500
            )
        
        # 测试对话
        messages = [HumanMessage(content="""
        请简要介绍股票投资的基本概念，包括：
        1. 什么是股票
        2. 股票投资的风险
        3. 基本的投资策略
        请用中文回答，控制在200字以内。
        """)]
        
        print("💭 正在生成回答...")
        response = llm.invoke(messages)
        print(f"🎯 DeepSeek V3回答:\n{response.content}")
        
        return True
        
    except Exception as e:
        print(f"❌ 简单对话演示失败: {e}")
        return False

def demo_reasoning_analysis():
    """演示推理分析功能"""
    print("\n🧠 演示DeepSeek V3推理分析...")
    
    try:
        from tradingagents.llm.deepseek_adapter import create_deepseek_adapter
        from langchain.schema import HumanMessage
        
        # 创建DeepSeek适配器
        adapter = create_deepseek_adapter(model="deepseek-chat")
        
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
        
        messages = [HumanMessage(content=complex_query)]
        
        print("💭 正在进行深度分析...")
        response = adapter.chat(messages)
        print(f"🎯 DeepSeek V3分析:\n{response}")
        
        return True
        
    except Exception as e:
        print(f"❌ 推理分析演示失败: {e}")
        return False

def demo_stock_analysis_with_tools():
    """演示带工具的股票分析"""
    print("\n📊 演示DeepSeek V3工具调用股票分析...")
    
    try:
        from tradingagents.llm.deepseek_adapter import create_deepseek_adapter
        from langchain.tools import tool
        
        # 定义股票分析工具
        @tool
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
        
        @tool
        def get_financial_metrics(symbol: str) -> str:
            """获取财务指标"""
            return f"股票{symbol}的财务指标：ROE 15%，毛利率 35%，净利润增长率 12%"
        
        @tool
        def get_market_sentiment(symbol: str) -> str:
            """获取市场情绪"""
            return f"股票{symbol}当前市场情绪：中性偏乐观，机构持仓比例65%"
        
        # 创建DeepSeek适配器
        adapter = create_deepseek_adapter(model="deepseek-chat")
        
        # 创建智能体
        tools = [get_stock_info, get_financial_metrics, get_market_sentiment]
        system_prompt = """
        你是一个专业的股票分析师，擅长使用各种工具分析股票。
        请根据用户的问题，使用合适的工具获取信息，然后提供专业的分析建议。
        分析要深入、逻辑清晰，并给出具体的投资建议。
        回答要用中文，格式清晰。
        """
        
        agent = adapter.create_agent(tools, system_prompt, verbose=True)
        
        # 测试股票分析
        test_queries = [
            "请全面分析苹果公司(AAPL)的投资价值，包括基本面、财务状况和市场情绪",
            "对比分析招商银行(600036)和平安银行(000001)，哪个更值得投资？"
        ]
        
        for query in test_queries:
            print(f"\n❓ 用户问题: {query}")
            print("💭 正在分析...")
            
            result = agent.invoke({"input": query})
            print(f"🎯 分析结果:\n{result['output']}")
            print("-" * 50)
        
        return True
        
    except Exception as e:
        print(f"❌ 工具调用演示失败: {e}")
        return False

def demo_trading_system():
    """演示完整的交易分析系统"""
    print("\n🎯 演示DeepSeek V3完整交易分析系统...")
    
    try:
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        
        # 配置DeepSeek
        config = DEFAULT_CONFIG.copy()
        config["llm_provider"] = "deepseek"
        config["deep_think_llm"] = "deepseek-chat"
        config["quick_think_llm"] = "deepseek-chat"
        config["max_debate_rounds"] = 1  # 快速演示
        config["online_tools"] = False   # 使用缓存数据
        
        print("🏗️ 创建DeepSeek交易分析图...")
        ta = TradingAgentsGraph(debug=True, config=config)
        
        print("✅ DeepSeek V3交易分析系统初始化成功！")
        print("\n📝 系统特点:")
        print("- 🧠 使用DeepSeek V3大模型，推理能力强")
        print("- 🛠️ 支持工具调用和智能体协作")
        print("- 📊 可进行多维度股票分析")
        print("- 💰 成本极低，性价比极高")
        print("- 🇨🇳 中文理解能力优秀")
        
        print("\n💡 使用建议:")
        print("1. 通过Web界面选择DeepSeek模型")
        print("2. 输入股票代码进行分析")
        print("3. 系统将自动调用多个智能体协作分析")
        print("4. 享受高质量、低成本的AI分析服务")
        
        return True
        
    except Exception as e:
        print(f"❌ 交易系统演示失败: {e}")
        return False

def main():
    """主演示函数"""
    print("🎯 DeepSeek V3股票分析演示")
    print("=" * 50)
    
    # 检查配置
    if not check_deepseek_config():
        return False
    
    # 运行演示
    demos = [
        ("简单对话", demo_simple_chat),
        ("推理分析", demo_reasoning_analysis),
        ("工具调用分析", demo_stock_analysis_with_tools),
        ("完整交易系统", demo_trading_system),
    ]
    
    success_count = 0
    for demo_name, demo_func in demos:
        print(f"\n{'='*20} {demo_name} {'='*20}")
        try:
            if demo_func():
                success_count += 1
                print(f"✅ {demo_name}演示成功")
            else:
                print(f"❌ {demo_name}演示失败")
        except Exception as e:
            print(f"❌ {demo_name}演示异常: {e}")
    
    # 总结
    print("\n" + "="*50)
    print("📋 演示总结")
    print("="*50)
    print(f"成功演示: {success_count}/{len(demos)}")
    
    if success_count == len(demos):
        print("\n🎉 所有演示成功！")
        print("\n🚀 DeepSeek V3已成功集成到TradingAgents！")
        print("\n📝 特色功能:")
        print("- 🧠 强大的推理和分析能力")
        print("- 🛠️ 完整的工具调用支持")
        print("- 🤖 多智能体协作分析")
        print("- 💰 极高的性价比")
        print("- 🇨🇳 优秀的中文理解能力")
        print("- 📊 专业的金融分析能力")
        
        print("\n🎯 下一步:")
        print("1. 在Web界面中选择DeepSeek模型")
        print("2. 开始您的股票投资分析之旅")
        print("3. 体验高性价比的AI投资助手")
    else:
        print(f"\n⚠️ {len(demos) - success_count} 个演示失败")
        print("请检查API密钥配置和网络连接")
    
    return success_count == len(demos)

if __name__ == "__main__":
    success = main()
    print(f"\n{'🎉 演示完成' if success else '❌ 演示失败'}")
    sys.exit(0 if success else 1)
