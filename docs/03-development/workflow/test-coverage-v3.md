# TradingAgents-CN v3.0 测试覆盖文档

> 自动生成于 2026-06-22 | 总用例数：155

---

## 一、测试概览

| 测试类型 | 文件数 | 用例数 | 框架 |
|----------|--------|--------|------|
| 前端 E2E 测试 | 10 | 85 | Playwright + Chromium |
| 后端 API 测试 | 9 | 70 | pytest + httpx |
| **合计** | **19** | **155** | |

---

## 二、前端 E2E 测试（85 个）

### 2.1 认证模块（5 个）

| 用例 | 验证内容 |
|------|----------|
| 登录页应正确加载 | 登录表单、用户名/密码输入框、协议复选框可见 |
| 正确凭据登录成功并跳转到 Dashboard | 填写用户名密码 → 勾选协议 → 点击登录 → 跳转到仪表板 |
| 错误密码登录失败 | 错误密码 → 提示错误信息 → 停留在登录页 |
| 未登录访问受保护路由应跳转到登录页 | 无 token 访问 /portfolio → 302 到 /login |
| 公开页面无需登录可访问 | /login、/register 等公开路由无需认证 |

### 2.2 核心页面导航（10 个）

| 用例 | 验证内容 |
|------|----------|
| Dashboard 页面正确加载 | 仪表板页面渲染、统计卡片可见 |
| 导航到单股分析页面 | 侧边栏点击 → /analysis/single |
| 导航到筛选页面 | 侧边栏点击 → /screening |
| 导航到收藏页面 | 侧边栏点击 → /favorites |
| 导航到报告页面 | 侧边栏点击 → /reports |
| 导航到持仓页面 | 侧边栏点击 → /portfolio |
| 导航到模拟交易页面 | 侧边栏点击 → /paper-trading |
| 导航到交易复盘页面 | 侧边栏点击 → /review |
| 导航到任务中心页面 | 侧边栏点击 → /tasks/unified |
| 导航到设置页面 | 侧边栏点击 → /settings |

### 2.3 单股深度分析（15 个）

| 用例 | 验证内容 |
|------|----------|
| **触发单股分析 - 输入股票代码并启动分析** | 填入600519 → 选1级快速 → 按钮启用 → 点击 → 等待分析完成(6-7分钟) → 验证结果卡片、股票标签、分析概览、报告标签页、报告内容 → 检查无降级错误 |
| 分析页面加载 - 各分析维度入口可见 | 分析表单、股票输入框、深度选项可见 |
| 查看历史分析结果 | 历史分析列表、分析记录可见 |
| 任务中心 - 查看分析任务列表 | 任务表格渲染、数据行可见 |
| **任务中心 - 验证分析任务已提交** | 触发分析 → 跳转任务中心 → 表格中有数据行（确认任务入库） |
| 任务中心 - 按状态筛选任务 | 状态筛选下拉框可用 |
| 任务中心 - 查看任务详情 | 点击任务 → 详情面板/对话框出现 |
| 任务中心 - 重试失败任务 | 重试按钮可见并可点击 |
| 任务中心 - 取消运行中任务 | 取消按钮可见并可点击 |
| 对分析结果进行评分反馈 | 评分组件可见、可提交反馈 |
| 定时分析配置页面加载 | /settings/scheduled-analysis 页面渲染 |
| 创建定时分析任务 | 点击创建配置 → 填写名称 → 选深度 → 保存 |
| 测试执行定时分析 | 点击测试执行 → 等待执行结果提示 |
| **ETF分析 - 完整流程验证** | 切换ETF市场 → 输入510050 → 1级快速 → 等待分析完成 → 验证结果完整性 → 检查无降级错误 |
| **批量分析 - 提交任务并验证** | 输入3只股票(000001/000002/600036) → 解析 → 选1级深度 → 提交 → 确认对话框 → 验证成功消息 → 任务中心验证入库 |

> **加粗**用例为真实端到端验证，会等待分析引擎跑完后检查结果完整性

### 2.4 单股分析流程-简化版（4 个）

| 用例 | 验证内容 |
|------|----------|
| 分析页面正确加载并有输入框 | 页面渲染、输入框可见 |
| 输入股票代码可以触发分析 | 输入代码 → 按钮启用 |
| 任务中心页面加载并显示任务列表 | 任务表格渲染 |
| 任务中心统计信息显示 | 统计卡片可见 |

