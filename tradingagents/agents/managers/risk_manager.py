import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
from tradingagents.agents.utils.instrument_utils import build_instrument_context
logger = get_logger("default")


def create_risk_manager(llm, memory, config=None):
    def risk_manager_node(state) -> dict:

        company_name = state["company_of_interest"]
        instrument_context = build_instrument_context(company_name)

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        sentiment_report = state["sentiment_report"]
        trader_plan = state["investment_plan"]
        trader_execution_plan = state.get("trader_investment_plan", "")

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"

        # 安全检查：确保memory不为None
        if memory is not None:
            past_memories = memory.get_memories(curr_situation, n_matches=2)
        else:
            logger.warning(f"⚠️ [DEBUG] memory为None，跳过历史记忆检索")
            past_memories = []

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        risk_preference = (config or {}).get("risk_preference", "neutral")
        risk_preference_text = {
            "conservative": "保守：最终建议应优先控制回撤、估值安全边际和下行风险。",
            "neutral": "中性：最终建议应平衡上涨空间、估值安全边际和风险暴露。",
            "aggressive": "激进：最终建议可更重视上涨空间，但必须说明可接受的风险边界。"
        }.get(risk_preference, "中性：最终建议应平衡上涨空间、估值安全边际和风险暴露。")

        prompt = f"""作为风险管理委员会主席和投资组合经理，您的目标是评估三位风险分析师——激进、中性和安全/保守——在“独立初评 + 交叉质询”流程中形成的观点，并确定交易员的最佳行动方案。您的决策必须产生明确的建议：买入、卖出或持有。只有在有具体论据强烈支持时才选择持有，而不是在所有方面都似乎有效时作为后备选择。力求清晰、可执行、可复盘。

决策指导原则：
1. **分阶段阅读证据**：先看三位分析师的独立初评，识别各自原始判断；再看交叉质询，识别哪些观点经得起反驳。
2. **按角色权重取证**：
   - 激进分析师主要贡献机会、催化剂、预期差、赔率空间。
   - 保守分析师主要贡献大盘、行业、流动性、本金损失和尾部风险。
   - 中性分析师主要贡献风险收益比、证据质量、信号冲突和执行条件。
3. **完善交易员计划**：从研究经理投资计划**{trader_plan}**和交易员执行计划**{trader_execution_plan}**开始，根据分析师的见解进行调整。
4. **从过去的错误中学习**：使用**{past_memory_str}**中的经验教训来解决先前的误判，改进您现在做出的决策，确保您不会做出错误的买入/卖出/持有决定而亏损。

用户风险偏好：{risk_preference_text}

最终决策校验：
- 必须检查交易员计划是否已经纳入新闻面、基本面和同行业对比；若遗漏，您需要补充这些因素后再给最终建议。
- 同行业对比是基本面风险校验的一部分；若同业估值、可比公司或历史分位显示估值偏离，必须影响风险评分、仓位或买卖建议。
- 如果新闻面与基本面/同业对比信号冲突，请说明最终采用的主导依据。
- 如果保守分析师指出大盘或行业系统性风险，必须说明这些风险是否会压低仓位、推迟买入或触发卖出。
- 如果激进分析师指出机会窗口，必须说明机会是否足以补偿风险。
- 如果中性分析师指出证据不足或风险收益不对称，必须在最终动作、仓位或止损中体现。

交付成果：
请按以下结构输出，使用中文：
1. **最终建议**：买入 / 持有 / 卖出，并给出一句话结论。
2. **风险评分**：分别给出基本面风险、估值风险、大盘/行业风险、技术面风险、新闻/政策风险、情绪/流动性风险、综合风险，均为0-10分。
3. **证据裁决**：说明激进、保守、中性三方中哪些观点被采纳，哪些被否决，原因是什么。
4. **价格与仓位**：给出目标价区间、止损价/减仓条件、建议仓位或仓位上限。
5. **执行方案**：一次性买入、分批、观察、减仓或卖出的具体条件。
6. **重新评估触发器**：列出会让结论升级或降级的关键条件。
7. **置信度**：0-1之间，并解释主要不确定性。

标的约束：
{instrument_context}

---

**分析师辩论历史：**
{history}

---

专注于可操作的见解和持续改进。建立在过去经验教训的基础上，批判性地评估所有观点，确保每个决策都能带来更好的结果。请用中文撰写所有分析内容和建议。"""

        # 📊 统计 prompt 大小
        prompt_length = len(prompt)
        # 粗略估算 token 数量（中文约 1.5-2 字符/token，英文约 4 字符/token）
        estimated_tokens = int(prompt_length / 1.8)  # 保守估计

        logger.info(f"📊 [Risk Manager] Prompt 统计:")
        logger.info(f"   - 辩论历史长度: {len(history)} 字符")
        logger.info(f"   - 交易员计划长度: {len(trader_plan)} 字符")
        logger.info(f"   - 历史记忆长度: {len(past_memory_str)} 字符")
        logger.info(f"   - 总 Prompt 长度: {prompt_length} 字符")
        logger.info(f"   - 估算输入 Token: ~{estimated_tokens} tokens")

        # 增强的LLM调用，包含错误处理和重试机制
        max_retries = 3
        retry_count = 0
        response_content = ""

        while retry_count < max_retries:
            try:
                logger.info(f"🔄 [Risk Manager] 调用LLM生成交易决策 (尝试 {retry_count + 1}/{max_retries})")

                # ⏱️ 记录开始时间
                start_time = time.time()

                response = llm.invoke(prompt)

                # ⏱️ 记录结束时间
                elapsed_time = time.time() - start_time
                
                if response and hasattr(response, 'content') and response.content:
                    response_content = response.content.strip()

                    # 📊 统计响应信息
                    response_length = len(response_content)
                    estimated_output_tokens = int(response_length / 1.8)

                    # 尝试获取实际的 token 使用情况（如果 LLM 返回了）
                    usage_info = ""
                    if hasattr(response, 'response_metadata') and response.response_metadata:
                        metadata = response.response_metadata
                        if 'token_usage' in metadata:
                            token_usage = metadata['token_usage']
                            usage_info = f", 实际Token: 输入={token_usage.get('prompt_tokens', 'N/A')} 输出={token_usage.get('completion_tokens', 'N/A')} 总计={token_usage.get('total_tokens', 'N/A')}"

                    logger.info(f"⏱️ [Risk Manager] LLM调用耗时: {elapsed_time:.2f}秒")
                    logger.info(f"📊 [Risk Manager] 响应统计: {response_length} 字符, 估算~{estimated_output_tokens} tokens{usage_info}")

                    if len(response_content) > 10:  # 确保响应有实质内容
                        logger.info(f"✅ [Risk Manager] LLM调用成功")
                        break
                    else:
                        logger.warning(f"⚠️ [Risk Manager] LLM响应内容过短: {len(response_content)} 字符")
                        response_content = ""
                else:
                    logger.warning(f"⚠️ [Risk Manager] LLM响应为空或无效")
                    response_content = ""

            except Exception as e:
                elapsed_time = time.time() - start_time
                logger.error(f"❌ [Risk Manager] LLM调用失败 (尝试 {retry_count + 1}): {str(e)}")
                logger.error(f"⏱️ [Risk Manager] 失败前耗时: {elapsed_time:.2f}秒")
                response_content = ""
            
            retry_count += 1
            if retry_count < max_retries and not response_content:
                logger.info(f"🔄 [Risk Manager] 等待2秒后重试...")
                time.sleep(2)
        
        # 如果所有重试都失败，生成默认决策
        if not response_content:
            logger.error(f"❌ [Risk Manager] 所有LLM调用尝试失败，使用默认决策")
            response_content = f"""**默认建议：持有**

由于技术原因无法生成详细分析，基于当前市场状况和风险控制原则，建议对{company_name}采取持有策略。

**理由：**
1. 市场信息不足，避免盲目操作
2. 保持现有仓位，等待更明确的市场信号
3. 控制风险，避免在不确定性高的情况下做出激进决策

**建议：**
- 密切关注市场动态和公司基本面变化
- 设置合理的止损和止盈位
- 等待更好的入场或出场时机

注意：此为系统默认建议，建议结合人工分析做出最终决策。"""

        new_risk_debate_state = {
            "judge_decision": response_content,
            "history": risk_debate_state.get("history", ""),
            "risky_history": risk_debate_state.get("risky_history", ""),
            "safe_history": risk_debate_state.get("safe_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Judge",
            "stage": "decision",
            "current_risky_response": risk_debate_state.get("current_risky_response", ""),
            "current_safe_response": risk_debate_state.get("current_safe_response", ""),
            "current_neutral_response": risk_debate_state.get("current_neutral_response", ""),
            "count": risk_debate_state.get("count", 0),
        }

        logger.info(f"📋 [Risk Manager] 最终决策生成完成，内容长度: {len(response_content)} 字符")
        
        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": response_content,
        }

    return risk_manager_node
