"""
代码生成器 — LLM 驱动的 Skill 代码生成

核心能力：
1. 内置工具模板参考 — 从 core/tools/implementations/ 读取编码规范
2. 已生成 Skill 参考 — 从 MongoDB external_skills 查询同类案例
3. LLM 代码生成 — 结构化 Prompt → Python 函数 + 元数据 + 测试用例
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.llm import UnifiedLLMClient, Message

from .skill_spec import GeneratedCode, ImplementationFactReport, SkillSpec, TestCase
from .symbol_utils import SYMBOL_NORMALIZE_INLINE
from .external_data_source_catalog import (
    build_external_data_source_doc_for_skill,
    is_known_external_source,
)
from .data_contracts import build_data_contract_doc_for_skill
from core.skill_runtime import build_factor_catalog_prompt_context
from .stock_data_catalog import build_stock_data_collection_doc_for_skill

logger = logging.getLogger(__name__)

# 深度思考模型生成完整 Skill 代码常需 3-6 分钟，240s 曾多次超时；
# 可通过 run_agentic(codegen_timeout=...) 按次覆盖（前端失败后可调大重试）
CODEGEN_LLM_TIMEOUT_SECONDS = 480

# ==================== 内置工具模板映射 ====================

# category → 参考文件路径（相对于项目根目录）
BUILTIN_TEMPLATES: Dict[str, str] = {
    "news": "core/tools/implementations/news/stock_news.py",
    "market": "core/tools/implementations/market/stock_market_data.py",
    "fundamentals": "core/tools/implementations/fundamentals/financial_tools.py",
    "social": "core/tools/implementations/social/stock_sentiment.py",
    "trade_review": "core/tools/implementations/trade_review/trade_info.py",
    "technical": "core/tools/implementations/market/stock_market_data.py",
    "utility": "core/tools/implementations/fundamentals/financial_tools.py",
}

# 编码规范模式（始终注入到 Prompt 中）
CODING_PATTERNS = """\
【编码规范 — 10 条铁律】
1. 纯函数：生成普通 Python 函数，不使用任何装饰器（不要 @tool、不要 @register_tool）
2. 参数注解：使用 type hints（如 symbol: str = "000001"），参数带默认值方便测试
3. 返回类型：返回 dict（结构化数据，必须包含 status 和 data 字段）或 str（Markdown 格式）
4. 错误处理：所有外部调用用 try/except 包裹，出错时返回 {"status": "error", "message": "..."}
5. 日志规范：使用 logger = logging.getLogger(__name__)，关键步骤用 emoji 日志
6. 导入规范：只使用标准库和常见第三方库（requests, pandas, akshare 等）；只允许从 core.skill_runtime.data_access 或 core.skill_runtime.project_access 导入项目运行时能力；严禁直接导入 tradingagents.dataflows.interface、tradingagents.dataflows.providers 及其任何子模块；禁止臆造其他未文档化项目接口
7. 函数体 < 100 行，超过说明做的事太多。**严格控制代码长度**：含辅助函数在内不超过 250 行，避免代码被 LLM 输出截断导致语法错误。辅助函数（如 _normalize_a_share_symbol、_safe_divide）应精简到 5-10 行，不要写大段注释。
8. 股票代码参数：本系统传递的股票代码为 6 位纯数字（如 600519、000001），不带 .SH/.SZ 后缀。生成的函数参数必须接收此格式；若数据源 API 需要其他格式（如 600519.SH），需在函数内部自行转换，不要要求调用方传入带后缀的格式。
9. 禁止模拟数据：严禁使用 mock、模拟、假数据、占位数据。必须真实调用数据源（API、akshare、tushare、本地数据库等）获取数据。若无数据则返回 {"status": "success", "data": [], "message": "未找到xxx数据"}，绝不可返回伪造数据。
10. 禁止占位代码：严禁写「这里需要实际的 API 调用」「由于无法直接调用」「需要配置 API 密钥」等注释后不实现。必须写出可执行的完整 API 调用（requests.get/post 等）。若某 API 需付费 Token，改用 akshare、tushare 等免费替代方案实现，不得用占位逻辑替代。
11. 禁止自造项目能力：不要自行创建 MongoClient、不要硬编码数据库名、不要发明 get_mongo_connection 或未文档化 provider 方法；优先复用提示词中给出的 local_data helper 和外部数据源入口。
"""

# 股票代码参数名（用于判断是否需要注入多格式支持）
SYMBOL_PARAM_NAMES = frozenset({"symbol", "stock_code", "code", "stock_symbol"})

# 本地数据 API 紧凑索引（local_data 模式注入；替代全量 LOCAL_DATA_API_DOC，
# 详细签名/Returns 结构由侦察报告 fact_report 按需注入，避免 prompt 膨胀与注意力稀释）
LOCAL_DATA_API_INDEX = """\
【本地数据访问 — API 索引（详细签名与返回结构以侦察报告为准）】
优先本地，再外部。from core.skill_runtime.data_access import ...
- get_stock_basic_info(symbol) -> dict|None：股票基础信息（name/industry/total_mv/pe_ttm/pb）
- get_stock_daily_quotes(symbol, start_date, end_date, period="daily", limit=1000) -> list：日线行情（open/high/low/close/volume）
- get_stock_news(symbol, start_date=None, end_date=None, limit=20) -> list：股票新闻（title/content/publish_time/url）；按日期范围用 get_stock_news_by_date_range
- get_market_quotes(symbol) -> dict|None：实时行情快照（close/pct_chg/volume/amount）
- get_latest_stock_price(symbol) -> float|None：标准价格入口（估值类优先用，不要把价格设成 0）
- get_stock_financial_data(symbol, start_date=None, end_date=None, limit=20) -> list：财务数据（兼容 report_period/report_date）
- get_stock_financial_periods(symbol, limit=20) -> list：按报告期展开的标准财务记录（同比/CAGR/多期计算优先用）
- get_stock_valuation_context(symbol) -> dict：估值标准入口（basic_info/market_quotes/current_price/pe_ttm/pb/ps_ttm/financial_data）
- get_industry_peer_basic_info(industry, exclude_symbol=None, limit=200) -> list：本地同行样本（行业对比/相对估值）
- summarize_industry_valuation(industry, metric="pb", exclude_symbol=None) -> dict：行业估值统计 average/median/min/max/count（相对估值优先用，不要自己写聚合）
【标准结构化金融数据】from core.skill_runtime.standard_financial_apis import ...
- get_historical_financial_annual_series(symbol, years=10) -> dict：最近 N 年年报序列（revenue/net_profit/roe/gross_margin/operating_cashflow/free_cashflow 等）
- get_profitability_stability_metrics(symbol, years=10) -> dict：盈利稳定性统计（均值/中位数/波动率/变异系数）
- get_cashflow_quality_trend(symbol, years=10) -> dict：现金流质量趋势（OCF/净利、FCF/净利、OCF/FCF margin）
- get_historical_valuation_percentile(symbol, metrics=None, lookback_years=5) -> dict：pe_ttm/pb/ps_ttm/pcf_ttm 历史分位与当前值
⚠️ 历史估值分位不要用 get_market_quotes/get_latest_stock_price（仅当前快照），用 get_historical_valuation_percentile。"""

# 项目数据访问紧凑索引（local_data 模式注入；替代全量 PROJECT_DATA_ACCESS_DOC）
PROJECT_ACCESS_INDEX = """\
【项目数据访问 — API 索引（同步函数，禁止 async/await）】
from core.skill_runtime.project_access import ...
- query_stock_collection(collection, filters=None, projection=None, sort=None, limit=100) -> list：本地集合通用查询（stock_basic_info/market_quotes/stock_daily_quotes/stock_financial_data/stock_financial_periods/stock_news）
- aggregate_stock_collection(collection, pipeline, limit=100) -> list：本地聚合（helper 无法满足时再用）
- list_supported_stock_collections() -> list：可访问集合目录
- get_external_stock_news(symbol, limit=10) -> dict：外部新闻 {source, data}
- get_external_historical_data(symbol, start_date, end_date, period="daily") -> dict：外部历史行情（仅 OHLCV，不含估值）
- get_external_financial_data(symbol, report_type="quarterly", limit=4) -> dict：外部财务数据
- get_external_valuation_data(symbol, start_date, end_date) -> dict：外部历史估值序列（pe_ttm/pb_mrq/ps_ttm/pcf_ttm；估值类优先用这个）
- get_external_query_news(query, curr_date, look_back_days=7) -> dict：Google News/Finnhub 新闻
硬规则：不要 import pymongo/MongoClient；不要硬编码数据库名；不要直接 await provider；inspect_* 仅侦察用；不要导入 external_sources/sync_wrappers/catalog 内部模块。"""

# 外部接口集成规则（external_api 模式注入；此类需求不涉及本地股票数据资产）
EXTERNAL_API_RULES = """\
⚠️ 外部接口集成关键要求：
- 生成的代码必须是独立可运行的同步纯 Python 函数（禁止 async def / await）
- HTTP 调用必须设置超时（如 requests.get(url, headers=..., timeout=10)），并用 try-except 包裹
- 外部接口可能限流/偶发失败：单次执行内对同一接口的调用要有节制（合并请求、设置分页上限），必要时加 time.sleep 短暂退避；不要在循环里逐条打接口
- 参数防御：必填参数缺失或格式非法时立即返回结构化错误，不发起网络请求
- 数据为空/接口无返回时优雅返回：{"status": "success", "data": [], "message": "未找到xxx数据"}，绝不可伪造数据
- 返回值一致性：无论成功失败，返回 dict 必须包含 status 字段（"success"/"error"）；失败时包含 error_code 与 message
- 异常兜底：主函数体用 try-except 包裹，捕获异常后返回结构化错误响应，不要抛出未捕获异常
- 接口字段以实际响应为准：字段映射必须来自侦察报告确认的响应结构，禁止臆造字段名"""

VALUATION_KEYWORDS = (
    "估值", "valuation", "pe", "pb", "ps", "dcf", "市盈率", "市净率", "市销率",
)


class CodeGenerator:
    """
    LLM 代码生成器

    根据 SkillSpec 生成完整的 Python 工具函数代码。
    """

    def __init__(
        self,
        llm_client: Optional[UnifiedLLMClient] = None,
        provider: str = "deepseek",
        model: Optional[str] = None,
    ):
        """
        Args:
            llm_client: 预配置的 LLM 客户端（优先使用）
            provider: LLM 提供商（llm_client 为空时使用）
            model: 模型名称（可选）
        """
        self._client = llm_client
        self._provider = provider
        self._model = model

    def _get_client(self, timeout_seconds: Optional[int] = None) -> UnifiedLLMClient:
        """懒加载 LLM 客户端；timeout_seconds 可按次覆盖默认超时"""
        timeout = timeout_seconds or CODEGEN_LLM_TIMEOUT_SECONDS
        if self._client is None:
            kwargs = {"timeout": timeout}
            if self._model:
                kwargs["model"] = self._model
            self._client = UnifiedLLMClient.from_provider(self._provider, **kwargs)
        else:
            adapter = getattr(self._client, "_adapter", None)
            config = getattr(adapter, "config", None)
            if config and getattr(config, "timeout", 0) != timeout:
                config.timeout = timeout
                try:
                    adapter.initialize()
                except Exception as e:
                    logger.warning(f"更新代码生成 LLM 超时时间失败: {e}")
        return self._client

    def generate(
        self,
        spec: SkillSpec,
        feedback: str = "",
        previous_code: str = "",
        fact_report: Optional[ImplementationFactReport] = None,
        timeout_seconds: Optional[int] = None,
        on_thinking: Optional[Callable[[str, str], None]] = None,
        iteration_mode: str = "repair",
    ) -> GeneratedCode:
        """
        生成 Skill 代码

        Args:
            spec: Skill 规格书
            feedback: 上一轮的反馈（迭代时使用）
            previous_code: 上一轮生成的代码（迭代时使用）
            timeout_seconds: 单次 LLM 调用超时（秒），None 用默认值
            on_thinking: 思考过程回调 on_thinking(kind, text)，
                kind ∈ {"reset", "reasoning", "content"}，用于前端实时展示
            iteration_mode: "repair"=失败后定向修复（默认）；
                "upgrade"=在已验证的旧版本代码上做最小改动升级

        Returns:
            GeneratedCode 包含代码、元数据和测试用例
        """
        start = time.time()
        client = self._get_client(timeout_seconds)

        # 构建 Prompt
        system_prompt = self._build_system_prompt(spec)
        user_prompt = self._build_user_prompt(
            spec, feedback, previous_code, fact_report, iteration_mode=iteration_mode
        )

        # 将完整 prompt 写入日志文件，方便排查 LLM 未调用推荐 helper 的问题
        self._dump_prompt_to_logfile(spec, system_prompt, user_prompt, fact_report)

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        # 调用 LLM — 代码生成需要较大的输出空间，显式设置 max_tokens
        # 注意：8192 tokens 对于含中文注释的复杂金融分析函数可能不够（约 4000 行代码），
        # 曾出现代码被截断导致语法错误的情况。提升到 12288 以确保完整输出。
        logger.info(
            f"\n{'─'*50}\n"
            f"📤 [CodeGenerator] LLM 输入 (tool_id={spec.tool_id})\n"
            f"{'─'*50}\n"
            f"🔧 System Prompt ({len(system_prompt)} 字符):\n{system_prompt[:2000]}\n"
            f"{'...(截断)' if len(system_prompt) > 2000 else ''}\n"
            f"📝 User Prompt ({len(user_prompt)} 字符):\n{user_prompt[:3000]}\n"
            f"{'...(截断)' if len(user_prompt) > 3000 else ''}\n"
            f"{'─'*50}"
        )
        # 有思考回调时走流式（推理模型的 reasoning_content 增量实时透出），
        # 无回调时保持原有非流式调用
        if on_thinking is not None:
            response = client.chat_stream(messages, on_delta=on_thinking, max_tokens=12288)
        else:
            response = client.chat(messages, max_tokens=12288)
        raw = response.content or ""
        logger.info(
            f"\n{'─'*50}\n"
            f"📥 [CodeGenerator] LLM 输出 ({len(raw)} 字符)\n"
            f"{'─'*50}\n"
            f"{raw[:3000]}\n"
            f"{'...(截断)' if len(raw) > 3000 else ''}\n"
            f"{'─'*50}"
        )

        # 解析结果
        result = self._parse_response(raw, spec)
        result.generation_time = round(time.time() - start, 2)
        result.generation_model = response.model or self._provider

        return result

    async def agenerate(
        self,
        spec: SkillSpec,
        feedback: str = "",
        previous_code: str = "",
        fact_report: Optional[ImplementationFactReport] = None,
        iteration_mode: str = "repair",
    ) -> GeneratedCode:
        """异步版本的 generate"""
        start = time.time()
        client = self._get_client()

        system_prompt = self._build_system_prompt(spec)
        user_prompt = self._build_user_prompt(
            spec, feedback, previous_code, fact_report, iteration_mode=iteration_mode
        )

        # 将完整 prompt 写入日志文件，方便排查 LLM 未调用推荐 helper 的问题
        self._dump_prompt_to_logfile(spec, system_prompt, user_prompt, fact_report)

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        logger.info(
            f"\n{'─'*50}\n"
            f"📤 [CodeGenerator.async] LLM 输入 (tool_id={spec.tool_id})\n"
            f"{'─'*50}\n"
            f"🔧 System Prompt ({len(system_prompt)} 字符):\n{system_prompt[:2000]}\n"
            f"{'...(截断)' if len(system_prompt) > 2000 else ''}\n"
            f"📝 User Prompt ({len(user_prompt)} 字符):\n{user_prompt[:3000]}\n"
            f"{'...(截断)' if len(user_prompt) > 3000 else ''}\n"
            f"{'─'*50}"
        )
        response = await client.achat(messages, max_tokens=12288)
        raw = response.content or ""
        logger.info(
            f"\n{'─'*50}\n"
            f"📥 [CodeGenerator.async] LLM 输出 ({len(raw)} 字符)\n"
            f"{'─'*50}\n"
            f"{raw[:3000]}\n"
            f"{'...(截断)' if len(raw) > 3000 else ''}\n"
            f"{'─'*50}"
        )

        result = self._parse_response(raw, spec)
        result.generation_time = round(time.time() - start, 2)
        result.generation_model = response.model or self._provider

        return result

    # ==================== Prompt 日志转储 ====================

    def _dump_prompt_to_logfile(
        self,
        spec: SkillSpec,
        system_prompt: str,
        user_prompt: str,
        fact_report: Optional[ImplementationFactReport],
    ) -> None:
        """将完整的 system_prompt 和 user_prompt 写入日志文件，方便排查 LLM 未调用推荐 helper 的问题。

        日志文件位置：logs/codegen_prompts/<tool_id>_<timestamp>.log
        每次生成都覆盖同一个 tool_id 的最新日志，并保留历史版本（带时间戳）。
        """
        try:
            from datetime import datetime
            log_dir = Path("logs/codegen_prompts")
            log_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_tool_id = re.sub(r"[^\w\-]", "_", spec.tool_id or "unknown")

            # 构建 helper 摘要（让排查时一眼看到推荐了哪些 helper）
            helper_summary = "（无 fact_report）"
            if fact_report:
                if fact_report.available_helpers:
                    helper_lines = []
                    for h in fact_report.available_helpers:
                        helper_lines.append(
                            f"  - {h.module}.{h.name} | signature={h.signature or ''} | "
                            f"data_source_handling={h.data_source_handling or ''} | reason={h.reason or ''}"
                        )
                    helper_summary = f"共 {len(fact_report.available_helpers)} 个:\n" + "\n".join(helper_lines)
                else:
                    helper_summary = "available_helpers 为空"

            content = (
                f"{'=' * 80}\n"
                f"# CodeGenerator Prompt Dump\n"
                f"{'=' * 80}\n"
                f"# tool_id: {spec.tool_id}\n"
                f"# timestamp: {timestamp}\n"
                f"# spec.display_name: {spec.display_name}\n"
                f"# spec.description: {spec.description[:200] if spec.description else ''}\n"
                f"# system_prompt 长度: {len(system_prompt)} 字符\n"
                f"# user_prompt 长度: {len(user_prompt)} 字符\n"
                f"\n"
                f"{'─' * 80}\n"
                f"## 侦察层推荐的 available_helpers\n"
                f"{'─' * 80}\n"
                f"{helper_summary}\n"
                f"\n"
                f"{'─' * 80}\n"
                f"## System Prompt（完整）\n"
                f"{'─' * 80}\n"
                f"{system_prompt}\n"
                f"\n"
                f"{'─' * 80}\n"
                f"## User Prompt（完整）\n"
                f"{'─' * 80}\n"
                f"{user_prompt}\n"
            )

            # 写入带时间戳的历史版本
            hist_path = log_dir / f"{safe_tool_id}_{timestamp}.log"
            hist_path.write_text(content, encoding="utf-8")

            # 覆盖最新版本（方便排查最新一次）
            latest_path = log_dir / f"{safe_tool_id}_latest.log"
            latest_path.write_text(content, encoding="utf-8")

            logger.info(
                f"[CodeGenerator] Prompt dump 已写入: {latest_path} "
                f"(system={len(system_prompt)}字符, user={len(user_prompt)}字符, "
                f"helpers={len(fact_report.available_helpers) if fact_report else 0}个)"
            )
        except Exception as exc:
            logger.warning(f"[CodeGenerator] 写入 prompt dump 日志失败: {exc}", exc_info=True)

    # ==================== Prompt 构建 ====================

    def _build_system_prompt(self, spec: SkillSpec) -> str:
        """构建系统提示词（按需求类型裁剪文档，按需注入）。

        - external_api（外部接口集成，如懂车帝）：只保留外部数据源说明 + 外部接口
          规则 + 编码规范，不注入本地股票集合目录/数据契约/本地 API 文档/参考模板。
        - local_data（默认）：用紧凑 API 索引替代全量 API 文档；详细签名和 Returns
          结构由侦察报告（fact_report）在 user prompt 中按需注入。
        """
        from .requirement_analyzer import classify_requirement_mode

        mode = classify_requirement_mode(spec)
        external_source_doc = build_external_data_source_doc_for_skill(spec)

        # 目录外数据源（如 dongchedi）：系统目录（AKShare/Tushare 等）与需求无关，
        # 注入完整目录反而诱导 LLM 绕开用户指定接口；改为一条目录外集成说明。
        if spec.data_source and not is_known_external_source(spec.data_source):
            external_source_doc = (
                f"【外部数据源】本次需求的数据源「{spec.data_source}」不在系统外部数据源目录"
                "（AKShare、Tushare Pro 等）中，属于目录外接口集成：\n"
                "- 以用户提供的接口规格（URL、请求头、参数、返回字段）为唯一事实源直接实现\n"
                "- 严禁改用系统目录中的其他数据源（如 AKShare/Tushare）替代用户指定的接口\n"
                "- 严禁臆造接口路径或字段；接口规格未提及的一律不要假设"
            )

        if mode == "external_api":
            logger.info(
                f"[CodeGenerator] requirement_mode=external_api，system prompt 仅注入外部接口规则 "
                f"(tool_id={spec.tool_id}, data_source={spec.data_source})"
            )
            return f"""你是一个专业的 Python 工具函数生成器。你的任务是根据用户的需求规格书（SkillSpec），生成一个完整的、可直接运行的纯 Python 函数。

