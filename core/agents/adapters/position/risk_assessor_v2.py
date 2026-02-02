"""
风险评估师 v2.0 (持仓分析)

基于ResearcherAgent基类实现的风险评估师
"""

import logging
from typing import Dict, Any, List

from ...researcher import ResearcherAgent
from ...config import AgentMetadata, AgentCategory, LicenseTier
from ...registry import register_agent

logger = logging.getLogger(__name__)

# 尝试导入模板系统
try:
    from tradingagents.utils.template_client import get_agent_prompt
except (ImportError, KeyError) as e:
    logger.warning(f"无法导入模板系统: {e}")
    get_agent_prompt = None


@register_agent
class RiskAssessorV2(ResearcherAgent):
    """
    风险评估师 v2.0 (持仓分析)

    功能：
    - 评估风险敞口
    - 设置风险控制参考和收益预期参考价位
    - 分析波动性
    
    工作流程：
    1. 读取持仓信息、资金信息和市场数据
    2. 使用LLM评估风险
    3. 生成风险评估报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("pa_risk_v2", llm)

        result = agent.execute({
            "position_info": {...},
            "capital_info": {...},
            "market_data": {...}
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="pa_risk_v2",
        name="风险评估师 v2.0",
        description="评估持仓风险，包括风险敞口、风险控制参考价位、波动性分析",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 不需要工具
    )

    # 研究员类型
    researcher_type = "position_risk"
    
    # 立场（中性）
    stance = "neutral"
    
    # 输出字段名
    output_field = "risk_analysis"

    def _build_system_prompt(self, stance: str, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词
        
        Args:
            stance: 立场（对于风险评估师，始终为neutral）
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
                # 货币符号
                "currency_symbol": "¥",
                "currency_name": "人民币",
            }

        # 使用基类的通用方法从模板系统获取提示词（参考 research_manager_v2）
        logger.info("🔍 [RiskAssessorV2] 开始构建系统提示词")
        
        prompt = self._get_prompt_from_template(
            agent_type="position_analysis_v2",
            agent_name="pa_risk_v2",
            variables=variables,  # 🔧 修复：传递准备好的变量给模板系统
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context") if state else None,  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
        )
        
        logger.info(f"📝 系统提示词长度: {len(prompt)} 字符")
        if prompt:
            logger.info(f"✅ 从模板系统获取风险评估师提示词 (长度: {len(prompt)})")
            return prompt

        # 降级：使用默认提示词
        return """您是一位专业的风险评估师。

您的职责是评估持仓股票的风险状态。

分析要点：
1. 风险敞口分析 - 当前风险敞口是否过大
2. 风险控制参考 - 风险控制参考价位（仅供参考）
3. 收益预期参考 - 收益预期参考价位（仅供参考）
4. 波动风险 - 股票波动性评估
5. 风险等级 - 低/中/高风险评级

