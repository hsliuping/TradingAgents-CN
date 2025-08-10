# 发布说明 - 2025-08-11

## 概览
- 同步本地改动并提交至远端，清理误生成文件，新增文档与测试脚本。
- 关键更新覆盖 risk_manager、memory、trading_graph、web/components/sidebar.py、web/utils/persistence.py。
- 加入 .gitignore 规则忽略 .clinerules/ 与 .cursor/。

## 提交摘要（按时间倒序）

- 997676d | 2025-08-11 | chore: 清理误生成文件 tatus 与 tatus --porcelain
  - 删除 tatus、tatus --porcelain（共 174 行删除）

- e041fff | 2025-08-11 | chore: 从版本控制中移除 .clinerules 与 .cursor 并加入 .gitignore
  - .gitignore 新增忽略规则：.clinerules/、.cursor/
  - 从版本控制中移除已追踪文件：.clinerules/mcp-interactive-feedback-rule.md、.cursor/rules/mcp-interactive-feedback.mdc

- 4d6d9d8 | 2025-08-11 | chore: 新增未跟踪文件并同步所有本地改动（.clinerules/.cursor/docs/scripts/辅助文件）
  - 文档：docs/MEMORY_MODEL_INDEPENDENCE_FIX.md、docs/MEMORY_MODEL_PROVIDER_SWITCH_FIX.md
  - 脚本：scripts/test_memory_model_independence.py、scripts/test_memory_model_provider_switch.py
  - 提示：.clinerules/ 与 .cursor/ 已在后续提交中从版本控制移除并忽略

- 8b76605 | 2025-08-11 | chore: 提交本地修改以与仓库同步（risk_manager/memory/trading_graph/sidebar/persistence）
  - 变更文件：
    - tradingagents/agents/utils/memory.py（内存与持久化逻辑增强）
    - tradingagents/graph/trading_graph.py（交易图逻辑更新）
    - web/components/sidebar.py（侧边栏交互与 UI 调整）
    - web/utils/persistence.py（持久化工具改进）
    - tradingagents/agents/managers/risk_manager.py（风险管理微调）
  - 统计：5 files changed, 291 insertions(+), 68 deletions(-)

## 影响与注意事项
- 忽略目录：已将 .clinerules/ 与 .cursor/ 加入 .gitignore，不再纳入版本控制。
- 清理：误生成文件 tatus 与 tatus --porcelain 已清理并推送。
- 兼容性：无破坏性变更；无需数据库迁移。

## 建议操作
- 如需在项目主页展示变更，可将本说明同步摘要至 CHANGELOG.md 顶部。


