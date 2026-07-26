"""
分析规划器

实现三级保障机制的规划逻辑：
1. LLM 语义匹配种子流程（最可靠）
2. LLM 基于工具列表自主规划（较可靠）
3. 规划失败时标记回退到 ReAct（保底）

依赖：
- core/agents/seed_flows.py — 种子流程定义
- core/agents/planner_models.py — 数据模型
- core/llm/unified_client.py — LLM 调用
- core/tools/registry.py — 工具注册表
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set

from core.llm import UnifiedLLMClient
from core.llm.models import Message, MessageRole
from core.tools import get_tool_registry

from .planner_models import AnalysisPlan, PlanSource, PlanStep
from .seed_flows import SeedFlow, list_seed_flows, get_seed_flow

logger = logging.getLogger(__name__)


# ============================================================
# Prompt 模板
# ============================================================

def _build_seed_match_prompt(question: str, seed_flows: List[SeedFlow]) -> str:
    """构建种子流程语义匹配 prompt"""
    flow_list = "\n".join(
        f"{i + 1}. {sf.id}: {sf.description}"
        for i, sf in enumerate(seed_flows)
    )
    return f"""你是股票分析规划器。以下是可用的分析模板：

{flow_list}

用户问题：{question}

请选择最匹配的模板编号（1-{len(seed_flows)}），如果都不匹配返回 "none"。
只返回编号或 "none"，不要解释。"""


def _build_plan_prompt(
    question: str,
    tool_descriptions: str,
    curr_date: str,
    trade_date: str,
    knowledge_snippets: str = "",
) -> str:
    """构建 LLM 自主规划 prompt

    Args:
        knowledge_snippets: RAG 检索到的动态知识片段
    """
    # 构建可选的动态知识段落
    knowledge_section = f"\n{knowledge_snippets}\n" if knowledge_snippets else ""

    return f"""你是股票分析规划器。根据用户问题，制定一个精确的分析计划。

## 可用工具

{tool_descriptions}

## 当前日期信息
- 当前日期: {curr_date}
- 最近交易日: {trade_date}

## 用户问题
{question}
{knowledge_section}
## 重要说明
- 本系统仅支持 **A股（沪深两市）** 的个股和板块分析
- **不支持**: ETF、基金、港股、美股等品种

## 金融知识 - 问题分类与推荐工具组合

**A. 板块/行业/概念类**（用户问"XX板块"、"XX概念股"、"XX行业前景"）：
- 核心工具: analyze_sector_by_name（一站式板块综合分析，参数 sector_name=板块关键词）
- 补充工具: get_sector_constituents（查成分股龙头）、get_sector_daily（查板块走势）、search_sector（搜索板块）
- 注意: "XX概念股"指同花顺概念板块(S类型)的成分股，用板块工具查询，不需要 ticker

**B. 个股分析类**（用户问"XX股票怎么样"、"帮我分析XX"）：
- 基本面: get_stock_fundamentals_unified（PE/PB/ROE/财务数据）
- 行情: get_stock_market_data_unified（价格走势/成交量）
- 技术面: get_technical_indicators（MACD/RSI/KDJ/BOLL）
- 消息面: get_stock_news_unified（新闻动态）
- 建议并行获取基本面+行情+技术面+新闻

**C. 宏观/大盘类**（用户问"大盘怎么样"、"市场环境"）：
- 快速概览: get_china_market_overview 或 get_market_overview
- 深度分析: get_index_data + get_market_breadth + get_limit_stats
- 资金面: get_north_flow（北向资金）、get_margin_trading（两融）、get_fund_flow_data（板块资金流向）

**D. 对比类**（用户问"XX和YY哪个好"、"同行业对比"）：
- 核心工具: get_peer_comparison（同业对比）
- 补充: get_stock_fundamentals_unified（各公司基本面详情）

