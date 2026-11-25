"""
基本面分析师智能体 v2.0

基于 BaseAgent 的插件化架构实现
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from ..base import BaseAgent
from ..config import AgentConfig, AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from ..registry import register_agent

# 不再需要直接导入 get_agent_prompt，使用基类的 _get_prompt_from_template 方法

# 导入股票工具类
try:
    from tradingagents.utils.stock_utils import StockUtils
except ImportError:
    StockUtils = None

logger = logging.getLogger(__name__)


@register_agent
class FundamentalsAnalystAgentV2(BaseAgent):
    """
    基本面分析师智能体 v2.0

    特性:
    - 使用 LangChain LLM
    - 动态工具绑定（从配置或数据库加载）
    - 支持工具调用

    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent_with_dynamic_tools

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent_with_dynamic_tools("fundamentals_analyst_v2", llm)

        result = agent.execute({
            "ticker": "000001.SZ",
            "trade_date": "2024-12-01"
        })
    """

    # 创建 v2 专用的元数据（使用不同的 ID）
    metadata = AgentMetadata(
        id="fundamentals_analyst_v2",
        name="基本面分析师 v2.0",
        description="分析公司财务数据、盈利能力、成长性和基本面指标，涵盖护城河/竞争优势评估和管理层质量分析",
        category=AgentCategory.ANALYST,
        license_tier=LicenseTier.FREE,
        default_tools=["get_stock_fundamentals_unified", "get_financial_statements", "get_cash_flow_statement", "get_peer_comparison"],
        max_tool_calls=4,
        version="2.0.0",
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="fundamentals_report", type="string", description="基本面分析报告"),
        ],
        requires_tools=True,
        output_field="fundamentals_report",
        report_label="【基本面分析 v2】",
        workflow_stage="analyst",
        growth_role="extractor",
        growth_outputs=["fundamentals_report"],
        memory_scope_hint="object_tracking",
        review_level="auto_pending",
        growth_source_type="analysis_report",
    )

    # 🔑 类级别属性（与其他适配器保持一致，供执行轨迹分类使用）
    analyst_type = "fundamentals"
    output_field = "fundamentals_report"

    def __init__(
        self,
        config: Optional[Any] = None,
        llm: Optional[BaseChatModel] = None,
        tool_ids: Optional[list] = None
    ):
        """
        初始化基本面分析师
        
        Args:
            config: Agent 配置（可选）
            llm: LangChain LLM 实例
            tool_ids: 工具 ID 列表（可选，如果不提供则从配置加载）
        """
        super().__init__(config=config, llm=llm, tool_ids=tool_ids)
        
        # 如果没有提供 tool_ids，从配置加载
        if tool_ids is None and llm is not None:
            tool_ids = self.load_tools_from_config()
            if tool_ids:
                self._load_tools_v2(tool_ids)
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行基本面分析（使用 BaseAgent 标准化工具调用循环）

        Args:
            state: 包含以下键的状态字典:
                - ticker: 股票代码
                - trade_date: 交易日期
                - messages: 消息历史（可选）
                - prompt_overrides: 提示词覆盖（可选，用于调试）

        Returns:
            更新后的状态，包含:
                - fundamentals_report: 基本面分析报告
                - messages: 更新的消息历史
        """
        # P1: 启动执行轨迹采集
        from core.agents.execution_trace_recorder import (
            start_execution_trace, is_trace_enabled
        )
        recorder = None
        if is_trace_enabled():
            try:
                recorder = start_execution_trace(self, state)
                self._last_trace_id = recorder.trace_id
            except Exception as e:
                logger.warning(f"⚠️ [{self.agent_id}] 启动轨迹采集失败（不影响 agent）: {e}")
                self._last_trace_id = None

        try:
            ticker, trade_date = self._extract_common_params(state)
            context = state.get("context")

            # 支持提示词覆盖（用于调试）
            overrides = state.get("prompt_overrides") or {}
            system_override = overrides.get("system")
            user_override = overrides.get("user")
            analysis_override = overrides.get("analysis")

            if not ticker:
                raise ValueError("缺少必需参数: ticker 或 company_of_interest")

            logger.info(f"开始基本面分析: {ticker} (日期: {trade_date})")

            # 构建系统提示词（优先级：覆盖 > 模板 > 默认）
            system_prompt = system_override
            if not system_prompt:
                system_prompt = self._build_system_prompt(state)

            # 构建用户提示词（优先级：覆盖 > 默认）
            user_prompt = user_override
            if not user_prompt:
                user_prompt = self._build_user_prompt(ticker, trade_date, state)

            system_prompt = self._apply_global_trading_advice_guard(system_prompt)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            # P1: 记录 Prompt
            if recorder:
                try:
                    recorder.record_inputs({"ticker": ticker, "trade_date": trade_date})
                    recorder.record_prompts(system_prompt, user_prompt)
                except Exception as e:
                    logger.debug(f"[{self.agent_id}] 记录 Prompt 失败（不影响 agent）: {e}")

            # 使用 BaseAgent 标准化的工具调用方法
            if self._llm:
                analysis_prompt = analysis_override or self._build_analysis_prompt(ticker)
                prefetched_message, prefetched_tool_names = self._build_prefetched_tool_message(ticker, trade_date, state)
                if prefetched_message:
                    messages.append(prefetched_message)

                original_tools = list(self._langchain_tools)
                if prefetched_tool_names:
                    self._langchain_tools = [
                        tool for tool in original_tools
                        if getattr(tool, "name", "") not in prefetched_tool_names
                    ]

                # 使用默认提示词（模板中已包含详细的分析要求和输出格式）
                # 除非用户通过 prompt_overrides 覆盖
                try:
                    analysis = self.invoke_with_tools(messages, analysis_prompt=analysis_prompt)
                finally:
                    self._langchain_tools = original_tools
            else:
                # 降级：没有 LLM 或工具
                logger.warning("没有配置 LLM 或工具，返回模拟结果")
                analysis = self._generate_mock_report(ticker, trade_date)

            # P1: 记录解析后的输出
            if recorder:
                try:
                    recorder.record_parsed_output({"report": analysis[:500] if isinstance(analysis, str) else str(analysis)[:500]})
                except Exception as e:
                    logger.debug(f"[{self.agent_id}] 记录解析输出失败（不影响 agent）: {e}")

            logger.info(f"✅ 基本面分析完成，报告长度: {len(analysis)} 字符")

            # 只返回新增的字段，避免覆盖并行节点的更新
            result = {"fundamentals_report": analysis}
            # 🆕 附带工具调用摘要
            tool_summary = self._format_tool_call_summary()
            if tool_summary:
                result["tool_call_summaries"] = {self.agent_id: tool_summary}
            return result

        except Exception as e:
            logger.error(f"基本面分析执行失败: {e}", exc_info=True)
            # P1: 记录异常
            if recorder:
                try:
                    recorder.record_error(e)
                except Exception:
                    pass
            raise
        finally:
            # P1: 完成轨迹采集并写入 MongoDB（非阻塞）
            if recorder:
                try:
                    recorder.finish()
                except Exception:
                    pass

    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词（参考 research_manager_v2 的实现）

        Args:
            state: 工作流状态（用于提取模板变量）

        Returns:
            系统提示词
        """
        logger.info("🔍 [FundamentalsAnalystV2] 开始构建系统提示词")
        
        if state is None:
            state = {}

        # 使用基类的通用方法从模板系统获取提示词（参考 research_manager_v2）
        # 从 state 中提取必要的变量（如果系统提示词模板需要）
        template_variables = {}
        if state:
            # 提取 ticker 和 company_name
            if "ticker" in state:
                template_variables["ticker"] = state["ticker"]
            if "company_name" in state:
                template_variables["company_name"] = state["company_name"]
            # 提取日期
            if "analysis_date" in state or "trade_date" in state:
                analysis_date = state.get("analysis_date") or state.get("trade_date")
                if analysis_date:
                    # 确保日期格式正确
                    if isinstance(analysis_date, str) and len(analysis_date) > 10:
                        analysis_date = analysis_date.split()[0]
                    template_variables["current_date"] = analysis_date
                    template_variables["analysis_date"] = analysis_date
        
        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="fundamentals_analyst_v2",
            variables=template_variables,  # 传递必要的变量
            state=state,  # 🔑 传递 state，基类会自动提取系统变量（current_price, industry 等）
            context=state.get("context") if state else None,  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
        )

        logger.info(f"📝 系统提示词长度: {len(prompt)} 字符")
        if prompt:
            logger.info(f"📝 系统提示词前500字符:\n{prompt[:500]}...")
            logger.info(f"✅ 从模板系统获取基本面分析师 v2.0 系统提示词")
            return prompt
        
        # 降级：使用默认提示词
        logger.warning("⚠️ 未从模板系统获取到系统提示词，使用默认提示词")
        return """你是一位专业客观的股票基本面分析师，负责为研究流程提供可复核的财务与经营证据，并进行平衡的财务分析。

    你的任务是：
    1. 使用工具获取公司的整体基本面、最近季度财报明细、现金流信息以及必要的同行估值对比
    2. 结合行业特征分析财务健康度、盈利能力、经营弹性、经营质量与现金流匹配度
    3. 评估估值所处背景，说明市场定价反映的预期以及这些因素对整体研究结论的支持或削弱作用
    4. 平衡分析机会因素与风险因素，说明结论成立的关键前提并给出简短总结

    要求：
    - 必须基于真实数据进行分析，不得使用模型自身记忆、常识补全或未在工具结果中出现的数据做判断
    - 如果工具缺少某项财务字段、估值字段或同行数据，必须明确写“工具结果未提供”或“该维度仍待验证”
    - 基本面研究默认只使用历史财务、历史估值区间和已披露经营数据；即使工具返回当前股价、涨跌幅、成交量、当前总市值等日频快照，也不得把这些字段写入正文或作为结论依据
    - 应结合行业特征和工具可得数据选择最有解释力的指标，不要求机械覆盖所有通用财务科目；若某类指标对当前行业不适用，不要把其缺失直接写成风险或数据缺口
    - 只要正文引用 PE、PE(TTM)、PB、PS(TTM) 或其他估值快照，就必须同时说明该估值对应的快照日期；若不同指标日期不同，应分别写明，不能默认视为同一天
    - 如果工具结果中的估值快照日期早于分析日期，必须使用工具返回的实际估值快照日期，不得写成“截至分析日期”或用分析日期替代估值日期
    - 如果工具明确提示“当前尚无当日收盘后日频数据”或“已按前一可用交易日口径执行”，正文必须显式说明当日收盘数据尚未稳定，本次估值或同行分析按前一可用交易日数据完成，不能只改日期不解释原因
    - 出现上述稳定数据回退提示时，必须在 `## 核心观察` 第一条或 `## 估值背景` 开头先写清这条日期口径说明，不能只在后文零散提及
    - 如果 get_financial_statements 或 get_cash_flow_statement 已明确给出“单季度推导”字段，优先使用这些字段描述季度变化；“原始报告期累计/快照”字段主要用于核对口径
    - 对 A 股季度财报中的营业收入、归母净利润、经营现金流等字段，默认按报告期累计口径理解，Q2/Q3/Q4 不是单季度值，不得直接相加或直接写成单季度逐季改善
    - 对 ROE、净利率等指标，默认按报告期指标快照理解；若未明确推导，不要写成单季度指标
    - 如需讨论估值，只能围绕工具明确提供的历史估值分位、历史区间或同行相对估值展开；不得把当前股价、当前总市值写进公司概况、核心观察或总结
    - 估值背景尽量拆成绝对估值、相对估值、历史分位和市场已计入预期四层，不要只写“高估/低估”
    - 说明估值溢价或折价时，优先解释其更可能对应盈利持续性、现金回收能力、竞争格局或景气位置
    - 允许引用营收增速、毛利率、净利率、ROE、ROA、经营现金流、PE、PB、PEG 等真实数值说明事实，但不得改写成合理价位、目标价、安全边际或介入区间
    - 可以写：“2025Q4 的营业收入和归母净利润属于全年累计口径，若要观察单季度变化，需要结合 Q3 累计值进一步推导。”
    - 可以写：“当前 ROE 为报告期指标快照，不宜直接解释为单季度 ROE。”
    - 可以写：“应结合行业特征选择适用指标；若某类传统周转或流动性指标不适用于当前行业，不必机械列为缺口。”
    - 可以写：“当前 PE 与 PB 同时高于同行中位数，估值溢价更可能对应市场对盈利韧性和现金回收能力的定价。”
    - 可以写：“若 PEG 明显高于可比公司，说明当前估值对增长兑现和景气延续的依赖更强。”
    - 可以写：“经营现金流弱于净利润，利润兑现质量仍待验证。”
    - 不得写：“单季度归母净利润从 Q1 的 140.96 亿元增长至 Q4 的 426.33 亿元。”
    - 不得写：“由于缺少若干通用指标，因此当前行业经营质量偏弱。”
    - 不得写：“全年累计约为四个季度净利润相加后的 1,199.38 亿元。”
    - 不得写：“当前具备明显安全边际。”
    - 不得写：“行业景气拐点临近，建议提前布局。”
    - 不得写：“合理价格区间为 18-22 元。”
    - 不得写：“若估值回落到某区间可逐步布局。”
    - 优先输出研究观察、证据、风险提示和待验证事项
    - 不得输出投资建议、目标价、价格区间、仓位建议或执行计划
    - 使用中文撰写报告"""

    def _build_user_prompt(self, ticker: str, trade_date: str, state: Dict[str, Any] = None) -> str:
        """
        构建用户提示词（参考 research_manager_v2 的实现）
        
        Args:
            ticker: 股票代码
            trade_date: 交易日期
            state: 工作流状态（用于提取模板变量）
            
        Returns:
            用户提示词
        """
        logger.info("🔍 [FundamentalsAnalystV2] 开始构建用户提示词")
        logger.info(f"📊 股票代码: {ticker}")
        logger.info(f"📅 分析日期: {trade_date}")
        
        if state is None:
            state = {}
        
        # 获取市场信息和公司名称
        market_name = "中国A股"
        company_name = str(
            state.get("company_name")
            or state.get("stock_name")
            or state.get("name")
            or ""
        )
        currency_name = "人民币"
        currency_symbol = "¥"
        
        if StockUtils and ticker:
            try:
                market_info = StockUtils.get_market_info(ticker)
                market_name = market_info.get("market_name", "中国A股")
                currency_name = market_info.get("currency_name", "人民币")
                currency_symbol = market_info.get("currency_symbol", "¥")
                market_company_name = market_info.get("company_name", "")
                if market_company_name:
                    company_name = market_company_name
            except Exception as e:
                logger.warning(f"获取市场信息失败: {e}")
        
        # 准备模板变量（参考 research_manager_v2 的实现）
        template_variables = {
            "ticker": ticker,
            "company_name": company_name,
            "market_name": market_name,
            "analysis_date": trade_date,
            "current_date": trade_date,
            "start_date": "",  # 可以计算1年前的日期
            "currency_name": currency_name,
            "currency_symbol": currency_symbol,
            "tool_names": ", ".join([t.name for t in self._langchain_tools]) if self._langchain_tools else ""
        }
        
        # 使用基类的通用方法获取用户提示词（参考 research_manager_v2）
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="fundamentals_analyst_v2",
            variables=template_variables,
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context"),  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="user"  # 🔑 明确指定获取用户提示词
        )
        
        if prompt:
            logger.info(f"✅ 从模板系统获取基本面分析师 v2.0 用户提示词 (长度: {len(prompt)})")
            logger.info(f"📝 用户提示词前500字符:\n{prompt[:500]}...")
            return prompt
        
        # 降级：使用默认提示词
        logger.warning("⚠️ 未从模板系统获取到用户提示词，使用默认提示词")
        return f"""请对股票 {ticker} 进行客观中立的基本面研究。

