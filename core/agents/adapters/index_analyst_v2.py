"""
大盘分析师 v2.0

基于AnalystAgent基类实现的大盘分析师
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from core.agents.analyst import AnalystAgent
from core.agents.config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from core.agents.registry import register_agent

logger = logging.getLogger(__name__)

# ==================== 缓存配置 ====================
INDEX_REPORT_CACHE_TTL_HOURS = 1  # 大盘分析报告缓存有效期（小时）


def _get_cache_manager():
    """获取缓存管理器（延迟加载避免循环导入）"""
    try:
        from tradingagents.dataflows.cache import get_cache
        return get_cache()
    except Exception as e:
        logger.warning(f"⚠️ 无法获取缓存管理器: {e}")
        return None


def _get_cached_index_report(trade_date: str) -> Optional[str]:
    """
    从缓存获取大盘分析报告

    Args:
        trade_date: 交易日期

    Returns:
        缓存的报告内容，如果没有命中则返回 None
    """
    cache = _get_cache_manager()
    if not cache:
        return None

    try:
        # 大盘分析不依赖具体股票，使用 "market_v2" 作为 symbol 区分 v1.x
        # 🔑 确保 max_age_hours 是整数
        max_age_hours = int(INDEX_REPORT_CACHE_TTL_HOURS) if INDEX_REPORT_CACHE_TTL_HOURS else 1
        
        cache_key = cache.find_cached_analysis_report(
            report_type="index_report",
            symbol="market_v2",
            trade_date=trade_date,
            max_age_hours=max_age_hours
        )
        if cache_key:
            report = cache.load_analysis_report(cache_key)
            if report and len(report) > 100:
                logger.info(f"📦 [大盘分析师v2] 命中缓存: @ {trade_date}")
                return report
    except Exception as e:
        logger.warning(f"⚠️ 读取大盘分析缓存失败: {e}")

    return None


def _save_index_report_to_cache(trade_date: str, report: str) -> bool:
    """
    将大盘分析报告保存到缓存

    Args:
        trade_date: 交易日期
        report: 报告内容

    Returns:
        是否保存成功
    """
    cache = _get_cache_manager()
    if not cache:
        return False

    try:
        # 🔍 调试日志：记录缓存参数
        logger.debug(f"💾 [大盘分析师v2] 准备缓存: trade_date={trade_date}, "
                     f"trade_date_type={type(trade_date).__name__}, report_len={len(report)}")

        cache.save_analysis_report(
            report_type="index_report",
            report_data=report,
            symbol="market_v2",
            trade_date=trade_date
        )
        logger.info(f"💾 [大盘分析师v2] 报告已缓存: @ {trade_date} ({INDEX_REPORT_CACHE_TTL_HOURS}小时有效)")
        return True
    except Exception as e:
        # 🔍 增强错误日志：记录完整堆栈
        import traceback
        logger.warning(f"⚠️ 保存大盘分析缓存失败: {e}\n参数: trade_date={trade_date}, "
                       f"trade_date_type={type(trade_date).__name__}\n堆栈: {traceback.format_exc()}")
        return False

# 尝试导入股票工具
try:
    from tradingagents.utils.stock_utils import StockUtils
except ImportError:
    logger.warning("无法导入StockUtils，部分功能可能不可用")
    StockUtils = None


@register_agent
class IndexAnalystV2(AnalystAgent):
    """
    大盘分析师 v2.0
    
    功能：
    - 分析大盘指数走势
    - 评估市场整体环境
    - 分析市场风险和机会
    
    工作流程：
    1. 调用指数数据工具获取大盘数据
    2. 使用LLM分析大盘趋势
    3. 生成大盘分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("index_analyst_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15"
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="index_analyst_v2",
        name="大盘分析师 v2.0",
        description="分析大盘指数走势，评估市场整体环境",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=["get_index_data", "get_market_breadth"],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="index_report", type="string", description="大盘分析报告"),
        ],
        requires_tools=True,
        output_field="index_report",
        report_label="【大盘分析 v2】",
    )

    # 分析师类型
    analyst_type = "index"

    # 输出字段名
    output_field = "index_report"

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行大盘分析（带缓存）

        大盘分析结果会缓存1小时，避免重复分析。
        调试模式下跳过缓存，直接生成新报告。

        Args:
            state: 工作流状态字典

        Returns:
            更新后的状态字典，包含 index_report
        """
        # 提取分析日期
        raw_date = (
            state.get("analysis_date") or
            state.get("trade_date") or
            state.get("end_date") or
            datetime.now()
        )
        # 确保是字符串格式 YYYY-MM-DD
        if hasattr(raw_date, 'strftime'):
            analysis_date = raw_date.strftime("%Y-%m-%d")
        else:
            # 可能是 "2026-01-14 00:00:00" 或 "2026-01-14T00:00:00"
            analysis_date = str(raw_date).split()[0].split('T')[0]

        # 🔥 检查是否为调试模式或跳过缓存
        is_debug_mode = False
        skip_cache = state.get("skip_cache", False)  # 🆕 支持显式跳过缓存
        context = state.get("context") or state.get("agent_context")

        # 🔍 调试：打印 context 信息
        logger.info(f"🔍 [大盘分析师v2] state keys: {list(state.keys())}")
        logger.info(f"🔍 [大盘分析师v2] skip_cache from state: {skip_cache}")
        logger.info(f"🔍 [大盘分析师v2] context={context}, type={type(context)}")

        if context:
            if hasattr(context, 'is_debug_mode'):
                is_debug_mode = context.is_debug_mode
                logger.info(f"🔍 [大盘分析师v2] is_debug_mode from context (object): {is_debug_mode}")
            elif isinstance(context, dict):
                is_debug_mode = context.get('is_debug_mode', False)
                logger.info(f"🔍 [大盘分析师v2] is_debug_mode from context (dict): {is_debug_mode}")

        # 🔥 防止死循环：检查是否已经生成过报告（调试模式下也检查）
        existing_report = state.get("index_report", "")
        if existing_report and len(existing_report) > 100:
            logger.info(f"🌐 [大盘分析师v2] 已存在报告 ({len(existing_report)} 字符)，跳过重复分析")
            return {}

        # 📦 检查缓存：调试模式或 skip_cache 时跳过缓存
        if is_debug_mode or skip_cache:
            logger.info(f"🔧 [大盘分析师v2] 跳过缓存 (debug={is_debug_mode}, skip_cache={skip_cache})")
        else:
            cached_report = _get_cached_index_report(analysis_date)
            if cached_report:
                logger.info(f"🌐 [大盘分析师v2] 使用缓存报告 ({len(cached_report)} 字符)")
                return {
                    "index_report": cached_report,
                }

        logger.info(f"🌐 [大盘分析师v2] 开始分析 @ {analysis_date}")

        # 调用父类的 execute 方法执行实际分析
        result = super().execute(state)

        # 💾 保存到缓存
        report = result.get("index_report", "")
        if report and isinstance(report, str) and len(report) > 100:
            _save_index_report_to_cache(analysis_date, report)

        return result

    def _build_system_prompt(self, market_type: str = None, context=None, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词（参考 fundamentals_analyst_v2 的实现）

        Args:
            market_type: 市场类型（A股/港股/美股）（保留以兼容基类）
            context: AgentContext 对象（用于调试模式）
            state: 工作流状态（用于提取模板变量）

        Returns:
            系统提示词
        """
        logger.info("🔍 [IndexAnalystV2] 开始构建系统提示词")
        
        if state is None:
            state = {}
        
        # 从 state 中提取必要的变量（如果系统提示词模板需要）
        # 注意：虽然系统提示词通常不需要变量，但某些模板可能需要 ticker、current_date 等
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        template_variables = {}
        
        # 如果 state 中有 ticker 和 analysis_date，提取它们（系统提示词模板可能需要）
        if "ticker" in state:
            template_variables["ticker"] = state["ticker"]
        if "analysis_date" in state or "trade_date" in state:
            analysis_date = state.get("analysis_date") or state.get("trade_date")
            if analysis_date:
                # 确保日期格式正确
                if isinstance(analysis_date, str) and len(analysis_date) > 10:
                    analysis_date = analysis_date.split()[0]
                template_variables["current_date"] = analysis_date
                template_variables["analysis_date"] = analysis_date
        
        # 使用基类的通用方法从模板系统获取提示词（参考 research_manager_v2）
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="index_analyst_v2",
            variables=template_variables,  # 传递必要的变量
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=context or state.get("context"),  # 优先使用传入的 context，否则从 state 获取
            fallback_prompt=None,
            prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
        )
        
        logger.info(f"📝 系统提示词长度: {len(prompt)} 字符")

        if prompt:
            return prompt

        # 降级：使用默认提示词（包含工具信息）
        return f"""您是一位专业的{market_type}大盘分析师。

## 您的职责
分析大盘指数走势，评估市场整体环境，为投资决策提供宏观背景分析。

## 可用工具
您可以调用以下工具获取实时市场数据：
{tool_descriptions}

## ⚠️ 重要规则
1. **必须调用工具**：在分析之前，必须先调用相关工具获取真实数据
2. **基于数据分析**：所有结论必须基于工具返回的真实数据，不要编造数据
3. **多维度分析**：尽量调用多个工具，从不同维度分析市场状态

## 分析要点
1. 大盘指数走势和趋势（上证、深证、创业板等）
2. 市场技术面分析（MACD、RSI、KDJ等技术指标）
3. 资金流向分析（北向资金、两融余额）
4. 市场情绪和风险偏好（涨跌停统计、市场宽度）
5. 市场周期判断（牛熊阶段、估值水平）

## 输出格式
请使用中文撰写分析报告，结构清晰、数据准确、结论明确。"""

    def _get_tool_descriptions(self) -> str:
        """获取工具描述信息"""
        if not self._langchain_tools:
            return "（无可用工具）"

        descriptions = []
        for tool in self._langchain_tools:
            name = getattr(tool, 'name', 'unknown')
            desc = getattr(tool, 'description', '无描述')
            # 截取描述的前100字符
            if len(desc) > 100:
                desc = desc[:100] + "..."
            descriptions.append(f"- **{name}**: {desc}")

        return "\n".join(descriptions)

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        tool_data: Dict[str, Any],  # 保留参数以兼容基类，但工具数据会通过 ToolMessage 传递
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词（参考 research_manager_v2 和 fundamentals_analyst_v2 的实现）

        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            tool_data: 工具返回的数据（保留以兼容基类，但工具数据会通过 ToolMessage 传递）
            state: 工作流状态（用于提取模板变量）

        Returns:
            用户提示词
        """
        logger.info("🔍 [IndexAnalystV2] 开始构建用户提示词")
        logger.info(f"📊 股票代码: {ticker}")
        logger.info(f"📅 分析日期: {analysis_date}")
        
        if state is None:
            state = {}
        
        # 获取公司名称和市场信息
        company_name = self._get_company_name(ticker, state)
        market_type = state.get("market_type", "A股")
        market_name = market_type
        currency_name = "人民币"
        currency_symbol = "¥"
        
        if StockUtils and ticker:
            try:
                market_info = StockUtils.get_market_info(ticker)
                market_name = market_info.get('market_name', market_type)
                currency_name = market_info.get('currency_name', "人民币")
                currency_symbol = market_info.get('currency_symbol', "¥")
            except Exception as e:
                logger.warning(f"获取市场信息失败: {e}")
        
        # 准备模板变量（参考 research_manager_v2 的实现）
        template_variables = {
            "ticker": ticker,
            "company_name": company_name,
            "market_name": market_name,
            "market_type": market_type,
            "analysis_date": analysis_date,
            "current_date": analysis_date,
            "start_date": "",  # 可以计算1年前的日期
            "currency_name": currency_name,
            "currency_symbol": currency_symbol,
            "tool_names": ", ".join([t.name for t in self._langchain_tools]) if self._langchain_tools else ""
        }
        
        # 使用基类的通用方法获取用户提示词（参考 research_manager_v2）
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        # 🔑 注意：工具返回的数据会通过 ToolMessage 传递，不需要在 user_prompt 中检查
        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="index_analyst_v2",
            variables=template_variables,
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context"),  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="user"  # 🔑 明确指定获取用户提示词
        )
        
        if prompt:
            logger.info(f"✅ 从模板系统获取大盘分析师 v2.0 用户提示词 (长度: {len(prompt)})")
            logger.info(f"📝 用户提示词前500字符:\n{prompt[:500]}...")
            return prompt
        
        # 降级：使用默认提示词（不再检查 tool_data，因为工具数据会通过 ToolMessage 传递）
        logger.warning("⚠️ 未从模板系统获取到用户提示词，使用默认提示词")
        # 🔑 关键：在默认提示词中明确告诉LLM要使用什么参数调用工具
        return f"""## 分析任务

