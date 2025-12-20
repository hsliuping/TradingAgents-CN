#!/usr/bin/env python3
"""
国际新闻分析师 (International News Analyst)

职责（遵循职责分离原则）:
- 监控彭博、路透、WSJ等国际媒体
- 识别短期新闻事件（政策传闻/行业事件/市场情绪）
- 评估新闻影响持续期和影响强度
- ❌ 不给出仓位调整建议（由Strategy Advisor统一决策）

设计原则:
- 信息分析层：只负责信息采集和影响评估
- 输出影响强度（高/中/低），不输出仓位数值
- 决策由Strategy Advisor统一制定
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import json
from datetime import datetime

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")


def create_international_news_analyst(llm, toolkit):
    """
    创建国际新闻分析师节点
    
    Args:
        llm: 语言模型实例
        toolkit: 工具包
        
    Returns:
        国际新闻分析师节点函数
    """
    
    def international_news_analyst_node(state):
        """国际新闻分析师节点"""
        logger.info("🌍 [国际新闻分析师] 节点开始")
        
        # 1. 工具调用计数器（防死循环）
        tool_call_count = state.get("international_news_tool_call_count", 0)
        max_tool_calls = 3
        logger.info(f"🔧 [死循环修复] 国际新闻分析师工具调用次数: {tool_call_count}/{max_tool_calls}")
        
        # 2. 检查是否已有报告
        existing_report = state.get("international_news_report", "")
        if existing_report and len(existing_report) > 100:
            logger.info(f"✅ [国际新闻分析师] 已有报告，跳过分析")
            return {
                "messages": state["messages"],
                "international_news_report": existing_report,
                "international_news_tool_call_count": tool_call_count
            }
        
        # 3. 降级方案（达到最大调用次数）
        if tool_call_count >= max_tool_calls:
            logger.warning(f"⚠️ [国际新闻分析师] 达到最大工具调用次数，返回降级报告")
            fallback_report = json.dumps({
                "key_news": [],
                "overall_impact": "数据获取受限",
                "impact_strength": "低",
                "confidence": 0.3
            }, ensure_ascii=False)
            
            return {
                "messages": state["messages"],
                "international_news_report": fallback_report,
                "international_news_tool_call_count": tool_call_count
            }
        
        # 4. 获取指数信息
        index_code = state.get("company_of_interest", "")
        trade_date = state.get("trade_date", "")
        
        # 5. 识别指数类型，生成搜索关键词
        index_keywords = _get_search_keywords(index_code)
        logger.info(f"🌍 [国际新闻分析师] 分析指数: {index_code}, 关键词: {index_keywords}")
        
        # 6. 读取上游Policy Analyst报告（用于去重）
        policy_report = state.get("policy_report", "")
        logger.info(f"🌍 [国际新闻分析师] 上游政策报告长度: {len(policy_report)} 字符")
        
        # 7. 构建Prompt
        system_prompt = """你是一位国际新闻分析师，专注于监控彭博、路透、华尔街日报等国际媒体。

📋 **核心任务**
- 获取近7天国际媒体关于目标市场/行业的新闻
- **重点关注短期影响的新闻** (政策传闻、突发事件)
- 区分新闻类型和影响持续期
- 评估新闻影响强度 (高/中/低)

🎯 **分析目标**
- 指数代码: {index_code}
- 搜索关键词: {index_keywords}

🎯 **新闻分类标准**
1. **政策传闻** (重点关注)
   - 国际媒体提前爆料但国内未确认
   - 示例: '彭博社:中国计划千亿芯片支持'
   - 影响持续期: 中期 (1-4周)

2. **政策官宣**
   - 已被国内官方确认的政策
   - ⚠️ 如果已在上游Policy Analyst报告中 → 跳过
   - 影响持续期: 长期 (数月)

3. **行业突发事件**
   - 示例: 'ASML限制对华出口', '美国芯片法案通过'
   - 影响持续期: 中期 (1-4周)

4. **市场情绪**
   - 示例: '外资大幅增持中国科技股'
   - 影响持续期: 短期 (1-7天)

🔍 **去重规则** (避免与Policy Analyst重复)
- 如果新闻已在上游Policy Analyst报告中 → 标注为"已覆盖"
- 仅保留**未被Policy Analyst覆盖**的短期新闻

📊 **上游Policy Analyst报告**
{policy_report}

