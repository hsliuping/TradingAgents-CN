"""
技术面分析师 v2.0 (持仓分析)

基于ResearcherAgent基类实现的技术面分析师
"""

import logging
from typing import Dict, Any, List

from ...researcher import ResearcherAgent
from ...config import AgentMetadata, AgentCategory, LicenseTier
from ...registry import register_agent

logger = logging.getLogger(__name__)


# 不再需要直接导入 get_agent_prompt，使用基类的 _get_prompt_from_template 方法


@register_agent
class TechnicalAnalystV2(ResearcherAgent):
    """
    技术面分析师 v2.0 (持仓分析)
    
    功能：
    - 分析K线走势和技术指标
    - 评估支撑阻力位
    - 判断短期走势
    
    工作流程：
    1. 读取持仓信息和市场数据
    2. 使用LLM分析技术面
    3. 生成技术面分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("pa_technical_v2", llm)

        result = agent.execute({
            "position_info": {...},
            "market_data": {...}
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="pa_technical_v2",
        name="技术面分析师 v2.0",
        description="分析持仓股票的技术面，包括K线形态、技术指标、支撑阻力位",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=["get_stock_market_data_unified"],  # 🔧 修复：当没有缓存时需要调用工具获取市场数据
    )

    # 研究员类型
    researcher_type = "position_technical"
    
    # 立场（中性）
    stance = "neutral"
    
    # 输出字段名
    output_field = "technical_analysis"

    def _build_system_prompt(self, stance: str, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词
        
        Args:
            stance: 立场（对于技术分析师，始终为neutral）
            state: 工作流状态（可选，用于提取变量）
            
        Returns:
            系统提示词
        """
        # 准备模板变量（如果有state）
        variables = {}
        if state:
            position_info = state.get("position_info", {})
            code = position_info.get("code", "")
            name = position_info.get("name", "N/A")
            market = position_info.get("market", "CN")
            
            from datetime import datetime
            variables = {
                "code": code,
                "name": name,
                "ticker": code,  # 兼容旧模板的变量名
                "company_name": name,  # 兼容旧模板的变量名
                "current_date": datetime.now().strftime("%Y-%m-%d"),
                "market_name": "A股" if market == "CN" else "港股" if market == "HK" else "美股",
                "market": market,
            }
        
        # 使用基类的通用方法从模板系统获取提示词（持仓分析专用Agent，参考 research_manager_v2）
        logger.info("🔍 [TechnicalAnalystV2] 开始构建系统提示词")
        
        prompt = self._get_prompt_from_template(
            agent_type="position_analysis_v2",
            agent_name="pa_technical_v2",
            variables=variables,  # 🔧 修复：传递准备好的变量给模板系统
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context") if state else None,  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
        )
        
        logger.info(f"📝 系统提示词长度: {len(prompt)} 字符")
        if prompt:
            logger.info(f"✅ 从模板系统获取技术面分析师提示词 (长度: {len(prompt)})")
            return prompt
        
        # 降级：使用默认提示词
        return """您是一位专业的技术面分析师。

您的职责是分析持仓股票的技术面状态。

分析要点：
1. 趋势判断 - 当前处于上升/下降/震荡趋势
2. 支撑阻力 - 关键支撑位和阻力位
3. 技术指标 - MACD/KDJ/RSI等指标状态
4. 短期预判 - 未来3-5天可能走势
5. 技术评分 - 1-10分的技术面评分

请使用中文，基于真实数据进行分析。"""
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行技术面分析（覆盖基类方法，以便传递state给_build_system_prompt）
        """
        logger.info(f"开始执行技术面分析师: {self.agent_id}")

        try:
            # 1. 提取输入参数（兼容多种参数名）
            ticker = state.get("ticker") or state.get("company_of_interest")
            
            # 🆕 从 position_info 中提取 code 作为 ticker
            if not ticker and "position_info" in state:
                position_info = state.get("position_info", {})
                if isinstance(position_info, dict):
                    ticker = position_info.get("code")
            
            # 🆕 支持交易复盘场景：从 trade_info 中提取 code
            if not ticker and "trade_info" in state:
                trade_info = state.get("trade_info", {})
                if isinstance(trade_info, dict):
                    ticker = trade_info.get("code")

            analysis_date = state.get("analysis_date") or state.get("trade_date") or state.get("end_date")
            
            # 🆕 支持交易复盘场景：使用当前日期作为分析日期
            if not analysis_date:
                from datetime import datetime
                analysis_date = datetime.now().strftime("%Y-%m-%d")

            if not ticker:
                raise ValueError("Missing required parameters: ticker")
            
            # 2. 收集所需的报告
            reports = self._collect_reports(state)
            
            if not reports:
                raise ValueError("No reports available for analysis")
            
            # 🔧 关键修复：根据缓存情况生成 preference_id，并设置到 state["context"] 中
            # 这样 _build_system_prompt 和 _build_user_prompt 都会使用同一个 preference_id
            stock_report = state.get("stock_analysis_report", {})
            has_cache = stock_report.get("has_cache", False)
            user_preference = state.get("user_preference", "neutral")
            cache_scenario = "with_cache" if has_cache else "without_cache"
            preference_id = f"{cache_scenario}_{user_preference}"
            
            # 更新 state["context"] 中的 preference_id
            context = state.get("context")
            if context:
                if isinstance(context, dict):
                    context = {**context, "preference_id": preference_id}
                else:
                    # 如果是对象，创建字典包装
                    context_dict = {"user_id": getattr(context, "user_id", None)}
                    context_dict["preference_id"] = preference_id
                    context = context_dict
            else:
                context = {"preference_id": preference_id}
            
            # 将更新后的 context 设置回 state，确保后续方法都能使用
            state["context"] = context
            logger.info(f"🔧 [技术面分析师] 在 execute 中生成 preference_id: {preference_id}")
            
            # 3. 从记忆系统获取历史上下文（如果有）
            historical_context = self._get_historical_context(ticker) if self.memory else None
            
            # 4. 构建提示词（传递state给_build_system_prompt）
            system_prompt = self._build_system_prompt(self.stance, state)
            user_prompt = self._build_user_prompt(ticker, analysis_date, reports, historical_context, state)
            
            # 5. 调用LLM分析
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            logger.info(f"系统提示词: {system_prompt}")
            logger.info(f"用户提示词: {user_prompt}")
            
            if self._llm:
                # 🔧 修复：使用 invoke_with_tools 支持工具调用（当没有缓存时需要调用工具获取市场数据）
                if self._langchain_tools:
                    logger.info(f"🔧 [技术面分析师] 检测到工具，使用 invoke_with_tools 方法")
                    # 准备分析提示词（工具执行后生成报告）
                    analysis_prompt = """✅ 工具调用已完成，所有需要的数据都已获取。

