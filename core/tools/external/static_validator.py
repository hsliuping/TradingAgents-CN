"""
静态验证器 — 零 LLM 开销的代码检查

四项检查：
1. 语法检查 — ast.parse()
2. 安全扫描 — AST 遍历黑名单调用
3. 依赖检查 — 解析 import，对比白名单
4. 签名一致性 — 函数参数 vs SkillSpec 参数
"""

import ast
import keyword
import logging
import re
from typing import List, Set

from .skill_spec import GeneratedCode, SkillSpec, ValidationResult

logger = logging.getLogger(__name__)

# 合法 Python 参数名模式（snake_case 等）；需求分析阶段可能把 HTTP 请求头
# （如 headers.User-Agent / headers.Referer）误收录为函数参数，这类名字
# 不可能出现在函数签名中，签名对比时直接跳过，避免必然失败的死循环重试。
# Python 关键字（class/import 等）同样不可能作为参数名，一并跳过。
_VALID_PYTHON_PARAM = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _is_unusable_param_name(name: str) -> bool:
    """参数名是否不可能出现在 Python 函数签名中（非法标识符或关键字）"""
    return not _VALID_PYTHON_PARAM.match(name) or keyword.iskeyword(name)


# ==================== 黑名单 & 白名单 ====================

# 安全黑名单：禁止调用的函数/模块
SECURITY_BLACKLIST: Set[str] = {
    # 系统操作
    "os.system", "os.popen", "os.exec", "os.execl", "os.execle",
    "os.execlp", "os.execlpe", "os.execv", "os.execve", "os.execvp",
    "os.execvpe", "os.spawn", "os.spawnl", "os.spawnle",
    "os.remove", "os.rmdir", "os.unlink", "os.rename",
    # 子进程
    "subprocess.run", "subprocess.call", "subprocess.Popen",
    "subprocess.check_call", "subprocess.check_output",
    # 动态执行
    "eval", "exec", "compile", "__import__",
    # 文件写入
    "open",  # 只在写入模式下禁止（在 AST 中检查）
    # 网络（限制使用，部分允许）
    "socket.socket",
}

# 安全黑名单：禁止导入的模块
MODULE_BLACKLIST: Set[str] = {
    "subprocess", "shutil", "ctypes", "multiprocessing",
    "signal", "sys", "code", "codeop", "compileall",
    "importlib", "pickle", "shelve", "marshal",
}

# 占位代码黑名单（含这些字符串视为占位实现，验证不通过）
PLACEHOLDER_PATTERNS: Set[str] = {
    "这里需要实际的",
    "由于无法直接调用",
    "需要配置正确的 API",
    "需要配置 API 密钥",
    "在实际部署时",
    "_generate_mock_data",
    "模拟从聚宽API",
    "模拟API响应",
}

# 允许的 core 子模块（生成的 Skill 可从此处获取本地数据）— 精确匹配
ALLOWED_CORE_IMPORTS: Set[str] = {
    "core.skill_runtime.data_access",
    "core.skill_runtime.project_access",
    "core.skill_runtime.standard_financial_apis",
}

# 允许的 core 子模块前缀 — 前缀匹配（用于开放分析类工具子目录）
# 这些是 core.tools.implementations 下的分析类工具，与 agent 工坊共享
ALLOWED_CORE_PREFIXES: Set[str] = {
    "core.tools.implementations.fundamentals",
    "core.tools.implementations.market",
    "core.tools.implementations.technical",
    "core.tools.implementations.portfolio",
    "core.tools.implementations.risk",
    "core.tools.implementations.news",
    "core.tools.implementations.social",
    "core.tools.implementations.trade_review",
    "core.tools.implementations.legacy_bridge",
}

# 禁止直接导入的项目内部实现模块。
# 生成的 Skill 若需要这些能力，必须通过 core.skill_runtime 的公开接口访问。
BLOCKED_IMPORT_PREFIXES: Set[str] = {
    "tradingagents.dataflows.providers",
    "tradingagents.dataflows.interface",
    "hermes_tools",
    "sandbox_tools",
    "skill_build_tools",
    # agent_builder / assistant_ops / skill_builder 是流程类工具，skill 代码不应调用
    "core.tools.implementations.agent_builder",
    "core.tools.implementations.assistant_ops",
    "core.tools.implementations.skill_builder",
}

# 依赖白名单：允许导入的第三方库
DEPENDENCY_WHITELIST: Set[str] = {
    # 标准库
    "json", "re", "datetime", "time", "math", "decimal",
    "collections", "itertools", "functools", "typing",
    "urllib", "hashlib", "base64", "copy", "uuid",
    "logging", "traceback", "io", "csv",
    # 允许的第三方库
    "requests", "aiohttp", "httpx",
    "pandas", "numpy",
    "akshare",
    "bs4", "lxml",
    "pydantic",
}


