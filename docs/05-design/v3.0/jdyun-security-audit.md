# 京东云部署安全审查报告

**审查日期**: 2026-07-18
**审查范围**: TradingAgents-CN Pro v3.0 京东云合作版部署安全
**审查目标**: 识别部署到京东云前的安全隐患

---

## 审查总结

| 严重程度 | 数量 | 已修复 | 状态 |
|---------|------|------|------|
| 🔴 HIGH | 3 | 3 | ✅ 全部修复 |
| 🟡 MEDIUM | 5 | 3 | ✅ M1-M3 已修复，M4 已回退，M5 评估中 |
| 🟢 LOW | 3 | 0 | ⏳ 后续优化 |

## 修复记录（2026-07-18）

### ✅ H1 - 密码哈希迁移到 bcrypt
- **文件**: `app/services/user_service.py`
- **改动**: 
  - `hash_password()` 从 SHA-256 改为 bcrypt（rounds=12）
  - `verify_password()` 自动识别 bcrypt/SHA-256 哈希
  - `authenticate_user()` 添加存量密码自动升级：登录成功后将旧 SHA-256 哈希升级为 bcrypt
  - 移除密码哈希和明文密码的日志输出

### ✅ H2 - 消除硬编码数据库凭据
- **文件**: `.env.example`, `docker/.env.docker`, `docker-compose.yml`, `docker/scripts/docker-entrypoint.sh`
- **改动**:
  - 所有 `tradingagents123` 弱密码替换为 `PLEASE_CHANGE_*` 占位符或 `${MONGO_PASSWORD:?...}` 强制环境变量
  - docker-compose.yml 使用 `${VAR:?error}` 语法，未设置环境变量时报错退出
  - entrypoint.sh 修复 3 处硬编码默认密码

### ✅ H3 - JWT/CSRF 默认密钥黑名单
- **文件**: `app/core/config.py`, `.env.example`, `docker/.env.docker`
- **改动**:
  - 扩充 `_DEFAULT_SECRETS` 黑名单，覆盖所有可预测的默认值（含 jdyun/docker/placeholder 变体）
  - 生产模式下使用黑名单密钥会 `sys.exit(1)` 退出
  - env 模板使用 `PLEASE_CHANGE_*` 占位符并附生成说明

### ✅ M1 - Docker 非 root 用户
- **文件**: `docker/Dockerfile.backend.compiled.ubuntu`, `docker/scripts/docker-entrypoint.sh`
- **改动**:
  - 添加 appuser 用户（UID/GID 1000）
  - 安装 gosu 实现权限降级
  - entrypoint 以 root 启动 → chown 挂载卷 → `exec gosu appuser` 切换用户

### ✅ M2 - 数据库端口隔离
- **文件**: `docker/docker-compose.jdyun.yml`
- **改动**: MongoDB 和 Redis 从 `ports` 改为 `expose`，仅容器间访问

### ✅ M3 - XSS 防御（DOMPurify 集成）
- **文件**: `frontend/src/utils/markdown.ts`（新增）, 27 个 .vue 文件, `frontend/package.json`
- **改动**:
  - 新增统一的安全 Markdown 渲染工具 `renderMarkdown()`：marked 解析 + DOMPurify 净化
  - DOMPurify 配置白名单：ALLOWED_TAGS、ALLOWED_ATTR、ALLOWED_URI_REGEXP（禁止 javascript:/data: 协议）
  - 为所有外部链接自动添加 `rel="noopener noreferrer" target="_blank"`
  - 27 个 Vue 文件批量替换 `marked()` → `renderMarkdown()`
  - 添加 `dompurify` 和 `@types/dompurify` 依赖

### ⏪ M4 - 登录速率限制（已回退）
- **原因**: 京东云版是单用户容器部署，不存在多租户暴力破解场景
- **风险评估**: 
  - 用户可能锁死自己的系统（忘记密码 → 多试几次 → 被锁 15 分钟）
  - 外层防护（京东云安全组 + nginx）是更合适的防御层
  - 已有的 `RateLimitMiddleware`（每分钟5次）足够防止自动化扫描
- **回退操作**: 删除 `app/core/login_rate_limiter.py`，恢复 `app/routers/auth_db.py` 原状

---

## 🔴 HIGH 严重问题（需立即修复）

### H1. 密码哈希使用 SHA-256 无盐（非 bcrypt）

