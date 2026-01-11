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
    - 评估仓位风险
    - 设置止损止盈
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
        description="评估持仓风险，包括仓位风险、止损止盈、波动性分析",
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

        # 使用基类的通用方法从模板系统获取提示词
        prompt = self._get_prompt_from_template(
            agent_type="position_analysis_v2",
            agent_name="pa_risk_v2",
            variables=variables,
            context=state,
            fallback_prompt=None
        )
        if prompt:
            logger.info(f"✅ 从模板系统获取风险评估师提示词 (长度: {len(prompt)})")
            return prompt

        # 降级：使用默认提示词
        return """您是一位专业的风险评估师。

您的职责是评估持仓股票的风险状态。

分析要点：
1. 仓位风险 - 当前仓位是否过重
2. 止损设置 - 建议止损价位
3. 止盈设置 - 建议止盈价位
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
        
        code = position_info.get("code", ticker)
        name = position_info.get("name", "N/A")
        
        # 计算仓位占比
        market_value = position_info.get("market_value", 0)
        total_assets = capital_info.get("total_assets", 0)
        position_ratio = (market_value / total_assets * 100) if total_assets > 0 else 0
        
        return f"""请评估以下持仓的风险：

=== 持仓信息 ===
- 股票代码: {code}
- 股票名称: {name}
- 持仓数量: {position_info.get('quantity', 0)} 股
- 成本价: {position_info.get('cost_price', 0):.2f}
- 现价: {position_info.get('current_price', 0):.2f}
- 持仓市值: {market_value:.2f}
- 浮动盈亏: {position_info.get('unrealized_pnl', 0):.2f} ({position_info.get('unrealized_pnl_pct', 0):.2%})

=== 资金信息 ===
- 总资产: {total_assets:.2f}
- 仓位占比: {position_ratio:.2f}%

=== 市场数据 ===
- 波动性: {market_data.get('volatility', '未知')}

请撰写详细的风险评估报告，包括：
1. 仓位风险评估
2. 建议止损价位
3. 建议止盈价位
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

