"""定向更新风险辩论与风险经理模板导出文件。

默认仅更新以下 agent：
- risky_analyst_v2
- safe_analyst_v2
- neutral_analyst_v2
- risk_manager_v2

默认更新：
- exports/current_db_templates.json
- install/database_export_config_2026-02-10.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from update_research_brief_v2_prompts import (
    PREFERENCE_CONFIG,
    ROOT,
    TEMPLATE_BUILDERS,
    get_template_name,
    replace_content_block,
    with_standard_prompt_footer,
)


RISK_AGENT_NAMES = [
    "risky_analyst_v2",
    "safe_analyst_v2",
    "neutral_analyst_v2",
    "risk_manager_v2",
]

DEFAULT_TARGET_FILES = [
    ROOT / "exports" / "current_db_templates.json",
    ROOT / "install" / "database_export_config_2026-02-10.json",
]


def update_file(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    total_replacements = 0

    for agent_name in RISK_AGENT_NAMES:
        builder = TEMPLATE_BUILDERS[agent_name]
        for preference_type in PREFERENCE_CONFIG:
            template_name = get_template_name(agent_name, preference_type)
            new_content = builder(preference_type)
            system_prompt = new_content.get("system_prompt")
            if isinstance(system_prompt, str):
                new_content["system_prompt"] = with_standard_prompt_footer(system_prompt)

            text, replaced = replace_content_block(text, template_name, new_content)
            if replaced == 0:
                raise ValueError(f"{path} 中未找到模板 {template_name}")
            total_replacements += replaced

    path.write_text(text, encoding="utf-8")
    print(f"updated {path} replacements={total_replacements}")


def main() -> None:
    parser = argparse.ArgumentParser(description="定向更新风险辩论与风险经理模板导出文件")
    parser.add_argument("paths", nargs="*", type=Path, help="仅更新指定文件路径")
    args = parser.parse_args()

    target_files = args.paths or DEFAULT_TARGET_FILES
    for path in target_files:
        update_file(path)


if __name__ == "__main__":
    main()