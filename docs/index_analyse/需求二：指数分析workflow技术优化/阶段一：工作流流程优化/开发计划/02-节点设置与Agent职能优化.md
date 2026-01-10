# 开发计划 02 - 节点设置与 Agent 职能优化

## 1. 任务目标
*   实现政策分析与新闻分析的职能分离。
*   支持动态 Agent 选择。
*   新增情绪分析节点 (规划中)。

## 2. 详细设计
*   **Strategic Policy Analyst**: 聚焦长期政策，屏蔽短期传闻。
*   **News Analyst**: 整合国际/国内短期新闻。
*   **Dynamic Graph**: `_setup_index_graph` 支持 `selected_analysts` 参数过滤。

## 3. 开发步骤
1.  [x] 重构 `policy_analyst.py`，更新 System Prompt。
2.  [x] 重构 `international_news_analyst.py` 为 `News Analyst`，集成多源新闻工具。
3.  [x] 修改 `tradingagents/graph/setup.py`，实现动态图构建逻辑。(已在 `v2.6.0` 修复)
4.  [x] 修改 `tradingagents/services/analysis_service.py`，确保参数透传。(已在 `v2.6.0` 修复)
5.  [ ] (可选) 设计 `Sentiment Analyst` 原型。

## 4. 验收标准
*   **职能分离**: `Policy Analyst` 报告中无短期传闻，`News Analyst` 报告包含各类短期消息。
*   **动态选择**: API 传入 `['macro']` 时，只执行宏观分析，其他节点被跳过，最终报告只包含宏观部分。

## 5. 当前进度 (2026-01-03)
*   **状态**: 🟢 已完成 / 🚧 进行中 / 📋 规划中
*   **说明**:
    *   Agent 代码职能分离（`Policy Analyst` 与 `News Analyst` 重构）已完成。
    *   动态 Agent 选择：服务层参数透传和后端动态图构建的核心逻辑已完成（参考 `指数分析Workflow_多空与风控优化建议.md` 中的 `v2.6.0` 更新）。但仍需进行详细的完整性和健壮性验证，具体验证计划见第 6 节。
    *   情绪分析节点：仍处于规划中，原型设计待进行。

## 6. 动态 Agent 选择验证计划

为了确认和验证“动态 Agent 选择”的完整性和健壮性，需从**功能测试**、**边界条件测试**和**性能测试**三个方面入手。

### 6.1 完整性确认与验证

**目标**：确保所有预期功能都已实现，且按照设计工作。

*   **测试方法**：
    *   **正向功能测试**：
        *   **单 Agent 运行**：验证当只选择一个 Agent (例如 `macro` 或 `technical`) 时，Workflow 是否只执行该 Agent，并生成仅包含该 Agent 报告的结果。
            *   *示例命令*：`python index_analyse/Script/download_index_report.py --symbol 000300 --depth 快速 --analysts macro`
        *   **多 Agent 运行**：验证当选择多个 Agent (例如 `macro` 和 `policy`) 时，Workflow 是否执行所有选定的 Agent，并正确合并它们的报告。
            *   *示例命令*：`python index_analyse/Script/download_index_report.py --symbol 000300 --depth 快速 --analysts macro policy`
        *   **全 Agent 运行**：验证当选择所有默认 Agent 时 (例如 `macro`, `policy`, `news`, `sector`, `technical`)，Workflow 能否正常执行，并生成完整报告。
            *   *示例命令*：`python index_analyse/Script/download_index_report.py --symbol 000300 --depth 快速 --analysts macro policy news sector technical` (或不传 `--analysts` 参数，使用默认值)
        *   **Agent 报告的正确性**：检查最终报告中是否只有被选中的 Agent 的分析结果，且报告内容与 Agent 自身的输出一致。
    *   **集成测试**：确保 `AnalysisService` (或类似服务层) 能够正确接收 `selected_analysts` 参数，并将其传递给 `_setup_index_graph` 进行图构建。

*   **预期结果**：
    *   Workflow 只包含所选 Agent 对应的执行节点。
    *   最终报告中仅包含所选 Agent 的分析结果，未选中的 Agent 不会出现在报告中。
    *   没有出现不应有的错误或冗余计算。

### 6.2 健壮性确认与验证

**目标**：确保系统在异常情况或边界条件下仍能稳定运行，并给出合理的处理。

*   **测试方法**：
    *   **空 Agent 列表**：
        *   *场景*：当 `selected_analysts` 传入空列表 `[]` 或只包含不识别的 Agent 名称时。
        *   *预期*：Workflow 能够优雅地处理，可能返回一个提示“没有选择任何分析师，无法进行分析”或执行一个最小化的流程。不应导致系统崩溃。
    *   **重复 Agent 列表**：
        *   *场景*：`selected_analysts` 包含重复的 Agent 名称 (例如 `['macro', 'macro', 'policy']`)。
        *   *预期*：`_setup_index_graph` 能够正确去重，每个 Agent 只构建一个节点。
    *   **不合法 Agent 名称**：
        *   *场景*：`selected_analysts` 包含不在允许列表中的 Agent 名称。
        *   *预期*：系统能够识别并忽略这些不合法的名称，或者抛出明确的错误提示。
    *   **与 `research_depth` 结合测试**：
        *   *场景*：在不同 `research_depth` 下动态选择 Agent，验证是否仍能正确工作。例如，选择 `macro` 和 `technical`，同时 `depth` 为“全面”。
        *   *预期*：`research_depth` 的影响（如辩论轮次、Prompt 深度）与 `selected_analysts` 的动态选择相互独立且兼容。

*   **预期结果**：
    *   系统在各种边界情况下不崩溃。
    *   给出明确的错误提示或进行合理的默认处理。
    *   资源的消耗（尤其是 Token）与所选择的 Agent 数量成正比，没有因为冗余计算而额外增加。

### 6.3 性能测试

**目标**：验证动态选择对 Workflow 性能的影响。

*   **测试方法**：
    *   **比较不同选择组合的执行时间**：例如，“只运行 Macro” vs “运行所有 Agent”。
    *   **重点关注 Token 消耗**：验证未被选中的 Agent 确实没有被 LLM 调用，从而节约 Token。

*   **预期结果**：
    *   执行时间：少量 Agent < 较多 Agent < 全部 Agent (线性或接近线性的性能提升)。
    *   Token 消耗：少量 Agent 的 Token 消耗显著低于全部 Agent。