请对 **{ticker}（{company_name}）** 所在的{market_type}市场进行全面的大盘分析。

**分析日期**: {analysis_date}

**重要提示**：调用工具时，必须使用以下参数：
- get_china_market_overview: curr_date='{analysis_date}'
- get_index_data: trade_date='{analysis_date}', lookback_days=60
- get_market_breadth: trade_date='{analysis_date}'
- get_north_flow: trade_date='{analysis_date}', lookback_days=10
- get_margin_trading: trade_date='{analysis_date}', lookback_days=10
- get_limit_stats: trade_date='{analysis_date}'
- get_index_technical: trade_date='{analysis_date}', lookback_days=60
- get_market_environment: trade_date='{analysis_date}'
- identify_market_cycle: trade_date='{analysis_date}'

**必须使用上述参数值**，不要使用其他日期。

请调用工具获取市场数据，然后生成详细的大盘分析报告。"""

    def _get_tool_suggestions(self, market_type: str) -> str:
        """根据市场类型生成工具调用建议"""
        if not self.tool_names:
            return "（无可用工具，请基于已有知识分析）"

        suggestions = ["请根据分析需要调用以下工具："]

        # 根据工具名称给出调用建议
        tool_hints = {
            "get_index_data": "获取指数走势和均线数据",
            "get_market_breadth": "获取市场宽度（成交量、涨跌家数）",
            "get_market_environment": "获取市场环境（估值、波动率）",
            "identify_market_cycle": "识别当前市场周期阶段",
            "get_north_flow": "获取北向资金流向（仅A股）",
            "get_margin_trading": "获取两融余额数据（仅A股）",
            "get_limit_stats": "获取涨跌停统计（仅A股）",
            "get_index_technical": "获取技术指标（MACD/RSI/KDJ）",
        }

        for tool_name in self.tool_names:
            hint = tool_hints.get(tool_name, "获取相关数据")
            suggestions.append(f"- `{tool_name}`: {hint}")

        return "\n".join(suggestions)

    def _get_company_name(self, ticker: str, state: Dict[str, Any]) -> str:
        """获取公司名称"""
        # 优先从state获取
        if "company_name" in state:
            return state["company_name"]
        
        # 使用StockUtils获取
        if StockUtils:
            try:
                market_info = StockUtils.get_market_info(ticker)
                if market_info.get('is_china'):
                    from tradingagents.dataflows.interface import get_china_stock_info_unified
                    stock_info = get_china_stock_info_unified(ticker)
                    if "股票名称:" in stock_info:
                        return stock_info.split("股票名称:")[1].split("\n")[0].strip()
            except Exception as e:
                logger.debug(f"获取公司名称失败: {e}")
        
        return f"股票{ticker}"

