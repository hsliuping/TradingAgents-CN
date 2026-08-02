# 京东云对接指南 — 登录认证集成

> 本文档面向京东云工程师，描述京东云平台与我们系统在登录认证方面的对接要求。

---

## 1. 对接概述

### 1.1 部署架构

```
京东云用户 → 京东云网关（平台认证 + 注入 Basic Auth）→ 我们的容器（FastAPI 后端）
```

- **一用户一容器**：每个京东云用户开通服务时，京东云平台为该用户启动一个专属 Docker 容器
- **网关代理**：所有请求经京东云网关转发，网关在 HTTP 头中注入 `Authorization: Basic base64(username:token)`
- **单容器单用户**：每个容器的环境变量只配置该用户的凭据

### 1.2 认证流程

```
1. 用户在京东云平台登录
2. 京东云网关认证通过，在后续请求中注入 Authorization: Basic base64(user:token)
3. 我们的容器接收请求，校验 Basic Auth
4. 首次请求：自动为该用户建档（写入数据库）
5. 后续请求：识别用户身份，直接放行
```

---

## 2. 京东云侧需要做的事

### 2.1 注入 Basic Auth 请求头

京东云网关在代理每个请求时，必须在 HTTP 头中注入：

```
Authorization: Basic base64(username:token)
```

**示例**：
```bash
# username = jcloud-ugidvcp
# token = 8437F13DABE87D0BC1D4DCCD4739C5A7
# base64("jcloud-ugidvcp:8437F13DABE87D0BC1D4DCCD4739C5A7") = amNsb3VkLXVnaWR2Y3A6ODQzN0YxM0RBQkU4N0QwQkMxRDREQ0NENDczOUM1QTc=

curl --header 'Authorization: Basic amNsb3VkLXVnaWR2Y3A6ODQzN0YxM0RBQkU4N0QwQkMxRDREQ0NENDczOUM1QTc=' https://<容器地址>/api/auth/me
```

### 2.2 字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `username` | 京东云用户唯一标识（每个用户不同） | `jcloud-ugidvcp` |
| `token` | 京东云平台为该用户生成的访问令牌 | `8437F13DABE87D0BC1D4DCCD4739C5A7` |

### 2.3 关于 token 的说明

| 问题 | 答案 |
|------|------|
| token 是用户登录密码吗？ | **不是**。token 是京东云平台生成的访问令牌，与用户登录密码解耦 |
| token 会过期吗？ | 不会自动过期。但京东云可以主动轮换 |
| 用户改密码会影响 token 吗？ | **不影响**。token 与登录密码是独立的 |
| token 变化后需要重启容器吗？ | **不需要**。首次认证后用户已建档，后续 token 变化不影响登录 |
| token 可以是任意格式吗？ | 是。token 中如果包含冒号，编码时取第一个冒号分隔 |

---

## 3. 容器环境变量配置

### 3.1 必须配置的环境变量

京东云平台在启动容器时，必须注入以下环境变量：

| 环境变量 | 必填 | 说明 | 示例 |
|----------|------|------|------|
| `JDYUN_MODE` | ✅ | 京东云模式开关，必须为 `true` | `true` |
| `JDYUN_BASIC_AUTH_USERS` | ✅ | Basic Auth 白名单（用户名:访问令牌） | `jcloud-ugidvcp:8437F13DABE87D0BC1D4DCCD4739C5A7` |
| `OPENAI_API_BASE` | ✅ | 京东云 LLM 模型服务地址 | `https://modelservice.jdcloud.com/v1` |
| `OPENAI_API_KEY` | ✅ | 京东云 API Key（LLM 对话用） | `pk-xxxxxxxx` |
| `OPENAI_MODEL` | ✅ | 默认对话模型 | `GLM-5` 或 `DeepSeek-V4-Flash` |
| `EMBEDDING_API_BASE` | ✅ | 京东云 Embedding 模型服务地址 | `https://modelservice.jdcloud.com/v1` |
| `EMBEDDING_API_KEY` | ✅ | 京东云 API Key（Embedding 向量化用，通常与 OPENAI_API_KEY 相同） | `pk-xxxxxxxx` |
| `EMBEDDING_MODEL` | ✅ | Embedding 模型 | `Qwen3-Embedding-8B` |
| `TUSHARE_TOKEN` | ✅ | Tushare 数据源 Token | `<由用户提供>` |
| `MONGODB_PASSWORD` | ✅ | MongoDB 数据库密码（容器内部使用，不对外暴露，可用固定密码） | `<自定义密码>` |

