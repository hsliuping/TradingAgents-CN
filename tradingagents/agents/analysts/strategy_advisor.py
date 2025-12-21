#!/usr/bin/env python3
"""
策略顾问 (Strategy Advisor)

职责 (v2.1重构版 - 阶段三):
- 🎯 唯一的决策节点：整合所有上游信息给出最终仓位建议
- 📊 提取上游分析指标（只读取评估指标，不读取仓位值）
- 💼 基础仓位决策：基于长期政策支持和宏观环境
- ⚡ 短期调整决策：基于国际新闻影响
- 📋 生成分层持仓策略（核心长期/战术配置/现金储备）
- 🔔 生成动态调整触发条件

职责分离原则：
- ✅ 上游Agent只输出评估指标（强度、评分等）
- ✅ Strategy Advisor统一负责仓位决策
- ❌ 上游Agent不输出仓位建议

Version: v2.1.0
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage
import json

from tradingagents.utils.logging_manager import get_logger
from tradingagents.agents.utils.decision_algorithms import (
    extract_macro_sentiment_score,
    extract_economic_cycle,
    extract_policy_support_strength,
    extract_policy_continuity,
    extract_news_impact_strength,
    extract_news_credibility,
    extract_news_duration,
    extract_sector_heat_score,
    calculate_base_position,
    calculate_short_term_adjustment,
    generate_position_breakdown,
    generate_adjustment_triggers,
    make_strategy_decision
)

logger = get_logger("agents")


def create_strategy_advisor(llm):
    """
    创建策略顾问节点 (v2.1重构版)
    
    职责: 唯一的决策节点，整合所有上游信息给出最终仓位建议
    
    变化 (v2.1):
    - ✅ 新增：读取国际新闻报告 (international_news_report)
    - ✅ 新增：使用决策算法模块计算仓位
    - ✅ 新增：分层持仓策略输出
    - ✅ 新增：动态调整触发条件
    - ✅ 改进：不直接读取上游的仓位值，只读取评估指标
    
    Args:
        llm: 语言模型实例（通常使用deep_thinking_llm）
        
    Returns:
        策略顾问节点函数
    """
    
    def strategy_advisor_node(state):
        """策略顾问节点 (v2.1重构版)"""
        logger.info("🎯 [策略顾问] 节点开始 - 统一决策")
        
        # 1. 获取上游报告（v2.1: 新增国际新闻报告）
        macro_report = state.get("macro_report", "")
        policy_report = state.get("policy_report", "")
        sector_report = state.get("sector_report", "")
        international_news_report = state.get("international_news_report", "")  # v2.1新增
        technical_report = state.get("technical_report", "")  # v2.2新增
        session_type = state.get("session_type", "post")  # v2.2新增
        
        # v2.3: 获取辩论历史
        investment_debate_state = state.get("investment_debate_state", {})
        debate_history = investment_debate_state.get("history", "无辩论历史")
        
        logger.info(f"🎯 [策略顾问] 上游报告状态:")
        logger.info(f"   - 宏观报告: {len(macro_report)} 字符")
        logger.info(f"   - 政策报告: {len(policy_report)} 字符")
        logger.info(f"   - 板块报告: {len(sector_report)} 字符")
        logger.info(f"   - 国际新闻: {len(international_news_report)} 字符")
        logger.info(f"   - 技术报告: {len(technical_report)} 字符")
        logger.info(f"   - 会话类型: {session_type}")
        
        # 2. 验证上游报告完整性
        if not (macro_report and policy_report and sector_report):
            logger.warning(f"⚠️ [策略顾问] 上游报告不完整，返回降级报告")
            fallback_report = _generate_fallback_report()
            
            return {
                "messages": state["messages"],
                "strategy_report": fallback_report
            }
        
        # 3. v2.1: 使用决策算法进行统一决策
        logger.info("📊 [策略顾问] 开始调用决策算法...")
        
        # 如果没有国际新闻报告，使用默认空报告
        if not international_news_report:
            logger.warning("⚠️ [策略顾问] 国际新闻报告为空，使用默认值")
            international_news_report = json.dumps({
                "impact_strength": "低",
                "confidence": 0.5,
                "impact_duration": "短期"
            }, ensure_ascii=False)
        
        (
            base_position,
            short_term_adjustment,
            final_position,
            position_breakdown,
            adjustment_triggers
        ) = make_strategy_decision(
            macro_report=macro_report,
            policy_report=policy_report,
            international_news_report=international_news_report,
            sector_report=sector_report
        )
        
        # v2.2: 基于技术面和会话类型调整仓位 (简单的线性叠加)
        tech_adjustment = 0.0
        tech_signal = "NEUTRAL"
        if technical_report:
            try:
                tech_json = json.loads(technical_report) if '{' in technical_report else {}
                # 尝试从JSON提取，或者简单文本匹配
                if not tech_json:
                     # 简单文本提取
                     if "BULLISH" in technical_report: tech_signal = "BULLISH"
                     elif "BEARISH" in technical_report: tech_signal = "BEARISH"
                else:
                    tech_signal = tech_json.get("trend_signal", "NEUTRAL").split(" ")[0] # BULLISH
                
                # 调整逻辑
                if session_type == "morning":
                    # 早盘：技术面权重较高 (追涨杀跌)
                    if "BULLISH" in tech_signal: tech_adjustment = 0.1
                    elif "BEARISH" in tech_signal: tech_adjustment = -0.1
                elif session_type == "closing":
                    # 尾盘：技术面确认 (权重较低)
                    if "BULLISH" in tech_signal: tech_adjustment = 0.05
                    elif "BEARISH" in tech_signal: tech_adjustment = -0.05
                
                # 更新最终仓位
                old_final = final_position
                final_position = max(0.0, min(1.0, final_position + tech_adjustment))
                if tech_adjustment != 0:
                    logger.info(f"⚡ [策略顾问] 技术面调整 ({tech_signal}): {old_final:.2%} -> {final_position:.2%} (Adj: {tech_adjustment:+.2%})")
                    
            except Exception as e:
                logger.warning(f"⚠️ [策略顾问] 技术面调整计算失败: {e}")

        logger.info(f"✅ [策略顾问] 决策完成: 基础仓位={base_position:.2%}, 短期调整={short_term_adjustment:+.2%}, 技术调整={tech_adjustment:+.2%}, 最终仓位={final_position:.2%}")
        
        # 4. 构建Prompt（v2.1: 重构为基于决策结果生成报告）
        system_prompt = """你是一位资深的投资策略顾问。
        
