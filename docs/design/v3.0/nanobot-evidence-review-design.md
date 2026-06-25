# Nanobot 证据优先评审设计

## 1. 背景

当前 Agent Workshop 的正式评估入口是 production-review。

现状实现：

- Nanobot 负责触发测试链路和编排工具调用。
- AgentWorkshopService 负责接收 runtime_result，并生成正式 evaluation 记录。
- production-review 会先做一轮规则扫描，再把规格、版本信息、prompt 摘要、tool_trace 摘要、output_text、output_payload 预览一起提交给 LLM judge。
- 最终 issue、recommendations、scores 以 LLM judge 结果为主，规则扫描为辅。

这条链路的问题不是“模型不够聪明”，而是责任边界错误：

- 它没有把“发现问题”和“确认问题”拆开。
- 它没有为每条 issue 建立强制证据链。
- 它会把缺少证据的推断包装成正式问题。
- 它更像 artifact review，而不是 evidence-first 的调查流程。

典型现象：

- 实际日志没有出现某个工具报错，但 production-review 仍然生成“已确认工具参数错误”的 issue。
- tool_trace 缺失或不完整时，系统仍继续输出结论。
- 用户看到的不是“证据不足”，而是“貌似合理但无法复核”的正式评估报告。

因此，本设计的目标不是继续微调现有评审 prompt，而是重构 production-review 的工作模式。

## 2. 设计目标

本次补强的目标是：

- 将 production-review 从“LLM 直接裁决”改为“Nanobot 子 agent 负责调查，规则层负责定案”。
- 将每条正式 issue 升级为必须带 evidence 的结构化对象。
- 在证据不足时返回“无法确认”而不是继续生成正式故障结论。
- 保留当前 Agent Workshop 的 Spec / Version / Evaluation / Runtime Config 数据结构，不推翻已有资产模型。
- 为后续更细粒度的诊断子 agent 留出扩展接口。

## 3. 非目标

本次设计不追求：

- 让 Nanobot 完全替代 AgentWorkshopService 的版本、评估和发布持久化逻辑。
- 让 LLM 完全退出评估链路。
- 一次性重写所有前端页面和历史评估记录结构。
- 引入复杂的多模型协同或外部调度系统。

LLM 仍可保留，但只能退到辅助意见层，不能继续承担官方评估的主裁判职责。

## 4. 核心原则

新的评审链路遵循以下原则：

1. 先取证，后结论。
2. 证据不足时拒绝判定，不得脑补。
3. 发现问题、查证问题、汇总问题必须拆层。
4. 正式 evaluation 只接收结构化 evidence bundle，不直接消费自由文本猜测。
5. 发布门槛必须基于可复核事实，而不是基于一次解释型打分。

## 5. 当前 production-review 的问题拆解

当前实现可以抽象为：

1. 收集 runtime_result。
2. 做规则扫描。
3. 调用 LLM judge 对运行结果做综合评审。
4. 合并成正式 evaluation 并落库。

问题点如下：

### 5.1 规则检查只消费现有产物，不主动查证

当前规则扫描只看：

- output_text
- output_payload
- debug_prompt
- tool_trace
- required_tools
- execution_plan

它不会为了验证某个 issue 是否真实，再主动：

- 重放工具调用
- 查询运行日志
- 对照原始 tool result
- 查找某个失败点的直接异常文本

### 5.2 LLM judge 仍然在做“解释型裁决”

即使 prompt 明确要求“不能把证据中没有的事实当成事实”，模型仍然会在以下场景里产生推断：

- required_tools 没命中时，推断工具失败原因。
- 输出缺字段时，推断某个中间工具调用异常。
- tool_trace 缺失时，根据 spec 和历史问题补全失败叙事。

### 5.3 issue 缺少强制 evidence 结构

当前 issues 只是字符串数组，无法表达：

- 问题是如何发现的
- 对应证据来自哪里
- 是已证实还是仅仅可疑
- 证据强度有多高

这导致前端和用户无法区分“事实”与“推断”。

## 6. 目标架构

目标架构采用四层模型：

1. Nanobot Review Orchestrator
2. Nanobot Evidence Workers
3. Evidence Bundle
4. Rule-based Decision Layer

### 6.1 Nanobot Review Orchestrator

职责：

