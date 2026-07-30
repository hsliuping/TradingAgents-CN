#!/usr/bin/env python3
"""
个人股票分析脚本
根据您的需求自定义分析参数
"""

import os
import sys
from pathlib import Path

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('default')

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from tradingagents.llm_adapters import ChatDashScope
from langchain_core.messages import HumanMessage, SystemMessage

# 加载环境变量
load_dotenv()

def analyze_my_stock():
    """分析您感兴趣的股票"""
    
    # 🎯 在这里修改您要分析的股票
    STOCK_SYMBOL = "NVDA"  # 修改为您想分析的股票代码
    ANALYSIS_FOCUS = "AI芯片和数据中心业务前景"  # 修改分析重点
    
    logger.info(f"🚀 开始分析股票: {STOCK_SYMBOL}")
    logger.info(f"🎯 分析重点: {ANALYSIS_FOCUS}")
    logger.info(f"=")
    
    # 检查API密钥
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        logger.error(f"❌ 请设置 DASHSCOPE_API_KEY 环境变量")
        return
    
    try:
        # 初始化模型
        llm = ChatDashScope(
            model="qwen-plus-latest",  # 可选: qwen-turbo, qwen-plus-latest, qwen-max
            temperature=0.1,
            max_tokens=4000
        )
        
        # 构建分析提示
        system_prompt = """
你是一位专业的股票研究分析师，具有丰富的研究经验。
        请提供客观、详细的股票研究报告。
        分析应该包含具体数据、清晰逻辑和研究观察，不得输出买入/卖出/持有等交易指令。
        """

        analysis_prompt = f"""
        请对股票 {STOCK_SYMBOL} 进行全面的研究分析，特别关注{ANALYSIS_FOCUS}。

请从以下角度进行分析：

1. **公司基本面分析**
   - 最新财务数据（营收、利润、现金流）
   - 核心业务表现和增长趋势
   - 竞争优势和护城河

2. **技术面分析**
   - 当前股价走势和趋势判断
   - 关键技术指标（MA、RSI、MACD等）
   - 重要支撑位和阻力位

3. **行业和市场分析**
   - 行业发展趋势和市场机会
   - 主要竞争对手比较
   - 市场地位和份额变化

4. **风险评估**
   - 主要风险因素识别
   - 宏观经济影响
   - 行业特定风险

5. **研究结论**
   - 研究结论倾向（乐观/审慎/中性）
   - 关键验证区间（观察区，非目标价）
   - 适合关注的投资者类型
   - 后续跟踪要点

请用中文撰写，提供具体的数据和分析依据。本报告仅供研究参考，不构成投资建议。
"""
        
        # 生成分析
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=analysis_prompt)
        ]
        
        logger.info(f"⏳ 正在生成分析报告...")
        response = llm.invoke(messages)
        
        logger.info(f"\n📊 {STOCK_SYMBOL} 投资分析报告:")
        logger.info(f"=")
        print(response.content)
        logger.info(f"=")
        
        # 保存报告
        filename = f"{STOCK_SYMBOL}_analysis_report.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"股票代码: {STOCK_SYMBOL}\n")
            f.write(f"分析重点: {ANALYSIS_FOCUS}\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n")
            f.write(response.content)
        
        logger.info(f"✅ 分析报告已保存到: {filename}")
        
    except Exception as e:
        logger.error(f"❌ 分析失败: {e}")

if __name__ == "__main__":
    import datetime

    analyze_my_stock()