## 要求
1. 生成一个 JSON 格式的分析计划
2. 每个步骤必须指定具体的 tool（工具 ID）和 args（参数）
3. **args 中只能使用上面工具定义中列出的参数名，不能自创参数**
4. 使用 depends_on 标记步骤间的依赖关系（无依赖的步骤可并行执行）
5. intent 字段简要说明该步骤的目的
6. 步骤数量控制在 2-5 个
7. 所有需要日期的参数使用当前日期 {curr_date} 或交易日 {trade_date}
8. **板块/行业/概念类问题优先使用板块级别工具**（analyze_sector_by_name 等），它们接受 sector_name（板块名称关键词），无需 ticker
9. 只有涉及具体个股时才使用需要 ticker 参数的工具，ticker 必须是 6 位数字的股票代码（如 601012）
10. 先判断问题属于上述 A/B/C/D 哪一类，再选择对应的推荐工具组合

## 输出格式（严格 JSON）
```json
{{
  "steps": [
    {{
      "id": 1,
      "tool": "工具ID",
      "args": {{"参数名": "参数值"}},
      "intent": "步骤意图",
      "depends_on": []
    }}
  ]
}}
```

只返回 JSON，不要其他文字。"""


def _build_tool_descriptions(tool_ids: Set[str]) -> str:
    """构建工具描述列表（用于规划 prompt）"""
    registry = get_tool_registry()
    lines = []
    for meta in registry.list_all():
        if meta.id not in tool_ids:
            continue
        params = ", ".join(
            f"{p.name}({'必需' if p.required else '可选'}): {p.description}"
            for p in meta.parameters
        )
        line = f"- **{meta.id}**: {meta.description}"
        if meta.when_to_use:
            line += f"\n  何时使用: {meta.when_to_use}"
        if params:
            line += f"\n  参数: {params}"
        lines.append(line)
    return "\n".join(lines)


def _build_simplified_tool_descriptions(tool_ids: Set[str]) -> str:
    """构建简化版工具描述（仅 ID + 描述，用于修正重试 prompt）

    修正重试场景下，过详细的参数描述可能让 LLM 再次陷入"参数选择困难"，
    因此只暴露工具 ID 和一句话描述，让 LLM 先把"用哪些工具"这一层选对。
    """
    registry = get_tool_registry()
    lines = []
    for meta in registry.list_all():
        if meta.id not in tool_ids:
            continue
        # 只保留参数名列表（不展开描述），降低 prompt 复杂度
        param_names = ", ".join(p.name for p in meta.parameters) if meta.parameters else "无"
        lines.append(f"- {meta.id}: {meta.description}（参数: {param_names}）")
    return "\n".join(lines)


def _build_correction_plan_prompt(
    question: str,
    simplified_tool_desc: str,
    curr_date: str,
    trade_date: str,
    failure_hint: str = "",
) -> str:
    """构建修正重试 prompt（v3.6.0 项7）

    与 _build_plan_prompt 的差异：
    1. 步骤数量限制从 2-5 收紧到 1-3（降低复杂度）
    2. 去掉金融知识段落（避免 LLM 在分类上浪费 token）
    3. 显式提示"上一次规划失败"，鼓励 LLM 用最简单方式重新规划
    4. 工具描述使用简化版（仅 ID + 描述 + 参数名）
    """
    hint_section = f"\n## 上次失败原因\n{failure_hint}\n" if failure_hint else ""

    return f"""上一次规划失败，请用更简单的方式重新规划。{hint_section}
## 可用工具（简化版）

{simplified_tool_desc}

## 当前日期信息
- 当前日期: {curr_date}
- 最近交易日: {trade_date}

## 用户问题
{question}

## 要求
1. 生成一个 JSON 格式的分析计划
2. 步骤数量控制在 **1-3 个**（最多 3 个，越简单越好）
3. 优先使用最常见的工具组合：基本面/行情/技术面/新闻
4. 每个步骤必须指定具体的 tool（工具 ID）和 args（参数）
5. args 中只能使用上面工具定义中列出的参数名
6. 使用 depends_on 标记步骤间的依赖关系（无依赖的步骤可并行执行）
7. intent 字段简要说明该步骤的目的
8. 所有需要日期的参数使用当前日期 {curr_date} 或交易日 {trade_date}
9. ticker 必须是 6 位数字的股票代码（如 601012）