- 接收版本、规格和 runtime_result。
- 发现候选问题。
- 将候选问题拆成若干查证任务。
- 分配给不同 evidence worker。
- 汇总 worker 结果，生成 evidence bundle。

它不负责最终发布结论。

### 6.2 Nanobot Evidence Workers

每个 worker 只负责一类证据核查。

建议的第一批 worker：

- Tool Usage Worker
  - 检查 required_tools 是否真实调用。
  - 检查调用是否成功。
  - 检查工具参数和输出是否可用。

- Output Coverage Worker
  - 检查规格要求的输出字段是否真的出现在结果中。
  - 区分“字段缺失”和“字段只被口头提及”。

- Numeric Traceability Worker
  - 检查估值区间、目标价、评分等数字是否有来源。
  - 检查是否存在结构化计算依据。

- Constraint Worker
  - 检查是否越界。
  - 检查是否违背 non_goals / constraints。

- Runtime Failure Worker
  - 从 tool_trace、raw_result、运行日志中确认是否存在真实异常。
  - 不能从缺失证据推出异常原因。

### 6.3 Evidence Bundle

Evidence Bundle 是正式评估层唯一接收的调查结果。

它的核心要求是：

- 只包含已发现的事实、明确的未证实项、以及证据不足项。
- 不包含自由推断式总结。
- 每个问题都必须有结构化证据。

### 6.4 Rule-based Decision Layer

职责：

- 读取 evidence bundle。
- 将 evidence bundle 转为正式 evaluation。
- 根据硬规则决定：
  - 哪些 issue 成立
  - 哪些 issue 不成立
  - 哪些 issue 证据不足
  - 当前评估是否有效
  - 当前版本是否可发布

规则层必须 fail-closed。

## 7. 目标流程

目标流程如下：

1. 发现问题
2. 分配任务
3. 查证
4. 总结
5. 定案

### 7.1 发现问题

输入：

- spec
- version
- runtime_result

输出：

- candidate_findings

candidate_findings 只是一组待查证对象，例如：

- required_tools 未命中
- 某数值缺少来源
- 输出字段未覆盖
- 存在疑似工具调用失败

这一阶段不允许生成正式 issue。

### 7.2 分配任务

Orchestrator 根据 candidate_findings 生成 evidence tasks。

例如：

- task_1: 检查 analyze_a_share_dupont 是否被调用，调用是否成功
- task_2: 检查 valuation_report 是否覆盖 required output
- task_3: 检查 18-22 倍 PE 是否具备结构化来源

### 7.3 查证

各 worker 只返回结构化证据，不返回正式结论。

每个 worker 只允许返回三类状态：

- confirmed
- disproved
- insufficient_evidence

### 7.4 总结

Orchestrator 汇总所有 worker 结果，构建 evidence bundle。

### 7.5 定案

Decision Layer 只基于 evidence bundle 输出正式 evaluation。

如果 evidence bundle 中缺少关键证据：

- 不生成正式 pass/reject 结论
- 不生成“已确认故障”类 issue
- 返回 evaluation_invalid 或 evidence_incomplete 状态

## 8. Evidence Bundle 结构

建议数据结构如下：

```json
{
  "review_mode": "evidence-first",
  "version_id": "spec_x_v1",
  "spec_id": "spec_x",
  "runtime_context": {
    "symbol": "600519",
    "analysis_date": "2026-04-06",
    "has_output_text": true,
    "has_output_payload": true,
    "tool_trace_count": 3
  },
  "candidate_findings": [
    {
      "finding_id": "tool_usage_dupont_missing",
      "dimension": "runtime_tool_usage",
      "title": "杜邦分析维度未覆盖",
      "status": "insufficient_evidence"
    }
  ],
  "evidence_items": [
    {
      "finding_id": "tool_usage_dupont_missing",
      "worker": "tool-usage-worker",
      "status": "disproved",
      "evidence_type": "tool_trace",
      "evidence_source": "runtime_result.debug_prompt.tool_trace",
      "evidence_excerpt": "未发现 analyze_a_share_dupont 调用失败记录",
      "confidence": 0.92,
      "notes": ["当前证据只能证明未发现失败记录，不能证明工具一定已成功执行"]
    }
  ],
  "summary": {
    "confirmed_findings": [],
    "disproved_findings": ["tool_usage_dupont_missing"],
    "insufficient_evidence_findings": []
  }
}
```

