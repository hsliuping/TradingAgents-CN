# v2.0.1 Release Checklist

## Pre-release verification

- [ ] **manifest.json** - features, config_changes reviewed (auto-filled from change analysis)
- [ ] **upgrade_config.json** - add new templates/configs if any (see UPGRADE_SUGGESTIONS.md)
- [ ] **migrations/v2_0_1.py** - implement migration logic if schema changed (see change analysis in file header)
- [ ] **CHANGELOG** - add `## [v2.0.1]` section in docs/releases/CHANGELOG.md

## Change summary (e73b8a8b..7b26f765)

- **env_changes**: None (no new .env.example keys)
- **config_changes**: UPDATE_CHECK_BASE_URL configurable
- **Schema-related**: app/models/portfolio.py, migrations infra, mongodb_cache_adapter
- **Template-related**: enhance_researcher_anti_hallucination.py, research_manager_v2.py

## Build command

```powershell
.\scripts\deployment\release_all.ps1
```