## 输出格式（严格 JSON）
```json
{{
  "steps": [
    {{
      "id": 1,
      "tool": "工具ID",
      "args": {{"参数名": "参数值"}},
      "intent": "步骤意图",
      "depends_on": []
    }}
  ]
}}
```

只返回 JSON，不要其他文字。"""


# ============================================================
# Planner 类
# ============================================================

class Planner:
    """
    分析规划器

    实现三级保障规划逻辑：
      1. 种子流程语义匹配
      2. LLM 自主规划
      3. 标记 ReAct 回退
    """

    def __init__(
        self,
        llm_client: UnifiedLLMClient,
        curr_date: str,
        trade_date: str,
    ):
        self._llm = llm_client
        self._curr_date = curr_date
        self._trade_date = trade_date

        # 收集可用工具 ID（仅 fc_enabled 且有参数的）
        registry = get_tool_registry()
        self._valid_tool_ids: Set[str] = {
            m.id for m in registry.list_all()
            if m.fc_enabled and m.parameters
        }

    # ----------------------------------------------------------
    # 公共接口
    # ----------------------------------------------------------

    async def plan(
        self,
        question: str,
        context_messages: Optional[List[Message]] = None,
        knowledge_snippets: str = "",
    ) -> AnalysisPlan:
        """
        生成分析计划。

        Args:
            knowledge_snippets: RAG 检索到的动态知识片段

        Returns:
            AnalysisPlan — 若 source == REACT_FALLBACK 表示规划失败，应回退 ReAct
        """
        # 第一级：种子流程语义匹配
        seed_plan = await self._try_seed_match(question, context_messages)
        if seed_plan is not None:
            logger.info(f"[Planner] 种子流程匹配成功: {seed_plan.template_id}")
            return seed_plan

        # 第二级：LLM 自主规划
        llm_plan = await self._try_llm_plan(question, context_messages, knowledge_snippets)
        if llm_plan is not None:
            logger.info(f"[Planner] LLM 自主规划成功，{len(llm_plan.steps)} 个步骤")
            return llm_plan

        # 第二级补丁：规划失败修正重试1次（v3.6.0 项7）
        # 用更简单的 prompt 重新尝试生成有效计划，避免直接降级 ReAct
        corrected_plan = await self._try_llm_plan_with_correction(question, context_messages)
        if corrected_plan is not None:
            logger.info(f"[Planner] 修正重试规划成功，{len(corrected_plan.steps)} 个步骤")
            return corrected_plan

        # 第三级：标记 ReAct 回退
        logger.warning("[Planner] 规划失败（含修正重试），标记 ReAct 回退")
        return AnalysisPlan(
            question=question,
            source=PlanSource.REACT_FALLBACK,
            steps=[],
        )

    # ----------------------------------------------------------
    # 第一级：种子流程语义匹配
    # ----------------------------------------------------------

    async def _try_seed_match(
        self,
        question: str,
        context_messages: Optional[List[Message]] = None,
    ) -> Optional[AnalysisPlan]:
        """用 LLM 语义匹配种子流程，匹配成功则填充模板参数"""
        seed_flows = list_seed_flows()
        if not seed_flows:
            return None

        prompt = _build_seed_match_prompt(question, seed_flows)
        messages: List[Message] = []
        if context_messages:
            messages.extend(context_messages)
        messages.append(Message(role=MessageRole.USER, content=prompt))

        try:
            resp = await self._llm.achat(messages)
            answer = (resp.content or "").strip().lower()
            logger.info(f"[Planner] 种子匹配 LLM 返回: {answer}")

            # 解析返回值
            if answer == "none" or not answer:
                return None

            # 提取数字
            match = re.search(r"(\d+)", answer)
            if not match:
                return None

            idx = int(match.group(1)) - 1
            if idx < 0 or idx >= len(seed_flows):
                return None

            selected = seed_flows[idx]
            return await self._fill_seed_flow_async(question, selected)

        except Exception as e:
            logger.warning(f"[Planner] 种子匹配失败: {e}")
            return None

    def _fill_seed_flow(self, question: str, flow: SeedFlow) -> AnalysisPlan:
        """将种子流程模板填充为具体的 AnalysisPlan"""
        ticker = self._extract_ticker(question)
        sector_name = self._extract_sector_name(question)

        steps: List[PlanStep] = []
        for i, seed_step in enumerate(flow.steps):
            args = {}
            for k, v in seed_step.args_template.items():
                args[k] = (
                    v.replace("{ticker}", ticker)
                    .replace("{curr_date}", self._curr_date)
                    .replace("{trade_date}", self._trade_date)
                    .replace("{sector_name}", sector_name)
                )
            # depends_on 从 0-based 转为 1-based step id
            deps = [d + 1 for d in seed_step.depends_on]
            steps.append(PlanStep(
                id=i + 1,
                tool=seed_step.tool,
                args=args,
                intent=seed_step.intent,
                depends_on=deps,
            ))

        return AnalysisPlan(
            question=question,
            template_id=flow.id,
            source=PlanSource.SEED_FLOW,
            steps=steps,
        )

    async def _fill_seed_flow_async(self, question: str, flow: SeedFlow) -> AnalysisPlan:
        """将种子流程模板填充为具体的 AnalysisPlan（异步版，支持 LLM 提取 ticker 和板块名）"""
        ticker = self._extract_ticker(question)

        # 如果简单提取失败，用 LLM 提取
        if not ticker:
            ticker = await self._extract_ticker_by_llm(question)
            logger.info(f"[Planner] LLM 提取 ticker: '{ticker}'")

        # 提取板块名称（用于 {sector_name} 占位符）
        sector_name = self._extract_sector_name(question)
        logger.info(f"[Planner] 提取 sector_name: '{sector_name}'")

        steps: List[PlanStep] = []
        for i, seed_step in enumerate(flow.steps):
            args = {}
            for k, v in seed_step.args_template.items():
                args[k] = (
                    v.replace("{ticker}", ticker)
                    .replace("{curr_date}", self._curr_date)
                    .replace("{trade_date}", self._trade_date)
                    .replace("{sector_name}", sector_name)
                )
            deps = [d + 1 for d in seed_step.depends_on]
            steps.append(PlanStep(
                id=i + 1,
                tool=seed_step.tool,
                args=args,
                intent=seed_step.intent,
                depends_on=deps,
            ))

        return AnalysisPlan(
            question=question,
            template_id=flow.id,
            source=PlanSource.SEED_FLOW,
            steps=steps,
        )

    @staticmethod
    def _extract_sector_name(question: str) -> str:
        """
        从问题中提取板块/行业名称。
        规则：
        - 匹配 "XX板块"、"XX行业"、"XX概念"、"XX产业" 中的 XX
        - 也匹配常见板块关键词
        """
        # 先尝试匹配已知板块关键词 + 后缀模式（更精准）
        known_sectors = [
            "光伏", "太阳能", "新能源", "锂电", "锂电池", "储能",
            "半导体", "芯片", "集成电路", "消费电子",
            "白酒", "食品饮料", "医药", "生物医药", "中药",
            "人工智能", "AI", "大模型", "算力", "数据中心",
            "新能源汽车", "智能驾驶", "汽车零部件",
            "房地产", "建筑", "建材", "钢铁", "煤炭", "有色",
            "银行", "证券", "保险", "金融",
            "军工", "国防", "航天", "船舶",
            "农业", "养殖", "种业",
            "5G", "通信", "物联网",
            "机器人", "工业母机", "高端装备",
        ]
        # 优先匹配已知板块名（从长到短，避免短名误匹配）
        for sector in sorted(known_sectors, key=len, reverse=True):
            if sector in question:
                return sector

        # 匹配 "XX板块"、"XX行业"、"XX概念"、"XX产业" 模式
        # 使用 {1,6} 限制长度，避免贪婪匹配太多中文字
        patterns = [
            r"([\u4e00-\u9fa5A-Za-z0-9]{1,6})\s*(?:板块|行业|概念|产业|赛道|领域)",
            r"(?:板块|行业|概念|产业|赛道|领域)\s*([\u4e00-\u9fa5A-Za-z0-9]{1,6})",
        ]
        for p in patterns:
            m = re.search(p, question)
            if m:
                return m.group(1).strip()

        # 如果都没匹配到，用整个问题的核心关键词
        # 去掉常见疑问词和修饰词
        q = re.sub(r"(帮我|分析|看看|有哪些|怎么样|如何|最近|投资|机会|值得|关注|推荐|什么|哪些|请问)", "", question)
        q = q.strip()
        if 2 <= len(q) <= 8:
            return q

        return question[:8] if question else ""

    @staticmethod
    def _extract_ticker(question: str) -> str:
        """
        从问题中提取股票代码。
        简单规则：匹配 6 位数字。未匹配到则返回空字符串。
        """
        match = re.search(r"\b(\d{6})\b", question)
        return match.group(1) if match else ""

    async def _extract_ticker_by_llm(self, question: str) -> str:
        """
        用 LLM 从问题中提取或推断股票代码。
        支持：
        - 中文股票名 → 代码（如"茅台" → "600519"）
        - 板块/行业名 → 龙头股代码（如"光伏板块" → "601012"）
        """
        prompt = f"""从以下用户问题中提取一个最相关的A股股票代码（6位数字）。

