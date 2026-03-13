# Release Manifest (Version Baseline)

Each version has its own directory `releases/{version}/` containing all release-related content for that version.

## Directory Structure

```
releases/
├── README.md
├── 2.0.1/
│   ├── manifest.json      # 清单：版本、迁移、功能等
│   └── upgrade_config.json # 升级配置增量（新模板、新配置项）
└── 2.0.2/
    ├── manifest.json
    └── upgrade_config.json
```

## Manifest Fields (`manifest.json`)

| Field | Description |
|-------|-------------|
| `version` | Version number (e.g. 2.0.1) |
| `release_date` | Release date YYYY-MM-DD |
| `migrations` | Database migration scripts (migrations/v*.py) |
| `upgrade_config` | Filename in same dir (e.g. upgrade_config.json) |
| `features` | List of new features (for documentation) |
| `config_changes` | Config file changes (e.g. new .env keys) |
| `env_changes` | Environment variable changes |

## When Releasing a New Version

1. Create `releases/{version}/` directory
2. Create `releases/{version}/manifest.json`
3. Create `releases/{version}/upgrade_config.json` if new templates/configs
4. Add migration script in `migrations/` if schema changes
5. Update VERSION file
6. Run build (installer will include releases/ directory)

## Example: 2.0.2 Release

```
releases/2.0.2/
├── manifest.json
└── upgrade_config.json
```

`manifest.json`:
```json
{
  "version": "2.0.2",
  "release_date": "2026-03-10",
  "migrations": ["migrations/v2_0_2.py"],
  "upgrade_config": "upgrade_config.json",
  "features": ["New analyst template"],
  "config_changes": ["New system_config key: feature_x_enabled"],
  "env_changes": []
}
```