请使用中文，基于真实数据进行分析。"""
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行风险评估（覆盖基类方法，以便传递state给_build_system_prompt）
        """
        logger.info(f"开始执行风险评估师: {self.agent_id}")

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
            
            # 🔧 关键修复：风险评估师也需要考虑缓存场景（类似技术面和基本面分析师）
            # 将 preference_id 设置到 state["context"] 中，确保 _build_system_prompt 和 _build_user_prompt 使用同一个 preference_id
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
            logger.info(f"🔧 [风险评估师] 在 execute 中生成 preference_id: {preference_id}")
            
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
                response = self._llm.invoke(messages)
                report = self._parse_response(response.content)
            else:
                raise ValueError("LLM not initialized")
            
            # 6. 保存到记忆系统（如果有）
            if self.memory:
                self._save_to_memory(ticker, report)
            
            # 7. 输出到state（只返回新增的字段，避免并发冲突）
            output_key = self.output_field or f"{self.researcher_type}_report"

            logger.info(f"风险评估师 {self.agent_id} 执行成功")
            return {
                output_key: report
            }

        except Exception as e:
            logger.error(f"风险评估师 {self.agent_id} 执行失败: {e}", exc_info=True)
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
        同时可以访问技术面和基本面的分析结果（因为风险分析在它们之后执行）
        
        Args:
            ticker: 股票代码（从position_info中提取）
            analysis_date: 分析日期
            reports: 各类数据（position_info, capital_info, market_data等）
            historical_context: 历史上下文
            state: 当前状态
            
        Returns:
            用户提示词
        """
        position_info = state.get("position_info", {})
        capital_info = state.get("capital_info", {})
        market_data = state.get("market_data", {})
        stock_report = state.get("stock_analysis_report", {})
        
        # 🔧 新增：可以访问技术面和基本面的分析结果（因为风险分析在它们之后执行）
        technical_analysis_raw = state.get("technical_analysis", "")
        fundamental_analysis_raw = state.get("fundamental_analysis", "")
        
        # 🔧 修复：确保 technical_analysis 和 fundamental_analysis 是字符串类型
        # 如果它们是字典或其他类型，转换为字符串
        if isinstance(technical_analysis_raw, str):
            technical_analysis = technical_analysis_raw
        elif technical_analysis_raw:
            technical_analysis = str(technical_analysis_raw)
        else:
            technical_analysis = ""
        
        if isinstance(fundamental_analysis_raw, str):
            fundamental_analysis = fundamental_analysis_raw
        elif fundamental_analysis_raw:
            fundamental_analysis = str(fundamental_analysis_raw)
        else:
            fundamental_analysis = ""
        
        code = position_info.get("code", ticker)
        name = position_info.get("name", "N/A")
        
        # 检查是否有缓存报告
        has_cache = stock_report.get("has_cache", False)
        logger.info(f"🔧 [风险评估师] 检查缓存状态: has_cache={has_cache}, code={code}")
        
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
            logger.warning(f"⚠️ [风险评估师] context 不存在，使用降级 preference_id: {preference_id}")
        
        logger.info(f"🔧 [风险评估师] 从 context 获取 preference_id: {preference_id}")
        
        # 计算风险敞口占比
        market_value = position_info.get("market_value", 0)
        total_assets = capital_info.get("total_assets", 0)
        risk_exposure_ratio = (market_value / total_assets * 100) if total_assets > 0 else 0
        
        # 准备模板变量（支持多种变量名映射，兼容不同模板）
        from datetime import datetime
        # 🔧 修复：unrealized_pnl_pct 在数据源中已经是百分比格式（如 6.05），不需要再用 :.2% 格式化（会再次乘以100）
        # 应该使用 :.2f 格式化，然后手动添加 % 符号
        unrealized_pnl_pct_raw = position_info.get('unrealized_pnl_pct', 0)
        unrealized_pnl_pct_str = f"{unrealized_pnl_pct_raw:.2f}%" if isinstance(unrealized_pnl_pct_raw, (int, float)) else "0.00%"
        
        variables = {
            # 标准变量名
            "code": code,
            "name": name,
            "ticker": code,  # 兼容旧模板的变量名
            "company_name": name,  # 兼容旧模板的变量名
            "cost_price": f"{position_info.get('cost_price', 0):.2f}",
            "current_price": f"{position_info.get('current_price', 0):.2f}",
            "unrealized_pnl": f"{position_info.get('unrealized_pnl', 0):.2f}",
            "unrealized_pnl_pct": unrealized_pnl_pct_str,
            "market_value": f"{market_value:.2f}",
            "total_assets": f"{total_assets:.2f}",
            "risk_exposure_ratio": f"{risk_exposure_ratio:.2f}",
            "quantity": position_info.get('quantity', 0),
            "volatility": market_data.get('volatility', '未知'),
            # 日期相关
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "analysis_date": analysis_date,
            # 货币符号
            "currency_symbol": "¥",
            "currency_name": "人民币",
            # 🔧 新增：技术面和基本面分析结果（确保是字符串后再切片）
            # 🔧 修复：确保切片操作安全，避免 unhashable type: 'slice' 错误
            "technical_analysis": (technical_analysis[:2000] if isinstance(technical_analysis, str) and len(technical_analysis) > 2000 else technical_analysis) if technical_analysis else "",
            "fundamental_analysis": (fundamental_analysis[:2000] if isinstance(fundamental_analysis, str) and len(fundamental_analysis) > 2000 else fundamental_analysis) if fundamental_analysis else "",
        }
        
        # 如果有缓存，添加风险经理的决策报告（risk_management_decision）
        if has_cache:
            reports_data = stock_report.get("reports", {})
            # 🔧 修复：使用正确的字段名 risk_management_decision（风险经理的决策报告）
            risk_management_decision = reports_data.get("risk_management_decision", "")
            variables["risk_report"] = risk_management_decision  # 模板中使用 risk_report 变量名
            variables["risk_management_decision"] = risk_management_decision  # 同时提供完整字段名
            variables["has_cache"] = "true"
            logger.info(f"🔧 [风险评估师] 模板变量准备完成: risk_management_decision存在={bool(risk_management_decision)}, 长度={len(risk_management_decision) if risk_management_decision else 0}")
        else:
            variables["risk_report"] = ""
            variables["risk_management_decision"] = ""
            variables["has_cache"] = "false"
            logger.info(f"🔧 [风险评估师] 模板变量准备完成: 无缓存报告")
        
        # 尝试从数据库加载模板（preference_id 已经在 execute 方法中设置到 context 中）
        try:
            # 从 state 中提取 context（已经包含 preference_id）
            context = state.get("context") if state else None
            
            logger.info(f"🔧 [风险评估师] 传递 preference_id 到模板系统: {preference_id}")

            prompt = self._get_prompt_from_template(
                agent_type="position_analysis_v2",  # 持仓分析Agent类型 v2.0（与工作流ID一致）
                agent_name="pa_risk_v2",    # 持仓风险评估师v2.0
                variables=variables,
                context=context,  # context 已经包含 preference_id
                fallback_prompt=None
            )
            if prompt:
                logger.info(f"✅ [风险评估师] 从数据库加载提示词模板 (场景: {preference_id}, 长度: {len(prompt)})")
                return prompt
        except Exception as e:
            logger.warning(f"⚠️ [风险评估师] 从数据库加载提示词失败: {e}，使用降级提示词")
        
        # 降级：使用硬编码提示词（根据has_cache和技术面/基本面分析结果选择不同内容）
        if has_cache and (technical_analysis or fundamental_analysis):
            # 有缓存且有技术面/基本面分析结果
            reports_data = stock_report.get("reports", {})
            risk_report_content = reports_data.get("risk_report", "")
            
            # 🔧 修复：在 f-string 外进行切片操作，避免 unhashable type: 'slice' 错误
            risk_report_section = ""
            if risk_report_content:
                risk_report_text = risk_report_content[:2000] if isinstance(risk_report_content, str) else str(risk_report_content)[:2000]
                risk_report_section = f"""