class StaticValidator:
    """
    静态验证器

    对生成的代码进行四项纯程序化检查，零 LLM 开销，毫秒级完成。
    """

    def validate(self, code: GeneratedCode, spec: SkillSpec) -> ValidationResult:
        """执行全部四项检查"""
        result = ValidationResult(passed=True)

        # 1. 语法检查
        syntax_ok = self._check_syntax(code.code, result)
        if not syntax_ok:
            result.passed = False
            return result

        # 2. 安全扫描
        tree = ast.parse(code.code)
        self._check_security(tree, result)

        # 3. 依赖检查
        self._check_dependencies(tree, result)

        # 4. 签名一致性
        self._check_signature(tree, code.code, spec, result)

        # 5. 占位代码检测
        self._check_placeholder_code(code.code, result)

        # 6. 接口规格 URL 逐字比对（防 LLM 改写路径，如 rank_data → rank/data）
        self._check_interface_urls(code.code, spec, result)

        if result.errors:
            result.passed = False

        result.details["checks_run"] = 6
        return result

    # ==================== 检查 1: 语法 ====================

    def _check_interface_urls(self, code: str, spec: SkillSpec, result: ValidationResult) -> None:
        """接口规格 URL 双向校验。

        正向：规格中给出的 URL 必须原样出现在代码里（防 LLM 改写路径，
        如 rank_data → rank/data，沙箱 404 后浪费数轮迭代）。
        反向：代码中出现的接口端点必须来自规格（防 LLM 臆造新端点做
        品牌解析等映射，如 brand/all、select_series_v2，全部 404）。
        查询串（?a=b）不计入比对——示例参数应以函数参数实现，不应硬编码。
        URL 匹配仅限 ASCII URL 字符：中文紧贴 URL 时（如「rank_data发起请求」）
        必须截断，否则会拿被污染的串去比对、误杀正确代码。
        """
        import re as _re

        spec_base_urls: list[str] = []
        for constraint in spec.constraints or []:
            for m in _re.finditer(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+", str(constraint)):
                base_url = m.group(0).split("?")[0].rstrip(".,;:")
                spec_base_urls.append(base_url)
                if base_url not in code:
                    result.errors.append(
                        f"接口 URL 改写违规: 代码中未包含规格指定的接口 URL「{base_url}」。"
                        "接口路径必须逐字使用规格原文，严禁改写路径（如 rank_data 不得写成 rank/data）"
                    )
                else:
                    logger.debug(f"[StaticValidator] 接口 URL 逐字校验通过: {base_url}")

        # 反向：臆造端点检查（规格含接口 URL 时才启用）
        if spec_base_urls:
            reported: set[str] = set()
            for m in _re.finditer(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+", code):
                code_base = m.group(0).split("?")[0].rstrip(".,;:")
                if code_base in spec_base_urls or code_base in reported:
                    continue
                reported.add(code_base)
                result.errors.append(
                    f"臆造接口端点违规: 代码中出现的接口「{code_base}」不在规格中。"
                    "规格未提及的接口端点严禁自行编造（历史教训：臆造 brand/all、"
                    "select_series_v2 等品牌解析端点全部 404）；业务过滤（如品牌→车型映射）"
                    "接口不支持时，必须基于已拉取的数据在本地实现，无法覆盖时在输出中"
                    "明确说明「接口不含品牌字段，结果可能不完整」的数据边界"
                )

    def _check_syntax(self, code: str, result: ValidationResult) -> bool:
        """语法检查 — ast.parse()"""
        try:
            ast.parse(code)
            return True
        except SyntaxError as e:
            result.errors.append(f"语法错误 (行 {e.lineno}): {e.msg}")
            return False

    # ==================== 检查 2: 安全 ====================

    def _check_security(self, tree: ast.AST, result: ValidationResult) -> None:
        """安全扫描 — AST 遍历黑名单调用"""
        for node in ast.walk(tree):
            # 检查函数调用
            if isinstance(node, ast.Call):
                call_name = self._get_call_name(node)
                if call_name and call_name in SECURITY_BLACKLIST:
                    result.errors.append(f"安全违规: 禁止调用 {call_name}")

            # 检查 open() 的写入模式
            if isinstance(node, ast.Call) and self._get_call_name(node) == "open":
                if len(node.args) >= 2:
                    mode_arg = node.args[1]
                    if isinstance(mode_arg, ast.Constant) and "w" in str(mode_arg.value):
                        result.errors.append("安全违规: 禁止以写入模式打开文件")
                # 检查关键字参数 mode=
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        if "w" in str(kw.value.value) or "a" in str(kw.value.value):
                            result.errors.append("安全违规: 禁止以写入/追加模式打开文件")

    def _get_call_name(self, node: ast.Call) -> str:
        """从 AST Call 节点提取函数名"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return ""


    # ==================== 检查 3: 依赖 ====================

    def _check_dependencies(self, tree: ast.AST, result: ValidationResult) -> None:
        """依赖检查 — 解析 import 语句，对比白名单"""
        imported_modules: List[str] = []
        imported_full: List[str] = []

        for node in ast.walk(tree):
            # import xxx
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    top_level = name.split(".")[0]
                    imported_modules.append(top_level)
                    imported_full.append(name)
            # from xxx import yyy
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_full.append(node.module)
                    top_level = node.module.split(".")[0]
                    imported_modules.append(top_level)

        for full_mod in set(imported_full):
            blocked_prefix = next(
                (prefix for prefix in BLOCKED_IMPORT_PREFIXES if full_mod == prefix or full_mod.startswith(prefix + ".")),
                None,
            )
            if blocked_prefix:
                result.errors.append(
                    f"禁止直接导入: {full_mod}（请改用 core.skill_runtime.data_access 或 core.skill_runtime.project_access）"
                )
                continue

            if full_mod in ALLOWED_CORE_IMPORTS:
                continue
            # 前缀匹配：允许 ALLOWED_CORE_PREFIXES 下的子模块
            allowed_prefix = next(
                (prefix for prefix in ALLOWED_CORE_PREFIXES if full_mod == prefix or full_mod.startswith(prefix + ".")),
                None,
            )
            if allowed_prefix:
                continue
            top_level = full_mod.split(".")[0]
            if top_level == "core":
                result.errors.append(f"禁止导入: {full_mod}（仅允许 core.skill_runtime.* 和 core.tools.implementations 分析类子目录）")
                continue

        for mod in set(imported_modules):
            if mod in MODULE_BLACKLIST:
                result.errors.append(f"禁止导入模块: {mod}")
            elif mod not in DEPENDENCY_WHITELIST and mod != "core":
                result.warnings.append(f"未知依赖: {mod}（不在白名单中，可能需要额外安装）")

        result.details["imported_modules"] = list(set(imported_modules))

    # ==================== 检查 4: 签名一致性 ====================

    def _check_signature(
        self,
        tree: ast.AST,
        code: str,
        spec: SkillSpec,
        result: ValidationResult,
    ) -> None:
        """签名一致性 — 函数参数 vs SkillSpec 参数"""
        # 找到被 @tool 装饰的函数，或者第一个顶层函数
        target_func: ast.FunctionDef | None = None
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                target_func = node
                # 如果函数名与 spec.tool_id 匹配，优先使用
                if node.name == spec.tool_id:
                    break

        if target_func is None:
            result.errors.append("未找到顶层函数定义")
            return

        # 提取函数参数名（排除 self）
        func_params: List[str] = []
        for arg in target_func.args.args:
            if arg.arg != "self":
                func_params.append(arg.arg)

        # 对比 SkillSpec 中的参数（跳过非法 Python 标识符/关键字参数，如 headers.User-Agent）
        spec_params = {p.name for p in spec.parameters}
        skipped = {name for name in spec_params if _is_unusable_param_name(name)}
        if skipped:
            logger.warning(
                f"[StaticValidator] SkillSpec 含非法 Python 标识符参数，签名对比已跳过: {sorted(skipped)}"
            )
        spec_params -= skipped
        func_params_set = set(func_params)

        missing_in_func = spec_params - func_params_set
        extra_in_func = func_params_set - spec_params

        if missing_in_func:
            result.errors.append(
                f"函数缺少 SkillSpec 中定义的参数: {', '.join(sorted(missing_in_func))}"
            )
        if extra_in_func:
            result.warnings.append(
                f"函数包含 SkillSpec 中未定义的额外参数: {', '.join(sorted(extra_in_func))}"
            )

        result.details["function_name"] = target_func.name
        result.details["function_params"] = func_params
        result.details["spec_params"] = list(spec_params)

    # ==================== 检查 5: 占位代码 ====================

    def _check_placeholder_code(self, code: str, result: ValidationResult) -> None:
        """占位代码检测 — 禁止含占位注释/假实现的代码"""
        for pattern in PLACEHOLDER_PATTERNS:
            if pattern in code:
                result.errors.append(
                    f"禁止占位代码: 代码中含「{pattern}」，必须实现真实的数据获取逻辑"
                )