本需求为外部接口集成：数据来自外部 API（与本地股票数据库无关）。不要导入 core.skill_runtime 下的任何本地数据模块，不要查询 MongoDB 股票集合，不要使用本地股票数据 helper。

{external_source_doc}

{EXTERNAL_API_RULES}

{CODING_PATTERNS}

【输出格式】
你必须严格按照以下格式输出，用三个区块分隔：

```python
# === CODE START ===
<完整的 Python 代码>
# === CODE END ===
```

```json
// === METADATA START ===
{{"tool_id": "...", "name": "...", "description": "...", "category": "...", "is_online": true}}
// === METADATA END ===
```

```json
// === TESTS START ===
[{{"input": {{}}, "expected_fields": [], "expected_type": "list"}}]
// === TESTS END ===
```
"""

        template_code = self._get_builtin_template(spec.category)
        stock_data_doc = build_stock_data_collection_doc_for_skill(spec)
        data_contract_doc = build_data_contract_doc_for_skill(spec)
        factor_catalog_doc = build_factor_catalog_prompt_context(
            spec.description,
            category=spec.category,
            expected_fields=list(spec.expected_output.fields or []),
        )
        template_section = ""
        if template_code:
            # 截取前 80 行作为参考，并去掉装饰器相关行
            lines = []
            for line in template_code.split("\n")[:80]:
                # 跳过装饰器行和 core 模块导入行
                stripped = line.strip()
                if stripped.startswith("@tool") or stripped.startswith("@register_tool"):
                    continue
                if "from core.tools.base import" in stripped:
                    continue
                if "from langchain_core.tools import tool" in stripped:
                    continue
                lines.append(line)
            template_section = f"""