**位置**: [app/services/user_service.py:73-81](file:///c:/TradingAgentsCN/app/services/user_service.py#L73-L81)

**证据**:
```python
@staticmethod
def hash_password(password: str) -> str:
    # 使用 bcrypt 会更安全，但为了兼容性先使用 SHA-256
    return hashlib.sha256(password.encode()).hexdigest()

@staticmethod
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return UserService.hash_password(plain_password) == hashed_password
```

**风险分析**:
- SHA-256 是快速哈希算法，**不适用于密码存储**。现代 GPU 每秒可计算数十亿次 SHA-256
- **无盐（no salt）**：相同密码产生相同哈希，易受彩虹表攻击
- docker-compose.jdyun.yml 设置了 `BCRYPT_ROUNDS: "12"`，但代码完全未使用 bcrypt
- 代码注释明确承认"使用 bcrypt 会更安全"但选择了不安全的方案
- 若 MongoDB 数据库泄露，所有用户密码可在数分钟内被破解

**修复建议**:
- 迁移到 bcrypt 或 Argon2id（推荐 `passlib[bcrypt]` 库）
- 实现密码哈希版本升级：登录时检测旧 SHA-256 哈希，验证成功后自动升级为 bcrypt
- 对存量密码：可保留 SHA-256 哈希作为"中间态"，用户下次登录时自动迁移到 bcrypt

---

### H2. docker-compose.jdyun.yml 硬编码数据库凭据

**位置**: [docker/docker-compose.jdyun.yml:25-26, 49, 86-95](file:///c:/TradingAgentsCN/docker/docker-compose.jdyun.yml#L25-L95)

**证据**:
```yaml
# MongoDB（第25-26行）
MONGO_INITDB_ROOT_USERNAME: admin
MONGO_INITDB_ROOT_PASSWORD: tradingagents123  # ← 硬编码弱密码

# Redis（第49行）
command: redis-server --appendonly yes --requirepass tradingagents123  # ← 同样的弱密码

# 后端连接串（第89-95行）
MONGODB_URL: "mongodb://admin:tradingagents123@mongodb:27017/tradingagents?authSource=admin"
REDIS_URL: "redis://:tradingagents123@redis:6379/0"
```

**风险分析**:
- 数据库密码 `tradingagents123` 是弱密码，硬编码在版本控制的配置文件中
- 任何能访问代码仓库的人都能获取数据库凭据
- 密码在 docker-compose 环境变量、MongoDB 初始化变量、Redis 启动命令中重复出现，难以统一轮换
- 如果 MongoDB/Redis 端口被意外暴露到公网，此弱密码极易被暴力破解

**修复建议**:
- 将所有密码改为从 `.env` 文件读取：`MONGO_INITDB_ROOT_PASSWORD: ${MONGO_PASSWORD}`
- 在 `.env.jdyun.example` 中使用占位符而非真实密码
- 生成随机强密码：至少 24 字符，包含大小写字母、数字、特殊字符
- 示例：`openssl rand -base64 32` 或 `python -c "import secrets; print(secrets.token_urlsafe(32))"`

---

### H3. JWT/CSRF 默认密钥可预测且绕过验证

**位置**: [docker/docker-compose.jdyun.yml:98, 102](file:///c:/TradingAgentsCN/docker/docker-compose.jdyun.yml#L98-L102) + [app/core/config.py:408-411](file:///c:/TradingAgentsCN/app/core/config.py#L408-L411)

**证据**:
```yaml
# docker-compose.jdyun.yml
JWT_SECRET: "${JWT_SECRET:-jdyun-jwt-secret-key-change-in-production-2024}"
CSRF_SECRET: "${CSRF_SECRET:-jdyun-csrf-secret-key-change-in-production-2024}"
```

```python
# app/core/config.py - _DEFAULT_SECRETS 仅检查代码中的默认值
_DEFAULT_SECRETS = frozenset({
    "change-me-in-production",
    "change-me-csrf-secret",
})
# docker-compose 中的默认值不在 _DEFAULT_SECRETS 中，绕过了验证！
```

**风险分析**:
- 如果部署时未设置 `JWT_SECRET` 环境变量，将使用可预测的默认值 `jdyun-jwt-secret-key-change-in-production-2024`
- 此值不在 `_DEFAULT_SECRETS` 黑名单中，因此**绕过了生产环境安全验证**
- 攻击者知道此默认值后，可以**伪造任意用户的 JWT Token**，实现完全的认证绕过
- CSRF_SECRET 同理，攻击者可伪造 CSRF 令牌

**修复建议**:
- 将 `jdyun-jwt-secret-key-change-in-production-2024` 和 `jdyun-csrf-secret-key-change-in-production-2024` 添加到 `_DEFAULT_SECRETS` 黑名单
- docker-compose 中**不提供默认值**，强制用户设置：`JWT_SECRET: "${JWT_SECRET:?JWT_SECRET must be set}"`
- 部署文档中强调必须生成随机密钥

---

## 🟡 MEDIUM 严重问题（建议部署前修复）

### M1. Docker 容器以 root 用户运行

**位置**: [docker/Dockerfile.backend.compiled.ubuntu](file:///c:/TradingAgentsCN/docker/Dockerfile.backend.compiled.ubuntu)

**证据**: Dockerfile 中没有 `USER` 指令，容器内进程默认以 root 运行。

**风险分析**:
- 若容器存在 RCE 漏洞，攻击者获得容器内 root 权限
- 结合容器逃逸漏洞，可能升级到宿主机 root 权限

**修复建议**:
```dockerfile
# 在 Dockerfile 末尾 CMD 之前添加
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser
```

---

### M2. MongoDB/Redis 端口暴露到宿主机

**位置**: [docker/docker-compose.jdyun.yml:20-21, 43-44](file:///c:/TradingAgentsCN/docker/docker-compose.jdyun.yml#L20-L44)

**证据**:
```yaml
# MongoDB
ports:
  - "27019:27017"  # ← 暴露到宿主机

# Redis
ports:
  - "6381:6379"    # ← 暴露到宿主机
```

**风险分析**:
- MongoDB 和 Redis 端口映射到宿主机，如果宿主机防火墙未正确配置，这些端口可能被外部访问
- 结合 H2 中的弱密码，数据库可能被直接访问
- 在京东云环境中，如果安全组未限制这些端口，任何人都可以尝试连接

**修复建议**:
- 生产环境中使用 `expose` 而非 `ports`，仅在 Docker 网络内部可访问：
  ```yaml
  expose:
    - "27017"  # 仅同网络容器可访问
  ```
- 如果需要调试访问，通过 SSH 隧道而非直接端口映射
- 京东云安全组中仅开放 8082（nginx）端口，关闭 27019 和 6381

---

### M3. v-html + marked() 渲染未净化 HTML（XSS 风险）

**位置**: 28 个 Vue 文件使用 `v-html` 渲染 `marked()` 输出

**典型示例**: [frontend/src/views/Analysis/SingleAnalysis.vue:601, 846-858](file:///c:/TradingAgentsCN/frontend/src/views/Analysis/SingleAnalysis.vue#L846-L858)

**证据**:
```typescript
// marked 配置（无 HTML 净化）
marked.setOptions({
  breaks: true,
  gfm: true
  // 没有 sanitize 选项，没有 DOMPurify 集成
})

// 模板中直接 v-html 渲染
<div class="markdown-content" v-html="renderMarkdown(overviewBriefContent)"></div>
```

**风险分析**:
- `marked` 库默认不净化 HTML，会原样输出 markdown 中的 HTML 标签
- 通过 `v-html` 渲染时，`<script>`、`<img onerror>`、`<a onclick>` 等恶意 HTML 会执行
- 内容来源：LLM 生成的分析报告，用户可通过"分析目标""自定义参数"等输入影响 LLM 输出
- 攻击路径：用户构造特殊输入 → LLM 被诱导输出含恶意 HTML 的报告 → v-html 执行
- 结合 H3（如果 JWT 默认密钥未更换），XSS 窃取 localStorage 中的 Token 可实现完整账户接管

**修复建议**:
- 安装 `dompurify` 库：`npm install dompurify @types/dompurify`
- 在所有 `renderMarkdown` 函数中添加净化：
  ```typescript
  import DOMPurify from 'dompurify'
  function renderMarkdown(content: string): string {
    return DOMPurify.sanitize(marked.parse(content) as string)
  }
  ```
- 或使用 `marked` 的 `walkTokens` + 自定义 renderer 过滤危险 HTML

---

### M4. 认证端点无速率限制（暴力破解风险）

**位置**: [app/routers/auth_db.py:188-238](file:///c:/TradingAgentsCN/app/routers/auth_db.py#L188-L238)

**证据**: 登录端点 `/api/auth/login` 无任何速率限制、账户锁定或 CAPTCHA 机制。

**风险分析**:
- 攻击者可对任意用户名进行无限次密码尝试
- 结合 H1（SHA-256 无盐密码哈希），若获取了数据库，离线破解极快
- 常见弱密码（123456、password 等）可在数秒内被在线暴力破解

**修复建议**:
- 集成 `slowapi` 或自定义 Redis 限速器：每 IP 每分钟最多 5 次登录尝试
- 实现账户锁定：连续失败 5 次后锁定 15 分钟
- 可选：集成 CAPTCHA（如腾讯云验证码）用于多次失败后

---

### M5. JWT Token 存储在 localStorage（XSS Token 窃取）

**位置**: [frontend/src/api/request.ts](file:///c:/TradingAgentsCN/frontend/src/api/request.ts), [frontend/src/stores/auth.ts](file:///c:/TradingAgentsCN/frontend/src/stores/auth.ts)

**证据**: Token 存储在 `localStorage`，每次请求通过 axios 拦截器附加到 `Authorization` 头。

**风险分析**:
- `localStorage` 可被 JavaScript 读取，任何 XSS 漏洞（参见 M3）都可窃取 Token
- 与 M3 组合：XSS → 窃取 Token → 完整账户接管
- HttpOnly Cookie 不受 XSS 影响（但需要 CSRF 防护）

**修复建议**:
- 短期：确保 M3 的 XSS 漏洞被修复（优先级最高）
- 长期：考虑将 Token 迁移到 HttpOnly Cookie，后端设置 `Set-Cookie` 并配合 SameSite 属性
- 或使用 BFF（Backend For Frontend）模式，Token 完全存储在后端

---

## 🟢 LOW 严重问题（可后续优化）

### L1. CORS_ORIGINS 环境变量未映射到 ALLOWED_ORIGINS

**位置**: [docker/docker-compose.jdyun.yml:105](file:///c:/TradingAgentsCN/docker/docker-compose.jdyun.yml#L105) vs [app/core/config.py:28](file:///c:/TradingAgentsCN/app/core/config.py#L28)

**分析**: docker-compose 设置 `CORS_ORIGINS: "*"`，但 Settings 类的字段名是 `ALLOWED_ORIGINS`，此环境变量被忽略。实际 CORS 使用默认值（localhost:5173 等）。

**影响**: 生产环境通过 nginx 同源代理，CORS 不是实际问题。但配置项是"死代码"，容易误导运维人员。

**建议**: 统一环境变量名，或删除无用的 `CORS_ORIGINS` 配置。

---

### L2. ALLOWED_HOSTS 默认为 ["*"]

**位置**: [app/core/config.py:36](file:///c:/TradingAgentsCN/app/core/config.py#L36)

**证据**: `ALLOWED_HOSTS: List[str] = Field(default_factory=lambda: ["*"])`

**分析**: `TrustedHostMiddleware` 在非 DEBUG 模式启用，但 `ALLOWED_HOSTS` 为 `["*"]` 表示允许所有主机头，等于禁用了主机头验证。

**建议**: 京东云部署时设置 `ALLOWED_HOSTS` 为实际域名/IP。

---

### L3. Session 中间件复用 JWT_SECRET

**位置**: [app/main.py:991-993](file:///c:/TradingAgentsCN/app/main.py#L991-L993)

**证据**:
```python
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.JWT_SECRET,  # 使用相同的密钥
)
```

**分析**: Session 签名和 JWT 签名使用同一密钥，密钥泄露的影响范围更大。

**建议**: 为 Session 中间件使用独立的 `SESSION_SECRET` 密钥。

---

## 京东云部署安全清单

部署前请逐项确认：

### 🔴 必须完成（HIGH）
- [x] **H1**: 将密码哈希从 SHA-256 迁移到 bcrypt（含存量密码自动升级）
- [x] **H2**: 将 docker-compose.jdyun.yml 中所有硬编码密码改为从 .env 读取，生成强随机密码
- [x] **H3**: 将 docker-compose 默认 JWT/CSRF 密钥添加到 _DEFAULT_SECRETS 黑名单，或改为强制设置

### 🟡 强烈建议（MEDIUM）
- [x] **M1**: Dockerfile 添加非 root 用户
- [x] **M2**: MongoDB/Redis 使用 `expose` 替代 `ports`，京东云安全组仅开放 8082
- [x] **M3**: 集成 DOMPurify 净化 marked() 输出
- [⏪] **M4**: ~~登录端点添加速率限制~~（已回退：单用户部署不适用）
- [ ] **M5**: 确保 M3 修复后再评估 Token 存储方案

### 🟢 后续优化（LOW）
- [ ] **L1**: 清理 CORS_ORIGINS 死配置
- [ ] **L2**: 设置 ALLOWED_HOSTS 为实际域名
- [ ] **L3**: Session 中间件使用独立密钥

### 京东云安全组配置建议
```
入站规则：
- 端口 8082 (nginx): 允许 0.0.0.0/0（或限制为管理 IP）
- 端口 22 (SSH): 仅允许管理 IP
- 端口 27019 (MongoDB): 拒绝所有外部访问（仅内部 Docker 网络）
- 端口 6381 (Redis): 拒绝所有外部访问（仅内部 Docker 网络）
- 其他端口: 默认拒绝
```

### .env 文件安全要求
```bash
# 必须生成强随机值，禁止使用默认值
JWT_SECRET=$(openssl rand -base64 48)
CSRF_SECRET=$(openssl rand -base64 48)
MONGO_PASSWORD=$(openssl rand -base64 24)
REDIS_PASSWORD=$(openssl rand -base64 24)

# 京东云提供的凭据
OPENAI_API_KEY=<京东云提供的Key>
TUSHARE_TOKEN=<京东云提供的Token>
```

