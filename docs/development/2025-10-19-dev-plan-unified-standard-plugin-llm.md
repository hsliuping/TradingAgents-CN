# 开发计划：统一数据标准、插件体系、提示词策略化（基于 v1.0.0-preview）

日期：2025-10-19  
基线分支：`v1.0.0-preview`  
新开发分支：`feature/unified-standard-plugin-llm-v1`  
范围：数据一致性（PIT）、插件架构、LLM 提示策略化与最小后端接口

## 1. 目标与可交付物（Deliverables）
- 文档交付：
  - 统一数据标准与实施路径（已交付）
  - 插件体系与治理（已交付）
  - 提示词策略化指南（已交付）
  - 会议纪要（已交付）
  - 开发计划（本文件）
- 代码交付（MVP）：
  - `docs/config/` 字典与模板：`exchanges.json`、`industry-map.json`、`prompts/*`
  - 后端 `app/routers/data.py`：`GET /meta/symbol/resolve`、`GET /data/candles` 契约草案
  - 插件管理器 `app/plugins/manager.py`：注册/加载/健康检查/签名校验轮廓
  - 参考插件：`datasource.tushare`（符号解析与基础 OHLCV）
  - LLM 路由 `app/routers/llm.py`：`POST /llm/route`（JSON Schema 校验、事件日志钩子）
  - 测试：黄金样本集与契约测试（符号解析、行业映射、时间/单位归一化、LLM 输出校验）

## 2. 分阶段计划（2 周）
- Week 1（Phase A：基础能力）
  - `docs/config/` 发布 `exchanges.json/industry-map.json`（ISO 10383、GICS 映射）
  - `app/routers/data.py` 增加 `GET /meta/symbol/resolve` 与 schema；黄金样本集 50+ 标的
  - `app/plugins/manager.py` 基本轮廓与注册/健康探针（占位实现）
  - `docs/config/prompts/` 发布 `decision.v1/classification.v1` 的 JSON Schema 模板
  - 单元测试：符号解析、时间归一化、JSON Schema 校验器
- Week 2（Phase B：集成与观测）
  - `GET /data/candles` 基本契约与模拟数据返回（UTC/单位/币种元数据）
  - `datasource.tushare` 插件骨架并打通到 `data.py`（适配器返回 Canonical Schema）
  - `app/routers/llm.py` 路由与事件日志（`llm.prompt.sent/llm.response.received`）；SSE 观测订阅
  - 契约测试：数据服务与 LLM 路由；冲突与仲裁日志生成
  - 文档更新：API 契约与插件清单模板；发布兼容矩阵草案

## 3. 里程碑与验收标准
- 里程碑 A（周末验收）：
  - 解析接口 `GET /meta/symbol/resolve` 返回 `full_symbol/exchange_mic/vendor_symbols`（UTC 与枚举对齐）
  - prompt 模板与 Schema 可用；JSON 校验器拦截不合格输出
  - 插件管理器可注册与健康探针（占位），能列举插件清单
- 里程碑 B（两周验收）：
  - `GET /data/candles` 正确返回 UTC 对齐、单位与币种元信息；黄金样本契约测试通过
  - `datasource.tushare` 插件返回规范化 OHLCV 并被路由使用
  - `POST /llm/route` 正常执行并输出结构化 JSON；事件日志与 SSE 观测可见

## 4. 任务拆分（Sprint Tasks）
- 字典与模板：`exchanges.json`、`industry-map.json`、`prompts/*.schema.json`、`plugins.registry.template.json`
- 路由与适配器：`data.py`（resolve/candles）、`llm.py`（route/validate）
- 插件管理：`manager.py`（registry/load/health/signature）与 `datasource.tushare` 骨架
- 测试与样本：`tests/dataflows/` 与 `tests/services/` 的契约/单元/集成测试
- 文档更新：`docs/api/` 契约、`docs/config/` 字典发布、`docs/tech_reviews/` 变更记录

## 5. 分支策略与版本
- 新分支：`feature/unified-standard-plugin-llm-v1` 自 `v1.0.0-preview` 派生
- 提交规范：`type(scope): message`（如 `docs(tech_reviews): add unified standard`）
- 版本冻结：`schema=v1`、`apiVersion=v1`；破坏性变更走次分支与迁移指南

## 6. 风险与缓解
- 多来源差异与冲突：通过仲裁日志与人工覆盖台帐；优先黄金样本集
- 许可合规：Backtrader 作为独立服务；vectorbt Commons Clause 的“主要价值”评估；NOTICE 汇总
- 数据质量与单位：统一 `unit_multiplier/currency/fx_rate_timestamp`；增量修正策略
- LLM 输出不稳定：JSON Schema 强校验与降级路径；A/B 版本控制

## 7. 责任与沟通（可补充）
- 每日站会同步进度；需求与变更走变更记录与兼容矩阵
- 提交通过 CI 契约测试；合并需验证观测面板与 SSE 事件

注：本计划围绕最小可用路径，优先打通统一标准、路由与插件骨架；后续可按需引入 Backtrader/Lean 的 EngineAdapter 与 PaperService。