### 2.5 智能选股（10 个）

| 用例 | 验证内容 |
|------|----------|
| PE/PB/ROE 多条件组合筛选 | 切换高级模式 → 添加基本面筛选条件 → 执行筛选 |
| 行业板块筛选 | 行业筛选下拉框可用 |
| 筛选结果排序 | 结果表格排序功能 |
| 保存筛选条件 | 保存筛选方案 |
| 均线条件筛选 | 添加技术指标筛选条件 |
| 成交量条件筛选 | 成交量筛选条件 |
| 添加股票到自选 | 添加按钮可见可点击 |
| 自选股列表加载 | /favorites 页面、自选股列表渲染 |
| 自选股分组管理 | 分组管理功能 |
| 从自选股发起分析 | 从自选股触发分析 |

### 2.6 持仓与交易（14 个）

| 用例 | 验证内容 |
|------|----------|
| 持仓列表页面加载 | /portfolio 页面、持仓表格渲染 |
| 持仓收益统计 | 统计卡片（总资产等）可见 |
| 持仓统计卡片 | 收益/亏损统计展示 |
| 从持仓发起分析 | 持仓行操作按钮 → 触发分析 |
| 模拟交易页面加载 | /paper-trading 页面渲染 |
| 买入股票流程 | 买入表单、提交买入 |
| 卖出股票流程 | 卖出表单、提交卖出 |
| 查看交易记录 | 交易记录列表 |
| 查看持仓明细 | 模拟持仓明细 |
| 资产概览 | 账户资产统计 |
| 复盘概览页面加载 | /review 页面渲染 |
| 查看交易明细 | 交易明细列表 |
| 查看盈亏分析 | 盈亏统计展示 |
| 查看胜率统计 | 切换到模拟交易复盘标签 → 胜率统计可见 |

### 2.7 交易计划（6 个）

| 用例 | 验证内容 |
|------|----------|
| 交易计划列表页面加载 | /trading-system 页面、计划列表渲染 |
| 创建新交易计划 | 点击创建 → 填写表单 → 保存 |
| 编辑交易计划 | 编辑按钮 → 修改表单 → 保存 |
| 激活/停用交易计划 | 激活/停用切换 |
| 设置止损止盈规则 | 风险规则配置 |
| 查看交易计划详情 | 详情面板/对话框 |

### 2.8 投资报告（6 个）

| 用例 | 验证内容 |
|------|----------|
| 报告列表页面加载 | /reports 页面、报告列表渲染 |
| 查看报告详情 | 点击报告 → 详情页/对话框 |
| 搜索报告 | 搜索框输入 → 过滤结果 |
| 按时间筛选报告 | 时间范围筛选 |
| 导出报告 | 导出按钮可见可点击 |
| Token 消耗统计页面 | /usage-statistics 页面渲染 |

### 2.9 智能助手（4 个）

| 用例 | 验证内容 |
|------|----------|
| 智能助手页面加载 | /assistant 页面、标题、新主题按钮、输入区域可见 |
| **智能助手 - 快速对话** | 创建主题 → 输入问题 → 发送 → 等待流式回复 → 验证回复内容长度 > 10 |
| 智能助手 - 主题列表 | 主题树/空状态渲染 |
| 智能助手 - 助手设置弹窗 | 打开设置 → 弹窗可见 → 关闭 |

### 2.10 数据质量与系统配置（11 个）

| 用例 | 验证内容 |
|------|----------|
| 数据源配置管理页面加载 | /settings/config 页面渲染 |
| 多数据源同步页面加载 | /settings/sync 页面渲染 |
| 缓存管理页面加载 | /settings/cache 页面渲染 |
| QMT 诊断 - 配置管理页面可访问 | 配置管理页面可打开 |
| 运行 QMT 连接诊断 | 诊断按钮可点击、诊断结果展示 |
| 配置管理页面加载 | 系统配置页面渲染 |
| 设置首页加载 | /settings 页面渲染 |
| 自选股分组配置 | 分组配置功能 |
| Agent 列表页面加载 | /workflow/agent-workshop 页面渲染 |
| 查看 Agent 版本历史 | 版本历史面板可见 |
| Agent 版本回滚 | 回滚按钮可点击 |

---

## 三、后端 API 测试（70 个）

### 3.1 认证模块（8 个）

