"""
数据准备器 v2.0

智能数据准备智能体，通过 LLM 理解需求并调用工具获取数据
将准备好的数据存储在 context 中供后续智能体使用
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from ..analyst import AnalystAgent
from ..config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from ..registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class DataPreparerV2(AnalystAgent):
    """
    数据准备器 v2.0 - 智能数据准备智能体

    功能：
    - 🤖 调用 LLM 理解数据准备需求
    - 🔧 绑定所有技能化工具（市场数据、财务数据、新闻等）
    - 🎯 根据提示词智能选择需要调用的工具
    - 📦 将准备好的数据存储在 context 中
    - 🔗 后续智能体可以从 context 中读取数据

    工作流程：
    1. 读取输入参数（ticker, analysis_date, data_requirements等）
    2. LLM 理解需要准备什么数据
    3. 智能选择并调用相关工具
    4. 整理工具返回的数据
    5. 将数据存储在 context 字段中
    6. 返回准备好的上下文

    示例:
        from core.agents import create_agent
        from core.llm import UnifiedLLMClient

        llm = UnifiedLLMClient(provider="openai", model="gpt-4")
        agent = create_agent("data_preparer_v2", llm=llm)

        result = agent.execute({
            "ticker": "000001",
            "analysis_date": "2026-02-19",
            "data_requirements": "需要准备：1. 股票基本信息 2. 最近30天行情 3. 最新财务数据"
        })

        # result 包含:
        # - context: 准备好的数据上下文（Markdown格式）
        # - data_summary: 数据摘要
        # - tools_used: 使用的工具列表
    """

    metadata = AgentMetadata(
        id="data_preparer_v2",
        name="数据准备器 v2",
        description="智能数据准备智能体，通过 LLM 理解需求并调用工具获取数据，存储在 context 中供后续使用",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=["market", "fundamentals", "news", "social"],  # 默认绑定所有数据工具
        icon="🔧",
        color="#3498db",
        tags=["数据", "准备", "前处理", "智能", "v2.0"],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码", required=True),
            AgentInput(name="analysis_date", type="string", description="分析日期", required=False),
            AgentInput(name="data_requirements", type="string", description="数据需求描述", required=False),
        ],
        outputs=[
            AgentOutput(name="context", type="string", description="准备好的数据上下文"),
            AgentOutput(name="data_summary", type="string", description="数据摘要"),
            AgentOutput(name="tools_used", type="array", description="使用的工具列表"),
        ],
        requires_tools=True,
        output_field="context",
        report_label="【数据准备】",
        execution_order=0,  # 最先执行
    )

    analyst_type = "data_preparer"
    output_field = "context"

    def __init__(
        self,
        llm: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        初始化数据准备器

        Args:
            llm: LLM 客户端
            config: 智能体配置
            **kwargs: 其他参数
        """
        super().__init__(llm=llm, config=config, **kwargs)

        logger.debug(f"DataPreparerV2 初始化完成")

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
            agent_type="analysts_v2",
            agent_name="data_preparer_v2",
            variables={},
            context=None,
            fallback_prompt=None,
            state=state,
            prompt_type="system"
        )

        if prompt:
            return prompt

        # 默认提示词
        return """你是一个智能数据准备助手，负责为股票分析准备必要的数据。

你的任务：
1. 理解用户的数据需求
2. 选择合适的工具获取数据
3. 整理数据并生成结构化的上下文

可用工具：
- market: 获取市场行情数据（价格、成交量、涨跌幅等）
- fundamentals: 获取财务数据（财报、估值指标等）
- news: 获取新闻资讯
- social: 获取社交媒体情绪

输出要求：
- 以 Markdown 格式组织数据
- 包含清晰的章节标题
- 数据要准确、完整
- 突出关键信息

示例输出：
```markdown
# 数据准备报告

## 基本信息
- 股票代码: 000001
- 公司名称: 平安银行
- 所属行业: 银行

## 市场数据
- 当前价格: 12.50元
- 涨跌幅: +2.5%
- 成交量: 1000万股

## 财务数据
- 市盈率: 5.2
- 市净率: 0.8
- ROE: 12%
```
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
        data_requirements = state.get("data_requirements", "")

        # 尝试从模板系统获取提示词
        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="data_preparer_v2",
            variables={
                "ticker": ticker,
                "analysis_date": analysis_date,
                "data_requirements": data_requirements,
            },
            context=None,
            fallback_prompt=None,
            state=state,
            prompt_type="user"
        )

        if prompt:
            return prompt

        # 默认提示词
        if data_requirements:
            return f"""请为股票 {ticker} 准备以下数据（分析日期：{analysis_date}）：

{data_requirements}

请调用相关工具获取数据，并生成结构化的数据上下文。"""
        else:
            return f"""请为股票 {ticker} 准备分析所需的基础数据（分析日期：{analysis_date}）：

1. 股票基本信息（公司名称、行业、板块）
2. 最新市场数据（价格、市值、PE、PB）
3. 近期行情走势
4. 最新财务数据（如有）

请调用相关工具获取数据，并生成结构化的数据上下文。"""

