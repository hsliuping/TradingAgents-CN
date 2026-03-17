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
from typing import Any, Dict, List, Optional

from core.llm import UnifiedLLMClient, Message

from .skill_spec import GeneratedCode, SkillSpec, TestCase
from .symbol_utils import SYMBOL_NORMALIZE_INLINE
from .external_data_source_catalog import build_external_data_source_doc_for_skill
from .local_data import LOCAL_DATA_API_DOC
from .stock_data_catalog import build_stock_data_collection_doc_for_skill

logger = logging.getLogger(__name__)

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
6. 导入规范：只使用标准库和常见第三方库（requests, pandas, akshare 等）；允许 from core.tools.external.local_data import ... 获取本地数据库数据；禁止其他 from core.xxx import
7. 函数体 < 100 行，超过说明做的事太多
8. 股票代码参数：本系统传递的股票代码为 6 位纯数字（如 600519、000001），不带 .SH/.SZ 后缀。生成的函数参数必须接收此格式；若数据源 API 需要其他格式（如 600519.SH），需在函数内部自行转换，不要要求调用方传入带后缀的格式。
9. 禁止模拟数据：严禁使用 mock、模拟、假数据、占位数据。必须真实调用数据源（API、akshare、tushare、本地数据库等）获取数据。若无数据则返回 {"status": "success", "data": [], "message": "未找到xxx数据"}，绝不可返回伪造数据。
10. 禁止占位代码：严禁写「这里需要实际的 API 调用」「由于无法直接调用」「需要配置 API 密钥」等注释后不实现。必须写出可执行的完整 API 调用（requests.get/post 等）。若某 API 需付费 Token，改用 akshare、tushare 等免费替代方案实现，不得用占位逻辑替代。
"""

# 股票代码参数名（用于判断是否需要注入多格式支持）
SYMBOL_PARAM_NAMES = frozenset({"symbol", "stock_code", "code", "stock_symbol"})


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

    def _get_client(self) -> UnifiedLLMClient:
        """懒加载 LLM 客户端"""
        if self._client is None:
            kwargs = {}
            if self._model:
                kwargs["model"] = self._model
            self._client = UnifiedLLMClient.from_provider(self._provider, **kwargs)
        return self._client

    def generate(
        self,
        spec: SkillSpec,
        feedback: str = "",
        previous_code: str = "",
    ) -> GeneratedCode:
        """
        生成 Skill 代码

        Args:
            spec: Skill 规格书
            feedback: 上一轮的反馈（迭代时使用）
            previous_code: 上一轮生成的代码（迭代时使用）

        Returns:
            GeneratedCode 包含代码、元数据和测试用例
        """
        start = time.time()
        client = self._get_client()

        # 构建 Prompt
        system_prompt = self._build_system_prompt(spec)
        user_prompt = self._build_user_prompt(spec, feedback, previous_code)

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        # 调用 LLM
        response = client.chat(messages)
        raw = response.content or ""

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
    ) -> GeneratedCode:
        """异步版本的 generate"""
        start = time.time()
        client = self._get_client()

        system_prompt = self._build_system_prompt(spec)
        user_prompt = self._build_user_prompt(spec, feedback, previous_code)

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        response = await client.achat(messages)
        raw = response.content or ""

        result = self._parse_response(raw, spec)
        result.generation_time = round(time.time() - start, 2)
        result.generation_model = response.model or self._provider

        return result

    # ==================== Prompt 构建 ====================

    def _build_system_prompt(self, spec: SkillSpec) -> str:
        """构建系统提示词"""
        template_code = self._get_builtin_template(spec.category)
        stock_data_doc = build_stock_data_collection_doc_for_skill(spec)
        external_source_doc = build_external_data_source_doc_for_skill(spec)
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
```
"""
        return f"""你是一个专业的 Python 工具函数生成器。你的任务是根据用户的需求规格书（SkillSpec），生成一个完整的、可直接运行的纯 Python 函数。

{LOCAL_DATA_API_DOC}

{stock_data_doc}

{external_source_doc}

⚠️ 关键要求：
- 不要使用 @tool、@register_tool 等任何装饰器
- 不要 from core.xxx import 任何模块
- 不要 from langchain_core.xxx import 任何模块
- 生成的代码必须是独立可运行的纯 Python 函数

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

    def _build_user_prompt(
        self, spec: SkillSpec, feedback: str = "", previous_code: str = ""
    ) -> str:
        """构建用户提示词"""
        params_desc = "\n".join(
            f"  - {p.name} ({p.type}): {p.description}"
            + (f" [可选, 默认={p.default}]" if not p.required else " [必填]")
            for p in spec.parameters
        )

        output_desc = (
            f"  类型: {spec.expected_output.type}\n"
            f"  字段: {', '.join(spec.expected_output.fields) or '无特定要求'}\n"
            f"  说明: {spec.expected_output.description}"
        )

        constraints_desc = "\n".join(f"  - {c}" for c in spec.constraints) or "  无"

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

【行为约束】
{constraints_desc}
{symbol_section}

【⚠️ 严禁模拟/占位 — 必须真实实现】
- 禁止 mock、模拟、假数据、占位数据、_generate_mock_data 等
- 禁止占位注释：如「这里需要实际的 API 调用」「由于无法直接调用」「需要配置密钥」等，必须写出可执行的 requests.get/post 或 akshare 等真实调用
- 若某 API 需付费 Token（如 JoinQuant），改用 akshare、tushare 等免费替代方案实现，不得用占位逻辑或返回「需配置 API」类提示
- 若无数据：返回 {{"status": "success", "data": [], "message": "未找到xxx数据"}}，不可返回伪造数据

【测试输入】
{json.dumps(spec.test_input, ensure_ascii=False) if spec.test_input else '无'}
"""
        if feedback and previous_code:
            prompt += f"""
【⚠️ 迭代修复 — 上一轮代码有问题】
上一轮代码：
```python
{previous_code}
```

问题反馈：
{feedback}

请修复上述问题，重新生成完整代码。
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

