"""
报告生成器 v2.0

智能报告生成 Agent，通过 LLM 理解分析结果并生成格式化的综合报告
支持多种报告样式和格式，可通过提示词模板自定义
"""

import logging
from typing import Any, Dict, List, Optional
import json
from datetime import datetime

from ..analyst import AnalystAgent
from ..config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from ..registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class ReportGeneratorV2(AnalystAgent):
    """
    报告生成器 v2.0 - 智能报告生成 Agent

    功能：
    - 🤖 调用 LLM 理解分析结果
    - 📝 生成格式化的综合分析报告
    - 🎨 支持多种报告样式（简洁版、详细版、投资者版等）
    - 🔧 通过提示词模板自定义报告格式
    - 📊 智能提取关键信息和数据
    - 🔗 整合所有分析师的输出

    工作流程：
    1. 读取所有分析师报告（market_report, fundamentals_report等）
    2. LLM 理解报告内容和关键信息
    3. 根据提示词模板生成格式化报告
    4. 输出结构化的综合报告
    5. 存储在 reports 字段中

    示例:
        from core.agents import create_agent
        from core.llm import UnifiedLLMClient

        llm = UnifiedLLMClient(provider="openai", model="gpt-4")
        agent = create_agent("report_generator_v2", llm=llm)

        result = agent.execute({
            "ticker": "000001",
            "analysis_date": "2026-02-19",
            "market_report": "...",
            "fundamentals_report": "...",
            "bull_report": "...",
            "bear_report": "...",
            "investment_plan": {...}
        })

        # result 包含:
        # - reports: 生成的报告字典
        # - report_summary: 报告摘要
        # - report_style: 使用的报告样式
    """

    metadata = AgentMetadata(
        id="report_generator_v2",
        name="报告生成器 v2",
        description="智能报告生成 Agent，通过 LLM 理解分析结果并生成格式化的综合报告",
        category=AgentCategory.ANALYST,  # 改为 ANALYST 类别（因为调用 LLM）
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 不需要工具，只处理已有数据
        icon="📝",
        color="#9b59b6",
        tags=["报告", "生成", "汇总", "智能", "v2.0"],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码", required=False),
            AgentInput(name="analysis_date", type="string", description="分析日期", required=False),
            AgentInput(name="report_style", type="string", description="报告样式（简洁/详细/投资者）", required=False),
        ],
        outputs=[
            AgentOutput(name="reports", type="dict", description="生成的报告字典"),
            AgentOutput(name="report_summary", type="string", description="报告摘要"),
        ],
    )

    # 分析师类型
    analyst_type = "report_generator"

    # 输出字段名
    output_field = "reports"
    
    # 需要提取的报告字段
    REPORT_FIELDS = [
        # 宏观分析
        'index_report',
        'sector_report',
        # 个股分析
        'market_report',
        'sentiment_report',
        'news_report',
        'fundamentals_report',
        # 研究员报告
        'bull_report',
        'bear_report',
        # 投资计划
        'investment_plan',
        'trader_investment_plan',
        'final_trade_decision',
        # 风险评估
        'risk_assessment',
    ]

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        llm: Optional[Any] = None,
        tool_ids: Optional[List[str]] = None,
        **kwargs
    ):
        """
        初始化报告生成器

        Args:
            config: Agent配置
            llm: LLM实例
            tool_ids: 工具ID列表（报告生成器不需要工具）
            **kwargs: 其他参数
        """
        super().__init__(config=config, llm=llm, tool_ids=tool_ids, **kwargs)

        logger.debug(f"ReportGeneratorV2 初始化完成")
    
    def _build_system_prompt(self, state: Dict[str, Any]) -> str:
        """
        构建系统提示词

        Args:
            state: 工作流状态

        Returns:
            系统提示词
        """
        # 尝试从模板系统获取提示词
        prompt = self._get_prompt_from_template(
            agent_type="post_processors_v2",
            agent_name="report_generator_v2",
            variables={},
            context=None,
            fallback_prompt=None,
            state=state,
            prompt_type="system"
        )

        if prompt:
            return prompt

        # 默认提示词
        return """你是一位专业的报告生成器，负责将多个分析师的输出整合为结构化的综合分析报告。

## 核心职责
1. 汇总各分析师的报告和观点
2. 提取关键信息和数据
3. 根据报告样式生成格式化输出
4. 确保报告内容客观、完整、有条理

## 工作原则
- 保持客观中立，如实呈现各方观点
- 不添加主观判断或新的分析内容
- 按照报告样式要求的格式输出
- 突出关键数据和重要结论

## 输出要求
- 结构清晰，层次分明
- 数据准确，引用明确
- 语言简洁，重点突出
- 使用 Markdown 格式组织内容

## 报告样式
- **简洁版**: 只包含核心结论和关键数据
- **详细版**: 包含完整的分析过程和详细数据
- **投资者版**: 面向投资者的专业报告，突出研究观察汇总和风险提示
"""

    def _build_user_prompt(self, state: Dict[str, Any]) -> str:
        """
        构建用户提示词

        Args:
            state: 工作流状态

        Returns:
            用户提示词
        """
        ticker = state.get("ticker") or state.get("stock_code", "")
        analysis_date = state.get("analysis_date") or datetime.now().strftime("%Y-%m-%d")
        report_style = state.get("report_style", "详细版")

        # 提取所有可用的报告
        available_reports = self._extract_reports(state)

        # 尝试从模板系统获取提示词
        prompt = self._get_prompt_from_template(
            agent_type="post_processors_v2",
            agent_name="report_generator_v2",
            variables={
                "ticker": ticker,
                "analysis_date": analysis_date,
                "report_style": report_style,
                "available_reports": ", ".join(available_reports.keys()),
            },
            context=None,
            fallback_prompt=None,
            state=state,
            prompt_type="user"
        )

        if prompt:
            return prompt

        # 默认提示词
        reports_summary = "\n".join([
            f"- **{field}**: {len(content)} 字符"
            for field, content in available_reports.items()
        ])

        return f"""请为股票 {ticker} 生成综合分析报告（分析日期：{analysis_date}）

## 报告样式
{report_style}

## 可用的分析报告
{reports_summary}

## 任务要求
1. 整合所有分析师的报告
2. 提取关键信息和数据
3. 生成结构化的综合报告
4. 使用 Markdown 格式输出

## 报告结构（建议）
1. **执行摘要** - 一句话总结
2. **市场分析** - 市场行情和技术面
3. **基本面分析** - 财务数据和估值
4. **新闻和情绪** - 新闻资讯和市场情绪
5. **研究观察汇总** - 综合研究观察和风险提示
6. **关键数据** - 重要指标和数据

请开始生成报告。
"""

    def _extract_reports(self, state: Dict[str, Any]) -> Dict[str, str]:
        """
        从状态中提取所有报告

        Args:
            state: 工作流状态

        Returns:
            报告字典 {field_name: report_content}
        """
        reports = {}

        for field in self.REPORT_FIELDS:
            content = state.get(field)
            if content:
                # 提取文本内容
                text = self._extract_text(content)
                if text and len(text.strip()) > 5:
                    reports[field] = text.strip()
                    logger.debug(f"📄 [ReportGeneratorV2] 提取报告: {field} ({len(text)} 字符)")

        return reports

    def _extract_text(self, value: Any) -> str:
        """
        从各种格式中提取文本内容

        Args:
            value: 可能是字符串、字典或其他类型

        Returns:
            提取的文本内容
        """
        if isinstance(value, str):
            return value

        if isinstance(value, dict):
            # 尝试从字典中提取文本字段
            for key in ("content", "markdown", "text", "message", "report", "summary"):
                text = value.get(key)
                if isinstance(text, str) and text.strip():
                    return text

            # 如果是结构化数据，转换为JSON
            try:
                return json.dumps(value, ensure_ascii=False, indent=2)
            except:
                return str(value)

        return str(value) if value else ""

    def _parse_response(self, response: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析 LLM 响应

        Args:
            response: LLM 响应文本
            state: 工作流状态

        Returns:
            解析后的结果字典
        """
        # 将 LLM 生成的报告存储到 reports 字段
        result = {
            **state,
            "reports": {
                "综合报告": response
            },
            "report_summary": self._extract_summary(response),
            "report_style": state.get("report_style", "详细版"),
        }

        logger.info(f"✅ [ReportGeneratorV2] 报告生成完成，长度: {len(response)} 字符")
        return result

    def _extract_summary(self, report: str) -> str:
        """
        从报告中提取摘要

        Args:
            report: 完整报告

        Returns:
            摘要文本
        """
        # 尝试提取第一段或前200字符作为摘要
        lines = report.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and len(line) > 20:
                return line[:200] + "..." if len(line) > 200 else line

        # 如果没有找到合适的摘要，返回前200字符
        return report[:200] + "..." if len(report) > 200 else report

    # ========== 辅助方法 ==========

    def _generate_structured_reports(self, reports: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        """
        生成结构化报告（保留用于向后兼容）

        Args:
            reports: 原始报告字典

        Returns:
            结构化报告字典
        """
        structured = {}

        for field, content in reports.items():
            # 尝试解析JSON格式的报告
            try:
                if content.strip().startswith("{"):
                    data = json.loads(content)
                    structured[field] = {
                        "type": "json",
                        "data": data,
                        "markdown": self._json_to_markdown(data, field)
                    }
                else:
                    structured[field] = {
                        "type": "markdown",
                        "data": content,
                        "markdown": content
                    }
            except json.JSONDecodeError:
                structured[field] = {
                    "type": "markdown",
                    "data": content,
                    "markdown": content
                }

        return structured

    def _json_to_markdown(self, data: Dict[str, Any], field_name: str) -> str:
        """
        将JSON数据转换为Markdown格式

        Args:
            data: JSON数据
            field_name: 字段名称

        Returns:
            Markdown格式的文本
        """
        lines = []

        # 添加标题
        title_map = {
            "market_report": "市场分析",
            "fundamentals_report": "基本面分析",
            "bull_report": "积极证据研究观察",
            "bear_report": "谨慎证据研究观察",
            "investment_plan": "综合研究结论",
            "risk_assessment": "风险审阅",
        }
        title = title_map.get(field_name, field_name.replace("_", " ").title())
        lines.append(f"## {title}\n")

        # 提取关键字段
        for key, value in data.items():
            if isinstance(value, (str, int, float, bool)):
                lines.append(f"**{key}**: {value}")
            elif isinstance(value, list):
                lines.append(f"**{key}**:")
                for item in value:
                    lines.append(f"- {item}")
            elif isinstance(value, dict):
                lines.append(f"**{key}**:")
                for sub_key, sub_value in value.items():
                    lines.append(f"  - {sub_key}: {sub_value}")

        return "\n".join(lines)

