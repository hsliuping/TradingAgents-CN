# 发布准备

发布新版本时，使用本目录的智能体流程生成 manifest、upgrade_config、migrations 的智能建议。

## 触发方式

在对话中说「准备发布」「执行发布准备流程」「发布准备」，Agent 将按 [SKILL.md](SKILL.md) 执行流程。

## 目录结构

```
scripts/prepare_release/
├── SKILL.md          # 智能体流程主文档
├── reference.md      # manifest、upgrade_config、migration 格式参考
├── README.md         # 本说明
└── scripts/          # 轻量脚本（供 Agent 调用）
    ├── get_prev_version.py   # 获取上一版本
    ├── git_changed_files.py  # 变更文件列表
    └── env_diff_keys.py      # .env.example diff 提取 KEY
```

## 手动调用脚本

```bash
# 获取上一版本
python scripts/prepare_release/scripts/get_prev_version.py [current_version]

# 获取变更文件
python scripts/prepare_release/scripts/git_changed_files.py <prev_ref>

# 获取 .env 新增 KEY
python scripts/prepare_release/scripts/env_diff_keys.py <prev_ref>
```
