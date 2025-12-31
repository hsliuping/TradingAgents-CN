#!/usr/bin/env python3
"""
综合新闻分析师 (News Analyst - for Index Analysis)

职责（遵循职责分离原则）:
- 统一处理所有短期、即时性强的国内外新闻消息
- 监控彭博、路透、WSJ等国际媒体
- 监控国内政策传闻、市场热点
- 评估新闻事件的短期冲击和市场情绪影响
- ❌ 不给出仓位调整建议（由Strategy Advisor统一决策）

设计原则:
- 聚合多源信息（国内+国际）
- 区分新闻类型（政策传闻/官宣/事件/情绪）
- 专注于“快变量”
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import json
from datetime import datetime

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")


def create_index_news_analyst(llm, toolkit):
    """
    创建指数综合新闻分析师节点
    
    Args:
        llm: 语言模型实例
        toolkit: 工具包
        
    Returns:
        综合新闻分析师节点函数
    """
    
    def index_news_analyst_node(state):
        """综合新闻分析师节点"""
        logger.info("🌍 [综合新闻分析师] 节点开始")
        
        # 1. 工具调用计数器（防死循环）
        tool_call_count = state.get("international_news_tool_call_count", 0) # 复用字段名以免改动State定义
        max_tool_calls = 3
        logger.info(f"🔧 [死循环修复] 综合新闻分析师工具调用次数: {tool_call_count}/{max_tool_calls}")
        
        # 2. 检查是否已有报告
        existing_report = state.get("international_news_report", "") # 复用字段名
        if existing_report and len(existing_report) > 100:
            logger.info(f"✅ [综合新闻分析师] 已有报告，跳过分析")
            return {
                "messages": state["messages"],
                "international_news_report": existing_report,
                "international_news_tool_call_count": tool_call_count
            }
        
        # 3. 降级方案（达到最大调用次数）
        if tool_call_count >= max_tool_calls:
            logger.warning(f"⚠️ [综合新闻分析师] 达到最大工具调用次数，返回降级报告")
            fallback_report = json.dumps({
                "key_news": [],
                "overall_impact": "【新闻降级】数据获取受限，无法分析新闻影响。",
                "impact_strength": "低",
                "confidence": 0.3
            }, ensure_ascii=False)
            
            return {
                "international_news_messages": state.get("international_news_messages", []),
                "international_news_report": fallback_report,
                "international_news_tool_call_count": tool_call_count
            }
        
        # 4. 获取指数信息
        index_info = state.get("index_info", {})
        index_code = index_info.get("symbol", state.get("company_of_interest", "未知指数"))
        index_name = index_info.get("name", "未知指数")
        
        logger.info(f"🌍 [综合新闻分析师] 分析目标: {index_name} ({index_code})")
        
        # 5. 构建Prompt
        system_prompt = """你是一位专业的综合新闻分析师 (News Analyst)，负责统筹分析影响市场的短期新闻。

⚠️ **核心职责**
1. **统一入口**：你不仅关注国际新闻（Bloomberg/Reuters），也关注国内的短期政策传闻和市场热点。
2. **快变量分析**：你的重点是“快”——评估突发事件、传闻、情绪对市场的即时冲击（1-7天）和中短期影响（1-4周）。
3. **区分验证**：对于传闻，尝试交叉验证；对于官宣，评估其与预期的偏差。

📋 **任务清单**
1. **生成多维关键词**：
   - 国际视角：生成英文关键词（如 'China stimulus rumors', 'trade war'）。
   - 国内视角：生成中文关键词（如 '{index_name} 政策传闻', '{index_name} 突发'）。
2. **多源获取**：
   - 调用 `fetch_policy_news` 获取国内短期动态。
   - 调用国际新闻工具获取外部视角。
3. **融合分析**：
   - 综合国内外信息，判断市场当前的主流叙事。
   - 识别“预期差”：外媒爆料 vs 国内现状。

🎯 **新闻分类标准**
1. **政策传闻/吹风** (高关注)
   - 尚未正式官宣，但在市场流传的消息。
   - 来源：外媒爆料、分析师小作文。
2. **突发黑天鹅/灰犀牛**
   - 地缘政治冲突、贸易制裁、重大事故。
3. **短期情绪指标**
   - 资金流向异常、恐慌指数飙升。

📊 **输出要求**
请输出两部分内容：

### 第一部分：深度综合新闻简报（Markdown格式）
请撰写一份不少于400字的分析报告，包含：
1. **市场焦点**：当前市场最关注的1-3个核心叙事是什么？
2. **传闻与验证**：梳理关键传闻的来源、可信度及市场反应。
3. **内外温差**：国际视角与国内视角的差异分析。
4. **短期冲击推演**：未来3-5天市场可能的情绪走势。

### 第二部分：结构化数据总结（JSON格式）
```json
{{
  "key_news": [
    {{
      "title": "新闻标题",
      "source_type": "国际媒体/国内传闻/官方吹风",
      "type": "政策传闻/行业事件/市场情绪",
      "impact": "利好/利空/中性",
      "impact_duration": "短期(1-7天)/中期(1-4周)",
      "impact_strength": "高/中/低",
      "summary": "简要摘要"
    }}
  ],
  "market_sentiment": "恐慌/谨慎/乐观/狂热",
  "overall_impact": "利好/利空/中性",
  "confidence": 0.8
}}
```

⚠️ **注意**：
- 严格遵循JSON格式。
- 不提供仓位建议。
"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # 6. 设置prompt变量
        prompt = prompt.partial(
            index_code=index_code,
            index_name=index_name
        )
            
        # 7. 绑定工具 (新增 fetch_policy_news)
        from tradingagents.tools.international_news_tools import (
            fetch_bloomberg_news,
            fetch_reuters_news,
            fetch_google_news,
            fetch_cn_international_news
        )
        from tradingagents.tools.index_tools import fetch_policy_news
        
        # 聚合所有新闻工具
        tools = [
            fetch_bloomberg_news, 
            fetch_reuters_news, 
            fetch_google_news, 
            fetch_cn_international_news,
            fetch_policy_news
        ]
        
        chain = prompt | llm.bind_tools(tools)
        
        # 8. 调用LLM
        logger.info(f"🌍 [综合新闻分析师] 开始调用LLM...")
        msg_history = state.get("international_news_messages", [])
        result = chain.invoke({"messages": msg_history})
        logger.info(f"🌍 [综合新闻分析师] LLM调用完成")
        
        # 9. 处理结果
        has_tool_calls = hasattr(result, 'tool_calls') and result.tool_calls and len(result.tool_calls) > 0
        
        if has_tool_calls:
            logger.info(f"🌍 [综合新闻分析师] 检测到工具调用，返回等待工具执行")
            return {
                "international_news_messages": [result],
                "international_news_tool_call_count": tool_call_count + 1
            }
        
        report = result.content
        
        logger.info(f"✅ [综合新闻分析师] 生成完整分析报告: {len(report)} 字符")
        
        return {
            "international_news_messages": [result],
            "international_news_report": report,
            "international_news_tool_call_count": tool_call_count + 1
        }
    
    return index_news_analyst_node

