# v2.1.0 Upgrade Config Suggestions

## Changed files that may affect config/templates/runtime defaults

- app/services/simple_analysis_service.py
- core/workflow/builder.py
- tradingagents/graph/trading_graph.py
- app/scripts/init_providers.py
- app/worker/unified_thread_pool_sync_service.py
- tradingagents/dataflows/data_source_manager.py
- install/database_export_config_2026-04-30.json

## Recommended collections to review for upgrade_config.json

- system_configs
- llm_providers
- model_catalog
- prompt_templates
- agent_configs
- tool_configs
- tool_agent_bindings
- workflow_definitions
- agent_workflow_bindings
- agent_io_definitions
- stock_industry_mappings

## How to populate upgrade_config.json

1. 导出当前 MongoDB 配置基线。
2. 以 2.0.1 安装快照或 releases/2.0.1 为对照，仅收录 2.1.0 新增或发生变化的文档。
3. 优先保证 llm_providers、model_catalog、system_configs 和 tool/agent 绑定关系与运行时代码一致。
4. 如果行业映射将作为安装/升级基线一起发版，请把 stock_industry_mappings 纳入 upgrade_config，并确认导入集合包含该集合。

## Verification focus

- 升级后的旧安装必须拿到新的 provider::model 路由配置，避免同名模型选错厂家
- 旧安装必须能识别 AIHubMix 提供商与相关模型目录
- 工作流和 agent 绑定关系应与当前 install 快照保持一致