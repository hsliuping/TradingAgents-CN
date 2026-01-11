"""
板块分析师 v2.0

基于AnalystAgent基类实现的板块分析师
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from core.agents.analyst import AnalystAgent
from core.agents.config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from core.agents.registry import register_agent

logger = logging.getLogger(__name__)

# ==================== 缓存配置 ====================
SECTOR_REPORT_CACHE_TTL_HOURS = 1  # 板块分析报告缓存有效期（小时）


def _get_cache_manager():
    """获取缓存管理器（延迟加载避免循环导入）"""
    try:
        from tradingagents.dataflows.cache import get_cache
        return get_cache()
    except Exception as e:
        logger.warning(f"⚠️ 无法获取缓存管理器: {e}")
        return None


def _get_sector_name(ticker: str) -> Optional[str]:
    """
    获取股票所属板块名称

    Args:
        ticker: 股票代码

    Returns:
        板块名称，如果获取失败返回 None
    """
    try:
        from tradingagents.utils.stock_utils import StockUtils
        market_info = StockUtils.get_market_info(ticker)
        if market_info.get('is_china'):
            from tradingagents.dataflows.interface import get_china_stock_info_unified
            stock_info = get_china_stock_info_unified(ticker)
            # 尝试提取行业信息
            if "所属行业:" in stock_info:
                return stock_info.split("所属行业:")[1].split("\n")[0].strip()
            elif "行业:" in stock_info:
                return stock_info.split("行业:")[1].split("\n")[0].strip()
    except Exception as e:
        logger.debug(f"获取板块名称失败: {e}")
    return None


def _get_cached_sector_report(ticker: str, trade_date: str) -> Optional[str]:
    """
    从缓存获取板块分析报告

    Args:
        ticker: 股票代码（用于确定所属板块）
        trade_date: 交易日期

    Returns:
        缓存的报告内容，如果没有命中则返回 None
    """
    cache = _get_cache_manager()
    if not cache:
        return None

    try:
        # 获取股票所属板块作为缓存键
        sector_name = _get_sector_name(ticker)
        if not sector_name:
            # 如果无法获取板块名称，使用股票代码
            sector_name = ticker

        # 使用 sector_{板块名} 作为 symbol
        cache_symbol = f"sector_{sector_name}"

        cache_key = cache.find_cached_analysis_report(
            report_type="sector_report",
            symbol=cache_symbol,
            trade_date=trade_date,
            max_age_hours=SECTOR_REPORT_CACHE_TTL_HOURS
        )
        if cache_key:
            report = cache.load_analysis_report(cache_key)
            if report and len(report) > 100:
                logger.info(f"📦 [板块分析师v2] 命中缓存: {sector_name} @ {trade_date}")
                return report
    except Exception as e:
        logger.warning(f"⚠️ 读取板块分析缓存失败: {e}")

    return None


def _save_sector_report_to_cache(ticker: str, trade_date: str, report: str) -> bool:
    """
    将板块分析报告保存到缓存

    Args:
        ticker: 股票代码
        trade_date: 交易日期
        report: 报告内容

    Returns:
        是否保存成功
    """
    cache = _get_cache_manager()
    if not cache:
        return False

    try:
        # 获取股票所属板块作为缓存键
        sector_name = _get_sector_name(ticker)
        if not sector_name:
            sector_name = ticker

        cache_symbol = f"sector_{sector_name}"

        cache.save_analysis_report(
            report_type="sector_report",
            report_data=report,
            symbol=cache_symbol,
            trade_date=trade_date
        )
        logger.info(f"💾 [板块分析师v2] 报告已缓存: {sector_name} @ {trade_date} ({SECTOR_REPORT_CACHE_TTL_HOURS}小时有效)")
        return True
    except Exception as e:
        logger.warning(f"⚠️ 保存板块分析缓存失败: {e}")
        return False


# 尝试导入股票工具
try:
    from tradingagents.utils.stock_utils import StockUtils
except ImportError:
    logger.warning("无法导入StockUtils，部分功能可能不可用")
    StockUtils = None


@register_agent
class SectorAnalystV2(AnalystAgent):
    """
    板块分析师 v2.0
    
    功能：
    - 分析行业趋势和板块轮动
    - 评估同业对比和竞争格局
    - 分析资金流向
    
    工作流程：
    1. 调用板块数据工具获取行业数据
    2. 使用LLM分析板块趋势
    3. 生成板块分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("sector_analyst_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15"
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="sector_analyst_v2",
        name="板块分析师 v2.0",
        description="分析行业趋势、板块轮动和同业对比",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=["get_sector_data", "get_fund_flow_data"],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="sector_report", type="string", description="板块分析报告"),
        ],
        requires_tools=True,
        output_field="sector_report",
        report_label="【板块分析 v2】",
    )

    # 分析师类型
    analyst_type = "sector"

    # 输出字段名
    output_field = "sector_report"

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行板块分析（带缓存）

        同一板块的分析结果会缓存1小时，避免重复分析。

        Args:
            state: 工作流状态字典

        Returns:
            更新后的状态字典，包含 sector_report
        """
        # 提取参数
        ticker = state.get("ticker") or state.get("company_of_interest")
        if not ticker and "trade_info" in state:
            trade_info = state.get("trade_info", {})
            if isinstance(trade_info, dict):
                ticker = trade_info.get("code")

        analysis_date = (
            state.get("analysis_date") or
            state.get("trade_date") or
            state.get("end_date") or
            datetime.now().strftime("%Y-%m-%d")
        )

        # 🔥 防止死循环：检查是否已经生成过报告
        existing_report = state.get("sector_report", "")
        if existing_report and len(existing_report) > 100:
            logger.info(f"🏭 [板块分析师v2] 已存在报告 ({len(existing_report)} 字符)，跳过重复分析")
            return {}

        # 📦 检查缓存：如果有有效缓存，直接返回
        if ticker:
            cached_report = _get_cached_sector_report(ticker, analysis_date)
            if cached_report:
                logger.info(f"🏭 [板块分析师v2] 使用缓存报告 ({len(cached_report)} 字符)")
                return {
                    "sector_report": cached_report,
                }

        logger.info(f"🏭 [板块分析师v2] 开始分析 {ticker} @ {analysis_date}")

        # 调用父类的 execute 方法执行实际分析
        result = super().execute(state)

        # 💾 保存到缓存
        report = result.get("sector_report", "")
        if ticker and report and isinstance(report, str) and len(report) > 100:
            _save_sector_report_to_cache(ticker, analysis_date, report)

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
        # 获取可用工具列表
        tool_names_str = ", ".join(self.tool_names) if self.tool_names else "无"
        tool_descriptions = self._get_tool_descriptions()

        # 使用基类的通用方法从模板系统获取提示词
        template_variables = {
            "market_name": market_type,
            "ticker": "",
            "company_name": "",
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "currency_name": "人民币",
            "currency_symbol": "¥",
            "tool_names": tool_names_str,
            "tool_descriptions": tool_descriptions
        }

        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="sector_analyst_v2",
            variables=template_variables,
            context=context,
            fallback_prompt=None
        )

        if prompt:
            return prompt

        # 降级：使用默认提示词（包含工具信息）
        return f"""您是一位专业的{market_type}板块/行业分析师。