📊 **已完成的决策计算**：

💼 **仓位决策**：
- 基础仓位: {base_position:.2%}
  (基于政策支持强度和宏观环境)
- 短期调整: {short_term_adjustment:+.2%}
  (基于国际新闻影响)
- 技术调整: {tech_adjustment:+.2%}
  (基于技术面趋势: {tech_signal})
- 🎯 **最终仓位: {final_position:.2%}**

📋 **分层持仓策略**：
- 核心长期仓位: {core_holding:.2%}
  (基于长期政策支持，稳定持有)
- 战术配置: {tactical:.2%}
  (短期机会把握，灵活调整)
- 现金储备: {cash_reserve:.2%}
  (风险管理和流动性保障)

🔔 **动态调整触发条件**：
- 提升至 {increase_to:.2%}：{increase_condition}
- 降至 {decrease_to:.2%}：{decrease_condition}

📝 **上游分析报告**：

### 1️⃣ 宏观经济分析
{macro_report}

### 2️⃣ 政策分析
{policy_report}

### 3️⃣ 板块轮动分析
{sector_report}

### 4️⃣ 国际新闻分析
{international_news_report}

### 5️⃣ 技术面分析
{technical_report}

### 6️⃣ 投资辩论记录
{debate_history}

🎯 **任务要求**：
请基于以上决策结果、上游分析报告以及**投资辩论记录**，生成一份详细的投资策略报告。
**特别注意：请充分利用上游报告中的Markdown分析内容（如宏观周期推演、政策传闻分析、技术面形态研判等），作为你策略建议的有力论据。不要仅依赖JSON数据。**
当前会话类型: **{session_type}**

⚠️ **语言要求**：
- **必须严格使用中文**撰写报告。
- 专有名词（如CPI, GDP, PE）保留英文，但解释必须用中文。

**输出格式**（必须为严格的JSON）：
```json
{{
  "market_outlook": "看多|中性|看空",
  "final_position": {final_position},
  "position_breakdown": {{
    "core_holding": {core_holding},
    "tactical_allocation": {tactical},
    "cash_reserve": {cash_reserve}
  }},
  "adjustment_triggers": {{
    "increase_to": {increase_to},
    "increase_condition": "{increase_condition}",
    "decrease_to": {decrease_to},
    "decrease_condition": "{decrease_condition}"
  }},
  "key_risks": ["风险1", "风险2"],
  "opportunity_sectors": ["板块1", "板块2"],
  "debate_summary": "请总结投资辩论中的核心分歧与共识，必须使用中文。",
  "rationale": "请结合上游分析师的深度观点（如宏观周期、政策逻辑、技术形态等）撰写详细的策略依据，不少于300字。请勿重复罗列数字，而是侧重逻辑推演。",
  "decision_rationale": "基础({base_position:.2%}) + 新闻({short_term_adjustment:+.2%}) + 技术({tech_adjustment:+.2%}) = {final_position:.2%}",
  "confidence": 0.0-1.0
}}
```