### 3.2 可选环境变量（容器自动生成）

以下变量不设时，容器启动时自动生成随机值并持久化到数据卷，重启后不会变化：

| 环境变量 | 说明 | 自动生成方式 |
|----------|------|-------------|
| `JWT_SECRET` | JWT 签名密钥 | `head -c 32 /dev/urandom \| base64` |
| `CSRF_SECRET` | CSRF 防护密钥 | `head -c 32 /dev/urandom \| base64` |

> 如需自定义，可在 `.env` 中设置。不设则无需关心。

### 3.3 推荐配置的环境变量

| 环境变量 | 推荐 | 说明 | 示例 |
|----------|------|------|------|
| `JDYUN_GATEWAY_IPS` | ✅ 推荐 | 京东云网关 IP 白名单（第二道安全防线） | `10.0.0.1,172.16.0.0/12` |

### 3.4 JDYUN_BASIC_AUTH_USERS 格式

```
JDYUN_BASIC_AUTH_USERS=username1:token1,username2:token2
```

- 多个账户用英文逗号分隔（一用户一容器场景下通常只有一条）
- 用户名和令牌用英文冒号分隔
- 令牌中如果包含冒号，取第一个冒号切分（令牌部分可以包含冒号）

**一用户一容器示例**：
```bash
# 用户 jcloud-ugidvcp 的专属容器
JDYUN_BASIC_AUTH_USERS=jcloud-ugidvcp:8437F13DABE87D0BC1D4DCCD4739C5A7
```

---

## 4. 认证校验机制

### 4.1 分级校验策略

我们的系统采用分级校验策略：

| 场景 | 校验规则 | 说明 |
|------|----------|------|
| **新用户首次请求** | username + token 都必须匹配白名单 | 防伪造，必须用京东云提供的正确凭据 |
| **老用户后续请求** | 只校验 username | token 可任意变化，安全由京东云网关把关 |

### 4.2 为什么这样设计

1. **首次严格校验**：确保是京东云平台分配的合法用户，防止伪造
2. **后续免令牌校验**：京东云轮换 token 或用户改密码后，老用户不受影响，不需要重启容器
3. **安全由网关把关**：在"一用户一容器"架构下，容器端口不直接对外暴露，京东云网关已做认证

### 4.3 建档流程

```
首次请求（新用户）
    ↓
严格校验 username + token → 通过
    ↓
自动在数据库建档：
    · 用户名 = Basic Auth 中的 username
    · 角色 = admin（京东云用户默认管理员）
    · 密码 = 随机占位（真实 token 由京东云保管，我们不存储）
    ↓
返回用户信息（包含合法的用户 ID）
```

后续请求（老用户）：
- 直接识别 username → 返回同一个用户 ID
- 历史任务、报告、配置等数据全部保留

---

## 5. 安全防线

### 5.1 三道防线

| 防线 | 责任方 | 说明 |
|------|--------|------|
| 第一道：京东云网关认证 | 京东云 | 平台级用户认证，注入 Basic Auth |
| 第二道：IP 白名单 | 我们 | 校验请求来源 IP 是否在 `JDYUN_GATEWAY_IPS` 白名单中 |
| 第三道：Basic Auth 分级校验 | 我们 | 新用户严格校验，老用户免令牌 |

### 5.2 IP 白名单配置（推荐）

**请向京东云工程师确认网关出口 IP**，配置到容器的 `JDYUN_GATEWAY_IPS` 环境变量：