## 您的职责
分析股票所属行业的整体趋势、板块轮动情况，以及与同业公司的对比分析。

## 可用工具
您可以调用以下工具获取行业和板块数据：
{tool_descriptions}

## ⚠️ 重要规则
1. **必须调用工具**：在分析之前，必须先调用相关工具获取真实数据
2. **基于数据分析**：所有结论必须基于工具返回的真实数据，不要编造数据
3. **聚焦行业视角**：从行业/板块角度分析，而非单一个股

## 分析要点
1. 所属行业的整体走势和趋势
2. 板块在市场中的相对强弱
3. 行业内主要公司的表现对比
4. 板块资金流向和热度变化
5. 行业政策和事件影响

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
        tool_data: Dict[str, Any],
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词

        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            tool_data: 工具返回的数据（当前未使用，工具由LLM自主调用）
            state: 当前状态

        Returns:
            用户提示词
        """
        company_name = self._get_company_name(ticker, state)
        market_type = state.get("market_type", "A股")

        # 构建工具调用建议
        tool_suggestions = self._get_tool_suggestions()

        return f"""## 分析任务

请对 **{ticker}（{company_name}）** 所属的行业/板块进行全面分析。

**分析日期**: {analysis_date}
**市场**: {market_type}

## 请先调用工具获取数据

{tool_suggestions}

## 分析报告要求

基于工具返回的数据，撰写详细的中文板块分析报告，包括：

1. **行业概况**
   - 股票所属行业/板块识别
   - 行业整体走势和趋势
   - 行业在市场中的地位

2. **板块表现分析**
   - 板块指数走势
   - 板块相对大盘的强弱
   - 近期板块热度变化

3. **同业对比**
   - 行业内主要公司列表
   - 个股在行业中的排名
   - 竞争格局分析

4. **资金流向**
   - 板块资金净流入/流出
   - 主力资金动向
   - 板块轮动迹象

5. **行业前景与建议**
   - 行业政策和事件影响
   - 行业发展趋势
   - 对个股的影响评估

请确保所有分析基于真实数据，结论有理有据。"""

    def _get_tool_suggestions(self) -> str:
        """生成工具调用建议"""
        if not self.tool_names:
            return "（无可用工具，请基于已有知识分析）"

        suggestions = ["请根据分析需要调用以下工具："]

        # 根据工具名称给出调用建议
        tool_hints = {
            "get_sector_data": "获取板块基础数据（行业分类、板块走势）",
            "get_fund_flow_data": "获取板块资金流向数据",
            "get_industry_comparison": "获取同业公司对比数据",
            "get_sector_stocks": "获取板块成分股列表",
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

