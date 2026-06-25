# v3.0 L5/L6 召回质量优化实施说明

## 📋 文档信息

| 项目 | 内容 |
| ------ | ------ |
| 版本 | v1.0 |
| 状态 | P0 已完成首轮落地，观测能力仍待补齐 |
| 日期 | 2026-04-08 |
| 目标 | 记录 L5/L6 召回质量优化的当前落地状态、剩余缺口和后续补强方向 |
| 关联文档 | [v3.0 记忆系统优化待办清单](./memory-optimization-backlog.md)、[统一记忆层设计 — 基于 mem0 的全系统记忆整合](./unified-memory-layer-mem0.md)、[v3.0 能力与七层记忆对应关系](./memory-capability-layer-mapping.md)、[记忆消费闭环验证脚本](../../../scripts/validate_memory_consumption_loops.py) |

---

## 1. 目标收敛

这次优化不是为了“改 MemoryService 架构”，而是为了解决一个更直接的问题：

**当前 L5/L6 已经能召回，但还不能稳定保证召回结果足够相关、足够干净、足够适合注入 prompt。**

本项优化只处理三件事：

1. **先过滤准**：尽量先用 metadata 把候选集缩小
2. **再排序稳**：在语义相似度之外，补去重、新鲜度、对象精确性等重排逻辑
3. **再注入可控**：确保注入 prompt 的内容短、稳、可解释，不把上下文撑爆

### 1.1 截至 2026-04-08 的状态

当前这三件事都已经完成首轮落地：

1. 过滤链路已支持 exact filter 下推和本地 metadata 精修正
2. 召回链路已支持统一重排、去重和场景化 ranking profile
3. 注入链路已支持按 scope 分段和 per-scope 限流
4. 当前仍未完成的是统一观测面和更广的跨对象质量评估

---

## 2. 当前实现现状

## 2.1 当前主入口

当前 L5/L6 召回主入口在 [core/memory/service.py](../../../core/memory/service.py)：

1. `MemoryService.recall()`
2. `MemoryService.recall_formatted()`

主要消费方有：

1. 智能助手：[app/services/intelligent_assistant_service.py](../../../app/services/intelligent_assistant_service.py)
2. 股票分析：[app/services/unified_analysis_service.py](../../../app/services/unified_analysis_service.py)
3. Skill 生成：[app/services/skill_generation_service.py](../../../app/services/skill_generation_service.py)

---

## 2.2 当前代码行为

按当前实现，召回链路大致如下：

```text
调用方传 query/scopes/metadata_filters
-> MemoryService.recall()
-> 若单 scope + 简单 metadata，可下推 mem0 exact filter
-> 否则扩大 limit，拉更多候选到本地
-> 本地按 scope 过滤
-> 本地按 metadata 精确过滤
-> 按对象精度 / scope 权重 / 语义分数 / 新鲜度统一重排
-> 去重后再截断
-> recall_formatted() 按业务 profile 做分段和限流格式化
```

这个实现已经从“最小可用”提升到“主路径可用”，但观测和跨对象质量验证还没有补齐。

---

## 2.3 当前短板

### 1. 统一观测仍然不足

当前已经有统一重排，但还缺稳定的指标与 dashboard 来解释召回表现。

影响：

1. 很难快速回答某次召回为什么变差
2. 很难长期比较 profile 调整前后的收益

### 2. 跨对象质量验证还不够强

当前 profile 和 metadata 精确过滤已经补上，但高质量验证样本仍主要集中在助手、分析和 Skill 三条主链。

影响：

1. `workflow` 之外的更多业务对象仍缺少稳定评估样本
2. Agent 生成已进入首轮受控样本，但更广的非股票对象评估还不够系统

### 3. 统一观测仍然是 Agent 生成场景的主要剩余缺口

当前 Recall 质量优化已经开始覆盖 Agent 生成专用 L6，但统一指标和更早读取点还没有补齐。

影响：

1. 还不能稳定解释某次 Agent Builder lesson 为什么命中或为什么没命中
2. 需求确认阶段、版本构建前等更早读取点尚未进入统一样本集

---

## 3. 当前目标行为

当前召回链路已经变成：

```text
query + scope + metadata_filters
-> 尽量下推精确过滤
-> 拉候选集
-> 本地 metadata 精修正
-> 按对象精度 / scope 权重 / 相似度 / 新鲜度统一重排
-> 去重
-> 按业务场景格式化注入
-> 输出脚本级验证结果
-> 后续补统一观测指标
```

关键结果应该是：

1. 命中更准
2. 注入更短
3. 重复更少
4. 更容易解释为什么选中了这些记忆
5. 仍保留进一步补指标、补对象样本的空间

---

## 4. 实施范围

## 4.1 必改文件

