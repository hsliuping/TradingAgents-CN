"""
预检脚本：在启动后端前快速检查修改过的文件是否有语法错误或常见运行时陷阱。

用法：
    python scripts/pre_check.py                     # 检查所有核心文件
    python scripts/pre_check.py --changed            # 只检查 git diff 中的文件
    python scripts/pre_check.py --files a.py b.py    # 检查指定文件

检查项：
    1. py_compile：语法错误
    2. 条件 import 分支外使用检查：只报告真正可能 UnboundLocalError 的情况
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from subprocess import run as sub_run

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── 核心文件列表（每次检查） ──
CORE_FILES = [
    "core/embedded_nanobot/agent/context.py",
    "core/embedded_nanobot/agent/context_injection_policy.py",
    "core/embedded_nanobot/agent/memory.py",
    "core/embedded_nanobot/agent_builder_flow.py",
    "core/embedded_nanobot/intent_context.py",
    "core/embedded_nanobot/runtime.py",
    "core/tools/context.py",
    "core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py",
    "app/services/embedded_nanobot_service.py",
    "app/services/agent_workshop_service.py",
    "app/routers/embedded_nanobot.py",
    "app/schemas/embedded_nanobot.py",
]

# 标准库模块名（总是可用，不需要检查）
_STDLIB_MODULES = frozenset({
    "re", "os", "sys", "json", "time", "datetime", "logging", "typing",
    "pathlib", "collections", "itertools", "functools", "math", "random",
    "hashlib", "base64", "uuid", "copy", "enum", "io", "textwrap",
    "traceback", "warnings", "asyncio", "subprocess", "tempfile",
    "shutil", "glob", "fnmatch", "configparser", "csv", "argparse",
    "threading", "queue", "multiprocessing", "socket", "ssl", "email",
    "html", "xml", "urllib", "http", "ftplib", "poplib", "smtplib",
    "struct", "pickle", "shelve", "marshal", "sqlite3", "gettext",
    "locale", "string", "re", "pprint", "dataclasses", "contextlib",
    "contextvars", "abc", "atexit", "signal", "mmap", "gc", "inspect",
    "ast", "dis", "code", "codeop", "importlib", "pkgutil", "runpy",
    "token", "tokenize", "keyword", "symbol", "tabnanny", "py_compile",
    "compileall", "zipimport", "pydoc", "doctest", "unittest",
    "decimal", "fractions", "statistics", "numbers", "bisect",
    "heapq", "array", "weakref", "types", "operator", "reprlib",
})


def py_compile_check(file_path: Path) -> bool:
    """语法编译检查。"""
    result = sub_run(
        [sys.executable, "-m", "py_compile", str(file_path)],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    return result.returncode == 0


def check_conditional_import_usage(file_path: Path) -> list[str]:
    """检查条件分支内定义的变量是否在分支外使用（UnboundLocalError 风险）。

    过滤规则：
    1. 标准库模块名 → 跳过
    2. 已在模块级 import 的名字 → 跳过
    3. try/except 双路径 fallback 模式 → 跳过
    """
    issues = []
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except SyntaxError:
        return issues

    # ── 收集模块级导入的名字 ──
    module_level_names: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                name = alias.asname or alias.name
                module_level_names.add(name.split(".")[0])

    # ── 收集 try/except 双路径 fallback 导入 ──
    # 模式: try: import X; except: import Y  → X 和 Y 都是安全的
    fallback_imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            try_names = _collect_import_names(node.body)
            for handler in node.handlers:
                handler_names = _collect_import_names(handler.body)
                # 如果 handler 里也导入了同名模块，视为 fallback
                fallback_imports.update(try_names & handler_names)
                # 处理 "except: X = None" 模式
                handler_assigns = _collect_assign_names(handler.body)
                fallback_imports.update(try_names & handler_assigns)
            # else 分支也视为安全
            else_names = _collect_import_names(node.orelse)
            fallback_imports.update(try_names & else_names)

    # ── 收集条件块内的导入 ──
    conditional_imports: dict[str, tuple[int, int, set[str]]] = {}  # block_id -> (start, end, names)

    class ConditionalImportCollector(ast.NodeVisitor):
        def _record(self, node, block_id):
            names = _collect_import_names(node.body if hasattr(node, 'body') else [node])
            names |= _collect_import_names(node.orelse if hasattr(node, 'orelse') else [])
            # 过滤：去掉标准库、模块级、fallback 名字
            names = names - _STDLIB_MODULES - module_level_names - fallback_imports
            if names:
                end = getattr(node, 'end_lineno', None) or node.lineno
                conditional_imports[str(block_id)] = (node.lineno, end, names)

        def visit_If(self, node):
            self._record(node, id(node))
            self.generic_visit(node)

        def visit_Try(self, node):
            self._record(node, id(node))
            self.generic_visit(node)

    ConditionalImportCollector().visit(tree)

    if not conditional_imports:
        return []

    # ── 检查条件块外的使用 ──
    for block_id, (start, end, names) in conditional_imports.items():
        for name in names:
            # 在整个 AST 中查找该名字的使用
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == name:
                    if node.lineno < start or node.lineno > end:
                        # 排除在另一条件块内也在导入的情况
                        in_other_conditional = False
                        for other_id, (os_start, os_end, os_names) in conditional_imports.items():
                            if other_id != block_id and name in os_names:
                                if os_start <= node.lineno <= os_end:
                                    in_other_conditional = True
                                    break
                        if not in_other_conditional:
                            issues.append(
                                f"  Line {node.lineno}: '{name}' imported inside conditional "
                                f"(lines {start}-{end}) but used outside"
                            )

    return issues


def _collect_import_names(stmts: list) -> set[str]:
    """从语句列表中收集导入的名字。"""
    names: set[str] = set()
    for stmt in stmts:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                name = alias.asname or alias.name
                names.add(name.split(".")[0])
        elif isinstance(stmt, ast.ImportFrom):
            for alias in stmt.names:
                name = alias.asname or alias.name
                if name != "*":
                    names.add(name)
    return names


def _collect_assign_names(stmts: list) -> set[str]:
    """从语句列表中收集赋值的目标名字（用于识别 X = None 等 fallback）。"""
    names: set[str] = set()
    for stmt in stmts:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def get_git_changed_files() -> list[Path]:
    """获取 git diff 中的文件列表。"""
    result = sub_run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        return []
    files = []
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if line and line.endswith(".py"):
            p = PROJECT_ROOT / line
            if p.exists():
                files.append(p)
    return files


def main():
    import argparse
    parser = argparse.ArgumentParser(description="预检脚本")
    parser.add_argument("--changed", action="store_true", help="只检查 git diff 中的文件")
    parser.add_argument("--files", nargs="*", help="检查指定文件")
    args = parser.parse_args()

    if args.files:
        targets = [PROJECT_ROOT / f for f in args.files]
    elif args.changed:
        targets = get_git_changed_files()
        if not targets:
            print("✅ 没有检测到变更的 Python 文件")
            return 0
    else:
        targets = [PROJECT_ROOT / f for f in CORE_FILES]

    if not targets:
        print("✅ 没有需要检查的文件")
        return 0

    # ── 1. py_compile ──
    print("=" * 60)
    print("🔍 Step 1: py_compile 语法检查")
    print("=" * 60)
    compile_errors = []
    for f in targets:
        if not f.exists():
            print(f"  ⚠️  跳过（文件不存在）: {f.relative_to(PROJECT_ROOT)}")
            continue
        ok = py_compile_check(f)
        rel = f.relative_to(PROJECT_ROOT)
        if ok:
            print(f"  ✅ {rel}")
        else:
            print(f"  ❌ {rel}  — 语法错误！")
            compile_errors.append(rel)

    # ── 2. 条件 import 检查 ──
    print()
    print("=" * 60)
    print("🔍 Step 2: 条件 import 分支外使用检查（UnboundLocalError 风险）")
    print("=" * 60)
    ast_issues_total = 0
    for f in targets:
        if not f.exists():
            continue
        issues = check_conditional_import_usage(f)
        rel = f.relative_to(PROJECT_ROOT)
        if issues:
            # 只显示前 5 条，避免刷屏
            shown = issues[:5]
            print(f"  ⚠️  {rel} ({len(issues)} 处):")
            for issue in shown:
                print(issue)
            if len(issues) > 5:
                print(f"  ... 还有 {len(issues) - 5} 处")
            ast_issues_total += len(issues)
        else:
            print(f"  ✅ {rel}")

    # ── 汇总 ──
    print()
    print("=" * 60)
    if compile_errors:
        print(f"❌ py_compile 失败: {len(compile_errors)} 个文件")
    if ast_issues_total:
        print(f"⚠️  条件 import 风险: {ast_issues_total} 处")
    if not compile_errors and not ast_issues_total:
        print("✅ 全部检查通过，可以启动后端")
        return 0
    else:
        print("❌ 存在需要修复的问题，请修复后再启动")
        return 1


if __name__ == "__main__":
    sys.exit(main())