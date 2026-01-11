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
        cache_key = cache.find_cached_analysis_report(
            report_type="index_report",
            symbol="market_v2",
            trade_date=trade_date,
            max_age_hours=INDEX_REPORT_CACHE_TTL_HOURS
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
        cache.save_analysis_report(
            report_type="index_report",
            report_data=report,
            symbol="market_v2",
            trade_date=trade_date
        )
        logger.info(f"💾 [大盘分析师v2] 报告已缓存: @ {trade_date} ({INDEX_REPORT_CACHE_TTL_HOURS}小时有效)")
        return True
    except Exception as e:
        logger.warning(f"⚠️ 保存大盘分析缓存失败: {e}")
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

        Args:
            state: 工作流状态字典

        Returns:
            更新后的状态字典，包含 index_report
        """
        # 提取分析日期
        analysis_date = (
            state.get("analysis_date") or
            state.get("trade_date") or
            state.get("end_date") or
            datetime.now().strftime("%Y-%m-%d")
        )

        # 🔥 防止死循环：检查是否已经生成过报告
        existing_report = state.get("index_report", "")
        if existing_report and len(existing_report) > 100:
            logger.info(f"🌐 [大盘分析师v2] 已存在报告 ({len(existing_report)} 字符)，跳过重复分析")
            return {}

        # 📦 检查缓存：如果有有效缓存，直接返回
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

    def _build_system_prompt(self, market_type: str, context=None) -> str:
        """
        构建系统提示词

        Args:
            market_type: 市场类型（A股/港股/美股）
            context: AgentContext 对象（用于调试模式）


        Returns:
            系统提示词
        """
        # 使用基类的通用方法从模板系统获取提示词
        template_variables = {
            "market_name": market_type,
            "ticker": "",
            "company_name": "",
            "current_date": "",
            "currency_name": "人民币",
            "currency_symbol": "¥",
            "tool_names": ""
        }

        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="index_analyst_v2",
            variables=template_variables,
            context=context,
            fallback_prompt=None
        )

        if prompt:
            return prompt
        
        # 降级：使用默认提示词
        return f"""您是一位专业的大盘分析师。

您的职责是分析大盘指数走势，评估市场整体环境。

分析要点：
1. 分析主要指数的走势和趋势
2. 评估市场整体情绪和风险偏好
3. 分析市场宽度和参与度
4. 识别系统性风险和机会
5. 提供基于大盘的投资建议

请使用中文，基于真实数据进行分析。"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        tool_data: Dict[str, Any],
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词
        
        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            tool_data: 工具返回的数据
            state: 当前状态
            
        Returns:
            用户提示词
        """
        company_name = self._get_company_name(ticker, state)
        
        # 获取指数数据
        index_data = tool_data.get("get_index_data", "")
        market_breadth = tool_data.get("get_market_breadth", "")
        
        return f"""请基于以下大盘数据，对股票 {ticker}（{company_name}）所在市场进行详细的大盘分析：

=== 分析日期 ===
{analysis_date}

=== 指数数据 ===
{index_data}

=== 市场宽度数据 ===
{market_breadth}

请撰写详细的中文分析报告，包括：
1. 大盘走势分析
2. 市场情绪评估
3. 市场宽度分析
4. 系统性风险评估
5. 投资建议"""

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