【参考模板 — 同类内置工具的代码风格（仅参考逻辑，不要照搬装饰器和导入）】
```python
{chr(10).join(lines)}
```"""
        return f"""你是一个专业的 Python 工具函数生成器。你的任务是根据用户的需求规格书（SkillSpec），生成一个完整的、可直接运行的纯 Python 函数。

{LOCAL_DATA_API_INDEX}

{PROJECT_ACCESS_INDEX}

{stock_data_doc}

{data_contract_doc}

{external_source_doc}

{factor_catalog_doc}

⚠️ 关键要求：
- 不要使用 @tool、@register_tool 等任何装饰器
- 生成的 Skill 若要访问项目能力，允许导入以下模块：
  - core.skill_runtime.data_access / core.skill_runtime.project_access / core.skill_runtime.standard_financial_apis（标准数据访问和金融分析封装）
  - core.tools.implementations.fundamentals / market / technical / portfolio / risk / news / social / trade_review / legacy_bridge（180+ 个分析工具，与 agent 工坊共享）
- 不要直接导入 core.skill_runtime.catalog、core.skill_runtime.external_sources、core.skill_runtime.sync_wrappers 等内部实现模块
- 不要直接导入 tradingagents.dataflows.interface、tradingagents.dataflows.providers 或其任意子模块
- 不要导入 core.tools.implementations.agent_builder / assistant_ops / skill_builder（这些是流程类工具，skill 代码不应调用）
- 不要 from langchain_core.xxx import 任何模块
- 生成的代码必须是独立可运行的纯 Python 函数
- **🚫 禁止脚本入口与调试代码（必须遵守）**：Skill 是被外部调用的纯函数，不是脚本。代码末尾**严禁**出现 `if __name__ == "__main__":` 块、`print(xxx(...))` 形式的本地调试调用、或任何"演示用法"代码。测试调用由 TESTS 区块的 JSON 声明、沙箱统一执行（`func(**test_args)`），LLM 不需要在代码里"演示"如何调用。函数行为完全由参数决定，必填参数要有合理默认值或前置校验。
- 必须复用已有工具：如果 fact_report.available_helpers 中已有完成目标能力的工具，必须直接 from <module_path> import <function_name> 调用，禁止自行实现等价的数据获取逻辑
- **🚨 Helper 透传铁律（最高优先级）**：helper 返回的数据已经过聚合、计算和格式化。你的代码只需 ①调用helper → ②.get()取字段 → ③组装输出。**严禁自己实现**分组聚合/趋势计算/字段映射推导/风险等级计算。**严禁猜测字段名**，严格按 helper 的 Returns 说明来写。
- **⚠️ 防御性编程（status 检查）**：helper 返回的 status 字段可能有多种取值（"success" | "no_data" | "no_pledge" | "error" 等）。当 status 不是 "success" 时，数据字段（metrics/top_pledgers/records/series 等）可能为空字典 {{}}、空列表 [] 或不存在，必须做防御性处理：①先检查 status 再访问数据字段；②对列表用 for item in (list or []) 而非直接索引 [0]；③用 .get("field", {{}}) 或 .get("field", []) 设置默认值。
- 优先复用 standard_financial_apis 中的高级封装（如 get_historical_financial_annual_series、get_profitability_stability_metrics、get_cashflow_quality_trend、get_historical_valuation_percentile 等），避免手动重复计算 ROIC、CAGR、变异系数等指标
- 如果任务命中了常用分析因子白名单，优先复用 catalog 中已有 factor_id、bundle helper 和固定公式，不要自造新的底层因子字段
- **数据源标签使用规则**（根据 available_helpers 中每个 helper 的 data_source_handling 标签决策）：
  - `self_contained`：helper 已自包含数据源调用（内部已封装 MongoDB/外部 API），直接调用即可，**不要**再额外调用外部数据源补数据
  - `local_only`：helper 只查本地 MongoDB，若返回为空或数据不足，需在 skill 中补充外部数据源调用（如 tushare/akshare/finnhub）或项目外部数据接口（core.skill_runtime.external_sources）
  - `partial`：helper 仅覆盖部分需求，需结合其它 helper 或补充数据源/计算逻辑一起使用