| 用例 | 验证内容 |
|------|----------|
| test_login_success | POST /auth/login 正确凭据返回 token |
| test_login_wrong_password | 错误密码返回 401 |
| test_login_nonexistent_user | 不存在用户返回 401 |
| test_login_missing_fields | 缺少必填字段返回 422 |
| test_get_me_with_token | GET /auth/me 带 token 返回用户信息 |
| test_get_me_without_token | 无 token 返回 401 |
| test_get_me_with_invalid_token | 无效 token 返回 401 |
| test_logout_success | POST /auth/logout 登出成功 |

### 3.2 健康检查与系统状态（4 个）

| 用例 | 验证内容 |
|------|----------|
| test_health_check | GET /health 返回 200 |
| test_health_check_no_auth_required | 健康检查无需认证 |
| test_config_summary | GET /config/summary 返回配置摘要 |
| test_system_logs | GET /config/logs 返回日志列表 |

### 3.3 股票数据与筛选（7 个）

| 用例 | 验证内容 |
|------|----------|
| test_get_stock_quote | GET /stocks/{code}/quote 返回行情数据 |
| test_get_stock_quote_invalid_code | 无效代码返回 404 或空数据 |
| test_get_screening_fields | GET /screening/fields 返回筛选字段配置 |
| test_get_screening_presets | GET /screening/presets 返回筛选方案 |
| test_execute_screening | POST /screening/execute 执行筛选 |
| test_get_favorites | GET /favorites 返回收藏列表 |
| test_add_and_remove_favorite | 添加/删除收藏完整流程 |

### 3.4 分析任务（9 个）

| 用例 | 验证内容 |
|------|----------|
| test_trigger_analysis | POST /analysis/trigger 触发分析任务 |
| test_trigger_analysis_invalid_code | 无效代码触发分析被拒绝 |
| test_get_analysis_history | GET /analysis/history 返回分析历史 |
| test_get_analysis_tasks | GET /analysis/tasks 返回任务列表 |
| test_get_tasks_list | GET /tasks/unified 返回统一任务列表 |
| test_get_tasks_statistics | GET /tasks/statistics 返回任务统计 |
| test_get_tasks_list_with_filters | 带过滤条件获取任务列表 |
| test_submit_feedback | POST /analysis/feedback 提交分析反馈 |
| test_submit_feedback_invalid_rating | 无效评分被拒绝 |

### 3.5 持仓与交易计划（11 个）

| 用例 | 验证内容 |
|------|----------|
| test_get_portfolio_positions | GET /portfolio/positions 返回持仓列表 |
| test_get_portfolio_statistics | GET /portfolio/statistics 返回持仓统计 |
| test_get_portfolio_account | GET /portfolio/account 返回账户信息 |
| test_get_paper_positions | GET /paper-trading/positions 返回模拟持仓 |
| test_get_paper_account | GET /paper-trading/account 返回模拟账户 |
| test_get_trading_systems | GET /trading-system/systems 返回交易计划列表 |
| test_get_active_trading_system | GET /trading-system/active 返回活跃计划 |
| test_create_trading_system | POST /trading-system/systems 创建交易计划 |
| test_get_periodic_reviews | GET /review/periodic 返回周期性复盘 |
| test_get_review_statistics | GET /review/statistics 返回复盘统计 |
| test_trigger_periodic_review | POST /review/trigger 触发周期性复盘 |

### 3.6 报告与通知（6 个）

| 用例 | 验证内容 |
|------|----------|
| test_get_reports_list | GET /reports 返回报告列表 |
| test_get_reports_list_with_pagination | 分页参数获取报告列表 |
| test_get_notifications | GET /notifications 返回通知列表 |
| test_get_unread_count | GET /notifications/unread-count 返回未读数 |
| test_get_usage_statistics | GET /usage/statistics 返回使用统计 |
| test_get_token_statistics | GET /usage/tokens 返回 Token 统计 |

### 3.7 设置与配置（10 个）

| 用例 | 验证内容 |
|------|----------|
| test_get_system_config | GET /config 返回系统配置 |
| test_get_llm_config | GET /config/llm 返回 LLM 配置 |
| test_get_datasource_config | GET /config/datasource 返回数据源配置 |
| test_get_qmt_diagnosis | GET /config/qmt-diagnosis 返回 QMT 诊断结果 |
| test_get_datasource_quality | GET /config/datasource-quality 返回数据源质量统计 |
| test_get_tags | GET /tags 返回标签列表 |
| test_get_cache_info | GET /config/cache 返回缓存信息 |
| test_get_audit_logs | GET /mcp/audit-logs 返回 MCP 审计日志 |
| test_get_audit_logs_with_filters | 带过滤条件查询审计日志 |
| test_get_mcp_servers | GET /mcp/servers 返回 MCP 服务器列表 |