规则：
- 如果问题提到具体股票名称（如"茅台"、"比亚迪"），返回该股票代码
- 如果问题提到板块或行业（如"光伏板块"、"半导体"、"新能源"），返回该板块最具代表性的龙头股代码
- 如果无法确定，返回 "000001"（平安银行，作为默认值）

常见板块龙头参考：
- 光伏/太阳能: 601012（隆基绿能）
- 新能源汽车: 002594（比亚迪）
- 白酒: 600519（贵州茅台）
- 半导体/芯片: 002371（北方华创）
- 人工智能/AI: 002230（科大讯飞）
- 锂电池: 300750（宁德时代）
- 医药: 600276（恒瑞医药）
- 银行: 601398（工商银行）
- 房地产: 001979（招商蛇口）
- 券商: 601211（国泰君安）

用户问题：{question}

只返回6位数字的股票代码，不要其他文字。"""

        try:
            messages = [Message(role=MessageRole.USER, content=prompt)]
            resp = await self._llm.achat(messages)
            raw = (resp.content or "").strip()
            # 提取6位数字
            match = re.search(r"(\d{6})", raw)
            if match:
                return match.group(1)
        except Exception as e:
            logger.warning(f"[Planner] LLM 提取 ticker 失败: {e}")

        return "000001"  # 默认值

    # ----------------------------------------------------------
    # 第二级：LLM 自主规划
    # ----------------------------------------------------------

    async def _try_llm_plan(
        self,
        question: str,
        context_messages: Optional[List[Message]] = None,
        knowledge_snippets: str = "",
    ) -> Optional[AnalysisPlan]:
        """让 LLM 基于工具列表生成完整计划"""
        tool_desc = _build_tool_descriptions(self._valid_tool_ids)
        prompt = _build_plan_prompt(
            question=question,
            tool_descriptions=tool_desc,
            curr_date=self._curr_date,
            trade_date=self._trade_date,
            knowledge_snippets=knowledge_snippets,
        )

        messages: List[Message] = [
            Message(role=MessageRole.SYSTEM, content="你是一个专业的股票分析规划器，只输出 JSON。"),
        ]
        if context_messages:
            messages.extend(context_messages)
        messages.append(Message(role=MessageRole.USER, content=prompt))

        try:
            resp = await self._llm.achat(messages)
            raw = resp.content or ""
            plan_data = self._parse_plan_json(raw)
            if plan_data is None:
                return None

            steps = self._validate_steps(plan_data.get("steps", []))
            if not steps:
                return None

            return AnalysisPlan(
                question=question,
                template_id=None,
                source=PlanSource.LLM_PLAN,
                steps=steps,
            )

        except Exception as e:
            logger.warning(f"[Planner] LLM 规划失败: {e}")
            return None

    async def _try_llm_plan_with_correction(
        self,
        question: str,
        context_messages: Optional[List[Message]] = None,
        failure_hint: str = "",
    ) -> Optional[AnalysisPlan]:
        """修正重试规划（v3.6.0 项7）

        在 _try_llm_plan 返回 None 后调用，使用更简单的 prompt 再试一次：
        - 步骤数限制 1-3 个
        - 工具描述只保留 ID + 描述 + 参数名
        - 显式提示"上一次规划失败"

        失败 hint 可选，用于帮助 LLM 理解上次为何失败（如"未返回有效 JSON"、"步骤为空"）。
        """
        simplified_tool_desc = _build_simplified_tool_descriptions(self._valid_tool_ids)
        prompt = _build_correction_plan_prompt(
            question=question,
            simplified_tool_desc=simplified_tool_desc,
            curr_date=self._curr_date,
            trade_date=self._trade_date,
            failure_hint=failure_hint,
        )

        messages: List[Message] = [
            Message(
                role=MessageRole.SYSTEM,
                content="你是股票分析规划器，上一次规划失败，请用最简单的方式重新规划，只输出 JSON。",
            ),
        ]
        if context_messages:
            messages.extend(context_messages)
        messages.append(Message(role=MessageRole.USER, content=prompt))

        try:
            resp = await self._llm.achat(messages)
            raw = resp.content or ""
            plan_data = self._parse_plan_json(raw)
            if plan_data is None:
                # _parse_plan_json 已记录具体原因（未找到JSON/JSON解析异常/结构无效）
                return None

            steps = self._validate_steps(plan_data.get("steps", []))
            if not steps:
                logger.warning("[Planner] 修正重试：步骤为空或全部无效")
                return None

            # 标记来源为 LLM_PLAN（修正重试成功的计划与正常 LLM 规划等价对待）
            return AnalysisPlan(
                question=question,
                template_id=None,
                source=PlanSource.LLM_PLAN,
                steps=steps,
            )

        except Exception as e:
            logger.warning(f"[Planner] 修正重试规划失败: {e}")
            return None

    @staticmethod
    def _parse_plan_json(raw: str) -> Optional[Dict[str, Any]]:
        """从 LLM 输出中解析 JSON"""
        # 尝试提取 ```json ... ``` 块
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        text = json_match.group(1).strip() if json_match else raw.strip()

        # 尝试找到 JSON 对象
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            logger.warning("[Planner] 未找到 JSON 对象")
            return None

        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError as e:
            logger.warning(f"[Planner] JSON 解析失败: {e}")
            return None

    def _validate_steps(self, raw_steps: List[Dict[str, Any]]) -> List[PlanStep]:
        """验证并转换步骤列表，过滤掉不合法的步骤"""
        valid: List[PlanStep] = []
        for s in raw_steps:
            tool_id = s.get("tool", "")
            if tool_id not in self._valid_tool_ids:
                logger.warning(f"[Planner] 工具 '{tool_id}' 不在注册表中，跳过")
                continue
            try:
                step = PlanStep(
                    id=s.get("id", len(valid) + 1),
                    tool=tool_id,
                    args=s.get("args", {}),
                    intent=s.get("intent", ""),
                    depends_on=s.get("depends_on", []),
                )
                valid.append(step)
            except Exception as e:
                logger.warning(f"[Planner] 步骤验证失败: {e}")
        return valid