🛡️ 通用错误预防（必须遵循，避免边缘测试失败）：
1. **股票代码有效性预检**：函数开头必须验证股票代码是否存在于基础数据中。使用 get_stock_basic_info(symbol) 获取基本信息，如果返回为空或报错，立即返回结构化错误响应（不要继续执行后续查询，避免 API 调用超时）。示例：
   ```python
   basic_info = get_stock_basic_info(symbol)
   if not basic_info:
       return {{"status": "error", "error_code": "symbol_not_found", "message": f"股票代码 {{symbol}} 不存在于基础数据中", "symbol": symbol}}
   ```
2. **数据为空时优雅返回**：所有数据查询结果必须检查是否为空。如果关键数据为空，返回结构化错误响应（不要让后续计算因 None/空列表而崩溃）。
3. **除零保护**：所有比率计算必须使用安全除法。示例：`ratio = numerator / denominator if denominator else None` 或 `ratio = round(numerator / denominator, 4) if abs(denominator) > 1e-9 else None`。
4. **时间序列数据不足时降级**：如果历史数据不足 N 年，不要崩溃，改为用现有数据计算并标注 `data_sufficient: false`。
5. **API 调用超时保护**：不要在循环中反复调用外部 API；如果必须调用，设置合理的超时（如 5 秒）和 try-except 降级。
6. **异常兜底**：主函数体用 try-except 包裹，捕获异常后返回结构化错误响应（包含 error_code、message、symbol），不要抛出未捕获异常。
7. **返回值一致性**：无论成功还是失败，返回的 dict 必须包含 `status` 字段（"success"/"error"）和 `symbol` 字段，保证调用方能统一处理。

{CODING_PATTERNS}
{template_section}
【输出格式】
你必须严格按照以下格式输出，用三个区块分隔：

```python
# === CODE START ===
<完整的 Python 代码>
# === CODE END ===
```

```json
// === METADATA START ===
{{"tool_id": "...", "name": "...", "description": "...", "category": "...", "is_online": true}}
// === METADATA END ===
```