=== 单股分析报告中的风险分析（参考）===
{risk_report_text}

"""
            
            # 🔧 修复：在 f-string 外进行切片操作
            technical_text = (technical_analysis[:1000] if isinstance(technical_analysis, str) and len(technical_analysis) > 1000 else technical_analysis) if technical_analysis else '暂无技术面分析结果'
            fundamental_text = (fundamental_analysis[:1000] if isinstance(fundamental_analysis, str) and len(fundamental_analysis) > 1000 else fundamental_analysis) if fundamental_analysis else '暂无基本面分析结果'
            
            return f"""请基于以下单股分析报告中的风险分析、技术面、基本面分析结果和持仓信息，进行持仓风险评估：

{risk_report_section}=== 技术面分析结果 ===
{technical_text}

=== 基本面分析结果 ===
{fundamental_text}

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 持仓数量: {position_info.get('quantity', 0)} 股
- 成本价: {position_info.get('cost_price', 0):.2f}
- 现价: {position_info.get('current_price', 0):.2f}
- 持仓市值: {market_value:.2f}
- 浮动盈亏: {position_info.get('unrealized_pnl', 0):.2f} ({position_info.get('unrealized_pnl_pct', 0):.2f}%)

=== 资金信息 ===
- 总资产: {total_assets:.2f}
- 风险敞口占比: {risk_exposure_ratio:.2f}%

请结合单股分析报告中的风险分析、技术面和基本面分析结果，撰写详细的风险评估报告，包括：
1. 风险敞口评估（参考单股分析报告中的风险分析，结合持仓情况）
2. 风险控制参考价位（参考单股分析报告中的风险分析，结合技术面支撑位和持仓成本，仅供参考）
3. 收益预期参考价位（基于技术面阻力位和基本面估值，仅供参考）
4. 波动风险分析（参考单股分析报告中的风险分析，结合持仓周期）
5. 风险等级评定（综合单股分析报告中的风险分析、技术面、基本面和持仓风险，低/中/高）"""
        else:
            # 无缓存或无技术面/基本面分析结果
            return f"""请评估以下持仓的风险：

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 持仓数量: {position_info.get('quantity', 0)} 股
- 成本价: {position_info.get('cost_price', 0):.2f}
- 现价: {position_info.get('current_price', 0):.2f}
- 持仓市值: {market_value:.2f}
- 浮动盈亏: {position_info.get('unrealized_pnl', 0):.2f} ({position_info.get('unrealized_pnl_pct', 0):.2f}%)

=== 资金信息 ===
- 总资产: {total_assets:.2f}
- 风险敞口占比: {risk_exposure_ratio:.2f}%

=== 市场数据 ===
- 波动性: {market_data.get('volatility', '未知')}

请撰写详细的风险评估报告，包括：
1. 风险敞口评估
2. 风险控制参考价位（仅供参考）
3. 收益预期参考价位（仅供参考）
4. 波动风险分析
5. 风险等级评定（低/中/高）"""

    def _get_required_reports(self) -> List[str]:
        """
        获取需要的数据列表
        
        Returns:
            数据字段名列表
        """
        return [
            "position_info",
            "capital_info",
            "market_data"
        ]

