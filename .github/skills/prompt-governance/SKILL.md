---
name: prompt-governance
description: "审计、修复并验证 TradingAgentsCN 中 agent 与提示词工作流。用于持仓分析、workflow prompt、MongoDB prompt_templates、adapter prompt assembly、合规修复、运行期模板与代码同步。触发词：修改 agent 提示词、提示词治理、DB 模板同步、workflow 提示词修复、持仓分析提示词排查、prompt compliance、runtime prompt audit。"
argument-hint: "描述工作流、agent 名称、目标问题和是否允许直接修改。例如：修复 position_analysis_v2 的 pa_technical_v2 提示词日期漂移，并同步运行期模板与代码。"
user-invocable: true
---

# Prompt Governance

这个 skill 用来处理“agent 行为不对，既可能是提示词问题，也可能是代码装配、运行期模板或兼容解析路径问题”的场景。

它不是普通的文案改写流程，而是一个运行期优先的治理流程：先确认真正控制行为的提示词和代码路径，再做最小修复，并把验证做完。

## 何时使用

- 用户要求修改某个 workflow 或 agent 的提示词，但仓库文件改了以后运行结果仍不对。
- 需要同时检查 repo fallback 提示词、MongoDB 中的 prompt_templates、adapter 的 _build_system_prompt / _build_user_prompt，以及 service 侧解析逻辑。
- 需要做持仓分析、研究链路、合规改写、用户视图精简、触发语去除、DB 模板同步这类工作。
- 日志里出现“运行期生成内容”和“仓库中的模板/代码理解”不一致。

## 不适用场景

- 只改一小段纯文案，且可以确定运行期不走数据库模板。
- 单纯解释某个 agent 在做什么，而不是要修复。
- 完全不涉及 prompt / workflow / adapter / DB 模板的普通后端 Bug。

## 核心原则

1. 先查运行期真实控制面，再改仓库文件。
2. 先做最小可证伪假设，再做最小修复，不先大改模板。
3. DB 模板和代码装配可能同时控制行为，不能假设只改一处就够。
4. 任何改动后都要做窄验证，再做治理校验。

## 标准流程

### 1. 锁定控制路径

- 先找 workflow_id、agent_name、触发日志、失败输出、相关测试。
- 优先定位真正计算或拼装行为的地方，而不是只看注册层。
- 如果是提示词类问题，先分清：
  - 运行期 DB 模板
  - repo fallback 模板
  - adapter 追加/改写的提示词片段
  - service 对输出的二次解析或清洗

### 2. 先审运行期模板

- 优先查询 MongoDB `prompt_templates` 集合，不要先假设 repo 模板在生效。
- 读取目标 `agent_type` + `agent_name` + `preference_type` + `status=active` 的模板。
- 如果是 without_cache / with_cache 双分支，必须分别确认。
- 如需修改 DB 模板，只改目标 active 文档，修改后立刻回读确认。

### 3. 再审代码装配层

- 重点检查 adapter 中：
  - `_build_system_prompt`
  - `_build_user_prompt`
  - 无缓存 fallback 分支
  - 上游报告摘要/净化逻辑
- 重点检查 service / workflow 层：
  - analysis_date、current_price、effective_data_date 的来源
  - legacy action / price_targets / recommendation 提取逻辑
  - 输出清洗是否会重新引入旧语义

### 4. 判断修复面

- 只改 DB：运行期模板错误，代码装配正确。
- 只改代码：运行期模板正确，但 adapter / service 在追加、污染或误解析。
- 双改：运行期模板和代码装配都需要同步，否则后续还会漂移。

### 5. 实施修复

- 代码修改保持最小化，避免重写整个 prompt。
- 对无缓存场景，优先补“显式参数约束”，避免 LLM 自行猜日期、ticker、价格口径。
- 对上游污染，优先做摘要化和净化，而不是把原始长文本继续塞给下游 agent。
- 对兼容出口，优先移除旧逻辑的自动提取，而不是在最终文案层硬洗。

### 6. 验证

- 先补或更新最窄的回归测试。
- 第一轮验证只跑触达的测试切片。
- 再跑治理校验任务。
- 如果改了 DB 模板，必须做回读验证；如果改了运行期行为，优先重跑目标 workflow 并查日志。

### 7. 输出结果

最终结论至少要包含：

- 根因在 DB 模板、代码装配、service 解析、还是数据口径。
- 实际改了哪些控制面。
- 做了哪些验证，哪些已通过。
- 是否还存在残余风险或下一步观察点。

## 执行清单

执行时按下面顺序走，不要跳步：

1. 查日志里的真实 workflow / agent / tool args。
2. 查 MongoDB `prompt_templates` 中正在生效的文档。
3. 查 adapter / service 的真实拼装路径。
4. 选定最小修复面并实施。
5. 跑窄测试。
6. 跑治理校验。
7. 如涉及 DB，再回读确认。

## 常见坑

- 只改 repo 提示词，没有改运行期 DB 模板。
- 只改 manager prompt，没有处理上游 analyst 原文污染。
- 只洗最终输出，没有去掉 service 的 legacy 兼容提取。
- 只看 analysis_date 变量，没有看 LLM 实际调用工具时传了什么参数。
- 把 current_price 口径问题误判成提示词问题，而没去看日志和数据源。

详细检查点见 [治理检查清单](./references/checklist.md)。