| 文件 | 作用 |
| ------ | ------ |
| [core/memory/service.py](../../../core/memory/service.py) | 统一召回、重排、去重、格式化主入口 |
| [app/services/intelligent_assistant_service.py](../../../app/services/intelligent_assistant_service.py) | 助手侧召回场景配置 |
| [app/services/unified_analysis_service.py](../../../app/services/unified_analysis_service.py) | 股票分析侧召回场景配置 |
| [app/services/skill_generation_service.py](../../../app/services/skill_generation_service.py) | Skill 生成侧召回场景配置 |
| [scripts/evaluate_memory_recall_quality.py](../../../scripts/evaluate_memory_recall_quality.py) | 受控召回质量评估脚本 |
| [scripts/validate_memory_consumption_loops.py](../../../scripts/validate_memory_consumption_loops.py) | 受控消费闭环验证脚本 |

## 4.2 当前已新增文件

| 文件 | 作用 |
| ------ | ------ |
| [tests/core/memory/test_memory_service_filters.py](../../../tests/core/memory/test_memory_service_filters.py) | 召回排序、过滤、去重单测 |
| [tests/scripts/test_evaluate_memory_recall_quality.py](../../../tests/scripts/test_evaluate_memory_recall_quality.py) | 评估脚本测试 |
| [tests/scripts/test_validate_memory_consumption_loops.py](../../../tests/scripts/test_validate_memory_consumption_loops.py) | 消费闭环验证脚本测试 |
| [tests/services/test_workflow_growth_memory_bridge.py](../../../tests/services/test_workflow_growth_memory_bridge.py) | workflow growth 桥接与 pattern 召回回归测试 |

---

## 5. 分步落地状态

## 5.1 Step 1：在 MemoryService 内引入统一重排

状态：已完成

### Step 1 目标

让本地过滤后的结果，先经过统一排序，再交给上层使用。

### Step 1 建议规则

排序权重建议按以下顺序组合：

1. **对象精确命中优先**
   - `symbol` / `ticker` / `object_key` 精确命中优先
2. **scope 优先级**
   - 不同调用场景允许自定义 scope 权重
3. **语义相似度**
   - 继续使用 mem0 score 作为主体信号
4. **新鲜度**
   - 较新的内容优先，但不能完全盖过高相关内容

### Step 1 实现建议

当前实现主要由以下能力组成：

1. `_build_mem0_exact_filter(...)`
2. `_sort_recalled_items(...)`
3. `recall(..., ranking_profile="default")`

先不要引入复杂学习排序，当前版本只做规则重排。

### Step 1 完成标准

1. `recall()` 不再直接返回“过滤后原顺序结果”
2. 不同调用方可以选择基础 ranking profile

---

## 5.2 Step 2：引入统一去重逻辑

状态：已完成

### Step 2 目标

避免同义、同源、相近内容重复注入 prompt。

### Step 2 去重建议

至少做两级去重：

1. **ID 去重**
2. **文本归一化去重**
   - 去掉空白、标点差异后的近似相同文本

可选补充：

1. **同 object_key + 同 scope + 同源近似文本去重**

### Step 2 实现建议

在 [core/memory/service.py](../../../core/memory/service.py) 新增：

1. `_normalize_memory_text(...)`
2. `_dedupe_recalled_items(...)`

### Step 2 完成标准

1. `recall_formatted()` 生成的记忆块明显减少重复语句
2. 单元测试能覆盖“相同文本不同 metadata”的去重行为

---

## 5.3 Step 3：引入场景化 ranking profile

状态：已完成

### Step 3 目标

不同业务链路对记忆的优先级不同，不能一套排序打天下。

### Step 3 建议 profile

1. `assistant`
   - `user_preference` 和对象精确命中的 `analysis_insight` 优先
2. `analysis`
   - `analysis_insight`、`agent_experience` 优先，且 symbol 精确过滤优先级更高
3. `skill_generation`
   - `skill_lesson` 优先，metadata 精确命中高于语义近似

### Step 3 实现建议

1. 在 [core/memory/service.py](../../../core/memory/service.py) 维护 profile 配置表
2. 调用方改成显式传入 profile：
   - 助手：`ranking_profile="assistant"`
   - 股票分析：`ranking_profile="analysis"`
   - Skill：`ranking_profile="skill_generation"`

### Step 3 完成标准

1. 调用方不再只是给 `scopes + limit`
2. 不同链路能使用不同优先级策略

---

## 5.4 Step 4：把 recall_formatted 从“线性拼接”改成“受控注入”

状态：已完成

### Step 4 目标

让格式化输出更适合 prompt，而不是简单列条目。

### Step 4 当前问题

现在的格式是：

```text
【历史记忆】
- [偏好] ...
- [分析] ...
```

