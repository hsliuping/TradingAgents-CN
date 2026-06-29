"""
外部 Skill 加载器

从 MongoDB external_skills 集合加载 AI 生成的 Skill，
通过沙箱包装注册到 ToolRegistry，使 Agent 可在运行时调用。
"""

import json
import logging
import re
import subprocess
import sys
import tempfile
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.python_runtime import resolve_python_executable

logger = logging.getLogger(__name__)

_PROJECT_ROOT = str(Path(__file__).parent.parent.parent)
_PYTHON_EXECUTABLE = resolve_python_executable(
    _PROJECT_ROOT,
    env_var_names=("TRADINGAGENTS_SANDBOX_PYTHON_EXE", "TRADINGAGENTS_PYTHON_EXE"),
)

_DECORATOR_PATTERNS = [
    r"^\s*@tool\b.*$",
    r"^\s*@register_tool\b.*$",
]
_IMPORT_STRIP_PATTERNS = [
    r"^\s*from\s+core\.tools\.base\s+import\b.*$",
    r"^\s*from\s+langchain_core\.tools\s+import\s+tool\b.*$",
]


def _strip_decorators(code: str) -> str:
    lines = code.split("\n")
    cleaned = []
    all_patterns = _DECORATOR_PATTERNS + _IMPORT_STRIP_PATTERNS
    for line in lines:
        if any(re.match(pat, line) for pat in all_patterns):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _build_sandbox_wrapper(code: str, func_name: str, timeout: int = 30) -> Callable:
    """
    构建沙箱包装函数。

    返回一个同步可调用对象，内部通过子进程执行生成的代码，
    隔离主进程并捕获结果。
    """
    clean_code = _strip_decorators(code)

    def wrapper(**kwargs) -> str:
        args_json = json.dumps(kwargs, ensure_ascii=False, default=str)
        script = f"""
import json
import os
import sys

PROJECT_ROOT = r\"{_PROJECT_ROOT}\"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

{clean_code}

if __name__ == "__main__":
    try:
        test_args = json.loads('''{args_json}''')
        func = None
        for name, obj in list(locals().items()):
            if callable(obj) and name == "{func_name}":
                func = obj
                break
        if func is None:
            for name, obj in list(locals().items()):
                if callable(obj) and not name.startswith("_") and name not in ("json", "sys"):
                    func = obj
                    break
        if func is None:
            print(json.dumps({{"error": "函数未找到"}}))
            sys.exit(1)
        result = func(**test_args)
        print("__SANDBOX_OUTPUT_START__")
        print(json.dumps(result, ensure_ascii=False, default=str))
        print("__SANDBOX_OUTPUT_END__")
    except Exception as e:
        print(json.dumps({{"error": str(e)}}), file=sys.stderr)
        sys.exit(1)
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(script)
            temp_path = f.name

        env = os.environ.copy()
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = _PROJECT_ROOT + (os.pathsep + existing if existing else "")

        try:
            proc = subprocess.run(
                [_PYTHON_EXECUTABLE, temp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=_PROJECT_ROOT,
                env=env,
            )
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()

            if proc.returncode != 0:
                error_msg = stderr or "执行失败"
                try:
                    err_data = json.loads(stderr)
                    if "error" in err_data:
                        error_msg = err_data["error"]
                except (json.JSONDecodeError, TypeError):
                    pass
                return json.dumps({"error": error_msg}, ensure_ascii=False)

            if "__SANDBOX_OUTPUT_START__" in stdout:
                start = stdout.index("__SANDBOX_OUTPUT_START__") + len("__SANDBOX_OUTPUT_START__")
                end = stdout.index("__SANDBOX_OUTPUT_END__")
                return stdout[start:end].strip()

            return json.dumps({"result": stdout}, ensure_ascii=False)

        except subprocess.TimeoutExpired:
            return json.dumps({"error": f"执行超时（{timeout}s）"}, ensure_ascii=False)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    wrapper.__name__ = func_name
    wrapper.__doc__ = f"AI 生成的外部 Skill: {func_name}"
    return wrapper


def _build_tool_parameters(param_docs: List[Dict[str, Any]]) -> List:
    """将 external_skills 的 parameters 文档转为 ToolParameter 列表"""
    from core.tools.config import ToolParameter

    result = []
    for p in param_docs:
        result.append(ToolParameter(
            name=p.get("name", ""),
            type=p.get("type", "string"),
            description=p.get("description", ""),
            required=p.get("required", True),
            default=p.get("default"),
        ))
    return result


async def load_external_skills_to_registry(db, registry) -> int:
    """
    从 MongoDB external_skills 集合加载所有 active 的 AI 生成 Skill
    并注册到 ToolRegistry。

    Returns:
        成功注册的 Skill 数量
    """
    count = 0
    cursor = db.external_skills.find({"status": "active"})
    async for doc in cursor:
        try:
            tool_id = doc.get("tool_id")
            code = doc.get("code")
            if not tool_id or not code:
                continue

            params = doc.get("parameters", [])
            wrapper = _build_sandbox_wrapper(code, tool_id)
            tool_params = _build_tool_parameters(params)

            category = doc.get("category", "external")
            # 确保 category 值合法，回退到 external
            from core.tools.config import ToolCategory
            valid_categories = {c.value for c in ToolCategory}
            if category not in valid_categories:
                category = "external"

            skill_metadata = dict(doc.get("metadata") or {})
            registry.register_external_skill(
                tool_id=tool_id,
                func=wrapper,
                display_name=doc.get("display_name", tool_id),
                description=doc.get("description", ""),
                category=category,
                parameters=tool_params,
                capability_tags=doc.get("capability_tags") or skill_metadata.get("capability_tags") or [],
                tool_role_hint=doc.get("tool_role_hint") or skill_metadata.get("tool_role_hint") or "",
                output_shape=doc.get("output_shape") or skill_metadata.get("output_shape") or "",
                preferred_for=doc.get("preferred_for") or skill_metadata.get("preferred_for") or [],
                not_replacement_for=doc.get("not_replacement_for") or skill_metadata.get("not_replacement_for") or [],
            )
            count += 1
            logger.info(f"✅ 加载外部 Skill: {tool_id}")
        except Exception as e:
            logger.error(f"❌ 加载外部 Skill 失败 {doc.get('tool_id')}: {e}")
    return count


def register_single_external_skill(db_sync, registry, skill_doc: Dict[str, Any]) -> bool:
    """
    热注册单个外部 Skill（在 Skill 生成成功后立即调用）。

    Args:
        db_sync: 同步 MongoDB 客户端（不需要，skill_doc 已是完整文档）
        registry: ToolRegistry 实例
        skill_doc: external_skills 集合的文档

    Returns:
        是否注册成功
    """
    try:
        tool_id = skill_doc.get("tool_id")
        code = skill_doc.get("code")
        if not tool_id or not code:
            return False

        params = skill_doc.get("parameters", [])
        wrapper = _build_sandbox_wrapper(code, tool_id)
        tool_params = _build_tool_parameters(params)

        category = skill_doc.get("category", "external")
        from core.tools.config import ToolCategory
        valid_categories = {c.value for c in ToolCategory}
        if category not in valid_categories:
            category = "external"

        skill_metadata = dict(skill_doc.get("metadata") or {})
        registry.register_external_skill(
            tool_id=tool_id,
            func=wrapper,
            display_name=skill_doc.get("display_name", tool_id),
            description=skill_doc.get("description", ""),
            category=category,
            parameters=tool_params,
            capability_tags=skill_doc.get("capability_tags") or skill_metadata.get("capability_tags") or [],
            tool_role_hint=skill_doc.get("tool_role_hint") or skill_metadata.get("tool_role_hint") or "",
            output_shape=skill_doc.get("output_shape") or skill_metadata.get("output_shape") or "",
            preferred_for=skill_doc.get("preferred_for") or skill_metadata.get("preferred_for") or [],
            not_replacement_for=skill_doc.get("not_replacement_for") or skill_metadata.get("not_replacement_for") or [],
        )
        logger.info(f"✅ 热注册外部 Skill: {tool_id}")
        return True
    except Exception as e:
        logger.error(f"❌ 热注册外部 Skill 失败: {e}")
        return False