```json
// === TESTS START ===
[{{"input": {{}}, "expected_fields": [], "expected_type": "list"}}]
// === TESTS END ===
```
"""

    def _needs_symbol_normalize(self, spec: SkillSpec) -> tuple[bool, str | None]:
        """判断是否为 A 股相关 Skill 且包含股票代码参数，需注入多格式支持"""
        param_names = {p.name.lower() for p in spec.parameters}
        for name in SYMBOL_PARAM_NAMES:
            if name in param_names:
                # 进一步判断：描述或数据源涉及 A 股/股票
                desc_lower = (spec.description or "").lower()
                ds_lower = (spec.data_source or "").lower()
                if any(k in desc_lower or k in ds_lower for k in ("a股", "股票", "上市公司", "joinquant", "聚宽", "akshare", "tushare")):
                    return True, name
                # 默认：有 symbol 且是 fundamentals/market/news 等，视为 A 股
                if spec.category in ("fundamentals", "market", "news", "utility"):
                    return True, name
        return False, None

    @staticmethod
    def _format_previous_code_for_prompt(
        previous_code: str,
        *,
        full_code_line_limit: int = 260,
        head_lines: int = 140,
        tail_lines: int = 100,
    ) -> str:
        """优先保留完整上一轮代码，超长时退化为首尾关键片段。"""
        if not previous_code:
            return ""

        code_lines = previous_code.splitlines()
        if len(code_lines) <= full_code_line_limit:
            return previous_code

        return (
            "\n".join(code_lines[:head_lines])
            + f"\n# ... (中间省略，共 {len(code_lines)} 行) ...\n"
            + "\n".join(code_lines[-tail_lines:])
        )

    @staticmethod
    def _truncate_feedback_for_prompt(
        feedback: str,
        *,
        max_chars: int = 6000,
        head_chars: int = 3500,
    ) -> str:
        """保留反馈开头的执行上下文和结尾的根因/修复计划，避免关键信息丢失。"""
        if len(feedback) <= max_chars:
            return feedback

        tail_chars = max_chars - head_chars - 24
        if tail_chars <= 0:
            return feedback[:max_chars]

        return (
            feedback[:head_chars]
            + "\n... (中间省略) ...\n"
            + feedback[-tail_chars:]
        )

    @staticmethod
    def _build_fact_report_block(fact_report: Optional[ImplementationFactReport]) -> str:
        """将侦察层产出的事实报告格式化为结构化 Prompt 区块。

        分为多个子区块，让 LLM 清晰区分不同类型的实现事实：
        - 策略概要：总体实现方向
        - 可用 Helper：推荐调用的函数及签名
        - 数据库字段事实：集合中实际存在的字段名
        - 已确认事实：schema 探测发现的具体事实
        - 禁止路径 & 缺口：必须规避的实现路径
        - 验收条件：生成代码必须满足的业务检查
        """
        if not fact_report:
            return ""

        sections: list[str] = []

        # ── 区块 1: 策略概要 ──
        summary_lines: list[str] = []
        if fact_report.task_summary:
            summary_lines.append(f"任务: {fact_report.task_summary}")
        if fact_report.recommended_strategy:
            summary_lines.append(f"推荐策略: {fact_report.recommended_strategy}")
        if summary_lines:
            sections.append("▸ 策略概要\n" + "\n".join(f"  {l}" for l in summary_lines))

        # ── 区块 2: 可用 Helper 函数 ──
        if fact_report.available_helpers:
            helper_lines: list[str] = []
            # data_source_handling 标签说明（让 LLM 理解每个 helper 的数据源处理方式）
            ds_label_map = {
                "self_contained": "自包含(已封装数据源,直接调用)",
                "local_only": "仅本地MongoDB(可能需补充外部数据源)",
                "partial": "部分覆盖(可能需补充其它数据源或计算)",
            }
            # 限制 helper 数量避免 prompt 膨胀，但保留足够数量确保关键 helper 不被截断
            # 之前 [:8] 导致部分关键 helper（如质押函数）被截断，LLM 转而自行实现导致失败
            helpers_to_show = fact_report.available_helpers[:20]
            logger.info(
                f"[CodeGenerator] available_helpers 总数={len(fact_report.available_helpers)}, "
                f"展示前 {len(helpers_to_show)} 个: "
                f"{[h.name for h in helpers_to_show]}"
            )
            for h in helpers_to_show:
                line = f"  from {h.module} import {h.name}"
                if h.signature:
                    line += f"  # 签名: {h.signature}"
                if h.description:
                    logger.info(
                        f"[CodeGenerator] helper={h.name} desc_len={len(h.description)} "
                        f"has_returns={'Returns:' in h.description}"
                    )
                    desc = h.description
                    if len(desc) > 400:
                        # 优先展示 Returns 部分
                        returns_idx = desc.find("Returns:")
                        if returns_idx > 0:
                            desc_excerpt = desc[returns_idx:returns_idx + 350]
                            line += f"\n    📋 返回结构:\n      {desc_excerpt}"
                        else:
                            # 截断末尾
                            line += f"\n    📋 {desc[-350:]}"
                    else:
                        line += f"\n    📋 {desc}"
                # 显式展示 data_source_handling 标签，让 LLM 判断是否需要补充数据源
                ds_label = ds_label_map.get(h.data_source_handling, h.data_source_handling)
                line += f"  # 数据源: {ds_label}"
                if h.reason:
                    line += f"  # {h.reason}"
                helper_lines.append(line)
            sections.append(
                "▸ 可用 Helper（必须优先复用这些函数获取数据，禁止自行实现等价逻辑）\n"
                + "  数据源标签说明: self_contained=自包含(直接调用); local_only=仅本地MongoDB(可能需补充外部数据源); partial=部分覆盖\n"
                + "\n".join(helper_lines)
            )
            # 🚨 关键提醒：helper 已聚合好数据，直接透传
            sections.append(
                "▸ 🚨 Helper 使用铁律（不遵守将导致迭代失败）\n"
                "  - helper 返回的数据已经过聚合、计算和格式化，直接使用其返回值即可\n"
                "  - 禁止自己实现分组聚合、趋势计算、字段映射等逻辑（helper 已做好）\n"
                "  - 直接用 .get() 从 helper 返回值中取字段，不要猜测或推导字段名\n"
                "  - 如果 helper 的描述中有 Returns 说明，严格按照其中的字段名和类型来写代码\n"
                "  - ⚠️ 防御性编程：先检查 helper 返回的 status 字段。status 不是 'success' 时，\n"
                "    数据字段（metrics/top_pledgers/records/series 等）可能为空字典/空列表。\n"
                "    对列表用 for item in (list or []) 遍历，不要直接索引 [0]。\n"
                "    用 .get('field', {}) 或 .get('field', []) 设置默认值"
            )

        # ── 区块 3: 数据库集合字段（来自 sample_fields）──
        if fact_report.sample_fields:
            field_lines: list[str] = []
            for coll, fields in list(fact_report.sample_fields.items())[:4]:
                field_lines.append(f"  {coll}: {', '.join(fields[:15])}")
            sections.append(
                "▸ 数据库集合实际字段（侦察已验证存在，请直接使用这些字段名）\n"
                + "\n".join(field_lines)
            )

        # ── 区块 4: 已确认的 Schema 事实 ──
        if fact_report.schema_facts:
            fact_lines: list[str] = []
            for f in fact_report.schema_facts[:10]:
                evidence_tag = f" [{f.evidence}]" if f.evidence else ""
                fact_lines.append(f"  • [{f.source}] {f.fact}{evidence_tag}")
            sections.append("▸ 已确认事实\n" + "\n".join(fact_lines))

        # ── 区块 4.5: 金融 schema 指导卡 ──
        schema_bundle_context = fact_report.schema_bundle_context or {}
        method = schema_bundle_context.get("method") or {}
        contract = schema_bundle_context.get("contract") or {}
        verifier_rule = schema_bundle_context.get("verifier_rule") or {}
        applicability_rules = schema_bundle_context.get("applicability_rules") or {}
        if method or contract or verifier_rule or applicability_rules:
            schema_lines: list[str] = []
            if method:
                method_name = str(method.get("name") or schema_bundle_context.get("method_id") or "schema_method")
                schema_lines.append(f"  方法: {method_name}")
                objective = str(method.get("objective") or "").strip()
                if objective:
                    schema_lines.append(f"  目标: {objective}")
                required_metrics = list(method.get("required_metrics") or [])
                if required_metrics:
                    schema_lines.append(f"  必需指标: {', '.join(required_metrics[:6])}")
                required_fields = list(method.get("required_fields") or [])
                if required_fields:
                    schema_lines.append(f"  必需输入字段: {', '.join(required_fields[:8])}")
                steps = [str(item).strip() for item in method.get("steps") or [] if str(item).strip()]
                if steps:
                    schema_lines.append("  推荐步骤: " + " -> ".join(steps[:5]))
                limitations = [str(item).strip() for item in method.get("limitations") or [] if str(item).strip()]
                if limitations:
                    schema_lines.append("  方法局限: " + "；".join(limitations[:4]))

            if contract:
                contract_fields = [
                    str((field_def or {}).get("field_name") or "").strip()
                    for field_def in contract.get("required_fields") or []
                    if str((field_def or {}).get("field_name") or "").strip()
                ]
                if contract_fields:
                    schema_lines.append(f"  输出契约字段: {', '.join(contract_fields[:10])}")
                narrative_requirements = [
                    str(item).strip()
                    for item in contract.get("narrative_requirements") or []
                    if str(item).strip()
                ]
                if narrative_requirements:
                    schema_lines.append("  叙述要求: " + "；".join(narrative_requirements[:4]))
                prohibited_patterns = [
                    str(item).strip()
                    for item in contract.get("prohibited_patterns") or []
                    if str(item).strip()
                ]
                if prohibited_patterns:
                    schema_lines.append("  禁止模式: " + "；".join(prohibited_patterns[:3]))

            if verifier_rule:
                failure_message = str(verifier_rule.get("failure_message") or "").strip()
                remediation_hint = str(verifier_rule.get("remediation_hint") or "").strip()
                if failure_message:
                    schema_lines.append(f"  验收失败语义: {failure_message}")
                if remediation_hint:
                    schema_lines.append(f"  修复提示: {remediation_hint}")

            if applicability_rules:
                rule_lines = []
                for rule_id, rule in list(applicability_rules.items())[:4]:
                    human_description = str((rule or {}).get("human_description") or rule_id).strip()
                    rationale = str((rule or {}).get("rationale") or "").strip()
                    line = human_description
                    if rationale:
                        line += f" ({rationale})"
                    rule_lines.append(line)
                if rule_lines:
                    schema_lines.append("  适用性规则: " + "；".join(rule_lines))

            sections.append(
                "▸ 金融 schema 指导卡（生成代码时必须显式落实这些方法/规则/契约）\n"
                + "\n".join(schema_lines)
            )

        # ── 区块 5: 禁止路径 ──
        if fact_report.blocked_paths:
            blocked_lines = [
                f"  ✘ {item.path}: {item.reason} ({item.severity})"
                for item in fact_report.blocked_paths[:5]
            ]
            sections.append("▸ 禁止路径（不要使用以下方式实现）\n" + "\n".join(blocked_lines))

        # ── 区块 6: Runtime 缺口 ──
        if fact_report.runtime_gaps:
            gap_lines = [
                f"  ⚠ {item.path or '(未知)'}: {item.reason}"
                for item in fact_report.runtime_gaps[:4]
            ]
            sections.append("▸ Runtime 缺口（需注意的限制）\n" + "\n".join(gap_lines))

        # ── 区块 7: 验收条件（代码必须满足）──
        if fact_report.validation_checks:
            check_lines: list[str] = []
            for vc in fact_report.validation_checks[:8]:
                desc = vc.description or vc.name
                field_tag = f" [字段: {vc.field}]" if vc.field else ""
                check_lines.append(f"  ☑ {desc}{field_tag}")
            sections.append(
                "▸ 验收条件（生成代码的输出必须满足以下检查）\n"
                + "\n".join(check_lines)
            )

        # ── 区块 8: 备注 ──
        if fact_report.notes:
            note_lines = [f"  - {n}" for n in fact_report.notes[:4]]
            sections.append("▸ 侦察备注\n" + "\n".join(note_lines))

        if not sections:
            return ""

        header = (
            "\n【已查证实现事实 — 侦察层产出，置信度 {:.0%}】\n"
            "以下事实来自前置侦察层的实际探测。生成代码时必须严格基于这些事实实现，\n"
            "不要自行猜测新的内部接口、provider 方法或字段名称。"
        ).format(fact_report.confidence)

        return header + "\n\n" + "\n\n".join(sections)

    def _build_preflight_facts_block(self, spec: SkillSpec) -> str:
        """接口预检实测事实区块（spec.metadata.interface_preflight 存在时注入）。

        预检在规格确认阶段已沙箱真实调用过接口，实测到连通性、返回条数、
        返回条目的真实字段、验证可用的查询参数。把这些事实喂给 LLM：
        - 引用字段以实测清单为准，不臆造字段名
        - 业务过滤条件（如 brand）不在实测查询参数中 → 不得拼进 URL，
          必须拉取全量数据后按返回字段本地过滤
        区块文本与 Agent Loop 协调者 prompt 共用同一实现（interface_preflight.
        build_preflight_facts_text），保证两处规则一致。
        """
        from .interface_preflight import build_preflight_facts_text

        preflight = (getattr(spec, "metadata", None) or {}).get("interface_preflight")
        return build_preflight_facts_text(preflight)

    def _build_user_prompt(
        self,
        spec: SkillSpec,
        feedback: str = "",
        previous_code: str = "",
        fact_report: Optional[ImplementationFactReport] = None,
        iteration_mode: str = "repair",
    ) -> str:
        """构建用户提示词"""
        from .requirement_analyzer import classify_requirement_mode

        # 跳过非法 Python 标识符/关键字参数（需求分析可能把 HTTP 请求头如
        # headers.User-Agent 误收录为函数参数，不可能出现在函数签名中）
        from .static_validator import _is_unusable_param_name

        valid_params = [p for p in spec.parameters if not _is_unusable_param_name(p.name)]
        skipped_params = [p.name for p in spec.parameters if p not in valid_params]
        if skipped_params:
            logger.warning(
                f"[CodeGenerator] spec 含非法标识符参数，user prompt 已跳过: {skipped_params}"
            )
        params_desc = "\n".join(
            f"  - {p.name} ({p.type}): {p.description}"
            + (f" [可选, 默认={p.default}]" if not p.required else " [必填]")
            for p in valid_params
        )

        output_desc = (
            f"  类型: {spec.expected_output.type}\n"
            f"  字段: {', '.join(spec.expected_output.fields) or '无特定要求'}\n"
            f"  说明: {spec.expected_output.description}"
        )

        validation_desc = "\n".join(
            f"  - [{check.rule_level}] {check.name}: {check.description}"
            + (" (阻断)" if check.blocking else " (告警)")
            for check in spec.validation_checks[:10]
        ) or "  无"

        constraints_desc = "\n".join(f"  - {c}" for c in spec.constraints) or "  无"

        # 接口规格区块：constraints 中含 URL 的条目单列，要求逐字使用。
        # 背景：LLM 曾把用户提供的 rank_data 臆造改写为 rank/data 导致 404。
        interface_lines = [c for c in spec.constraints if re.search(r"https?://", str(c))]
        interface_block = ""
        if interface_lines:
            interface_desc = "\n".join(f"  {line}" for line in interface_lines)
            interface_block = f"""

