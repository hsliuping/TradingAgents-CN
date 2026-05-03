from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


MODULE_PATH = Path(r"c:\TradingAgentsCN\scripts\template_upgrades\update_research_brief_v2_prompts.py")
TARGET_PATHS = [
    Path(r"c:\TradingAgentsCN\exports\current_db_templates.json"),
    Path(r"c:\TradingAgentsCN\install\database_export_config_2026-02-10.json"),
]


def load_module():
    spec = spec_from_file_location("update_research_brief_v2_prompts", MODULE_PATH)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> None:
    module = load_module()
    updated = []

    target_paths = TARGET_PATHS
    if len(sys.argv) > 1:
        requested = {str(Path(arg).resolve()) for arg in sys.argv[1:]}
        target_paths = [path for path in TARGET_PATHS if str(path.resolve()) in requested]
        if not target_paths:
            raise RuntimeError("No matching target paths provided")

    for path in target_paths:
        text = path.read_text(encoding="utf-8")
        replacements = 0

        for preference_type in module.PREFERENCE_CONFIG:
            template_name = module.get_template_name("fundamentals_analyst_v2", preference_type)
            content = module.build_fundamentals_analyst_content(preference_type)
            system_prompt = content.get("system_prompt")
            if isinstance(system_prompt, str) and hasattr(module, "with_standard_prompt_footer"):
                content["system_prompt"] = module.with_standard_prompt_footer(system_prompt)
            text, replaced = module.replace_content_block(text, template_name, content)
            if replaced == 0:
                raise RuntimeError(f"{path} missing template {template_name}")
            replacements += replaced

        path.write_text(text, encoding="utf-8")
        updated.append((path, replacements))

    for path, replacements in updated:
        print(f"updated {path} replacements={replacements}")


if __name__ == "__main__":
    main()