🚫 **严格禁止再次调用工具**

📝 **现在请立即执行**：
基于上述工具返回的真实数据，按照之前的分析要求和输出格式，直接撰写完整的持仓技术面分析报告。

⚠️ **重要提醒**：
- 不要返回任何工具调用（tool_calls）
- 不要说"我需要调用工具"或"让我先获取数据"
- 直接输出中文分析报告内容

请立即开始撰写报告："""
                    report_content = self.invoke_with_tools(messages, analysis_prompt=analysis_prompt)
                    report = self._parse_response(report_content)
                else:
                    logger.info(f"🔧 [技术面分析师] 无工具，直接调用 LLM")
                    response = self._llm.invoke(messages)
                    report = self._parse_response(response.content)
            else:
                raise ValueError("LLM not initialized")
            
            # 6. 保存到记忆系统（如果有）
            if self.memory:
                self._save_to_memory(ticker, report)
            
            # 7. 输出到state（只返回新增的字段，避免并发冲突）
            output_key = self.output_field or f"{self.researcher_type}_report"

            logger.info(f"技术面分析师 {self.agent_id} 执行成功")
            return {
                output_key: report
            }

        except Exception as e:
            logger.error(f"技术面分析师 {self.agent_id} 执行失败: {e}", exc_info=True)
            # 返回错误状态（只返回新增的字段）
            output_key = self.output_field or f"{self.researcher_type}_report"
            return {
                output_key: {
                    "error": str(e),
                    "success": False
                }
            }

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        reports: Dict[str, str],
        historical_context: str,
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词
        
        根据是否有单股分析报告缓存，选择不同的提示词模板
        
        Args:
            ticker: 股票代码（从position_info中提取）
            analysis_date: 分析日期
            reports: 各类数据（position_info, market_data等）
            historical_context: 历史上下文
            state: 当前状态
            
        Returns:
            用户提示词
        """
        position_info = state.get("position_info", {})
        market_data = state.get("market_data", {})
        stock_report = state.get("stock_analysis_report", {})
        
        code = position_info.get("code", ticker)
        name = position_info.get("name", "N/A")
        
        # 检查是否有缓存报告
        has_cache = stock_report.get("has_cache", False)
        logger.info(f"🔧 [技术面分析师] 检查缓存状态: has_cache={has_cache}, code={code}")
        
        # 🔧 关键修复：preference_id 已经在 execute 方法中生成并设置到 state["context"] 中
        # 这里直接从 context 中获取，确保与 _build_system_prompt 使用同一个 preference_id
        context = state.get("context")
        if context:
            if isinstance(context, dict):
                preference_id = context.get("preference_id", "neutral")
            else:
                preference_id = getattr(context, "preference_id", "neutral")
        else:
            # 降级：如果没有 context，使用默认值（这种情况不应该发生）
            user_preference = state.get("user_preference", "neutral")
            cache_scenario = "with_cache" if has_cache else "without_cache"
            preference_id = f"{cache_scenario}_{user_preference}"
            logger.warning(f"⚠️ [技术面分析师] context 不存在，使用降级 preference_id: {preference_id}")
        
        logger.info(f"🔧 [技术面分析师] 从 context 获取 preference_id: {preference_id}")
        
        # 准备模板变量（支持多种变量名映射，兼容不同模板）
        from datetime import datetime
        cost_price = position_info.get('cost_price', 0)
        current_price = position_info.get('current_price', 0)
        
        variables = {
            # 标准变量名
            "code": code,
            "name": name,
            "ticker": code,  # 兼容旧模板的变量名
            "company_name": name,  # 兼容旧模板的变量名
            "cost_price": f"{cost_price:.2f}",
            "current_price": f"{current_price:.2f}",
            # 🔧 修复：unrealized_pnl_pct 在数据源中已经是百分比格式（如 6.05），不需要再用 :.2% 格式化
            "unrealized_pnl_pct": f"{position_info.get('unrealized_pnl_pct', 0):.2f}%",
            "market_data_summary": market_data.get('summary', '无K线数据'),
            "technical_indicators": market_data.get('technical_indicators', '无技术指标数据'),
            # 日期相关
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "analysis_date": analysis_date,
            # 价格相关（从市场数据中提取，如果没有则使用默认值）
            "resistance_price": market_data.get('resistance_price', f"{current_price * 1.05:.2f}"),  # 默认5%上涨
            "support_price": market_data.get('support_price', f"{current_price * 0.95:.2f}"),  # 默认5%下跌
            "secondary_resistance": market_data.get('secondary_resistance', f"{current_price * 1.08:.2f}"),
            "secondary_support": market_data.get('secondary_support', f"{current_price * 0.92:.2f}"),
            # 货币符号
            "currency_symbol": "¥",
            "currency_name": "人民币",
            # RSI值（从市场数据中提取，如果没有则使用默认值）
            "rsi_value": market_data.get('rsi', "50"),
            # 其他持仓信息
            "holding_days": position_info.get('holding_days', 0),
            "industry": position_info.get('industry', '未知'),
            "quantity": position_info.get('quantity', 0),
            "market_value": f"{position_info.get('market_value', 0):.2f}",
        }
        
        # 如果有缓存，添加市场报告内容（模板会根据是否有内容来显示）
        if has_cache:
            reports_data = stock_report.get("reports", {})
            market_report_content = reports_data.get("market_report", "")[:2000]
            variables["market_report"] = market_report_content
            variables["has_cache"] = "true"  # 标志位，模板可以用这个判断
            logger.info(f"🔧 [技术面分析师] 模板变量准备完成: market_report存在=True, 长度={len(market_report_content)}")
        else:
            variables["market_report"] = ""  # 空字符串，模板不会显示这部分
            variables["has_cache"] = "false"
            logger.info(f"🔧 [技术面分析师] 模板变量准备完成: market_report存在=False")
        
        # 尝试从数据库加载模板（preference_id 已经在 execute 方法中设置到 context 中）
        try:
            # 从 state 中提取 context（已经包含 preference_id）
            context = state.get("context") if state else None
            
            logger.info(f"🔧 [技术面分析师] 传递 preference_id 到模板系统: {preference_id}")

            prompt = self._get_prompt_from_template(
                agent_type="position_analysis_v2",  # 持仓分析Agent类型 v2.0（与工作流ID一致）
                agent_name="pa_technical_v2",    # 持仓技术面分析师v2.0
                variables=variables,
                context=context,  # context 已经包含 preference_id
                fallback_prompt=None
            )
            if prompt:
                logger.info(f"✅ [技术面分析师] 从数据库加载提示词模板 (场景: {preference_id}, 长度: {len(prompt)})")
                return prompt
        except Exception as e:
            logger.warning(f"⚠️ [技术面分析师] 从数据库加载提示词失败: {e}，使用降级提示词")
        
        # 降级：使用硬编码提示词（根据has_cache选择不同内容）
        if has_cache:
            reports_data = stock_report.get("reports", {})
            market_report = reports_data.get("market_report", "")[:2000]
            return f"""请基于以下单股技术面分析报告和持仓信息，进行持仓技术面分析：

=== 单股技术面分析报告（参考）===
{market_report}

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 成本价: {position_info.get('cost_price', 0):.2f}
- 现价: {position_info.get('current_price', 0):.2f}
- 浮动盈亏: {position_info.get('unrealized_pnl_pct', 0):.2f}%

请结合持仓情况（成本价、盈亏等），对技术面进行持仓视角的分析：
1. 当前技术面状态与持仓成本的关系
2. 基于持仓的技术面操作建议
3. 支撑阻力位与持仓成本的关系
4. 短期走势预判（考虑持仓盈亏）
5. 技术面评分（1-10分）"""
        else:
            return f"""请分析以下持仓股票的技术面：

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 成本价: {position_info.get('cost_price', 0):.2f}
- 现价: {position_info.get('current_price', 0):.2f}
- 浮动盈亏: {position_info.get('unrealized_pnl_pct', 0):.2f}%

=== 市场数据 ===
{market_data.get('summary', '无K线数据')}

=== 技术指标 ===
{market_data.get('technical_indicators', '无技术指标数据')}

请撰写详细的技术面分析报告，包括：
1. 趋势判断
2. 支撑阻力位
3. 技术指标分析
4. 短期走势预判
5. 技术面评分（1-10分）"""

    def _get_required_reports(self) -> List[str]:
        """
        获取需要的数据列表
        
        Returns:
            数据字段名列表
        """
        return [
            "position_info",
            "market_data"
        ]