【🌐 接口规格 — 唯一事实源，严禁改写】
{interface_desc}

- 接口 URL、路径段、查询参数名必须逐字使用上方规格中的原文，严禁按你的训练记忆"纠正"或改写路径
  （例如规格给的是 rank_data，就绝不能写成 rank/data）
- 规格未提及的路径/参数一律不要添加；请求头按规格要求设置
"""

        # 接口预检实测事实：external_api 模式下服务层把预检结果注入 spec.metadata，
        # 告知 LLM 真实字段与实测可用参数（防臆造字段/臆造查询参数，含本地过滤规则）
        preflight_block = self._build_preflight_facts_block(spec)

        is_valuation_skill = any(keyword in (spec.description or "").lower() for keyword in VALUATION_KEYWORDS)
        valuation_section = ""
        if is_valuation_skill:
            valuation_section = """

【⚠️ 估值类 Skill 实现范式 — 必须遵守】
- 优先调用 from core.skill_runtime.data_access import get_stock_valuation_context
- current_price 必须来自 get_stock_valuation_context()['current_price'] 或 get_latest_stock_price(symbol)
- 若 current_price 缺失、<=0，必须直接返回 error/invalid，禁止默认设为 0 后继续估值
- 财务数据必须优先使用 core.skill_runtime.data_access 返回的 financial_data，并兼容 report_period / report_date
- raw_data.financial_indicators[].end_date / report_period 常是季报与年报混合序列，不能默认按“连续年报”理解
- growth_years 当前若为 1，表示同口径同比；优先使用 netprofit_yoy / growth_YOYNI，若手工计算同比，也必须比较同口径期间，不能拿 2025Q3 直接对比 2024 年报
- PE/PB/PS 估值若缺少必要输入，应返回 invalid，禁止输出 fair_value=0
- DCF 若缺少 total_shares/净利润/有效增长率，必须明确返回 invalid 或降级说明，禁止静默返回 0
- 不要只从 basic_info 生拼价格字段；价格优先级应为 market_quotes -> basic_info

