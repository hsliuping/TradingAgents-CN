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

# 尝试导入模板系统
try:
    from tradingagents.utils.template_client import get_agent_prompt
except (ImportError, KeyError) as e:
    logger.warning(f"无法导入模板系统: {e}")
    get_agent_prompt = None


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
        default_tools=[],  # 不需要工具
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
        
        # 从模板系统获取提示词（持仓分析专用Agent）
        if get_agent_prompt:
            try:
                prompt = get_agent_prompt(
                    agent_type="position_analysis_v2",  # 持仓分析Agent类型 v2.0（与工作流ID一致）
                    agent_name="pa_technical_v2",    # 持仓技术面分析师v2.0
                    variables=variables,
                    preference_id="neutral",
                    fallback_prompt=None
                )
                if prompt:
                    logger.info(f"✅ 从模板系统获取技术面分析师提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取提示词失败: {e}")
        
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
        
        # 从state中获取用户偏好（风格偏好：aggressive/neutral/conservative）
        # 如果没有，默认使用neutral
        user_preference = state.get("user_preference", "neutral")
        logger.info(f"🔧 [技术面分析师] 用户偏好: user_preference={user_preference}")
        
        # 组合生成preference_id：缓存场景_风格偏好
        # 例如：with_cache_aggressive, without_cache_neutral 等
        cache_scenario = "with_cache" if has_cache else "without_cache"
        preference_id = f"{cache_scenario}_{user_preference}"
        logger.info(f"🔧 [技术面分析师] 组合preference_id: {cache_scenario}_{user_preference} -> {preference_id}")
        
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
            "unrealized_pnl_pct": f"{position_info.get('unrealized_pnl_pct', 0):.2%}",
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
        
        # 尝试从数据库加载模板（组合的preference_id：缓存场景_风格偏好）
        if get_agent_prompt:
            try:
                prompt = get_agent_prompt(
                    agent_type="position_analysis_v2",  # 持仓分析Agent类型 v2.0（与工作流ID一致）
                    agent_name="pa_technical_v2",    # 持仓技术面分析师v2.0
                    variables=variables,
                    preference_id=preference_id,  # 组合的preference_id：缓存场景_风格偏好（如with_cache_aggressive）
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
- 浮动盈亏: {position_info.get('unrealized_pnl_pct', 0):.2%}

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
- 浮动盈亏: {position_info.get('unrealized_pnl_pct', 0):.2%}

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

