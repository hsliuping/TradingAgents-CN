# 提交说明版短摘要

## 建议摘要

- 自选股：补齐港股实时展示与涨跌幅、优化标签管理与快捷编辑、支持删除联动清理
- 数据同步：新增同步历史与数据清理能力，支持按类型查看/删除
- 数据源：完善单股同步的实时/非实时/混合路由规则
- 配置管理：统一厂家/数据源密钥来源展示与新增保存逻辑
- 分析报告：增强中文报告标题规范与长文本阶段稳定性
- 工程化：整理公开部署脚本、提交检查清单和回归测试

## GitHub 提交说明简版

本次更新主要完善了自选股、数据同步、分析报告稳定性与公开提交准备：

- 自选股页面补齐港股实时展示与涨跌幅，优化“同步实时行情”的市场分流与失败回退逻辑
- 标签管理、快速标签、自选股编辑三处逻辑统一，新增标签自动入库、改名同步传播、删除后自动清理引用
- 新增同步历史与已同步数据清理能力，支持按类型查看与删除，并明确记录删除与真实数据删除的边界
- 完善单股同步的实时 / 非实时 / 混合数据源路由规则
- 配置管理页统一厂家与数据源的密钥来源展示，新增数据源密钥状态概览，并修复新增厂家时有效 API Key 被静默清空的问题
- 规范中文报告标题，增强长文本分析阶段稳定性
- 补充公开部署脚本、提交检查清单与回归测试，便于后续公开提交与部署
- 清理公开示例中的默认口令/长得像真实密钥的样例，降低公开提交时的误判风险

## 建议 PR 标题

推荐标题：

`fix: stabilize reports, sync cleanup, favorites data, and test baseline`

如果希望更偏产品侧，也可以用：

`feat: improve favorites sync, report stability, and public release hygiene`

## 建议 PR 正文骨架

可直接按下面结构整理：

### What changed

- 完善自选股页的实时行情展示、港股涨跌幅与标签快捷编辑/同步逻辑
- 新增同步历史与已同步数据清理能力，支持按类型查看和删除
- 修复分析报告链路中的部分长文本稳定性与中文标题规范问题
- 调整单股同步数据源路由规则，明确实时 / 非实时 / 混合同步行为
- 整理默认测试套件、占位符样例和公开提交文档

### Validation

- 后端默认标准套件：`471 passed, 2 skipped, 287 deselected`
- 前端工程校验：
  - `pnpm lint`
  - `pnpm type-check`
  - `pnpm build`
- 关键回归子集：
  - `tests/test_tushare_unified/test_tushare_provider.py`
  - `tests/test_tushare_unified/test_tushare_sync_service.py`
  - `tests/tradingagents/test_app_cache_toggle.py`
  - `tests/test_recent_changes_unittest.py`

### Notes

- 不包含本地 `.env`、运行产物、数据库导出物与 `codex` 本地专用脚本
- Docker 部署当前仅完成静态评估，真实容器回测待具备 Docker 环境后再执行

## 建议的暂存策略

如果你准备开始实际整理暂存区，建议按下面顺序：

1. 先暂存核心功能代码：
   - `app/`
   - `frontend/src/`
   - `tradingagents/`
2. 再暂存测试与配置：
   - `tests/`
   - `pyproject.toml`
3. 最后暂存文档：
   - `CHANGELOG.md`
   - `docs/maintenance/`
   - 本轮改过的配置/安全说明文档

建议暂不暂存：

- 未在本轮交付范围内、且没有实际产品价值说明的其他一次性排查脚本

## 不建议写入公开说明的内容

- `minimal mode`
- 本地 PID
- 本机路径
- `.env` 细节
- 具体第三方网关地址

## 建议保留的说明内容

- 功能变化
- 交互变化
- 数据清理边界
- 测试覆盖情况
