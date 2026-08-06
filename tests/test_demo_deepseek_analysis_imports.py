import ast
from pathlib import Path


def test_demo_deepseek_analysis_references_existing_adapter_modules():
    demo_path = Path(__file__).resolve().parents[1] / "examples" / "demo_deepseek_analysis.py"
    tree = ast.parse(demo_path.read_text(encoding="utf-8"))

    adapter_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith("tradingagents.llm_adapters.")
    ]

    adapters_dir = demo_path.parents[1] / "tradingagents" / "llm_adapters"

    assert adapter_imports
    for import_node in adapter_imports:
        module_name = import_node.module
        module_file = adapters_dir / f"{module_name.rsplit('.', 1)[-1]}.py"
        assert module_file.exists(), module_name

        module_tree = ast.parse(module_file.read_text(encoding="utf-8"))
        exported_names = {
            node.name for node in module_tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        }
        exported_names.update(
            target.id
            for node in module_tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        )
        for alias in import_node.names:
            assert alias.name in exported_names, f"{module_name}.{alias.name}"
