# 京东云合作版 — 开发进度报告

## 文档信息

| 项目 | 内容 |
|------|------|
| 分支 | `release/jdyun-v3.0` |
| 基础分支 | `pro/main` (3e210606d) |
| 报告日期 | 2026-07-18 |
| 状态 | ✅ 核心功能完成，安全审查通过 |
| 提交数 | 23 个 |
| 变更文件 | 80 个文件，+4511 / -464 行 |

---

## 1. 开发日程总览

| 阶段 | 时间 | 说明 |
|------|------|------|
| P1 核心功能 | 07-18 上午 | 京东云模式检测、配置读取、数据库初始化、前端适配 |
| P2 LLM 限速 | 07-18 上午 | 429 重试、降并发、任务间隔 |
| P3 文档完善 | 07-18 上午 | 用户手册优化、学习路径、京东云适配 |
| P4 品牌适配 | 07-18 上午 | License 跳过、高级学员 UI 隐藏 |
| P5 安全审查 | 07-18 下午 | 全面安全审查 + 修复 |
| P6 部署优化 | 07-18 下午 | 自定义端口、MongoDB 8.0 升级 |

---

## 2. 按功能模块的开发成果

### 2.1 京东云核心功能

**设计文档**：[jdyun-edition-design.md](file:///c:/TradingAgentsCN/docs/05-design/v3.0/jdyun-edition-design.md)

| 模块 | 改动范围 | 关键能力 |
|------|---------|---------|
| 模式检测 | `app/core/jdyun.py`（新增） | 统一读取 `JDYUN_MODE` 环境变量，提供 `is_jdyun_mode()` 等工具函数 |
| 配置读取 | `app/core/config.py` + `config_bridge.py` | 京东云模式下从环境变量读取 OpenAI/Tushare 配置，不走数据库 |
| LLM 链路 | `app/services/simple_analysis_service.py` + `unified_analysis_service.py` + `trading_graph.py` | 京东云模式下只使用单一 Provider 配置，不读取数据库 LLM 列表 |
| 数据库初始化 | `app/services/jdyun_init.py`（新增） | 首次启动自动写入 jdyun Provider、4 个模型、Tushare 数据源、Embedding 配置 |
| API 保护 | `app/routers/config.py` + `license.py` | 京东云模式下禁止 Provider/数据源的增删改 API |
| License 跳过 | `app/services/license_service.py` | 京东云模式下不验证 License，所有功能直接开放 |

**4 个预置模型**：GLM-5 / GLM-5.1 / GLM-5.2 / DeepSeek-V4-Flash  
**Embedding**：Qwen3-Embedding-8B（维度 4096）

### 2.2 前端适配

| 模块 | 文件 | 改动 |
|------|------|------|
| 配置管理 | `frontend/src/utils/config.ts` | 新增 `isJdyunMode()` / `enableJdyunMode()` |
| 模型选择 | `views/Settings/JdyunConfig.vue`（新增） | 京东云 4 个模型下拉选择 |
| 配置首页 | `views/Settings/index.vue` | 京东云模式下替换配置页面内容 |
| 侧边栏 | `components/Layout/SidebarMenu.vue` | 隐藏 License/高级学员入口 |
| License UI | `views/Settings/LicenseSettings.vue` | 京东云模式下页面内容替换 |
| 京东云标志 | `.env.jdyun` + 路由守卫 | 前端构建注入 `VITE_JDYUN_MODE=true` |

### 2.3 LLM 限速保护

**设计文档**：[jdyun-llm-rate-limit-design.md](file:///c:/TradingAgentsCN/docs/05-design/v3.0/jdyun-llm-rate-limit-design.md)

| 防护层 | 机制 | 配置 |
|--------|------|------|
| LLM 调用重试 | 429 指数退避重试 | `max_retries=8`，15 次 OpenAI 兼容调用 |
| 批量分析并发 | 降为 1 | `batch_max_concurrent=1` |
| Worker 并发 | 降为 1 | `worker_max_concurrent=1` |
| 任务间隔 | 10 秒等待 | `stock_interval_seconds=10` |

环境变量：`JDYUN_LLM_MAX_RETRIES` / `JDYUN_LLM_MAX_RPM` / `JDYUN_BATCH_MAX_CONCURRENT` / `JDYUN_WORKER_MAX_CONCURRENT` / `JDYUN_STOCK_INTERVAL_SECONDS`

### 2.4 用户手册完善

| 改动 | 说明 |
|------|------|
| 新增通用研究章节 | 补充 `general` 类型分析的使用说明 |
| 补充隐藏功能 | 股票详情页、Token 统计、提示词预览 |
| 修复不一致 | 与实际实现对齐的手册内容 |
| 新增学习路径 | 入门 → 基础 → 进阶 → 高级 → 专家五阶段 |
| 新增价值说明 | "系统能为您做什么"章节，客观说明辅助作用与局限性 |
| 京东云适配 | 17 处 License/高级功能说明添加京东云版提示 |

### 2.5 安全审查与修复

**审查报告**：[jdyun-security-audit.md](file:///c:/TradingAgentsCN/docs/05-design/v3.0/jdyun-security-audit.md)

| 级别 | 问题 | 修复方案 |
|------|------|---------|
| H1 | 密码哈希 SHA-256 无盐 | bcrypt rounds=12 + 存量自动升级 |
| H2 | docker-compose 硬编码弱密码 | 强制环境变量 `${VAR:?error}` |
| H3 | JWT/CSRF 默认密钥可预测 | 黑名单验证 + 生产模式退出 |
| H4 | 前端敏感日志泄露 | 移除 Token/API Key 输出 |
| M1 | Docker 以 root 运行 | gosu 权限降级 |
| M2 | 数据库端口暴露 | ports → expose |
| M3 | v-html XSS 风险 | DOMPurify 净化（27 个 Vue 文件） |
| M5 | DEBUG=false 未设置 | docker-compose 添加环境变量 |
| M6 | 后端日志敏感信息 | 移除长度输出 + 环境变量控制 |

**已回退**：M4 登录速率限制（单用户部署不适用）

### 2.6 部署优化

| 改动 | 说明 |
|------|------|
| NGINX_PORT 可配置 | `8082` → `${NGINX_PORT:-8082}`，适配 K8s 多服务环境 |
| MongoDB 升级 | `4.4` → `8.0`（EOL 2029-10），性能提升 32% |
| 健康检查适配 | `mongo` → `mongosh`（8.0 废弃旧 CLI） |

---

## 3. 相关设计文档

| 文档 | 说明 |
|------|------|
| [jdyun-edition-design.md](file:///c:/TradingAgentsCN/docs/05-design/v3.0/jdyun-edition-design.md) | 京东云合作版整体设计 |
| [jdyun-llm-rate-limit-design.md](file:///c:/TradingAgentsCN/docs/05-design/v3.0/jdyun-llm-rate-limit-design.md) | LLM 限速方案设计 |
| [jdyun-security-audit.md](file:///c:/TradingAgentsCN/docs/05-design/v3.0/jdyun-security-audit.md) | 安全审查报告 |

---

## 4. 当前进度状态

### ✅ 已完成

- [x] 京东云模式检测和配置读取
- [x] LLM 调用链路京东云适配
- [x] 数据库自动初始化（从环境变量）
- [x] API 端点保护（禁止增删改 Provider/数据源）
- [x] License 跳过验证
- [x] 前端模式配置页面
- [x] License/高级学员 UI 隐藏
- [x] LLM 限速保护（429 重试 + 降并发）
- [x] 部署脚本和打包支持
- [x] 用户手册京东云适配
- [x] 安全审查修复（6 个 HIGH + 5 个 MEDIUM，1 个已回退）
- [x] 自定义端口支持
- [x] MongoDB 8.0 升级

### ⏳ 暂缓 / 待定

- [ ] **品牌定制** — 等待京东云提供 logo、配色、品牌素材
- [ ] **端到端测试** — 需要京东云真实 API Key 验证
- [ ] **Docker 镜像构建** — 需要 npm 构建前端 + 生成后端 Dockerfile
- [ ] **K8s 部署配置** — 由京东云工程师负责

---

## 5. 待完成工作

### 5.1 京东侧需要提供

| 项目 | 说明 |
|------|------|
| API Key | 京东云模型服务的有效 API Key 用于 E2E 测试 |
| Tushare Token | 京东云统一提供的 Tushare Token |
| 品牌素材 | logo、配色方案、favicon 等 |
| 域名 | 用户访问域名（用于 CORS 白名单） |
| K8s 环境信息 | 节点内核版本（MongoDB 8.0 需确认非 6.19） |

### 5.2 开发侧需要完成

| 项目 | 优先级 | 说明 |
|------|--------|------|
| E2E 测试 | P0 | 使用京东云 API Key 完整跑通注册→登录→配置→单股分析 |
| 镜像构建 | P0 | `docker-compose -f docker/docker-compose.jdyun.yml build` |
| 品牌定制 | P1 | logo 替换、配色调整、favicon |
| 用户手册最终版 | P1 | 截京东云版实际运行截图替代占位图 |

---

## 6. 提交记录

```
f9d566336 feat: 升级 MongoDB 到 8.0（EOL 2029-10，支持期最长）
04add693c feat: 京东云部署支持自定义端口（NGINX_PORT）- 适配 k8s 多服务环境
e1ef29e73 fix: 前端敏感日志清除（H4）- 移除 Token/API Key 输出
157901c05 fix: 京东云部署补充安全修复 - DEBUG=false + 日志敏感信息清除
2ddb322f0 revert: 回退M4登录速率限制（单用户部署不适用）
a2722181f fix: 京东云部署安全审查修复（H1-H3 + M1-M3）
5d79ad643 feat: 京东云模式隐藏License/高级学员相关UI元素
8fb08951a feat: 京东云模式跳过License验证，所有功能开放
622d1ce95 docs: 京东云版无需License激活，所有功能开放
5727b3583 docs: 新增"系统能为您做什么"章节
44f48df63 docs: 新增分阶段学习路径引导
439a39c4f docs: 从用户角度优化使用手册
25d83208d docs: 修复用户手册与实际实现不一致的内容
a5f34ea33 docs: 用户手册补充股票详情页、Token统计、提示词预览功能说明
939c4e873 docs: 用户手册补充通用研究功能和京东云合作版章节
44e2ccfb0 feat: 京东云LLM限速部署配置和设计文档
6363327d4 feat: 京东云模式降并发和任务间间隔等待
650b3974f feat: 京东云LLM限速配置函数和429重试机制
f1fef2645 docs: 京东云合作版定制设计文档
4b52f7c8e feat: 京东云版部署脚本和打包支持
fd65b965b feat: 前端京东云模式配置页面替换和模型选择限制
bcd84ad17 feat: 京东云模式数据库自动初始化和API端点保护
228414cb9 feat: LLM配置链路添加京东云短路逻辑
347c6727a feat: 新增京东云合作版模式检测和配置读取
```

---

## 7. 部署方式

```
# 1. 克隆代码
git clone <repo> && cd TradingAgentsCN
git checkout release/jdyun-v3.0

# 2. 配置环境变量
cp .env.jdyun.example .env
# 编辑 .env，填入 OPENAI_API_KEY 和 TUSHARE_TOKEN

# 3. 自定义端口（可选，K8s 多服务环境建议设置）
# NGINX_PORT=18082

# 4. 启动
docker-compose -f docker/docker-compose.jdyun.yml up -d

# 5. 访问
# http://your-server:${NGINX_PORT:-8082}
```

---

**最后更新**: 2026-07-18  
**维护分支**: `release/jdyun-v3.0`