## 9. 正式 Issue 结构

当前字符串数组形式的 issue 无法满足证据要求。

建议升级为结构化 issue：

```json
{
  "severity": "medium",
  "dimension": "runtime_tool_usage",
  "title": "required_tools 未命中",
  "description": "本次运行没有命中 analyze_a_share_dupont。",
  "finding_status": "confirmed",
  "evidence": [
    {
      "source": "runtime_result.debug_prompt.tool_trace",
      "excerpt": "tool_trace 中仅出现 get_balance_sheet_analysis, get_cashflow_analysis",
      "type": "tool_trace"
    }
  ],
  "confidence": 0.95,
  "blocking": true
}
```

新规则：

- 没有 evidence 的 issue 不允许落库。
- finding_status 不是 confirmed 的 issue 不允许计入正式失败结论。
- insufficient_evidence 只能进入 warnings，不进入正式 issues。

## 10. 对 production-review 的改造建议

### 10.1 Phase 1：先做 fail-closed

在不引入完整 Nanobot 子 agent 之前，先把 production-review 改成保守模式：

- 若缺少 tool_trace / output_payload / debug_prompt 中的关键证据，则标记为 evidence_incomplete。
- 不再允许 LLM 直接生成确认性故障原因。
- 仅保留规则扫描结果和“证据不足”提示。

这一阶段的目标是先止血，避免继续产生幻觉型 issue。

### 10.2 Phase 2：新增 evidence-only 子流程

新增 Nanobot evidence review 子链路：

- 输入 runtime_result
- 输出 evidence bundle
- 不生成正式 decision

### 10.3 Phase 3：Decision Layer 替换当前 LLM judge 主裁判

当 evidence bundle 稳定后：

- 当前 _judge_runtime_result_with_llm 降级为 advisory layer
- 正式 evaluation 由规则层从 evidence bundle 生成

## 11. LLM 的保留方式

LLM 不是必须移除，但必须降级。

建议保留场景：

- 对 evidence bundle 做自然语言摘要
- 给出改进建议
- 帮助整理待确认问题

不应继续承担的职责：

- 直接确认某个故障真实存在
- 在证据不足时脑补失败原因
- 独立决定是否通过发布门槛

## 12. 与现有代码的接入点

建议最小接入点如下：

### 12.1 AgentWorkshopService.evaluate_version

保留作为统一正式评估入口，但内部逻辑改为：

- collect_evidence
- build_evidence_bundle
- decide_evaluation_from_evidence

### 12.2 run_agent_workshop_real_data_test

继续负责：

- 执行 debug_version
- 构造 runtime_result
- 触发正式评估

但正式评估内部不再直接进入 LLM judge 主裁判逻辑。

### 12.3 新增接口建议

建议增加内部方法或工具：

- _collect_runtime_evidence(...)
- _run_nanobot_evidence_review(...)
- _build_evidence_bundle(...)
- _decide_evaluation_from_evidence(...)

## 13. 验收标准

新的评估链路至少满足：

1. 没有证据的 issue 不得落库。
2. 任意“工具调用失败”类 issue 必须带 tool_trace 或日志证据。
3. 任意“参数错误”类 issue 必须带原始异常文本证据。
4. 若 evidence bundle 不完整，正式评估必须返回 evidence_incomplete，而不是继续生成 pass/reject。
5. 前端必须能区分：
   - 已证实问题
   - 未证实问题
   - 证据不足

## 14. 实施顺序

建议实施顺序：

1. 先改 production-review 为 fail-closed。
2. 引入 evidence bundle 数据结构。
3. 给前端补 evidence 状态展示。
4. 再接入 Nanobot 子 agent 做 evidence collection。
5. 最后把当前 LLM judge 降级为 advisory。

## 15. 结论

当前 production-review 最大的问题不是提示词不够好，而是角色定义错误。

它当前同时承担了：

- 问题发现
- 问题确认
- 问题解释
- 最终裁决

这会天然导致“缺证据时继续编排叙事”的问题。

新的方向应当是：

- Nanobot 子 agent 负责调查
- Evidence Bundle 负责承载事实
- Rule Layer 负责正式定案
- LLM judge 只保留为辅助意见

这样才能把“看起来像问题”与“已经证实的问题”真正区分开。