⚠️ **注意事项**：
- rationale部分必须详细，体现对上游分析师观点的综合与提炼。
- market_outlook必须与最终仓位匹配：>60%=看多, 40-60%=中性, <40%=看空
- key_risks必须结合宏观、政策、板块、技术面的潜在风险
- opportunity_sectors必须来自板块报告的hot_themes或top_sectors
- JSON格式必须严格
"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # 5. 设置prompt变量
        prompt = prompt.partial(
            base_position=base_position,
            short_term_adjustment=short_term_adjustment,
            tech_adjustment=tech_adjustment,
            tech_signal=tech_signal,
            final_position=final_position,
            core_holding=position_breakdown["core_holding"],
            tactical=position_breakdown["tactical_allocation"],
            cash_reserve=position_breakdown["cash_reserve"],
            increase_to=adjustment_triggers["increase_to"],
            increase_condition=adjustment_triggers["increase_condition"],
            decrease_to=adjustment_triggers["decrease_to"],
            decrease_condition=adjustment_triggers["decrease_condition"],
            macro_report=macro_report,
            policy_report=policy_report,
            sector_report=sector_report,
            international_news_report=international_news_report,
            technical_report=technical_report,
            debate_history=debate_history,
            session_type=session_type
        )
        
        # 6. 直接调用LLM（不绑定工具）
        logger.info(f"🎯 [策略顾问] 开始LLM生成综合报告...")
        chain = prompt | llm
        result = chain.invoke({"messages": state["messages"]})
        logger.info(f"🎯 [策略顾问] LLM调用完成")
        
        # 7. Strategy Advisor理论上不应该调用工具
        if hasattr(result, 'tool_calls') and result.tool_calls:
            logger.warning(f"⚠️ [策略顾问] 检测到意外的工具调用，将忽略")
        
        # 8. 提取JSON报告
        report_content = _extract_json_report(result.content)
        
        if not report_content:
            logger.warning(f"⚠️ [策略顾问] JSON报告提取失败，使用原始内容")
            report_content = result.content
        
        # 9. v2.1: 构建结构化输出（合并决策数据和LLM生成内容）
        try:
            llm_report = json.loads(report_content)
            
            # 合并决策结果（确保数据一致性）
            final_report_data = {
                # 从决策算法获取的数据（权威）
                "final_position": final_position,
                "position_breakdown": position_breakdown,
                "adjustment_triggers": adjustment_triggers,
                "decision_rationale": f"基于{extract_policy_support_strength(policy_report)}政策支持({base_position:.2%}) + {extract_news_impact_strength(international_news_report)}新闻影响({short_term_adjustment:+.2%}) + 技术调整({tech_adjustment:+.2%}) = {final_position:.2%}",
                
                # 从LLM获取的分析内容
                "market_outlook": llm_report.get("market_outlook", "中性"),
                "key_risks": llm_report.get("key_risks", []),
                "opportunity_sectors": llm_report.get("opportunity_sectors", []),
                "debate_summary": llm_report.get("debate_summary", "无辩论总结"),
                "rationale": llm_report.get("rationale", ""),
                "confidence": llm_report.get("confidence", 0.5)
            }
            
            # 将字典转换为JSON字符串，以便 report_exporter 处理
            final_report = json.dumps(final_report_data, ensure_ascii=False)
            
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ [策略顾问] JSON解析失败: {e}，使用降级报告")
            final_report = _generate_fallback_report()
            
        logger.info(f"✅ [策略顾问] 生成最终策略报告: {len(final_report)} 字符")
        
        # 10. 构建清洁的AIMessage
        clean_message = AIMessage(content=result.content)
        
        # 11. 返回状态更新
        return {
            "messages": [clean_message],
            "strategy_report": final_report,
            "investment_debate_state": investment_debate_state # 保持状态传递
        }
    
    return strategy_advisor_node


def _generate_fallback_report() -> str:
    """
    生成降级报告 (v2.1版本)
    
    当上游数据不完整或JSON解析失败时使用
    """
    fallback = {
        "final_position": 0.5,
        "position_breakdown": {
            "core_holding": 0.33,
            "tactical_allocation": 0.17,
            "cash_reserve": 0.50
        },
        "adjustment_triggers": {
            "increase_to": 0.70,
            "increase_condition": "数据完整后重新评估",
            "decrease_to": 0.40,
            "decrease_condition": "风险加剧"
        },
        "market_outlook": "中性",
        "key_risks": ["数据不完整"],
        "opportunity_sectors": ["无法确定"],
        "rationale": "由于上游分析数据不完整，无法给出有效的策略建议。建议等待数据完整后重新分析。",
        "decision_rationale": "降级模式: 默认中性仓位",
        "confidence": 0.3
    }
    return json.dumps(fallback, ensure_ascii=False)


def _extract_json_report(content: str) -> str:
    """从LLM回复中提取JSON报告"""
    try:
        if '{' in content and '}' in content:
            start_idx = content.index('{')
            end_idx = content.rindex('}') + 1
            json_str = content[start_idx:end_idx]
            
            # 验证JSON有效性
            json.loads(json_str)
            
            logger.info(f"✅ [策略顾问] JSON提取成功")
            return json_str
        else:
            logger.warning(f"⚠️ [策略顾问] 内容中未找到JSON标记")
            return ""
    
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ [策略顾问] JSON解析失败: {e}")
        return ""
    except Exception as e:
        logger.error(f"❌ [策略顾问] JSON提取异常: {e}")
        return ""
