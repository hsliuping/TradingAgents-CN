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
                "overall_impact": "【国际新闻降级】数据获取受限，无法分析国际新闻影响。",
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
        trade_date = state.get("trade_date", "")
        
        logger.info(f"🌍 [国际新闻分析师] 分析目标: {index_name} ({index_code})")
        
        # 5. 识别指数类型，生成搜索关键词
        # 移除静态关键词映射，转而由LLM根据指数/板块名称动态生成
        # index_keywords = _get_search_keywords(index_code)
        # logger.info(f"🌍 [国际新闻分析师] 分析指数: {index_code}, 关键词: {index_keywords}")
        
        # 6. 读取上游Policy Analyst报告（用于去重）
        policy_report = state.get("policy_report", "")
        logger.info(f"🌍 [国际新闻分析师] 上游政策报告长度: {len(policy_report)} 字符")
        
        # 7. 构建Prompt
        system_prompt = """你是一位国际新闻分析师，专注于监控彭博、路透、华尔街日报等国际媒体。

⚠️ **核心规则 - 违反将导致系统错误**
1. **禁止闲聊**：绝对禁止输出'我理解您希望...'、'我很抱歉...'等任何解释性文字。
2. **强制JSON**：如果因为任何原因（如数据缺失、工具失败）无法生成分析，必须直接输出预定义的JSON降级报告（格式见下文）。
3. **语言要求**：报告内容必须使用简体中文。
- 必须将所有外文新闻翻译成中文进行分析
- 禁止直接引用英文原文

📋 **核心任务**
1. **生成搜索关键词**：根据输入的指数/板块名称 '{index_name}' ({index_code})，分析其代表的行业或领域（例如 '半导体' -> Semiconductor, '机器人' -> Robotics），并生成：
   - **英文搜索关键词**（例如 'China semiconductor policy', 'China robotics industry news'）用于国际源。
   - **中文搜索关键词**（例如 '半导体', '机器人'）用于国内源。
2. **获取新闻**：
   - 优先使用生成的英文关键词调用国际新闻工具（fetch_bloomberg_news, fetch_reuters_news, fetch_google_news）。
   - **关键策略**：如果第一次调用国际新闻工具返回"暂无相关新闻"或失败，**请立即放弃继续尝试其他国际工具**，直接切换到 **fetch_cn_international_news** 并使用**中文关键词**。
   - 国内源（fetch_cn_international_news）在网络受限环境下更可靠。
3. **分析新闻**：获取近7天国际媒体关于该领域的短期影响新闻。
4. **生成报告**：评估新闻影响并生成分析报告。

🎯 **分析目标**
- 目标指数/板块: {index_name} ({index_code})
- 请自行推断最佳英/中文搜索关键词

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

🎯 **输出要求**
请输出两部分内容：

### 第一部分：深度国际新闻分析报告（Markdown格式）
请撰写一份不少于400字的专业国际新闻分析报告，包含：
1. **搜索策略说明**：简要说明你使用的英文搜索关键词。
2. **核心事件解读**：详细解读对市场有重大影响的政策传闻或突发事件，分析其真实性和潜在影响。
3. **国际舆情分析**：分析国际主流媒体（彭博、路透等）对中国市场的整体情绪倾向。
4. **政策预期差**：对比国际传闻与国内政策现状，识别潜在的预期差机会或风险。
5. **短期冲击评估**：评估相关新闻对市场情绪的短期冲击力度和持续时间。

### 第二部分：结构化数据总结（JSON格式）
请在报告末尾，将核心指标提取为JSON格式，包裹在 ```json 代码块中。字段要求如下：
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

⚠️ **注意事项**
- 务必先进行深度分析，展现你的思考过程，供人类投资者参考。
- 结合上游Policy Analyst报告进行去重和交叉验证。
- JSON格式必须严格。
"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # 8. 设置prompt变量
        prompt = prompt.partial(
            policy_report=policy_report if policy_report else "暂无政策报告",
            index_code=index_code,
            index_name=index_name
        )
            
        # 9. 绑定工具
        from tradingagents.tools.international_news_tools import (
            fetch_bloomberg_news,
            fetch_reuters_news,
            fetch_google_news,
            fetch_cn_international_news
        )
        tools = [fetch_bloomberg_news, fetch_reuters_news, fetch_google_news, fetch_cn_international_news]
        
        chain = prompt | llm.bind_tools(tools)
        
        # 10. 调用LLM
        logger.info(f"🌍 [国际新闻分析师] 开始调用LLM...")
        # v2.4 并行执行优化：使用独立的消息历史
        msg_history = state.get("international_news_messages", [])
        result = chain.invoke({"messages": msg_history})
        logger.info(f"🌍 [国际新闻分析师] LLM调用完成")
        
        # 11. 处理结果
        logger.info(f"🌍 [国际新闻分析师] 响应类型: {type(result).__name__}")
        logger.info(f"🌍 [国际新闻分析师] 响应内容前500字符: {str(result.content)[:500]}")
        
        # 检查是否有工具调用
        has_tool_calls = hasattr(result, 'tool_calls') and result.tool_calls and len(result.tool_calls) > 0
        
        if has_tool_calls:
            logger.info(f"🌍 [国际新闻分析师] 检测到工具调用，返回等待工具执行")
            return {
                "international_news_messages": [result],
                "international_news_tool_call_count": tool_call_count + 1
            }
        
        # 12. 直接使用完整回复作为报告（包含Markdown分析和JSON总结）
        # 下游的 Strategy Advisor 会使用 extract_json_block 自动提取 JSON 部分
        # 前端的 Report Exporter 会自动识别混合内容并进行展示
        report = result.content
        
        logger.info(f"✅ [国际新闻分析师] 生成完整分析报告: {len(report)} 字符")
        
        # 13. 返回状态更新
        return {
            "international_news_messages": [result],
            "international_news_report": report,
            "international_news_tool_call_count": tool_call_count + 1
        }
    
    return international_news_analyst_node


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
