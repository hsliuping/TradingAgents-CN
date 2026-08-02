# 京东云合作版登录认证设计文档

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v3.0 JD Cloud Edition |
| 分支 | `release/jdyun-v3.0` |
| 日期 | 2026-08-02 |
| 状态 | ✅ 已实施 |
| 依赖文档 | [京东云合作版定制设计](jdyun-edition-design.md) |

---

## 1. 背景

京东云合作版采用"一用户一容器"部署模式：每个京东云用户开通服务时，京东云平台为该用户启动一个专属 Docker 容器。京东云网关代理所有请求，并在 HTTP 头中注入 `Authorization: Basic base64(username:token)` 进行身份传递。

本文档描述后端如何处理该 Basic Auth 请求，包括新用户建档、老用户登录、令牌变化、安全防线等完整链路。

---

## 2. 认证架构

### 2.1 三道防线模型

```
用户请求
    ↓
🛡️ 第一道防线：京东云网关认证（京东云侧）
    · 京东云平台对用户做登录认证
    · 认证通过后在请求头注入 Authorization: Basic base64(user:token)
    ↓
🛡️ 第二道防线：IP 白名单（我们侧）
    · 校验请求来源 IP 是否在 JDYUN_GATEWAY_IPS 白名单中
    · 非白名单 IP 直接返回 403
    · 未配置白名单时不拦截（向后兼容）
    ↓
🛡️ 第三道防线：Basic Auth 分级校验（我们侧）
    · 新用户（DB 无记录）：严格校验 username + token
    · 老用户（DB 已建档）：只校验 username，token 可任意变化
    · 通过后自动建档/复用真实 DB 记录
    ↓
认证通过，进入业务逻辑
```

### 2.2 请求流转图

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  京东云用户   │────→│  京东云网关      │────→│  我们的容器       │
│  (浏览器)    │     │  (平台认证)     │     │  (FastAPI 后端)  │
└─────────────┘     └─────────────────┘     └──────────────────┘
                           │                         │
                     注入 Basic Auth           ① IP 白名单校验
                     base64(user:token)        ② Basic Auth 分级校验
                           │                   ③ 建档/复用用户
                           ↓                         │
                    Authorization: Basic              ↓
                    amNsb3VkLXVnaWR2...         返回用户信息
                                                 (id=ObjectId)
```

---

## 3. 分级校验策略

### 3.1 核心逻辑

| 用户类型 | DB 状态 | 校验规则 | 说明 |
|----------|---------|----------|------|
| 新用户 | 无记录 | username + token 都必须匹配白名单 | 防伪造，首次必须用京东云提供的正确凭据 |
| 老用户 | 已建档 | 只校验 username | token 可变，安全由京东云网关把关 |

### 3.2 为什么老用户免令牌校验

**前提条件**（京东云架构保证）：
1. 容器端口不直接对外暴露，只能通过京东云网关访问
2. 京东云网关已对用户做过平台级认证
3. 到达容器的请求都是可信的

**结论**：容器只需识别"是哪个用户"即可，不需要二次校验 token。这样：
- 京东云轮换 token → 老用户不受影响
- 用户改密码 → 老用户不受影响
- 不需要重启容器

### 3.3 新用户首次认证流程

```
请求进来，带 Authorization: Basic base64(username:token)
    ↓
查 DB users 集合（username + provider="jdyun"）
    ↓ 未找到
严格校验：verify_jdyun_basic_auth(username, token)
    · 从 JDYUN_BASIC_AUTH_USERS 环境变量读取白名单
    · 用 hmac.compare_digest 比对 token（防时序攻击）
    ↓ 匹配
调用 get_or_create_jdyun_user(username) 建档
    · insert 一条新 user 文档到 users 集合
    · _id = MongoDB 自动生成的 ObjectId（24 字符 hex）
    · password_hash = bcrypt(随机占位串)（真实 token 由京东云保管）
    · provider = "jdyun"，is_admin = True
    ↓
返回用户信息（id = str(ObjectId)）
```

### 3.4 老用户登录流程

```
请求进来，带 Authorization: Basic base64(username:token)
    ↓
