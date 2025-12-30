"""
基本面分析师 v2.0 (持仓分析)

基于ResearcherAgent基类实现的基本面分析师
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
class FundamentalAnalystV2(ResearcherAgent):
    """
    基本面分析师 v2.0 (持仓分析)
    
    功能：
    - 分析财务数据和估值水平
    - 评估行业地位和成长性
    - 判断基本面价值
    
    工作流程：
    1. 读取持仓信息和基本面报告
    2. 使用LLM分析基本面
    3. 生成基本面分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("pa_fundamental_v2", llm)

        result = agent.execute({
            "position_info": {...},
            "stock_analysis_report": {...}
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="pa_fundamental_v2",
        name="基本面分析师 v2.0",
        description="分析持仓股票的基本面，包括财务数据、估值水平、行业地位",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 不需要工具
    )

    # 研究员类型
    researcher_type = "position_fundamental"
    
    # 立场（中性）
    stance = "neutral"
    
    # 输出字段名
    output_field = "fundamental_analysis"

    def _build_system_prompt(self, stance: str, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词
        
        Args:
            stance: 立场（对于基本面分析师，始终为neutral）
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
                    agent_name="pa_fundamental_v2",  # 持仓基本面分析师v2.0
                    variables=variables,
                    preference_id="neutral",
                    fallback_prompt=None
                )
                if prompt:
                    logger.info(f"✅ 从模板系统获取基本面分析师提示词 (长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"从模板系统获取提示词失败: {e}")
        
        # 降级：使用默认提示词
        return """您是一位专业的基本面分析师。

您的职责是分析持仓股票的基本面状态。

分析要点：
1. 财务状况 - 营收、利润、现金流分析
2. 估值水平 - PE/PB/PEG等估值指标
3. 行业地位 - 竞争优势和市场份额
4. 成长性 - 未来增长潜力
5. 基本面评分 - 1-10分的基本面评分

请使用中文，基于真实数据进行分析。"""
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行基本面分析（覆盖基类方法，以便传递state给_build_system_prompt）
        """
        logger.info(f"开始执行基本面分析师: {self.agent_id}")

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

            logger.info(f"基本面分析师 {self.agent_id} 执行成功")
            return {
                output_key: report
            }

        except Exception as e:
            logger.error(f"基本面分析师 {self.agent_id} 执行失败: {e}", exc_info=True)
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
        
        Args:
            ticker: 股票代码（从position_info中提取）
            analysis_date: 分析日期
            reports: 各类数据（position_info, stock_analysis_report等）
            historical_context: 历史上下文
            state: 当前状态
            
        Returns:
            用户提示词
        """
        position_info = state.get("position_info", {})
        stock_report = state.get("stock_analysis_report", {})
        
        code = position_info.get("code", ticker)
        name = position_info.get("name", "N/A")
        
        # 检查是否有缓存报告
        has_cache = stock_report.get("has_cache", False)
        logger.info(f"🔧 [基本面分析师] 检查缓存状态: has_cache={has_cache}, code={code}")
        
        # 从state中获取用户偏好（风格偏好：aggressive/neutral/conservative）
        # 如果没有，默认使用neutral
        user_preference = state.get("user_preference", "neutral")
        logger.info(f"🔧 [基本面分析师] 用户偏好: user_preference={user_preference}")
        
        # 组合生成preference_id：缓存场景_风格偏好
        # 例如：with_cache_aggressive, without_cache_neutral 等
        cache_scenario = "with_cache" if has_cache else "without_cache"
        preference_id = f"{cache_scenario}_{user_preference}"
        logger.info(f"🔧 [基本面分析师] 组合preference_id: {cache_scenario}_{user_preference} -> {preference_id}")
        
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
            "industry": position_info.get('industry', '未知'),
            "cost_price": f"{cost_price:.2f}",
            "current_price": f"{current_price:.2f}",
            "unrealized_pnl_pct": f"{position_info.get('unrealized_pnl_pct', 0):.2%}",
            "holding_days": position_info.get('holding_days', 0),
            # 日期相关
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "analysis_date": analysis_date,
            # 货币符号
            "currency_symbol": "¥",
            "currency_name": "人民币",
            # 其他持仓信息
            "quantity": position_info.get('quantity', 0),
            "market_value": f"{position_info.get('market_value', 0):.2f}",
        }
        
        # 如果有缓存，添加基本面报告内容（模板会根据是否有内容来显示）
        if has_cache:
            reports_data = stock_report.get("reports", {})
            fundamentals_report_content = reports_data.get("fundamentals_report", "")[:2000]
            variables["fundamentals_report"] = fundamentals_report_content
            variables["has_cache"] = "true"  # 标志位，模板可以用这个判断
            logger.info(f"🔧 [基本面分析师] 模板变量准备完成: fundamentals_report存在=True, 长度={len(fundamentals_report_content)}")
        else:
            variables["fundamentals_report"] = ""  # 空字符串，模板不会显示这部分
            variables["has_cache"] = "false"
            logger.info(f"🔧 [基本面分析师] 模板变量准备完成: fundamentals_report存在=False")
        
        # 尝试从数据库加载模板（组合的preference_id：缓存场景_风格偏好）
        if get_agent_prompt:
            try:
                prompt = get_agent_prompt(
                    agent_type="position_analysis_v2",  # 持仓分析Agent类型 v2.0（与工作流ID一致）
                    agent_name="pa_fundamental_v2", # 持仓基本面分析师v2.0
                    variables=variables,
                    preference_id=preference_id,  # 组合的preference_id：缓存场景_风格偏好（如with_cache_aggressive）
                    fallback_prompt=None
                )
                if prompt:
                    logger.info(f"✅ [基本面分析师] 从数据库加载提示词模板 (场景: {preference_id}, 长度: {len(prompt)})")
                    return prompt
            except Exception as e:
                logger.warning(f"⚠️ [基本面分析师] 从数据库加载提示词失败: {e}，使用降级提示词")
        
        # 降级：使用硬编码提示词（根据has_cache选择不同内容）
        if has_cache:
            reports_data = stock_report.get("reports", {})
            fundamentals_report = reports_data.get("fundamentals_report", "")[:2000]
            return f"""请基于以下单股基本面分析报告和持仓信息，进行持仓基本面分析：

=== 单股基本面分析报告（参考）===
{fundamentals_report}

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 所属行业: {position_info.get('industry', '未知')}
- 成本价: {position_info.get('cost_price', 0):.2f}
- 现价: {position_info.get('current_price', 0):.2f}
- 持仓天数: {position_info.get('holding_days', 0)} 天

请结合持仓情况（成本价、持仓天数等），对基本面进行持仓视角的分析：
1. 当前基本面状态与持仓成本的关系
2. 基于持仓的基本面操作建议
3. 估值水平与持仓成本的关系
4. 成长性判断（考虑持仓周期）
5. 基本面评分（1-10分）"""
        else:
            return f"""请分析以下持仓股票的基本面：

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 所属行业: {position_info.get('industry', '未知')}
- 成本价: {position_info.get('cost_price', 0):.2f}
- 现价: {position_info.get('current_price', 0):.2f}
- 持仓天数: {position_info.get('holding_days', 0)} 天

请撰写详细的基本面分析报告，包括：
1. 财务状况分析
2. 估值水平评估
3. 行业地位分析
4. 成长性判断
5. 基本面评分（1-10分）"""

    def _get_required_reports(self) -> List[str]:
        """
        获取需要的数据列表
        
        Returns:
            数据字段名列表
        """
        return [
            "position_info",
            "stock_analysis_report"
        ]

