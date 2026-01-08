# 提示词的策略化：标准、模板、评估与合规

日期：2025-10-19  
项目：TradingAgents-CN  
用途：LLM 提示词策略化的工程与治理指南（与统一数据标准、插件体系配套）

## 1. 目标与原则
- 可复现：提示、上下文、参数与输出契约版本化（PIT：`data_version/feature_version/prompt_version`）。
- 可控：约束输出为结构化 JSON/函数调用，禁止自由文本泄露关键路径。
- 可审计：记录提示与响应（摘要/哈希），事件化：`llm.prompt.sent/llm.response.received/llm.eval.score`。
- 可组合：把提示当作“策略单元”，与数据、风控、引擎插件解耦；可路由可替换。
- 合规：敏感数据最小化注入；许可与内容政策对齐（含 Commons Clause 的“主要价值”评估）。

## 2. 策略化模型（Prompt as Strategy）
- Prompt 策略定义：
  - 元数据：`name/category/version/apiVersion/modelClass`（如 `reasoning/semantic/rlHF`）。
  - 输入契约：`input_schema`（引用 Canonical Schema 中必要字段）。
  - 输出契约：`output_schema`（决策/标签/结构化信息）。
  - 约束与规则：`guardrails`（禁止项、长度、敏感词、引用来源）、`eval_metrics`（精确率/一致性/置信度）。
- 策略类型：
  - 提取/归档：字段抽取、实体解析（公司名、行业）、事件摘要。
  - 分类/打标：行业/主题/情绪、风险标签；支持层级与多标签。
  - 决策/建议：信号、权重、风险动作；须给出理由与证据引用。
  - 生成/报告：面向人类的报告但通过结构化中间层落地。

## 3. 结构化提示模板（Template）
- 模板结构：`system`（角色与边界）+ `instructions`（任务与约束）+ `context`（数据片段）+ `output_format`（JSON 模式）。
- 输出格式示例：
```json
{
  "decision": "hold|buy|sell",
  "confidence": 0.0,
  "reasons": ["..."],
  "constraints_checked": {
    "no_future_leak": true,
    "data_version": "2025-10-19.v1",
    "feature_version": "sentiment.v3"
  },
  "references": [{"type":"doc","id":"news:123","ts":"2025-10-18T00:00:00Z"}]
}
```
- 函数调用（可选）：定义 `function_schema`，由模型走 `tool_call` 返回，避免自由文本。

## 4. 上下文注入与数据一致性
- 统一数据标准：上下文仅注入 Canonical Schema 字段（`full_symbol/exchange_mic/market/UTC ts/...`）。
- RAG 检索：从 `docs/` 与数据服务检索片段，标注 `asof` 与来源；禁止注入未来数据。
- 窗口与裁剪：优先结构化字段（数值/标签），摘要文本限制长度与敏感词；保留哈希。

## 5. 决策路由与模型选择（Orchestration）
- 路由策略：
  - 轻任务（提取/分类）→ 小模型；复杂推理/链路 → 大模型或工具增强。
  - 成本与延迟门控：`latency_budget/cost_budget`；退化路径（简化输出或延迟返回）。
- 多步链路：分类→打标→决策；每步固化输出并传递；失败熔断与降级策略。

## 6. 输出契约与验证
- JSON Schema 校验：后端强制校验输出结构与类型；空值与范围处理。
- 置信度与证据：要求 `confidence` 与 `references`（数据/文档 ID）；不满足则降级/重试。
- 风控集成：决策输出需通过风控插件 `pre_trade_check`；不合规则拒绝或修改。

## 7. 评估、版本冻结与 A/B
- 评估集：黄金样本（CN/HK/US 多市场、多行业、多场景）；对齐真实指标。
- 指标：精确率/召回/一致性（PIT）、稳定性（多次采样）、可解释性质量。
- A/B 与回放：固定 `prompt_version/model_version/data_version`；记录实验配置与报告。
- 发布策略：通过阈值门槛与回滚策略；弃用窗口与迁移提示。

## 8. 安全与合规
- 敏感信息：最小化注入；脱敏；只传必要 ID 与聚合指标。
- 许可与政策：避免生成违反开源条款或市场监管内容；Commons Clause 的“主要价值”审查。
- 审计：事件与日志结构化；保留哈希与摘要，而非原文全文。

## 9. 实施路径（Phased Plan）
- Phase 0：定义 `prompt.yaml` 清单（元数据/输入输出/guardrails/eval_metrics）；发布模板库。
- Phase 1：后端路由器与校验器（JSON Schema/函数调用/事件日志）；与数据服务对接 RAG。
- Phase 2：评估框架与黄金样本；A/B 管理与报告；SSE 事件流接入前端观测。
- Phase 3：与插件体系联动：把提示作为 `Strategy.Feature/Report` 插件；版本与兼容矩阵对齐。

## 10. 示例：prompt.yaml（片段）
```yaml
name: decision.sentiment.v1
category: decision
version: 1.0.0
apiVersion: v1
modelClass: reasoning
input_schema: schema://canonical.market.news.v1
output_schema: schema://decision.v1
guardrails:
  max_tokens: 1024
  disallow_future_leak: true
  require_references: true
eval_metrics:
  - accuracy
  - stability
```

## 11. 检查清单（Checklist）
- 发布 `prompt.yaml` 模板与路由契约；冻结 `prompt_version`。
- 启用 JSON Schema 校验与函数调用；落地事件日志与审计。
- 对接统一数据标准与 RAG；控制窗口与敏感信息。
- 建立评估与 A/B；设定阈值与回滚。
- 与插件体系对齐，把提示策略作为可替换模块管理。

注：本指南与统一数据标准及插件治理文档配套；后续可在 `docs/config/prompts/` 发布模板与 Schema，在后端 `app/routers/llm.py` 实现路由与校验，并在前端增加观测面板。