推荐骨架：
```python
from core.skill_runtime.data_access import get_stock_valuation_context

ctx = get_stock_valuation_context(symbol)
current_price = ctx["current_price"]
if current_price is None or current_price <= 0:
    return {"status": "error", "message": f"未获取到股票 {symbol} 的有效现价，无法估值"}

pe_ttm = ctx["pe_ttm"]
pb = ctx["pb"]
ps_ttm = ctx["ps_ttm"]
financial_data = ctx["financial_data"]
```
"""

        symbol_section = ""
        needs_norm, param_name = self._needs_symbol_normalize(spec)
        if needs_norm and param_name:
            symbol_section = f"""
【⚠️ 股票代码多格式支持 — 必须实现】
参数 {param_name} 需支持多种输入格式，用户可能输入：600519、SH600519、600519.SH、600519.SS、SZ000001、000001.SZ 等。
请在函数开头对 {param_name} 做标准化处理，将以下辅助函数内联到你的代码中，并在调用数据源 API 前执行：
{param_name} = _normalize_a_share_symbol({param_name})

辅助函数（必须包含在函数外部或内部）：
{SYMBOL_NORMALIZE_INLINE}
"""

        fact_report_block = self._build_fact_report_block(fact_report)
        # 因子白名单是股票分析因子目录（MA/RSI/MACD 等），与外部接口集成无关；
        # 关键词匹配对非股票需求易误命中（如"月度/周期"命中 technical_core）
        is_external_api = classify_requirement_mode(spec) == "external_api"
        if is_external_api:
            factor_catalog_doc = ""
            # Skill Runtime 接口约束/因子约束是本地数据导向，外部接口需求不注入
            runtime_interface_section = ""
            factor_rules_section = ""
            # 「付费 Token 改用 akshare/tushare 替代」会诱导 LLM 抛弃用户指定接口，替换为外部接口版本
            no_mock_section = """
【⚠️ 严禁模拟/占位 — 必须真实实现】
- 禁止 mock、模拟、假数据、占位数据、_generate_mock_data 等
- 禁止占位注释：如「这里需要实际的 API 调用」「由于无法直接调用」「需要配置密钥」等，必须写出可执行的 requests.get/post 真实调用
- 不得改用其他数据源（AKShare/Tushare 等）替代用户指定的外部接口
- 若无数据：返回 {{"status": "success", "data": [], "message": "未找到xxx数据"}}，不可返回伪造数据
"""
        else:
            factor_catalog_doc = build_factor_catalog_prompt_context(
                spec.description,
                category=spec.category,
                expected_fields=list(spec.expected_output.fields or []),
            )
            runtime_interface_section = """
【⚠️ Skill Runtime 接口约束 — 必须遵守】
- 本项目给生成 Skill 的正式运行时接口只有两个：core.skill_runtime.data_access 与 core.skill_runtime.project_access
- 数据库 helper、外部数据源桥接、同步包装器都已经收口到 skill_runtime 内部；生成的代码不要直接导入其内部细分模块
- 如果需要本地数据库数据，优先用 core.skill_runtime.data_access
- 如果需要外部数据源桥接、同步 wrapper 或通用集合查询，优先用 core.skill_runtime.project_access
- 严禁直接导入 tradingagents.dataflows.interface、tradingagents.dataflows.providers 或其任意子模块，即使你知道这些内部实现存在，也不能在生成代码中直接使用
- 若某项能力当前在 skill_runtime 公开接口中不存在，也不要绕过公开接口直连内部 provider；应改用现有公开接口重构方案，或返回清晰的降级结果
"""
            factor_rules_section = """
【⚠️ 常用分析因子约束 — 命中白名单时必须遵守】
- 如果需求本质上只是 value_core / quality_core / growth_cashflow_core / technical_core 中的现有因子读取、组合或固定公式计算，优先复用现有 helper 或 bundle，不要重新发明同义字段。
- 若 expected_output.fields 已经命中 catalog 因子字段，返回结构必须沿用这些 factor_id，不要改写为 growth_rate、profit_margin_pct、macdValue 这类新名字。
- 若需求超出当前白名单因子范围，应明确新增的最小字段/计算缺口，不要把整个 Skill 实现都建立在自造底层因子上。
"""
            no_mock_section = """