查 DB users 集合（username + provider="jdyun"）
    ↓ 找到
老用户免令牌：auth_passed = True（不校验 token）
    ↓
调用 get_or_create_jdyun_user(username) 复用
    · update_one 刷新 last_login
    · 返回同一个 ObjectId（历史任务/报告数据不丢失）
    ↓
返回用户信息（id = 同一个 str(ObjectId)）
```

---

## 4. 代码实现

### 4.1 核心文件

| 文件 | 职责 |
|------|------|
| `app/core/jdyun.py` | 白名单解析、令牌校验、IP 白名单校验 |
| `app/services/user_service.py` | 京东云用户建档/复用、老用户检测 |
| `app/routers/auth_db.py` | Basic Auth 分支接入 `get_current_user` |
| `frontend/src/stores/auth.ts` | 前端 jdyun 模式免 JWT 登录 |
| `frontend/mock-jdyun-gateway.mjs` | 本地模拟京东云网关（测试用） |

### 4.2 白名单解析

**文件**: `app/core/jdyun.py` — `get_jdyun_basic_auth_users()`

```python
环境变量格式: JDYUN_BASIC_AUTH_USERS=user1:token1,user2:token2
- 多个账户用英文逗号分隔（一用户一容器场景下通常只有一条）
- 用户名和访问令牌用英文冒号分隔
- 令牌中的冒号用第一个冒号切分（避免歧义）
```

### 4.3 令牌校验

**文件**: `app/core/jdyun.py` — `verify_jdyun_basic_auth(username, token)`

- 严格模式：白名单中令牌为具体值时，username + token 都必须匹配
- 通配符模式：白名单中令牌为 `*` 时，只校验 username（兼容旧方案）
- 使用 `hmac.compare_digest` 做恒定时间比较（防时序攻击）

### 4.4 分级校验接入

**文件**: `app/routers/auth_db.py` — `get_current_user()` 方式 0

```python
if is_jdyun_mode() and authorization.startswith("basic "):
    # ① IP 白名单校验
    if not is_from_jdyun_gateway(client_ip):
        raise HTTPException(403)

    # ② 分级校验
    is_existing = user_service.is_existing_jdyun_user(username)
    if is_existing:
        auth_passed = True  # 老用户免令牌
    else:
        auth_passed = verify_jdyun_basic_auth(username, token)  # 新用户严格

    # ③ 建档/复用
    if auth_passed:
        jdyun_user = await user_service.get_or_create_jdyun_user(username)
        return {id: str(jdyun_user.id), ...}
```

### 4.5 用户建档

**文件**: `app/services/user_service.py` — `get_or_create_jdyun_user()`

```python
async def get_or_create_jdyun_user(self, jdyun_username, is_admin=True):
    existing = self.users_collection.find_one({"username": username})
    if existing:
        # 老用户：刷新 last_login → 返回
        return User(**existing)
    # 新用户：insert 新记录（ObjectId 自动生成）
    new_user_doc = {
        "username": username,
        "email": f"{username}@jdyun.local",
        "password_hash": bcrypt(随机占位串),
        "provider": "jdyun",
        "is_admin": is_admin,
        "is_verified": True,
        ...
    }
    result = self.users_collection.insert_one(new_user_doc)
    return User(**new_user_doc)  # id = ObjectId
