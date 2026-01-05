# 混合认证方案

## 📋 概述

TradingAgents-CN Pro 使用**混合认证方案**，同时支持两种认证方式：

1. **Session Cookie**（Web 前端）- 类似 Flask/Django
2. **JWT Token**（API 调用）- 适合移动端、第三方调用

---

## 🎯 设计目标

- ✅ **Web 前端**：自动管理 Cookie，用户无需手动处理 Token
- ✅ **API 调用**：使用 JWT Token，灵活、跨域友好
- ✅ **安全性**：修改密码/退出登录时，两种方式都失效
- ✅ **兼容性**：同时支持两种方式，互不干扰

---

## 🔧 技术实现

### 1. Session Cookie（Web 前端）

**使用 Starlette SessionMiddleware**：

```python
from starlette.middleware.sessions import SessionMiddleware

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.JWT_SECRET,
    session_cookie="tradingagents_session",
    max_age=3600,  # 1 小时
    same_site="lax",
    https_only=False if settings.DEBUG else True,
)
```

**登录时设置 Session**：

```python
request.session["user_id"] = str(user.id)
request.session["username"] = user.username
request.session["is_admin"] = user.is_admin
```

**退出登录时清除 Session**：

```python
request.session.clear()
```

---

### 2. JWT Token（API 调用）

**生成 Token**：

```python
from app.services.auth_service import AuthService

token = AuthService.create_access_token(
    sub=user.username,
    session_id=session_id  # 关联到 session
)
```

**验证 Token**：

```python
token_data = AuthService.verify_token(token)
if token_data and token_data.session_id:
    session = session_service.verify_session(token_data.session_id)
```

---

### 3. 混合认证中间件

**优先级**：JWT Token > Session Cookie

```python
async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None)
) -> dict:
    # 方式 1: JWT Token 认证（优先）
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        token_data = AuthService.verify_token(token)
        if token_data:
            # 验证 session
            if token_data.session_id:
                session = session_service.verify_session(token_data.session_id)
                if session:
                    return user
    
    # 方式 2: Session Cookie 认证（回退）
    user_id = request.session.get("user_id")
    if user_id:
        user = await user_service.get_user_by_id(user_id)
        if user and user.is_active:
            return user
    
    # 两种方式都失败
    raise HTTPException(status_code=401, detail="未登录或登录已过期")
```

---

## 📝 使用场景

### 场景 1: Web 前端（Vue.js）

**重要配置**：

```javascript
// 必须设置 withCredentials: true 才能发送和接收 Cookie
const instance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  withCredentials: true,  // 🔥 重要：允许发送和接收 Cookie
  headers: {
    'Content-Type': 'application/json'
  }
})
```

**登录**：

```javascript
// 登录时不需要手动保存 token
const response = await axios.post('/api/auth/login', {
  username: 'admin',
  password: 'admin123'
});

// Session Cookie 自动设置，无需手动处理
console.log('登录成功');
```

**调用 API**：

```javascript
// 不需要手动添加 Authorization header
// Session Cookie 会自动发送
const response = await axios.get('/api/auth/me');
console.log(response.data);
```

**退出登录**：

```javascript
// Session Cookie 自动清除
await axios.post('/api/auth/logout');
```

---

### 场景 2: API 调用（移动端、第三方）

**登录**：

```python
import httpx

response = httpx.post('http://localhost:8000/api/auth/login', json={
    'username': 'admin',
    'password': 'admin123'
})

data = response.json()
access_token = data['data']['access_token']
```

**调用 API**：

```python
response = httpx.get(
    'http://localhost:8000/api/auth/me',
    headers={'Authorization': f'Bearer {access_token}'}
)
```

**退出登录**：

```python
httpx.post(
    'http://localhost:8000/api/auth/logout',
    headers={'Authorization': f'Bearer {access_token}'}
)
```

---

## 🔐 安全特性

### 1. 修改密码后强制重新登录

```python
# 清除 Session Cookie
request.session.clear()

# 撤销所有 JWT Session
session_service.revoke_all_user_sessions(user_id)
```

### 2. 退出登录后立即失效

```python
# 清除 Session Cookie
request.session.clear()

# 撤销当前 JWT Session
session_service.revoke_session(session_id)
```

### 3. Token 泄露后可撤销

```python
# 管理员可以撤销用户的所有 session
session_service.revoke_all_user_sessions(user_id)
```

---

## 🧪 测试

运行测试脚本：

```powershell
python tests\test_hybrid_auth.py
```

测试内容：
- ✅ JWT Token 认证
- ✅ Session Cookie 认证
- ✅ 退出登录后两种方式都失效
- ✅ 修改密码后两种方式都失效

---

**最后更新**: 2026-01-06  
**版本**: v1.0.1

