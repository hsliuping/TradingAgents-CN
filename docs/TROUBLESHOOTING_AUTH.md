# 认证问题排查指南

## 🔴 问题 1：登录后立即退出

### 症状
- 用户登录成功
- 跳转到仪表板页面
- 立即被重定向回登录页

### 原因分析

#### 1. Cookie 未正确发送（最常见）

**问题**：Axios 默认不发送 Cookie

**解决方案**：

```javascript
// frontend/src/api/request.ts
const instance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  withCredentials: true,  // 🔥 必须设置为 true
  headers: {
    'Content-Type': 'application/json'
  }
})
```

**验证方法**：

1. 打开浏览器开发者工具（F12）
2. 切换到 Network 标签
3. 登录后查看 `/api/auth/login` 请求
4. 检查 Response Headers 中是否有 `Set-Cookie`
5. 检查后续请求（如 `/api/auth/me`）的 Request Headers 中是否有 `Cookie`

**正确的请求头**：

```
# 登录响应
Set-Cookie: tradingagents_session=xxx; Path=/; HttpOnly; SameSite=Lax

# 后续请求
Cookie: tradingagents_session=xxx
```

---

#### 2. CORS 配置问题

**问题**：后端 CORS 配置不允许发送 Cookie

**解决方案**：

```python
# app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,  # 🔥 必须设置为 True
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
```

**验证方法**：

检查响应头中是否有：
```
Access-Control-Allow-Credentials: true
Access-Control-Allow-Origin: http://localhost:5173
```

---

#### 3. Session 配置问题

**问题**：SessionMiddleware 配置错误

**检查清单**：

```python
# app/main.py
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.JWT_SECRET,  # ✅ 确保密钥存在
    session_cookie="tradingagents_session",  # ✅ Cookie 名称
    max_age=3600,  # ✅ 过期时间（秒）
    same_site="lax",  # ✅ CSRF 保护
    https_only=False if settings.DEBUG else True,  # ✅ 开发环境设为 False
)
```

**常见错误**：

- ❌ `https_only=True` 但使用 HTTP（开发环境）
- ❌ `same_site="strict"` 导致跨域请求无法发送 Cookie
- ❌ `secret_key` 为空或太短

---

#### 4. 前端路由守卫问题

**问题**：路由守卫检查认证状态时，Session Cookie 还未生效

**解决方案**：

确保登录后等待认证状态更新：

```javascript
// frontend/src/views/Auth/Login.vue
const handleLogin = async () => {
  const success = await authStore.login({
    username: loginForm.username,
    password: loginForm.password
  })

  if (success) {
    // ✅ 等待认证状态更新
    await authStore.checkAuthStatus()
    
    // 跳转到仪表板
    const redirectPath = authStore.getAndClearRedirectPath()
    router.push(redirectPath)
  }
}
```

---

#### 5. Token 和 Session 不一致

**问题**：JWT Token 有效，但 Session 无效（或反之）

**调试方法**：

```javascript
// 在浏览器控制台执行
console.log('Token:', localStorage.getItem('auth-token'))
console.log('Cookies:', document.cookie)
console.log('isAuthenticated:', authStore.isAuthenticated)
```

**解决方案**：

清除所有认证信息，重新登录：

```javascript
// 浏览器控制台
localStorage.clear()
document.cookie.split(";").forEach(c => {
  document.cookie = c.replace(/^ +/, "").replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/")
})
location.reload()
```

---

## 🧪 测试工具

### 1. HTML 测试页面

打开 `tests/test_cookie_auth.html` 在浏览器中测试：

```bash
# 启动后端
python app/main.py

# 在浏览器中打开
http://localhost:8000/tests/test_cookie_auth.html
```

测试步骤：
1. 点击"登录"按钮
2. 检查是否返回 Token 和设置 Cookie
3. 点击"使用 Cookie 认证"（不带 Authorization header）
4. 检查是否认证成功

---

### 2. Python 测试脚本

```bash
python tests\test_hybrid_auth.py
```

---

### 3. 浏览器开发者工具

**检查 Cookie**：

1. F12 打开开发者工具
2. Application 标签 → Cookies
3. 查看 `tradingagents_session`

**检查请求**：

1. Network 标签
2. 登录后查看 `/api/auth/me` 请求
3. Request Headers 中应该有 `Cookie: tradingagents_session=xxx`

---

## 📝 常见问题 FAQ

### Q1: 为什么登录后 Cookie 没有设置？

**A**: 检查以下几点：
1. ✅ Axios 设置了 `withCredentials: true`
2. ✅ 后端 CORS 设置了 `allow_credentials=True`
3. ✅ SessionMiddleware 已添加
4. ✅ 开发环境 `https_only=False`

---

### Q2: 为什么 Cookie 设置了但没有发送？

**A**: 检查：
1. ✅ Axios 设置了 `withCredentials: true`
2. ✅ `same_site` 设置为 `"lax"` 或 `"none"`
3. ✅ 前后端域名一致（或正确配置 CORS）

---

### Q3: 为什么刷新页面后就退出登录了？

**A**: 可能原因：
1. ❌ Cookie 过期时间太短
2. ❌ Session 存储有问题
3. ❌ 前端没有正确保存 Token 到 localStorage

---

### Q4: 如何查看 Session 是否有效？

**A**: 在后端日志中查看：

```
✅ Session Cookie 已设置: user_id=xxx
✅ Session 认证成功，用户: admin
```

或者在 MongoDB 中查看 `user_sessions` 集合。

---

---

## 🔴 问题 2：刷新 Token 失败（401 错误）

### 症状
- 登录成功后一段时间
- 自动刷新 token 时返回 401
- 用户被强制退出登录

### 错误日志

```
❌ 验证会话失败: '_asyncio.Future' object is not subscriptable
❌ Refresh token 的 session 无效
POST /api/auth/refresh - 状态: 401
```

### 原因分析

**SessionService 使用了同步的 MongoDB 操作，但在异步上下文中被调用**

- `SessionService` 使用 `find_one()`, `insert_one()` 等同步方法
- 但在异步路由处理函数中被调用
- 导致 `'_asyncio.Future' object is not subscriptable` 错误

### 解决方案

**修改 `get_session_service()` 使用同步的数据库连接**：

```python
# app/services/session_service.py

def get_session_service(db: Optional[Database] = None) -> SessionService:
    """
    获取 SessionService 单例

    注意：SessionService 使用同步的 MongoDB 操作，
    因此需要使用 get_mongo_db_sync() 而不是 get_mongo_db()
    """
    global _session_service

    if _session_service is None:
        if db is None:
            from app.core.database import get_mongo_db_sync
            db = get_mongo_db_sync()  # 🔥 使用同步的数据库连接

        _session_service = SessionService(db)

    return _session_service
```

### 验证修复

1. **重启后端服务**
2. **登录并等待 token 自动刷新**（约 50 分钟后）
3. **检查日志**：应该看到 `✅ Token刷新成功`

---

**最后更新**: 2026-01-06
**版本**: v1.0.1