```

### 4.6 IP 白名单

**文件**: `app/core/jdyun.py` — `is_from_jdyun_gateway(client_ip)`

```python
环境变量: JDYUN_GATEWAY_IPS=10.0.0.1,172.16.0.0/12
- 支持单个 IP 和 CIDR 格式
- 留空则不启用 IP 校验（向后兼容）
```

### 4.7 前端适配

**文件**: `frontend/src/stores/auth.ts` — `_doCheckAuthStatus()`

京东云模式下，即使 localStorage 没有 JWT token，也会主动调 `/api/auth/me`：
- cookie 由网关注入 Basic Auth → 后端返回用户信息
- 前端写入 `isAuthenticated = true` + `user` + 权限
- 避免前端二次弹出登录页

**隐藏的功能**：
- `UserProfile.vue`：jdyun 模式不显示"退出登录"菜单
- `Settings/index.vue`：jdyun 模式不显示"修改密码"按钮

---

## 5. 环境变量配置

### 5.1 必须配置

| 环境变量 | 说明 | 示例 |
|----------|------|------|
| `JDYUN_MODE` | 京东云模式开关 | `true` |
| `JDYUN_BASIC_AUTH_USERS` | Basic Auth 白名单 | `jcloud-ugidvcp:8437F13D...` |
| `OPENAI_API_BASE` | LLM 模型服务地址 | `https://modelservice.jdcloud.com/v1` |
| `OPENAI_API_KEY` | LLM API Key | `pk-xxxxxxxx` |
| `OPENAI_MODEL` | 默认对话模型 | `GLM-5` |
| `EMBEDDING_API_BASE` | Embedding 模型服务地址 | `https://modelservice.jdcloud.com/v1` |
| `EMBEDDING_API_KEY` | Embedding API Key（通常与 OPENAI_API_KEY 相同） | `pk-xxxxxxxx` |
| `EMBEDDING_MODEL` | Embedding 模型 | `Qwen3-Embedding-8B` |
| `MONGODB_PASSWORD` | MongoDB 数据库密码 | `<自定义强密码>` |
| `JWT_SECRET` | JWT 签名密钥 | `openssl rand -base64 48` |
| `CSRF_SECRET` | CSRF 防护密钥 | `openssl rand -base64 48` |

### 5.2 推荐配置（生产环境）

| 环境变量 | 说明 | 示例 |
|----------|------|------|
| `JDYUN_GATEWAY_IPS` | 京东云网关 IP 白名单 | `10.0.0.1,172.16.0.0/12` |

### 5.3 配置文件

京东云版使用独立环境文件 `.env.docker.jdyun`，由 `start_dev.ps1 backend jdyun` 自动加载。
生产环境通过 `docker-compose.yml` + `.env` 文件配置。

---

## 6. 安全性分析

### 6.1 攻击面分析

| 攻击场景 | 防线 | 结果 |
|----------|------|------|
| 外部攻击者知道 username，伪造请求 | IP 白名单 | ✅ 被拒绝（IP 不在白名单） |
| 外部攻击者直接访问容器 | IP 白名单 | ✅ 被拒绝 |
| 伪造新用户（不在白名单） | Basic Auth 严格校验 | ✅ 被拒绝 |
| 白名单中新用户 + 错误 token | Basic Auth 严格校验 | ✅ 被拒绝 |
| DB 被注入伪造用户 | 需先攻破 DB | ⚠️ 需 DB 安全防护 |

### 6.2 安全前提

分级校验（老用户免令牌）的安全性依赖：
1. **容器端口不直接对外暴露** — 只能通过京东云网关访问
2. **京东云网关已认证** — 到达容器的请求都是可信的
3. **IP 白名单作为第二道防线** — 即使 username 泄露，外部攻击者也无法伪造

### 6.3 与严格模式对比

| | 严格模式（每次校验 token） | 分级模式（老用户免令牌） |
|---|---|---|
| token 轮换 | 需更新环境变量 + 重启 | 不影响 |
| 安全性 | 最高 | 依赖网络隔离 + IP 白名单 |
| 适用场景 | token 固定不变 | token 动态变化（京东云场景） |

---

## 7. 本地测试

### 7.1 模拟网关

**文件**: `frontend/mock-jdyun-gateway.mjs`

模拟京东云网关完整行为：
- 登录页 `/login` - 模拟京东云平台登录（凭据写死 `testuser / Test@123456`）
- Session 机制 - 登录成功后设置 `jdyun_session` cookie
- 自动注入 Basic Auth - 后续所有 `/api` 请求从 cookie 提取凭据注入 Header
- 统一目标 - 所有请求转发到单容器 `http://127.0.0.1:8082`（Nginx 内部区分前端/后端）

### 7.2 启动方式

```powershell
# 终端1: Docker 容器（单容器镜像，含 MongoDB + Redis + 后端 + 前端）
.\start_dev.ps1 docker 3.0
bash deploy-all-in-one/run.sh --jdyun

# 终端2: 模拟网关
node frontend/mock-jdyun-gateway.mjs
```