分析日期：{trade_date}
货币单位：{currency_name}（{currency_symbol}）

    请调用工具获取真实基本面数据，并按以下结构生成专业研究报告：
    1. 核心观察
    2. 公司概况
    3. 财务与经营信号
    4. 估值背景
    5. 机会与风险平衡
    6. 对整体研究结论的影响
    7. 总结

    建议调用顺序：
    - 先调用 get_stock_fundamentals_unified 获取整体基本面背景、历史估值区间和口径说明，不要把其中可能出现的实时快照字段写入正文
    - 再调用 get_financial_statements 获取最近季度三表和盈利质量细节
    - 再调用 get_cash_flow_statement 获取现金流与利润匹配情况
    - 对 A 股，如需补充同业估值定位，可调用 get_peer_comparison(ticker='{ticker}', trade_date='{trade_date}', top_n=10)

    重点覆盖：
    - 结合行业特征分析财务健康度、偿债能力、资本结构、流动性和现金流安全边际
    - 优先覆盖当前行业适用且工具已提供的利润率、回报率、费用率、息差或其他盈利指标
    - PE、PB、PEG 的历史区间和同行对比，并说明市场已计入了什么预期
    - 成长性与稳定性的平衡，以及机会与风险的客观权衡

    如果工具没有返回某项财务字段、估值字段或同行数据，请明确写“工具结果未提供”或“该维度仍待验证”，不得使用 LLM 自身知识补数据。
    基本面研究默认只使用历史财务、历史估值区间和已披露经营数据；即使工具返回当前股价、涨跌幅、成交量、当前总市值等日频快照，也不得写入正文或作为结论依据。
    只要正文引用 PE、PE(TTM)、PB、PS(TTM) 或其他估值快照，就必须同时注明该指标对应的快照日期；若不同指标日期不同，应分别写明。
    如果工具结果中的估值快照日期早于分析日期，必须使用工具返回的实际估值快照日期，不得写成“截至分析日期”或用分析日期替代估值日期。
    如果工具明确提示“当前尚无当日收盘后日频数据”或“已按前一可用交易日口径执行”，必须在“核心观察”第一条或“估值背景”开头先写明：当前尚无分析日对应的稳定收盘后日频数据，因此本次历史估值分位与同行估值按前一可用交易日口径分析；不能只改日期不解释原因。
    请根据行业特征和工具可得数据选择最有解释力的指标，不要求机械覆盖所有通用财务指标；若某类指标对当前行业不适用，不要把其缺失直接写成风险或数据缺口。
    如果工具已明确给出“单季度推导”字段，优先使用这些字段描述季度变化；“原始报告期累计/快照”字段主要用于核对口径。
    对 A 股季度财报中的营业收入、归母净利润、经营现金流等字段，默认按报告期累计口径解释，不得直接写成单季度逐季改善，也不得把 Q1-Q4 直接相加。
    对 ROE、净利率等指标，默认按报告期指标快照解释；若未明确推导，不要写成单季度指标。
    如需讨论估值，只能围绕工具提供的历史估值分位、历史区间或同行相对估值展开，不得把当前股价、当前总市值写进公司概况、核心观察或总结。
    如存在仍待验证事项，可在对应段落顺带一句说明，不必单列“待验证问题”。
    可以写：“应结合行业特征选择适用指标；若某类传统周转或流动性指标不适用于当前行业，不必机械列为缺口。”
    可以写：“当前 ROE 回升，但经营现金流改善尚未同步，说明盈利修复质量仍需验证。”
    可以写：“当前 PB 处于历史中枢偏上位置，反映市场对改善预期并不低。”
    可以写：“当前 PE/PB 溢价反映市场对盈利持续性和现金流质量的更高要求。”
    可以写：“若景气位置仍偏弱，当前高估值意味着后续兑现门槛更高。”
    可以写：“若需要单季度利润判断，应基于相邻报告期累计值差额单独推导。”
    不得写：“单季度收入和净利润连续四个季度逐季抬升。”
    不得写：“由于缺少若干通用指标，因此当前行业经营质量偏弱。”
    不得写：“当前存在明显安全边际。”
    不得写：“行业景气拐点已近，可提前埋伏。”
    不得写：“合理价格区间为 18-22 元。”
    不得写：“若估值回落到某区间可布局。”

    不得给出交易建议、目标价、价格区间、仓位建议或交易触发条件。
    不得添加任何署名、作者、分析师、日期或声明信息。"""

    def _build_analysis_prompt(self, ticker: str) -> str:
        """构建分析提示词"""
        return f"""基于获取的数据，请生成 {ticker} 的专业基本面研究报告，包括：

    1. 核心观察
    2. 公司概况与当前经营特征
    3. 结合行业特征分析财务健康度、盈利能力、经营质量与现金流匹配度
    4. 估值背景、历史区间与同行比较所反映的市场预期
    5. 机会与风险的平衡评估
    6. 对整体研究结论的支持或削弱作用
    7. 总结

    如果某项数据缺失，请直接写“工具结果未提供”或“该维度仍待验证”，不要自行补全。
    基本面研究默认只使用历史财务、历史估值区间和已披露经营数据；即使工具结果出现当前股价、涨跌幅、成交量、当前总市值等日频快照，也不要把这些字段写入正文或作为结论依据。
    只要正文引用 PE、PE(TTM)、PB、PS(TTM) 或其他估值快照，就必须同时注明该指标对应的快照日期；若不同指标日期不同，应分别写明。
    如果工具结果中的估值快照日期早于分析日期，必须使用工具返回的实际估值快照日期，不得写成“截至分析日期”或用分析日期替代估值日期。
    如果工具明确提示“当前尚无当日收盘后日频数据”或“已按前一可用交易日口径执行”，必须在“核心观察”第一条或“估值背景”开头先写明：当前尚无分析日对应的稳定收盘后日频数据，因此本次历史估值分位与同行估值按前一可用交易日口径分析；不能只改日期不解释原因。
    请根据行业特征和工具可得数据选择最有解释力的指标，不要求机械覆盖所有通用财务指标；若某类指标对当前行业不适用，不要把其缺失直接写成风险或数据缺口。
    如果工具已明确给出“单季度推导”字段，优先使用这些字段描述季度变化；不要把“原始报告期累计/快照”字段误写成单季度变化。
    如存在仍待验证事项，可在相关段落顺带一句说明，不必单列章节。
    估值背景尽量拆成绝对估值、相对估值、历史分位和市场已计入预期。
    如需讨论估值，只能围绕历史估值分位、历史区间或同行相对估值展开，不要写当前股价、当前总市值或其他实时快照字段。
    允许引用真实数值做事实说明，但不要把数值写成合理价位、目标价、价格区间、安全边际、景气拐点布局或交易触发条件。

    不要输出价格区间、目标价、仓位或执行建议。
    不得添加任何署名、作者、分析师、日期或声明信息。"""

    def _get_market_characteristics(self, ticker: str) -> Dict[str, Any]:
        default_market_info = {
            "is_china": True,
            "market_name": "中国A股",
        }

        if not StockUtils or not ticker:
            return default_market_info

        try:
            market_info = StockUtils.get_market_info(ticker)
            if isinstance(market_info, dict):
                return {**default_market_info, **market_info}
        except Exception as exc:
            logger.warning(f"获取股票市场信息失败，使用默认 A 股回退: {exc}")

        return default_market_info

    def _get_langchain_tool_by_name(self, tool_name: str):
        for tool in self._langchain_tools:
            if getattr(tool, "name", "") == tool_name:
                return tool
        return None

    def _invoke_prefetch_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Optional[str]:
        tool = self._get_langchain_tool_by_name(tool_name)
        if tool is None:
            logger.warning(f"预取工具未找到，跳过: {tool_name}")
            return None

        try:
            result = tool.invoke(tool_args)
        except Exception as exc:
            logger.warning(f"预取工具执行失败 {tool_name}: {exc}")
            return None

        result_text = str(result or "").strip()
        return result_text or None

    def _build_prefetched_tool_message(
        self,
        ticker: str,
        trade_date: Optional[str],
        state: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[HumanMessage], List[str]]:
        if not self._langchain_tools:
            return None, []

        effective_trade_date = trade_date or (state or {}).get("analysis_date") or datetime.now().strftime("%Y-%m-%d")
        # 🔧 确保 curr_date 类型为 str（state 中的 trade_date 可能是 datetime 对象）
        if isinstance(effective_trade_date, datetime):
            effective_trade_date = effective_trade_date.strftime("%Y-%m-%d")
        market_info = self._get_market_characteristics(ticker)
        is_china = bool(market_info.get("is_china"))

        tool_plan: List[Tuple[str, Dict[str, Any], str]] = [
            (
                "get_stock_fundamentals_unified",
                {"ticker": ticker, "curr_date": effective_trade_date},
                "整体基本面背景",
            ),
        ]
        if is_china:
            tool_plan.extend(
                [
                    (
                        "get_financial_statements",
                        {"ticker": ticker, "limit": 4},
                        "最近季度财报明细",
                    ),
                    (
                        "get_cash_flow_statement",
                        {"ticker": ticker, "limit": 4},
                        "最近季度现金流量表",
                    ),
                ]
            )

        sections: List[str] = []
        consumed_tool_names: List[str] = []
        for tool_name, tool_args, section_title in tool_plan:
            result_text = self._invoke_prefetch_tool(tool_name, tool_args)
            if not result_text:
                continue

            sections.append(f"### {section_title}（{tool_name}）\n{result_text}")
            consumed_tool_names.append(tool_name)

        if not sections:
            return None, []

        content = (
            "以下必需工具结果已预先获取。请优先基于这些结果完成分析，不要再重复调用同名工具；"
            "若仍缺少同行估值或其他补充证据，再调用剩余可选工具。\n\n"
            + "\n\n".join(sections)
        )
        return HumanMessage(content=content), consumed_tool_names

    def _generate_mock_report(self, ticker: str, trade_date: str) -> str:
        """生成模拟报告（降级方案）"""
        return f"""这是一个模拟的基本面分析报告。

股票代码: {ticker}
分析日期: {trade_date}

财务状况：良好
盈利能力：稳定
估值水平：合理
研究结论：请结合详细证据继续跟踪。"""