🎯 **输出格式** (严格JSON)
```json
{{
  "key_news": [
    {{
      "source": "Bloomberg",
      "title": "...",
      "date": "2025-12-10",
      "type": "政策传闻" | "行业事件" | "市场情绪",
      "impact": "利好" | "利空" | "中性",
      "impact_duration": "短期(1-7天)" | "中期(1-4周)" | "长期(数月)",
      "impact_strength": "高" | "中" | "低",
      "credibility": 0.8,
      "covered_by_policy_analyst": false,
      "summary": "新闻摘要"
    }}
  ],
  "overall_impact": "重大利好" | "利好" | "中性" | "利空" | "重大利空",
  "impact_strength": "高" | "中" | "低",
  "confidence": 0.85
}}
```

⚠️ **职责分离原则 - 重要提醒**: 
- ❌ 不要输出 position_adjustment 字段
- ❌ 不要输出 adjustment_rationale 字段
- ❌ 不要输出 base_position_recommendation 字段
- ✅ 只评估影响强度,不给出仓位建议
- ✅ 仓位决策由Strategy Advisor统一制定

请使用工具获取国际新闻数据，然后进行分析。
"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # 8. 设置prompt变量
        prompt = prompt.partial(
            policy_report=policy_report if policy_report else "暂无政策报告",
            index_code=index_code,
            index_keywords=index_keywords
        )
        
        # 9. 绑定工具
        from tradingagents.tools.international_news_tools import (
            fetch_bloomberg_news,
            fetch_reuters_news,
            fetch_google_news
        )
        
        tools = [fetch_bloomberg_news, fetch_reuters_news, fetch_google_news]
        
        logger.info(f"🌍 [国际新闻分析师] 绑定工具: Bloomberg, Reuters, Google News")
        
        chain = prompt | llm.bind_tools(tools)
        
        # 10. 调用LLM
        logger.info(f"🌍 [国际新闻分析师] 开始调用LLM...")
        result = chain.invoke({"messages": state["messages"]})
        logger.info(f"🌍 [国际新闻分析师] LLM调用完成")
        
        # 11. 处理结果
        logger.info(f"🌍 [国际新闻分析师] 响应类型: {type(result).__name__}")
        logger.info(f"🌍 [国际新闻分析师] 响应内容前500字符: {str(result.content)[:500]}")
        
        # 检查是否有工具调用
        has_tool_calls = hasattr(result, 'tool_calls') and result.tool_calls and len(result.tool_calls) > 0
        
        if has_tool_calls:
            logger.info(f"🌍 [国际新闻分析师] 检测到工具调用，返回等待工具执行")
            return {
                "messages": [result],
                "international_news_tool_call_count": tool_call_count + 1
            }
        
        # 12. 提取JSON报告
        report = _extract_json_report(result.content)
        
        if report:
            logger.info(f"✅ [国际新闻分析师] JSON报告提取成功: {len(report)} 字符")
        else:
            logger.warning(f"⚠️ [国际新闻分析师] JSON报告提取失败，使用原始内容")
            report = result.content
        
        # 13. 返回状态更新
        return {
            "messages": [result],
            "international_news_report": report,
            "international_news_tool_call_count": tool_call_count + 1
        }
    
    return international_news_analyst_node


def _get_search_keywords(index_code: str) -> str:
    """
    根据指数代码生成搜索关键词
    
    Args:
        index_code: 指数代码
        
    Returns:
        搜索关键词
    """
    # 行业指数关键词映射
    keyword_map = {
        "sh931865": "China semiconductor chip policy",  # 中证半导体
        "sh000991": "China pharmaceutical healthcare",  # 全指医药
        "sh931643": "China new energy vehicle EV",      # 新能源车
        "sh000300": "China A-share market policy",      # 沪深300
        "sz399006": "China ChiNext technology policy",  # 创业板指
        "^GSPC": "S&P 500 US market policy",            # 标普500
        "^HSI": "Hong Kong Hang Seng China",            # 恒生指数
    }
    
    return keyword_map.get(index_code, "China stock market policy")


def _extract_json_report(content: str) -> str:
    """
    从LLM回复中提取JSON报告
    
    Args:
        content: LLM原始回复
        
    Returns:
        提取的JSON字符串，失败返回空字符串
    """
    try:
        if '{' in content and '}' in content:
            start_idx = content.index('{')
            end_idx = content.rindex('}') + 1
            json_str = content[start_idx:end_idx]
            
            # 验证JSON有效性
            json.loads(json_str)
            
            logger.info(f"✅ [国际新闻分析师] JSON提取成功")
            return json_str
        else:
            logger.warning(f"⚠️ [国际新闻分析师] 内容中未找到JSON标记")
            return ""
    
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ [国际新闻分析师] JSON解析失败: {e}")
        return ""
    except Exception as e:
        logger.error(f"❌ [国际新闻分析师] JSON提取异常: {e}")
        return ""