```bash
# 单个 IP
JDYUN_GATEWAY_IPS=10.0.0.1

# 多个 IP
JDYUN_GATEWAY_IPS=10.0.0.1,10.0.0.2

# CIDR 网段
JDYUN_GATEWAY_IPS=172.16.0.0/12

# 混合
JDYUN_GATEWAY_IPS=10.0.0.1,172.16.0.0/12
```

**作用**：即使 username 泄露，非京东云网关的请求也会被拒绝（403 Forbidden）。

**未配置时**：不拦截（仅依赖网络隔离，安全性较低，不推荐生产环境）。

---

## 6. 新用户开通流程

### 6.1 京东云侧操作

当新用户开通服务时，京东云平台需要：

1. **生成用户凭据**：为该用户分配 `username` 和 `token`
2. **启动专属容器**：注入以下环境变量
   ```bash
   JDYUN_MODE=true
   JDYUN_BASIC_AUTH_USERS=<username>:<token>
   JDYUN_GATEWAY_IPS=<京东云网关IP>
   OPENAI_API_BASE=https://modelservice.jdcloud.com/v1
   OPENAI_API_KEY=<京东云API Key>
   OPENAI_MODEL=<默认模型>
   EMBEDDING_API_BASE=https://modelservice.jdcloud.com/v1
   EMBEDDING_API_KEY=<京东云API Key>
   EMBEDDING_MODEL=Qwen3-Embedding-8B
   TUSHARE_TOKEN=<Tushare Token>
   MONGODB_PASSWORD=<自定义强密码>
   ```
   > JWT_SECRET / CSRF_SECRET 无需设置，容器启动时自动生成。
3. **配置网关**：京东云网关注入 `Authorization: Basic base64(<username>:<token>)`

### 6.2 我们系统自动处理

用户首次访问时，系统自动：
- 校验白名单 → 通过
- 在数据库建档 → 生成合法用户 ID
- 后续请求自动识别 → 无需额外操作

**不需要手动创建用户，不需要预置数据。**

---

## 7. token 轮换/用户改密码

### 7.1 token 变化后的影响

| 时间点 | token 状态 | 用户能登录吗 | 需要操作吗 |
|--------|-----------|-------------|-----------|
| 首次启动 | 正确 | ✅ 能 | 无 |
| 首次认证后（已建档） | 正确 | ✅ 能 | 无 |
| 京东云轮换 token | 变了 | ✅ 能（老用户免令牌） | **无** |
| 用户改密码 | token 不变 | ✅ 能 | 无 |
| 容器重启 | 环境变量里的 token 可能过期 | ✅ 能（老用户免令牌） | 无 |

### 7.2 什么情况下需要更新环境变量

- **新增白名单用户**（一用户一容器场景下不会发生）
- **容器数据卷被清空**（用户需重新建档，需要正确的 token）

### 7.3 什么情况下需要重启容器

- **更新环境变量后**（环境变量在启动时加载）
- **代码更新后**（需要加载新代码）

token 变化**不需要**重启容器。

---

## 8. 对接验证

### 8.1 京东云侧验证

容器启动后，京东云工程师可以通过以下方式验证对接是否成功：

```bash
# 替换 <容器地址>、<username>、<token> 为实际值
curl -u "<username>:<token>" https://<容器地址>/api/auth/me
```

**预期返回**（HTTP 200）：
```json
{
    "success": true,
    "data": {
        "id": "6a6e5d8342be7f5a1bab15ac",
        "username": "jcloud-ugidvcp",
        "is_admin": true,
        "auth_method": "basic",
        "provider": "jdyun"
    },
    "message": "获取用户信息成功"
}
```

**关键字段**：
- `id`：24 字符 hex 格式的 ObjectId（合法用户 ID）
- `auth_method`：必须为 `"basic"`（表示 Basic Auth 认证通过）
- `is_admin`：`true`（京东云用户默认管理员）

### 8.2 首次认证 vs 后续认证

