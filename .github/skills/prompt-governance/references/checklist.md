# Prompt Governance Checklist

## 运行期模板检查

- 是否先查了 `prompt_templates` 而不是只看 repo 文件。
- 是否确认了 `agent_type`、`agent_name`、`preference_type`、`status=active`。
- 是否分别核对了 with_cache 和 without_cache。
- 修改 DB 后是否立刻回读。

## 代码装配检查

- 是否检查 `_build_system_prompt` 和 `_build_user_prompt`。
- 是否检查无缓存 fallback 分支。
- 是否检查 adapter 是否把上游原文直接透传。
- 是否检查 service 是否仍在做 legacy action / price_targets / recommendation 提取。

## 数据与参数检查

- 是否检查 analysis_date 在日志里的真实值。
- 是否检查 tool args 里的 `start_date` / `end_date` / `ticker`。
- 是否确认 current_price、technical latest_price、effective_data_date 是否来自同一口径。
- 是否把“日期漂移”“价格口径漂移”“提示词污染”区分开。

## 合规与输出检查

- 是否只去掉表面建议词，而没有处理隐性触发语。
- 是否同时检查上游 analyst、risk、advisor，而不是只看最终 manager。
- 是否确认 user_view 和详细研究正文没有重复堆砌。
- 是否确认最终 sanitizer 没有重新引入旧兼容字段。

## 验证检查

- 是否先跑最窄回归测试。
- 是否对失败点做同一切片修复后重跑。
- 是否再跑治理校验。
- 如果改了 DB 模板，是否做了独立回读。
- 如果改了运行期行为，是否建议或执行重跑目标 workflow 并查日志。

## TradingAgentsCN 常见根因

- DB 模板已过时，repo fallback 其实没生效。
- adapter 把上游原始报告直接塞进下游 prompt，导致合规触发语扩散。
- 无缓存场景没有把 tool 参数写死到 `analysis_date`，LLM 自行猜了历史日期。
- service 层仍在解析 neutral JSON 中的 legacy action / price_targets。
- current_price 与技术分析使用的价格序列不是同一日期或同一来源。