这对调试友好，但对模型未必最优。

### Step 4 建议优化

按 scope 分段输出，例如：

```text
【历史偏好】
- ...

【历史洞察】
- ...

【历史经验】
- ...
```

并加入每个 scope 的最大条数控制，避免某一类记忆完全占满空间。

### Step 4 实现建议

1. 在 [core/memory/service.py](../../../core/memory/service.py) 为 `recall_formatted()` 增加：
   - `group_by_scope`
   - `per_scope_limit`
   - `ranking_profile`
2. 默认保持向后兼容，调用方逐步切换新参数。

### Step 4 完成标准

1. 格式化输出可按 scope 分段
2. 单个 scope 不会独占全部注入空间

---

## 5.5 Step 5：补观测和评估脚本

状态：部分完成

### Step 5 目标

让这轮优化有明确的“前后对比”。

### Step 5 评估样本建议

1. 智能助手：
   - 同一用户不同主题下的偏好召回
   - 同一股票的历史洞察召回
2. 股票分析：
   - 同 symbol 历史结论是否优先命中
   - manager / researcher 经验是否优先命中
3. Skill 生成：
   - 相同 category + data_source 的历史 lesson 是否优先命中
4. Agent 生成：
   - 同 spec 的 `agent_builder_lesson` 是否优先于泛化 `agent_experience`
   - 相同 spec_id 的失败 lesson 是否能在 runtime governance 场景优先命中

### Step 5 指标建议

1. 命中率
2. 空召回率
3. 去重前后条数变化
4. 注入字符数
5. 对象精确命中占比

### Step 5 实现建议

1. 已新增 `scripts/evaluate_memory_recall_quality.py`
2. 用受控样本而不是线上全量数据做第一轮比较
3. 输出 JSON 或 Markdown 结果，便于后续迭代对比

### Step 5 完成标准

1. 能跑出一份优化前后的对比结果
2. 后续每次改召回规则，都能复用这套样本

### Step 5 当前缺口

1. 仍缺统一指标入口，当前主要依赖脚本结果和测试断言
2. 评估样本虽然已补 Agent Builder 首轮场景，但更广的非股票对象覆盖仍不够

---

## 6. 调用方当前状态

## 6.1 智能助手

文件：[app/services/intelligent_assistant_service.py](../../../app/services/intelligent_assistant_service.py)

当前状态：

1. 给 `recall_formatted()` 显式加 `ranking_profile="assistant"`
2. 开启按 scope 分段输出
3. 对 `conversation` 设置更低的注入优先级，避免压过 `user_preference` / `analysis_insight`

## 6.2 股票分析

文件：[app/services/unified_analysis_service.py](../../../app/services/unified_analysis_service.py)

当前状态：

1. 给 `recall_formatted()` 显式加 `ranking_profile="analysis"`
2. 强化 `symbol` 命中权重
3. 让 `analysis_insight` / `agent_experience` 比 `user_preference` 更靠前

## 6.3 Skill 生成

文件：[app/services/skill_generation_service.py](../../../app/services/skill_generation_service.py)

当前状态：

1. 给 `recall_formatted()` 显式加 `ranking_profile="skill_generation"`
2. 强化 `category + data_source` 命中优先级
3. 对 `tool_id` 回退匹配保留，但优先级低于完整 metadata 精确命中

---

## 7. 当前测试状态

## 7.1 单元测试

当前已补测试文件：

- `tests/core/memory/test_memory_service_filters.py`

至少覆盖：

1. 单 scope / 多 scope 下的排序行为
2. metadata 精确命中优先
3. 重复文本去重
4. 分段格式化输出
5. 不同 ranking profile 的差异

## 7.2 集成验证

当前已补脚本：

- `scripts/evaluate_memory_recall_quality.py`

至少覆盖：

1. 助手场景
2. 股票分析场景
3. Skill 生成场景

---

## 8. 不在本次范围内

本次优化明确不做：

1. 重构 mem0 底层 SDK 接入方式
2. 让 mem0 取代 Nanobot 本地 compact
3. 处理 legacy memory 彻底删除
4. 引入复杂机器学习排序模型
5. 一次性覆盖全部对象类型

---

## 9. 后续推荐顺序

1. 先补统一观测字段和指标入口
2. 再扩评估样本到 Agent 生成等非主召回对象
3. 最后继续细化 object 维度过滤策略

这个顺序的好处是：

- 先把公共能力收口
- 再扩散到调用方
- 最后用评估证明这轮改动有价值

---

## 10. 一句话版

这次 P0-2 当前更准确的状态是：

1. 统一重排已经落地
2. 去重和分段注入已经落地
3. 统一评估已完成脚本化第一轮，统一观测仍待补齐
