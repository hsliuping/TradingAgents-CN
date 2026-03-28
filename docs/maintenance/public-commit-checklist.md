# 公开提交检查清单

这份清单用于把当前仓库整理成可公开提交的版本。

目标：

- 提交功能代码与必要文档
- 不提交任何本地运行时配置、真实密钥、第三方敏感信息、个人设备信息
- 不提交仅用于当前 `codex` 本地环境的辅助脚本

## 1. 允许提交的内容

优先纳入以下类型：

- 后端源码：`app/`、`tradingagents/`
- 前端源码：`frontend/src/`
- 公共脚本：`scripts/startup/start_local_stack.sh`、`scripts/startup/bootstrap_local_env.py`、`scripts/startup/init_local_env_db.py`
- 公共示例配置：`scripts/startup/local_stack.env.example`
- 修复或说明文档：`docs/`
- 依赖声明：`pyproject.toml`、`requirements.txt`、前端 `package.json` / `yarn.lock`
- 测试与示例中明确使用占位字符串的安全样例

## 2. 必须排除的内容

以下内容不要进入公开提交：

- 本地环境变量文件：
  - `.env`
  - `.env.local`
  - `frontend/.env.local`
  - 任意 `.env.*.local`
- 运行时生成文件：
  - `config/models.json`
  - `config/settings.json`
  - `runtime/`
  - `logs/`
  - `results/`
  - `cache/`
  - `data/`
- 本地数据库或缓存导出物
- 任何包含真实账号、密码、token、cookie、连接串的调试文件
- 仅供当前 `codex` 本地环境使用的脚本：
  - `scripts/startup/bootstrap_codex_local.py`
  - `scripts/startup/init_codex_local_db.py`
  - `scripts/startup/start_local_codex_stack.sh`
- 个人设备或本地路径相关信息：
  - `/Users/...`
  - `C:\\Users\\...`
  - 本机用户名
  - 本地专用端口、目录、服务管理脚本

## 3. 占位符规则

以下内容可以保留：

- `your-...`
- `your_...`
- `your_password_here`
- `placeholder_api_key_here`

以下内容即使大概率是假的，也应替换成更明显的测试占位串：

- 类似真实 OpenAI key 的字符串
- 类似真实 Google API key 的字符串
- 类似真实 OpenRouter / 百度千帆 / 其他厂商密钥格式的字符串

推荐格式：

- `sk-test-placeholder-001`
- `sk-or-v1-test-placeholder-001`
- `AIzaSyTEST_PLACEHOLDER_xxx`
- `bce-v3/PLACEHOLDER_ACCESS_KEY/PLACEHOLDER_SECRET_KEY`
- `change_me_local_admin_password`
- `your_mongodb_password_here`
- `your_redis_password_here`

测试专用环境变量建议使用空值占位，例如：

- `TEST_DASHSCOPE_API_KEY=`
- `TEST_FINNHUB_API_KEY=`
- `TEST_OPENAI_API_KEY=`
- `TEST_TUSHARE_TOKEN=`

没有配置测试专用密钥时，相关外部集成测试应为 `skipped`，不应为 `failed`。

## 4. 提交前必跑检查

在仓库根目录执行：

```bash
git status --short
git diff --name-only
git diff --cached --name-only
```

确认不要出现以下文件：

```bash
git status --short | rg '(^| )(\.env|\.env\.local|frontend/\.env\.local|config/models\.json|config/settings\.json|runtime/|logs/|results/|cache/|data/)'
```

确认不要出现本地专用脚本：

```bash
git status --short | rg 'scripts/startup/(bootstrap_codex_local|init_codex_local_db|start_local_codex_stack)\.sh|scripts/startup/(bootstrap_codex_local|init_codex_local_db)\.py'
```

搜索可能的敏感串：

```bash
rg -n --hidden --glob '!*.svg' --glob '!*.png' --glob '!*.jpg' --glob '!*.pdf' \
  '(sk-[A-Za-z0-9_-]{12,}|sk-or-v1-[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{12,}|api[_-]?key|secret|token|password)' .
```

人工复核命中结果，只保留明确的占位符、文档说明或脱敏代码。

## 5. 建议的提交范围

如果这次要公开提交当前改动，建议优先纳入：

- 报告失败诊断增强
- 报告标题中文化修复
- 长文本与风险评估节点流式化
- 自选股标签体系修复
- 同步记录 / 数据清理联动界面
- 公开版一键部署脚本
- 测试样例密钥占位符清理