```bash
# 首次认证（新用户，必须用正确 token）
curl -u "jcloud-ugidvcp:8437F13DABE87D0BC1D4DCCD4739C5A7" https://<容器地址>/api/auth/me
# → 200，建档成功

# 后续认证（老用户，token 可变）
curl -u "jcloud-ugidvcp:ANY_TOKEN" https://<容器地址>/api/auth/me
# → 200，同一个用户 ID

# 伪造用户（不在白名单）
curl -u "fake-user:anything" https://<容器地址>/api/auth/me
# → 401，被拒绝
```

### 8.3 IP 白名单验证

如果配置了 `JDYUN_GATEWAY_IPS`：

```bash
# 从非白名单 IP 发起请求
curl -u "jcloud-ugidvcp:8437F13D..." https://<容器地址>/api/auth/me
# → 403 Forbidden（如果从非白名单 IP 访问）
```

---

## 9. 常见问题

### Q1: token 是用户的登录密码吗？

**不是**。token 是京东云平台为该用户生成的访问令牌，与用户在京东云平台的登录密码完全独立。用户改登录密码不会影响 token。

### Q2: token 变化后需要通知我们吗？

**不需要**。首次认证后用户已建档到数据库，后续 token 变化不影响登录。系统会自动识别老用户身份。

### Q3: 一个容器可以服务多个用户吗？

**技术上支持**（`JDYUN_BASIC_AUTH_USERS` 支持逗号分隔多个账户），但**不推荐**。建议一用户一容器，确保数据隔离。

### Q4: 用户数据会丢失吗？

**不会**。用户首次认证后建档到数据库，容器重启、token 变化都不影响已建档的用户记录。用户的任务、报告、配置等数据全部保留。

### Q5: 如何添加新用户？

京东云平台为新用户启动一个新容器，注入该用户的 `JDYUN_BASIC_AUTH_USERS` 环境变量即可。系统会自动为新用户建档。

### Q6: 如果数据库被清空怎么办？

用户需要重新首次认证。此时 `JDYUN_BASIC_AUTH_USERS` 环境变量中的 token 必须是有效的（与京东云网关注入的 Basic Auth 中的 token 一致）。

### Q7: 可以不用 Basic Auth 吗？

**不可以**。`JDYUN_BASIC_AUTH_USERS` 是京东云模式登录的核心配置，必须填写。

如果留空，会导致以下问题：
1. 京东云网关注入的 Basic Auth 凭据无法通过白名单校验
2. 后端返回 401 未授权
3. 前端收到 401 后跳转到**应用内登录页**（而非京东云平台登录页），出现"网关登录后又跳转到二次登录页"的现象
4. 用户无法正常使用系统

**正确做法**：即使一用户一容器场景下只有一条凭据，也必须配置 `JDYUN_BASIC_AUTH_USERS=<username>:<token>`。首次认证通过后，后续 token 变化不影响老用户登录（见第 7 节）。

---

## 10. 联系方式

如有对接问题，请联系我方技术团队。

| 项目 | 内容 |
|------|------|
| 认证方式 | Basic Auth（京东云网关注入） |
| 对接文档版本 | v1.1 |
| 更新日期 | 2026-08-03 |
| 系统版本 | TradingAgents-CN Pro v3.0 JD Cloud Edition |

---

## 11. 部署方式

### 11.1 docker-compose 部署（推荐）

京东云工程师可使用以下 `docker-compose.yml` 部署：

