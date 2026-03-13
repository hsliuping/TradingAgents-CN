# v2.0.1 Upgrade Config Suggestions

## Changed files that may affect config/templates

- `app/services/config_service.py`
- `scripts/template_upgrades/enhance_researcher_anti_hallucination.py`
- `core/agents/adapters/research_manager_v2.py`

## How to populate upgrade_config.json

1. If MongoDB is running, export current config:
   ```powershell
   python scripts/import_config_and_create_user.py --export-to-stdout
   ```
   Or use API/frontend export.

2. Compare with `releases/2.0.0/upgrade_config.json` or `install/database_export_config_*.json` from 2.0.0 baseline.

3. Add **only NEW** items (prompt_templates, agent_configs, system_configs, etc.) to `releases/2.0.1/upgrade_config.json` `data` section.

4. See [install/README_UPGRADE_CONFIG.md](../../install/README_UPGRADE_CONFIG.md) for format and unique keys.
