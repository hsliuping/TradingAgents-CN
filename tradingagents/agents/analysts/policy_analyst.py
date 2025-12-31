#!/usr/bin/env python3
"""
战略政策分析师 (Strategic Policy Analyst)

职责（遵循职责分离原则）:
- 专注于已颁布的、正式的、具有长期指导意义的国内政策文件和法规的深度解读
- 识别长期战略政策（5-10年）
- 评估政策的长期影响、结构性变化
- ❌ 不处理短期新闻报道或市场传闻（由 News Analyst 处理）
- ❌ 不给出基础仓位建议（由 Strategy Advisor 统一决策）

设计原则:
- 信息分析层：只负责深度政策解读
- 输出：深度洞察报告 + 结构化长期政策评估
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import json

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")


def create_strategic_policy_analyst(llm, toolkit):
    """
    创建战略政策分析师节点
    
    Args:
        llm: 语言模型实例
        toolkit: 工具包，包含fetch_policy_news等工具
        
    Returns:
        战略政策分析师节点函数
    """
    
    def strategic_policy_analyst_node(state):
        """战略政策分析师节点"""
        logger.info("📜 [战略政策分析师] 节点开始")
        
        # 1. 工具调用计数器
        tool_call_count = state.get("policy_tool_call_count", 0)
        max_tool_calls = 3
        logger.info(f"🔧 [死循环修复] 战略政策分析师工具调用次数: {tool_call_count}/{max_tool_calls}")
        
        # 2. 检查是否已有报告
        existing_report = state.get("policy_report", "")
        if existing_report and len(existing_report) > 100:
            logger.info(f"✅ [战略政策分析师] 已有报告，跳过分析")
            return {
                "messages": state["messages"],
                "policy_report": existing_report,
                "policy_tool_call_count": tool_call_count
            }
        
        # 3. 降级方案
        if tool_call_count >= max_tool_calls:
            logger.warning(f"⚠️ [战略政策分析师] 达到最大工具调用次数，返回降级报告")
            fallback_report = json.dumps({
                "strategic_direction": "数据获取受限",
                "long_term_policies": [],
                "structural_impact": "无法评估",
                "policy_continuity": 0.5,
                "analysis_summary": "由于数据获取限制，无法进行完整的战略政策分析。",
                "confidence": 0.3
            }, ensure_ascii=False)
            
            return {
                "messages": state["messages"],
                "policy_report": fallback_report,
                "policy_tool_call_count": tool_call_count
            }
        
        # 4. 构建Prompt
        index_info = state.get("index_info", {})
        index_name = index_info.get("name", "未知指数")
        
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是一位专注于中国宏观战略的**战略政策分析师 (Strategic Policy Analyst)**。\n"
                "\n"
                "⚠️ **核心职责与界限**\n"
                "1. **你的关注点**：已颁布的、正式的、具有长期指导意义的官方文件（如五年规划、政府工作报告、中央文件、法律法规）。\n"
                "2. **你的禁区**：\n"
                "   - ❌ **绝对不处理** 短期市场传闻、路透/彭博社爆料、未证实的“小作文”。（这些由 News Analyst 处理）\n"
                "   - ❌ **不关注** 短期的市场情绪波动或单一事件的即时反应。\n"
                "3. **深度要求**：分析必须基于政策文本本身，挖掘其对经济结构的深远影响，而非复述新闻标题。\n"
                "\n"
                "📋 **分析任务**\n"
                "- 调用工具获取政策信息，并**筛选出官方性质的、长期的政策内容**。\n"
                "- 深度解读政策背后的战略意图（如“高质量发展”、“自主可控”的具体落地路径）。\n"
                "- 评估政策的连贯性（Policy Continuity）和执行力度。\n"
                "- 分析政策对 {index_name} 所代表行业的结构性机遇与风险。\n"
                "\n"
                "📊 **分析维度**\n"
                "1. **战略定调**\n"
                "   - 识别国家级战略方向（如：科技自立自强、绿色低碳转型）。\n"
                "   - 判断当前处于政策周期的哪个阶段（酝酿期/爆发期/深化期/退坡期）。\n"
                "\n"
                "2. **结构性影响**\n"
                "   - 哪些行业是“政策红利”的长期受益者？\n"
                "   - 哪些行业面临“政策由于”的长期约束？\n"
                "\n"
                "3. **政策工具箱评估**\n"
                "   - 财政支持（专项债、补贴）\n"
                "   - 货币支持（再贷款、低息）\n"
                "   - 制度改革（要素市场化、准入放宽）\n"
                "\n"
                "🎯 **输出要求**\n"
                "请输出两部分内容：\n"
                "\n"
                "### 第一部分：深度战略政策洞察（Markdown格式）\n"
                "请撰写一份不少于500字的深度报告，包含：\n"
                "1. **核心战略解读**：不仅是“有什么政策”，而是“为什么有这个政策”以及“未来5年怎么走”。\n"
                "2. **关键文件剖析**：引用具体的官方文件或会议精神（如“十四五规划”、“二十届三中全会”）。\n"
                "3. **结构性机会/风险**：针对 {index_name} 的具体分析。\n"
                "\n"
                "### 第二部分：结构化评估（JSON格式）\n"
                "请在报告末尾，将核心指标提取为JSON格式，包裹在 ```json 代码块中。字段要求如下：\n"
                "```json\n"
                "{{\n"
                "  \"strategic_direction\": \"高质量发展/逆周期调节/结构性改革\",\n"
                "  \"long_term_policies\": [\n"
                "    {{\n"
                "      \"name\": \"政策名称（如：大规模设备更新）\",\n"
                "      \"source\": \"发改委/国务院\",\n"
                "      \"duration\": \"5年+\",\n"
                "      \"impact_level\": \"深远\",\n"
                "      \"beneficiary_sectors\": [\"高端装备\", \"工业母机\"]\n"
                "    }}\n"
                "  ],\n"
                "  \"structural_impact\": \"利好/中性/利空\",\n"
                "  \"policy_continuity\": 0.0-1.0, // 政策连贯性评分\n"
                "  \"confidence\": 0.0-1.0,\n"
                "  \"analysis_summary\": \"100字以内的战略总结\"\n"
                "}}\n"
                "```\n"
                "\n"
                "⚠️ **重要提示**\n"
                "- 如果工具返回的内容多为短期新闻，请在分析中明确指出“缺乏重磅官方文件”，并仅基于现有信息中具备长期价值的部分进行分析。\n"
                "- 务必保持客观、理性和深度。\n"
            ),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # 5. 绑定工具
        # 注意：虽然工具名是 fetch_policy_news，但在Prompt中我们要求Agent将其作为素材库，
        # 并主动筛选出“官方”、“长期”的内容。
        # 局限性记录：目前缺乏直接获取政府白皮书/原文的专用工具，依赖新闻聚合。
        
        # 补充缺失的变量
        prompt = prompt.partial(index_name=index_name)
        
        from tradingagents.tools.index_tools import fetch_policy_news
        tools = [fetch_policy_news]
        
        logger.info(f"📜 [战略政策分析师] 绑定工具: fetch_policy_news")
        
        chain = prompt | llm.bind_tools(tools)
        
        # 6. 调用LLM
        logger.info(f"📜 [战略政策分析师] 开始调用LLM...")
        result = chain.invoke({"messages": state["messages"]})
        logger.info(f"📜 [战略政策分析师] LLM调用完成")
        
        # 7. 处理结果
        has_tool_calls = hasattr(result, 'tool_calls') and result.tool_calls and len(result.tool_calls) > 0
        
        if has_tool_calls:
            logger.info(f"📜 [战略政策分析师] 检测到工具调用，返回等待工具执行")
            return {
                "messages": [result],
                "policy_tool_call_count": tool_call_count + 1
            }
        
        report = result.content
        
        logger.info(f"✅ [战略政策分析师] 生成完整分析报告: {len(report)} 字符")
        
        # 9. 返回状态更新
        return {
            "messages": [result],
            "policy_report": report,
            "policy_tool_call_count": tool_call_count + 1
        }
    
    return strategic_policy_analyst_node


def _extract_json_report(content: str) -> str:
    """从LLM回复中提取JSON报告"""
    try:
        if '{' in content and '}' in content:
            start_idx = content.index('{')
            end_idx = content.rindex('}') + 1
            json_str = content[start_idx:end_idx]
            
            # 验证JSON有效性
            json.loads(json_str)
            
            logger.info(f"✅ [政策分析师] JSON提取成功")
            return json_str
        else:
            logger.warning(f"⚠️ [政策分析师] 内容中未找到JSON标记")
            return ""
    
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ [政策分析师] JSON解析失败: {e}")
        return ""
    except Exception as e:
        logger.error(f"❌ [政策分析师] JSON提取异常: {e}")
        return ""