```yaml
services:
  tradingagents:
    image: agentengine-tradingagent-cn-north-1.jcr.service.jdcloud.com/tradingagent:3.0.0-jdyun
    container_name: tradingagents-jdyun
    hostname: tradingagents
    restart: unless-stopped
    ports:
      - "${HOST_PORT:-8082}:8082"
    volumes:
      - ta-data:/data/db
      - ta-redis:/var/lib/redis
      - ta-runtime:/app/runtime
      - ta-logs:/app/logs
      - ta-qdrant:/app/data
    environment:
      TZ: "Asia/Shanghai"
      MONGODB_PASSWORD: "${MONGODB_PASSWORD:?MONGODB_PASSWORD must be set in .env}"
      JDYUN_MODE: "true"
      OPENAI_API_BASE: "${OPENAI_API_BASE:-https://modelservice.jdcloud.com/v1}"
      OPENAI_API_KEY: "${OPENAI_API_KEY:?OPENAI_API_KEY must be set in .env}"
      OPENAI_MODEL: "${OPENAI_MODEL:-GLM-5}"
      EMBEDDING_API_BASE: "${EMBEDDING_API_BASE:-https://modelservice.jdcloud.com/v1}"
      EMBEDDING_API_KEY: "${EMBEDDING_API_KEY}"
      EMBEDDING_MODEL: "${EMBEDDING_MODEL:-Qwen3-Embedding-8B}"
      TUSHARE_TOKEN: "${TUSHARE_TOKEN}"
      JWT_SECRET: "${JWT_SECRET:-}"
      CSRF_SECRET: "${CSRF_SECRET:-}"
      # 🔧 必填！京东云网关注入的 Basic Auth 凭据（留空会导致网关登录后跳转到二次登录页）
      JDYUN_BASIC_AUTH_USERS: "${JDYUN_BASIC_AUTH_USERS:?JDYUN_BASIC_AUTH_USERS must be set in .env}"
      # 推荐配置（留空则不启用 IP 校验，仅依赖网络隔离）
      JDYUN_GATEWAY_IPS: "${JDYUN_GATEWAY_IPS:-}"

volumes:
  ta-data:
    driver: local
  ta-redis:
    driver: local
  ta-runtime:
    driver: local
  ta-logs:
    driver: local
  ta-qdrant:
    driver: local
```

### 11.2 .env 配置文件

创建 `.env` 文件配置环境变量：

```bash
# 必填项
MONGODB_PASSWORD=<自定义强密码>
OPENAI_API_KEY=<京东云API Key>
EMBEDDING_API_KEY=<京东云API Key>
JDYUN_BASIC_AUTH_USERS=<username>:<token>

# 推荐配置
JDYUN_GATEWAY_IPS=<京东云网关IP>

# 可选（容器自动生成，无需设置）
# JWT_SECRET / CSRF_SECRET：不设则容器启动时自动生成并持久化

# 可选（有默认值）
HOST_PORT=8082
OPENAI_API_BASE=https://modelservice.jdcloud.com/v1
EMBEDDING_API_BASE=https://modelservice.jdcloud.com/v1
OPENAI_MODEL=GLM-5
EMBEDDING_MODEL=Qwen3-Embedding-8B
TUSHARE_TOKEN=<用户的Tushare Token>
```

### 11.3 启动与验证

```bash
# 启动
docker-compose up -d

# 验证（替换实际凭据）
curl -u "<username>:<token>" http://localhost:8082/api/auth/me

# 预期返回
# {"success":true,"data":{"username":"...","is_admin":true,"auth_method":"basic","provider":"jdyun"}}
```

### 11.4 镜像内置内容

镜像 `tradingagent:3.0.0-jdyun` 已内置：

| 内容 | 说明 |
|------|------|
| 前端构建产物 | Vite 编译好的静态文件 |
| 后端 Python 代码 | FastAPI 应用 |
| MongoDB 7.0 | 数据库 |
| Redis 7 | 缓存 |
| Nginx | 反向代理 |
| s6-overlay | 进程管理 |
| 用户手册 | 内置文档 |
| 预生成向量索引 | 开箱即用，首次部署无需等待 embedding |
| 能力索引 | 内置工具索引数据 |

**数据持久化卷**（5 个）：

| 卷名 | 容器路径 | 用途 |
|------|---------|------|
| `ta-data` | `/data/db` | MongoDB 数据 |
| `ta-redis` | `/var/lib/redis` | Redis 数据 |
| `ta-runtime` | `/app/runtime` | 运行时配置 |
| `ta-logs` | `/app/logs` | 日志 |
| `ta-qdrant` | `/app/data` | Qdrant 向量数据库 |

容器删除重建后，只要数据卷保留，用户数据和索引都不会丢失。