### 7.3 浏览器测试

打开 `http://localhost:3100`，输入 `testuser` / `Test@123456`。

### 7.4 API 测试

```bash
# 新用户首次认证（严格校验，需用 .env.docker.jdyun 中的正确凭据）
curl -u "jcloud-ugidvcp:8437F13DABE87D0BC1D4DCCD4739C5A7" http://127.0.0.1:8082/api/auth/me

# 老用户免令牌（token 可变）
curl -u "jcloud-ugidvcp:AnyToken" http://127.0.0.1:8082/api/auth/me

# 伪造用户被拒绝
curl -u "fake-user:anything" http://127.0.0.1:8082/api/auth/me  # 401
```

---

## 8. 测试验证结果

以下场景已全部验证通过（2026-08-02）：

| 场景 | 描述 | 结果 |
|------|------|------|
| 1 | 新用户首次认证（正确 token） | ✅ 通过 + 建档 |
| 2a | 老用户 + token 不变 | ✅ 免令牌通过 |
| 2b | 老用户 + token 变化 | ✅ 免令牌通过 |
| 2c | 老用户 + 随机 token | ✅ 免令牌通过 |
| 2d | 老用户复用同一 ObjectId | ✅ 数据不丢失 |
| 3a | 127.0.0.1 在 IP 白名单 | ✅ 通过 |
| 3b | 8.8.8.8 不在 IP 白名单 | ✅ 被拒绝 |
| 3c | 未配置 IP 白名单 | ✅ 不拦截（向后兼容） |
| 4a | 伪造新用户（不在白名单） | ✅ 被拒绝 |
| 4b | 白名单新用户 + 正确 token | ✅ 通过 + 建档 |
| 4c | 白名单新用户 + 错误 token | ✅ 被拒绝 |
| 4d | 老用户 + 错误 token | ✅ 免令牌通过 |
| 5a | 未登录访问首页 → 重定向 | ✅ 302 → /login |
| 5b | 获取登录页面 | ✅ 200 |
| 5c | 正确凭据登录 | ✅ 302 + cookie |
| 5d | 带 cookie 访问首页 | ✅ 200 |
| 5e | 带 cookie 调 API | ✅ 200 + 用户信息 |
| 5f | 错误密码登录 | ✅ 被拒绝 |

---

## 9. 关键设计决策

### 9.1 为什么用 Basic Auth 而不是 JWT

| 因素 | Basic Auth | JWT |
|------|-----------|-----|
| 京东云网关支持 | ✅ 原生支持 | ❌ 需京东云改造 |
| 无状态 | ✅ 每次请求带凭据 | ❌ 需要刷新机制 |
| token 失效处理 | 不存在（每次带） | 需 refresh token |
| 改造成本 | 低 | 高 |

### 9.2 为什么老用户免令牌

- 京东云 token 可能动态变化（轮换/用户改密码）
- 如果每次都严格校验，token 变化后需要重启容器
- 在"一用户一容器 + 网关代理"架构下，安全由网关把关
- 容器只需识别用户身份，不需要二次认证

### 9.3 为什么需要 IP 白名单

- 分级校验下老用户免令牌，存在 username 泄露后被伪造的风险
- IP 白名单确保请求必须来自京东云网关
- 即使 username 泄露，外部攻击者也无法伪造请求
- 作为第二道防线，与网络隔离形成双重保险

---

## 10. 变更记录

| 日期 | 变更 | 提交 |
|------|------|------|
| 2026-07-18 | 初始 Basic Auth 实现（虚拟用户） | release/jdyun-v3.0 |
| 2026-08-01 | Basic Auth 返回真实 DB 记录（修复 ObjectId 报错） | release/jdyun-v3.0 |
| 2026-08-02 | 分级校验策略（新用户严格，老用户免令牌） | release/jdyun-v3.0 |
| 2026-08-02 | IP 白名单第二道防线 | release/jdyun-v3.0 |
| 2026-08-02 | 前端 jdyun 模式免 JWT 登录 | release/jdyun-v3.0 |