【⚠️ 严禁模拟/占位 — 必须真实实现】
- 禁止 mock、模拟、假数据、占位数据、_generate_mock_data 等
- 禁止占位注释：如「这里需要实际的 API 调用」「由于无法直接调用」「需要配置密钥」等，必须写出可执行的 requests.get/post 或 akshare 等真实调用
- 若某 API 需付费 Token（如 JoinQuant），改用 akshare、tushare 等免费替代方案实现，不得用占位逻辑或返回「需配置 API」类提示
- 若无数据：返回 {{"status": "success", "data": [], "message": "未找到xxx数据"}}，不可返回伪造数据
"""

        prompt = f"""请根据以下 Skill 规格书生成 Python 工具函数代码：

【基本信息】
- tool_id: {spec.tool_id}
- 显示名称: {spec.display_name}
- 功能描述: {spec.description}
- 分类: {spec.category}
- 数据源: {spec.data_source or '无'}

【参数定义】
{params_desc}

【期望输出】
{output_desc}

【输出字段命名约束】
- expected_output.fields 中列出的字段名是最终契约，必须严格使用，不要擅自改名、缩写或换同义词。
- 例如规格若要求 earnings_growth_rate 和 peg_ratio，就不能输出成 growth_rate 或 peg。
- 若某字段当前无法提供，应保留该字段语义并通过 failure_reason 等失效字段说明原因，不要私自改成另一套返回结构。

【规格级验收规则】
{validation_desc}

【行为约束】
{constraints_desc}
{interface_block}
{preflight_block}
{valuation_section}
{symbol_section}
{factor_catalog_doc}
{fact_report_block}
{runtime_interface_section}
{factor_rules_section}
{no_mock_section}

【测试输入】
{json.dumps(spec.test_input, ensure_ascii=False) if spec.test_input else '无'}
"""
        if previous_code:
            truncated_code = self._format_previous_code_for_prompt(previous_code)
            if iteration_mode == "upgrade":
                # 版本升级：父版本是已通过验证的基线，要求像人类维护者一样做最小改动，
                # 而不是从零重写（历史教训：重写会丢掉父版本多轮迭代才修好的细节，
                # 如分页/重试/本地过滤/品牌别名匹配等）
                upgrade_ask = self._truncate_feedback_for_prompt(feedback) if feedback else ""
                upgrade_ask_section = ""
                if upgrade_ask:
                    upgrade_ask_section = f"\n本次升级需求：\n{upgrade_ask}\n"
                prompt += f"""
【⬆️ 版本升级 — 在当前已验证版本的基础上做最小改动，严禁从零重写】

当前版本代码（已通过验证，是本次升级的基线）：
```python
{truncated_code}
```
{upgrade_ask_section}
【升级要求 — 极其重要】
1. **最小改动**：像人类维护者改代码一样——加字段就只加字段、加参数就只加参数，只动与新需求直接相关的代码
2. **保留已验证逻辑**：请求构造、分页/翻页、重试退避、响应解析、本地过滤、字段映射、异常处理等已跑通的逻辑原样保留，严禁顺手重写或「优化」
3. **不重新设计**：保持函数结构、命名风格、返回结构不变（新规格明确要求变更的除外）
4. **函数名以新规格为准**：输出的函数名/tool_id 必须与新规格一致（版本号可能已变化）
5. **输出完整代码**：在基线上改完后输出完整函数代码，不要输出 diff，也不要用注释省略未改动部分
"""
            else:
                truncated_feedback = self._truncate_feedback_for_prompt(feedback)
                prompt += f"""
【⚠️ 迭代修复 — 上一轮代码有问题，请定向修复】

上一轮代码：
```python
{truncated_code}
```

完整执行上下文与反馈：
{truncated_feedback or '(无)'}

【修复要求 — 极其重要】
1. **定向修复**：只修改有问题的代码，保留已正确工作的部分
2. **不要重新设计**：保持整体架构不变，除非架构本身就是问题所在
3. **关注根因**：优先解决根因分析中指出的核心问题
4. **验证修复**：确保修复后的代码能处理上述执行上下文中暴露的场景
5. **输出完整代码**：即使只修改了几行，也要输出完整的函数代码
"""
        return prompt

    # ==================== 模板加载 ====================

    def _get_builtin_template(self, category: str) -> str:
        """
        获取内置工具模板代码

        Args:
            category: Skill 分类 (news, market, fundamentals, etc.)

        Returns:
            模板代码字符串，找不到返回空字符串
        """
        template_path = BUILTIN_TEMPLATES.get(category)
        if not template_path:
            template_path = BUILTIN_TEMPLATES.get("utility", "")

        if not template_path:
            return ""

        try:
            # 从项目根目录读取
            full_path = Path(__file__).parent.parent.parent.parent / template_path
            if full_path.exists():
                return full_path.read_text(encoding="utf-8")
            else:
                logger.warning(f"模板文件不存在: {full_path}")
                return ""
        except Exception as e:
            logger.warning(f"读取模板文件失败: {e}")
            return ""

    # ==================== 响应解析 ====================

    def _parse_response(self, raw: str, spec: SkillSpec) -> GeneratedCode:
        """解析 LLM 输出，提取代码、元数据、测试用例"""
        code = self._extract_block(raw, "CODE START", "CODE END")
        metadata = self._extract_json_block(raw, "METADATA START", "METADATA END")
        tests_raw = self._extract_json_block(raw, "TESTS START", "TESTS END")

        # 如果提取失败，尝试从 markdown 代码块提取
        if not code:
            code = self._extract_markdown_code(raw)

        if not code:
            logger.warning("无法从 LLM 输出中提取代码")
            code = raw  # 兜底：使用完整输出

        code = self._sanitize_extracted_code(code)

        # 构建测试用例
        test_cases = []
        if isinstance(tests_raw, list):
            for t in tests_raw:
                if isinstance(t, dict):
                    test_cases.append(TestCase(
                        input=t.get("input", {}),
                        expected_fields=t.get("expected_fields", []),
                        expected_type=t.get("expected_type", "list"),
                    ))

        return GeneratedCode(
            code=code,
            metadata=metadata if isinstance(metadata, dict) else {},
            test_cases=test_cases,
        )

    def _sanitize_extracted_code(self, code: str) -> str:
        """清理 LLM 输出中残留的 Markdown fence 和 CODE START/END 标记。"""
        text = str(code or "").strip()

        # LLM 有时输出未闭合的 ```python fence，fallback raw 后会把 fence 当成代码首行。
        text = re.sub(r"^```(?:python|py)?\s*\n", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\n```\s*$", "", text)

        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if re.match(r"^#\s*===\s*CODE\s+(START|END)\s*===\s*$", stripped, flags=re.IGNORECASE):
                continue
            if stripped == "```":
                continue
            lines.append(line)
        return "\n".join(lines).strip()

    def _extract_block(self, text: str, start_marker: str, end_marker: str) -> str:
        """提取标记之间的文本块"""
        pattern = rf"#\s*===\s*{start_marker}\s*===\s*\n(.*?)#\s*===\s*{end_marker}\s*==="
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_json_block(
        self, text: str, start_marker: str, end_marker: str
    ) -> Any:
        """提取标记之间的 JSON 块"""
        pattern = rf"//\s*===\s*{start_marker}\s*===\s*\n(.*?)//\s*===\s*{end_marker}\s*==="
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        return {}

    def _extract_markdown_code(self, text: str) -> str:
        """从 Markdown 代码块提取 Python 代码"""
        pattern = r"```python\s*\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            # 返回最长的代码块（通常是主代码）
            return max(matches, key=len).strip()
        return ""

