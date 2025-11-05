# Git 提交计划

## 提交策略

建议分 5 个 commit 提交，按功能模块分组：

---

## Commit 1: 修复 API Key 配置问题

**描述**: 修复 LLM 适配器 API Key 验证和传递问题

**文件列表**:
```bash
git add tradingagents/llm_adapters/dashscope_openai_adapter.py
git add tradingagents/llm_adapters/deepseek_adapter.py
git add tradingagents/llm_adapters/google_openai_adapter.py
git add tradingagents/llm_adapters/openai_compatible_base.py
git add tradingagents/agents/analysts/fundamentals_analyst.py
```

**Commit 消息**:
```
fix: 修复 LLM 适配器 API Key 验证和传递问题

- 所有 LLM 适配器添加 API Key 占位符验证
- fundamentals_analyst 创建新 LLM 实例时传递 API Key
- 确保从数据库配置的 API Key 优先于环境变量
```

---

## Commit 2: 修复时区和数据同步问题

**描述**: 修复时间字段时区标识和数据同步性能问题

**文件列表**:
```bash
git add app/services/simple_analysis_service.py
git add app/services/basics_sync_service.py
git add app/services/basics_sync/processing.py
git add app/worker/akshare_sync_service.py
git add app/worker/tushare_sync_service.py
git add tradingagents/dataflows/realtime_metrics.py
```

**Commit 消息**:
```
fix: 修复时区标识和数据同步性能问题

- /user/history API 返回时间添加 UTC+8 时区标识
- 修复实时行情同步性能问题（单股票同步触发全量同步）
- 优化 PE/PB 计算逻辑
```

---

## Commit 3: 修复数据源优先级和股票筛选

**描述**: 修复数据源优先级配置和股票筛选功能

**文件列表**:
```bash
git add app/services/database_screening_service.py
git add app/services/config_service.py
git add app/services/data_sources/tushare_adapter.py
git add app/routers/stock_sync.py
git add app/routers/stocks.py
git add app/routers/config.py
```

**Commit 消息**:
```
fix: 修复数据源优先级和股票筛选功能

- 数据源优先级正确读取和应用
- 股票筛选使用优先级最高的数据源
- 优化配置服务的数据源管理
```

---

## Commit 4: 前端修复和优化

**描述**: 前端 API 调用和界面优化

**文件列表**:
```bash
git add frontend/src/api/request.ts
git add frontend/src/api/stockSync.ts
git add frontend/src/views/Settings/components/DataSourceConfigDialog.vue
git add frontend/src/views/Stocks/Detail.vue
```

**Commit 消息**:
```
fix: 前端 API 调用和界面优化

- 优化 API 请求错误处理
- 改进数据源配置对话框
- 优化股票详情页面显示
```

---

## Commit 5: 添加 Windows 绿色版打包支持

**描述**: 添加 Windows 绿色版（便携版）打包脚本和文档

**文件列表**:
```bash
# 主打包脚本
git add scripts/deployment/build_portable_package.ps1
git add scripts/deployment/sync_to_portable.ps1
git add scripts/deployment/get_vendors.ps1

# 诊断脚本
git add scripts/diagnose_nginx.ps1

# 调试脚本（可选）
git add scripts/check_datasource_priority.py
git add scripts/check_stock_source.py
git add scripts/debug_mongodb_time.py

# 文档
git add docs/deployment/WINDOWS_PORTABLE.md
git add docs/guides/portable-installation-guide.md

# 其他配置
git add app/__main__.py
git add app/main.py
git add app/core/startup_validator.py
git add app/routers/health.py
git add start_api.py
git add docker-compose.v1.0.0.yml
git add .gitignore
```

**Commit 消息**:
```
feat: 添加 Windows 绿色版（便携版）打包支持

- 添加一键打包脚本 build_portable_package.ps1
- 自动清理 MongoDB 调试符号，优化包大小到 330 MB
- 添加 Nginx 启动诊断脚本
- 添加绿色版部署文档和安装指南
- 优化启动流程和健康检查
- 首次启动自动导入配置和创建默认用户
```

---

## 执行步骤

### 1. 更新 .gitignore
```bash
git add .gitignore
git commit -m "chore: 更新 .gitignore 排除构建产物和临时文件"
```

### 2. 按顺序执行上述 5 个 commit

### 3. 推送到远程仓库
```bash
git push origin windows-portable-installer
```

---

## 注意事项

⚠️ **敏感信息检查**:
- ✅ `.env` 文件已在 .gitignore 中，不会被提交
- ✅ 确认没有硬编码的 API Key（你的 Tushare Token 在 .env 中）
- ✅ 确认没有提交数据库密码

⚠️ **不要提交的文件**:
- `release/` 目录（构建产物）
- `test_*.py` 临时测试文件
- `frontend/package-lock.json`（使用 yarn.lock）
- `frontend/.eslintrc-auto-import.json`（自动生成）
- `frontend/auto-imports.d.ts`（自动生成）
- `frontend/tsconfig.tsbuildinfo`（构建缓存）

⚠️ **废弃的脚本**（不要提交）:
- `scripts/deployment/assemble_portable_release.ps1`
- `scripts/deployment/assemble_portable_release_fixed.ps1`
- `scripts/deployment/build_portable_release.ps1`
- `scripts/deployment/package_with_7zip.ps1`
- `scripts/deployment/quick_sync_and_build.ps1`
- `scripts/deployment/stage_local_vendors.ps1`

---

## 快速执行命令

```bash
# 1. 更新 .gitignore
git add .gitignore
git commit -m "chore: 更新 .gitignore 排除构建产物和临时文件"

# 2. Commit 1: API Key 修复
git add tradingagents/llm_adapters/*.py tradingagents/agents/analysts/fundamentals_analyst.py
git commit -m "fix: 修复 LLM 适配器 API Key 验证和传递问题"

# 3. Commit 2: 时区和数据同步
git add app/services/simple_analysis_service.py app/services/basics_sync*.py app/services/basics_sync/*.py app/worker/*_sync_service.py tradingagents/dataflows/realtime_metrics.py
git commit -m "fix: 修复时区标识和数据同步性能问题"

# 4. Commit 3: 数据源优先级
git add app/services/database_screening_service.py app/services/config_service.py app/services/data_sources/tushare_adapter.py app/routers/stock_sync.py app/routers/stocks.py app/routers/config.py
git commit -m "fix: 修复数据源优先级和股票筛选功能"

# 5. Commit 4: 前端修复
git add frontend/src/api/*.ts frontend/src/views/Settings/components/DataSourceConfigDialog.vue frontend/src/views/Stocks/Detail.vue
git commit -m "fix: 前端 API 调用和界面优化"

# 6. Commit 5: 绿色版打包
git add scripts/deployment/build_portable_package.ps1 scripts/deployment/sync_to_portable.ps1 scripts/deployment/get_vendors.ps1 scripts/diagnose_nginx.ps1 scripts/check_*.py scripts/debug_*.py docs/deployment/WINDOWS_PORTABLE.md docs/guides/portable-installation-guide.md app/__main__.py app/main.py app/core/startup_validator.py app/routers/health.py start_api.py docker-compose.v1.0.0.yml
git commit -m "feat: 添加 Windows 绿色版（便携版）打包支持"

# 7. 推送
git push origin windows-portable-installer
```