### 当前这批改动的最终建议提交范围

建议提交：

- 核心后端功能：
  - `app/models/analysis.py`
  - `app/models/user.py`
  - `app/routers/favorites.py`
  - `app/services/favorites_service.py`
  - `app/services/foreign_stock_service.py`
  - `app/services/simple_analysis_service.py`
  - `app/services/stock_data_service.py`
  - `app/services/tags_service.py`
- 前端功能与交互：
  - `frontend/src/api/`
  - `frontend/src/components/`
  - `frontend/src/main.ts`
  - `frontend/src/router/index.ts`
  - `frontend/src/stores/`
  - `frontend/src/views/`
- TradingAgents 适配层：
  - `tradingagents/agents/utils/agent_utils.py`
  - `tradingagents/config/config_manager.py`
  - `tradingagents/config/runtime_settings.py`
  - `tradingagents/dataflows/news/google_news.py`
  - `tradingagents/dataflows/news/google_news_rss.py`
  - `tradingagents/dataflows/providers/china/tushare.py`
  - `tradingagents/dataflows/providers/hk/hk_stock.py`
  - `tradingagents/dataflows/providers/sina_finance.py`
  - `tradingagents/graph/conditional_logic.py`
- 测试与测试配置：
  - `pyproject.toml`
  - `tests/README.md`
  - `tests/conftest.py`
  - 这轮修改过、且属于默认/标准回归链路的 `tests/**/*.py`
- 文档：
  - `CHANGELOG.md`
  - `docs/maintenance/public-commit-checklist.md`
  - `docs/maintenance/release-note-summary.md`
  - `docs/maintenance/docker-assessment-2026-03.md`
  - `docs/maintenance/upstream-review-2026-03.md`
  - 本轮同步修改过的 API key / 安全 / 配置相关文档
- 这次确认一并纳入的历史脚本清洁性修正：
  - `scripts/test_api_key_edit.py`
  - `scripts/test_api_key_priority.py`
  - `scripts/test_api_key_validation.py`
  - `scripts/补充行业信息_akshare.py`

建议不要提交：

- 本地生成配置与运行产物：
  - `.env`
  - `.env.local`
  - `frontend/.env.local`
  - `config/models.json`
  - `config/settings.json`
  - `frontend/dist/`
  - `logs/`
  - `runtime/`
- `codex` 本地专用脚本：
  - `scripts/startup/bootstrap_codex_local.py`
  - `scripts/startup/init_codex_local_db.py`
  - `scripts/startup/start_local_codex_stack.sh`
- 其他本轮未明确纳入范围、且偏一次性人工排查的脚本式文件

### 当前这批改动的建议纳入文件

建议按下面的分组纳入：

- 后端业务代码：
  - `app/`
- 前端业务代码：
  - `frontend/src/`
- TradingAgents 适配层：
  - `tradingagents/`
- 正式测试：
  - `tests/`
  - 其中优先保留 `pytest` 标准套件相关文件
- 公开部署与示例配置：
  - `scripts/startup/start_local_stack.sh`
  - `scripts/startup/bootstrap_local_env.py`
  - `scripts/startup/init_local_env_db.py`
  - `scripts/startup/local_stack.env.example`
- 公开说明文档：
  - `CHANGELOG.md`
  - `docs/maintenance/public-commit-checklist.md`
  - `docs/maintenance/release-note-summary.md`
  - `tests/README.md`
  - `.env.example`

### 当前这批改动建议排除的文件

如果你想让公开提交更干净，建议暂不纳入这些脚本式调试文件：

- `scripts/test_api_key_edit.py`
- `scripts/test_api_key_priority.py`
- `scripts/test_api_key_validation.py`
- `scripts/test_progress_tracking.py`

原因：

- 它们不属于默认标准测试套件
- 更偏向人工排查与一次性诊断
- 会增加公开提交噪音，但对主功能交付价值有限

## 6. 提交前人工确认项

逐项确认：

- 页面和接口改动不依赖 `~/.codex`
- 仓库里没有真实 provider key
- 仓库里没有真实数据库密码
- 仓库里没有个人本机路径截图或硬编码
- 本地专用脚本未进入暂存区
- 生成文件未进入暂存区

## 7. 暂不执行的动作

按当前约定，以下动作需要额外确认后再做：

- GitHub fork
- 新 remote 配置
- `git commit`
- `git push`