### 3.8 Agent 工坊与工作流（9 个）

| 用例 | 验证内容 |
|------|----------|
| test_get_agents | GET /agents 返回 Agent 列表 |
| test_get_available_agents | GET /agents/available 返回可用 Agent |
| test_get_agent_categories | GET /agents/categories 返回 Agent 分类 |
| test_get_tools | GET /tools 返回工具列表 |
| test_get_tool_categories | GET /tools/categories 返回工具分类 |
| test_get_workflows | GET /workflows 返回工作流列表 |
| test_get_workflow_templates | GET /workflows/templates 返回工作流模板 |
| test_get_specs | GET /agent-workshop/specs 返回 Agent 工坊规格 |
| test_rollback_spec | POST /agent-workshop/specs/{id}/rollback 版本回滚 |

### 3.9 ETF GA（6 个）

| 用例 | 验证内容 |
|------|----------|
| test_get_sh_etf_quote | GET /etf/quote/sh 返回上交所 ETF 行情 |
| test_get_sz_etf_quote | GET /etf/quote/sz 返回深交所 ETF 行情 |
| test_get_etf_fundamentals | GET /etf/fundamentals 返回 ETF 基本面 |
| test_get_etf_kline | GET /etf/kline 返回 ETF K线数据 |
| test_trigger_etf_sync | POST /etf/sync 触发 ETF 数据同步 |
| test_get_etf_paper_quote | GET /etf/paper-quote 返回 ETF 模拟交易行情 |

---

## 四、投资人日常场景覆盖矩阵

| 日常场景 | E2E 测试 | API 测试 | 覆盖程度 |
|----------|----------|----------|----------|
| 登录系统 | ✅ 5个 | ✅ 8个 | 完整 |
| 查看仪表板/大盘概览 | ✅ 1个 | - | 基本 |
| 单股深度分析 | ✅ 3个(含真实分析验证) | ✅ 2个 | 完整 |
| ETF分析 | ✅ 1个(含真实分析验证) | ✅ 6个 | 完整 |
| 批量分析 | ✅ 1个 | - | 完整 |
| 定时分析 | ✅ 3个 | - | 完整 |
| 智能选股 | ✅ 10个 | ✅ 5个 | 完整 |
| 智能助手对话 | ✅ 4个(含真实对话验证) | - | 完整 |
| 查看持仓 | ✅ 4个 | ✅ 3个 | 完整 |
| 模拟交易 | ✅ 6个 | ✅ 2个 | 完整 |
| 交易复盘 | ✅ 4个 | ✅ 3个 | 完整 |
| 交易计划管理 | ✅ 6个 | ✅ 3个 | 完整 |
| 查看报告 | ✅ 6个 | ✅ 2个 | 完整 |
| 自选股管理 | ✅ 4个 | ✅ 2个 | 完整 |
| 数据源配置/诊断 | ✅ 5个 | ✅ 5个 | 完整 |
| Agent工坊 | ✅ 3个 | ✅ 9个 | 完整 |
| 系统设置 | ✅ 3个 | ✅ 4个 | 完整 |
| MCP审计日志 | - | ✅ 3个 | API层完整 |
| 分析反馈 | ✅ 1个 | ✅ 2个 | 完整 |
| 通知中心 | - | ✅ 2个 | API层完整 |

---

## 五、运行方式

### 前端 E2E 测试

```bash
# 确保 v3.0 前后端服务已启动
# 后端: localhost:8002, 前端: localhost:3002

# 运行全部 E2E 测试
$env:E2E_BASE_URL = "http://localhost:3002"
npx playwright test

# 运行单个模块
npx playwright test e2e/analysis_core.spec.ts

# 运行真实分析验证（耗时较长）
npx playwright test --grep "触发单股分析|ETF分析|批量分析|快速对话"
```

### 后端 API 测试

```bash
# 确保 v3.0 后端服务已启动 (localhost:8002)
$env:BACKEND_URL = "http://localhost:8002"
pytest tests/acceptance/ -v
```

### 一键验收脚本

```powershell
# 按版本号运行全部验收测试
.\run_acceptance.ps1 -Version 3.0
```
