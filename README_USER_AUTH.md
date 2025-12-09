# 用户注册和权限系统实现文档

## 概述

本系统实现了一套完整的用户注册、登录和权限控制系统，支持：

- ✅ 用户注册功能（自动登录）
- ✅ 基于角色的权限控制（超级权限 vs 普通权限）
- ✅ VIP等级预留字段（未来扩展）
- ✅ 完整的测试覆盖

## 系统架构

### 后端架构 (FastAPI)

```
app/
├── models/user.py          # 用户数据模型（新增vip_level字段）
├── routers/auth_db.py      # 认证路由（新增注册接口）
├── services/user_service.py # 用户服务（新增邮箱检查等方法）
└── core/permissions.py     # 权限控制核心逻辑
```

### 前端架构 (Vue 3)

```
frontend/src/
├── views/Auth/Login.vue     # 登录注册页面（添加注册Tab）
├── stores/auth.ts          # 认证状态管理（支持注册自动登录）
└── router/index.ts         # 路由配置（添加权限控制）
```

## 核心功能

### 1. 用户注册

**后端接口**: `POST /api/auth/register`

**功能特点**:
- 用户名唯一性验证
- 邮箱格式验证和重复检查
- 密码强度要求（至少6位）
- 注册成功后自动登录并返回JWT token

**请求示例**:
```json
{
  "username": "newuser",
  "email": "user@example.com",
  "password": "password123"
}
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "expires_in": 3600,
    "user": {
      "id": "507f191e810c19729de860ea",
      "username": "newuser",
      "email": "user@example.com",
      "is_admin": false,
      "vip_level": 0
    }
  },
  "message": "注册成功，已自动登录"
}
```

### 2. 权限控制

**权限级别**:
- **超级权限**: `is_admin = True` → 可访问所有页面
- **普通权限**: `is_admin = False` → 受限访问

**受控页面**:
- 系统设置中的"系统设置"部分
- 系统管理相关页面：配置管理、数据库管理、操作日志等

**实现方式**:
- 后端：JWT token + 角色检查
- 前端：路由守卫 + 动态菜单控制

### 3. VIP等级系统

**字段设计**:
```python
# User模型中新增字段
vip_level: int = Field(default=0, description="VIP等级：0=普通用户，1=VIP1，2=VIP2，3=VIP3")
```

**当前状态**: 预留字段，不影响现有逻辑，为未来功能扩展做准备。

## 数据库变更

### MongoDB users集合

新增字段：
```json
{
  "username": "string",
  "email": "string",
  "hashed_password": "string",
  "is_active": true,
  "is_admin": false,
  "vip_level": 0,  // 新增字段
  "created_at": "datetime",
  // ... 其他现有字段
}
```

## 前端变更

### 登录页面改造

**新增功能**:
- Tab切换式界面（登录/注册）
- 注册表单验证
- 密码确认检查
- 自动登录处理

**表单验证规则**:
```typescript
const registerRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度为3-20位', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_]+$/, message: '用户名只能包含字母、数字和下划线', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: (rule, value, callback) => {
      if (value !== registerForm.password) {
        callback(new Error('两次输入密码不一致'))
      } else {
        callback()
      }
    }, trigger: 'blur' }
  ]
}
```

### 路由权限控制

**实现逻辑**:
```typescript
// 路由守卫中的权限检查
router.beforeEach(async (to, from, next) => {
  // 管理员页面权限检查
  const systemAdminRoutes = ['ConfigManagement', 'DatabaseManagement', 'OperationLogs']

  if (systemAdminRoutes.includes(to.name) && !authStore.isAdmin) {
    ElMessage.warning('您没有权限访问此页面')
    next('/dashboard')
    return
  }

  // 系统设置页面权限控制
  if (to.path === '/settings' && to.query.tab === 'system' && !authStore.isAdmin) {
    ElMessage.warning('您没有权限访问系统设置')
    next('/settings?tab=profile')
    return
  }
})
```

## 测试覆盖

### 后端测试

1. **单元测试** (`tests/test_user_registration.py`)
   - 用户注册成功/失败场景
   - 重复用户名/邮箱检查
   - 表单验证测试
   - 权限验证测试

2. **API测试** (`tests/test_auth_api.py`)
   - 认证接口状态测试
   - Token验证测试
   - 完整认证流程测试

3. **集成测试** (`tests/test_integration.py`)
   - 完整用户生命周期测试
   - 并发注册测试
   - 数据持久化测试
   - 错误处理测试

### 前端测试

1. **单元测试** (`frontend/tests/unit/auth.test.ts`)
   - Auth Store功能测试
   - 表单验证测试
   - 权限逻辑测试

2. **路由测试** (`frontend/tests/unit/router.test.ts`)
   - 路由守卫测试
   - 权限重定向测试

3. **端到端测试** (`frontend/tests/e2e/auth.spec.ts`)
   - 完整注册登录流程
   - UI交互测试
   - 权限访问测试

## 运行测试

### 快速测试
```bash
# 运行所有测试
python run_tests.py

# 只运行后端测试
python run_tests.py --frontend none

# 只运行前端测试
python run_tests.py --backend none

# 运行特定类型测试
python run_tests.py --backend unit
python run_tests.py --frontend e2e
```

### 手动运行
```bash
# 后端测试
pytest tests/test_user_registration.py -v
pytest tests/test_auth_api.py -v
pytest tests/test_integration.py -v

# 前端测试
cd frontend
npm run test:unit
npm run test:e2e
```

## 部署注意事项

1. **数据库迁移**: 现有用户需要添加`vip_level`字段，默认值为0
2. **环境变量**: 确保MongoDB连接配置正确
3. **JWT密钥**: 确保JWT密钥设置合理
4. **测试数据**: 部署前清理测试数据

## 未来扩展计划

### VIP等级功能
1. 根据VIP等级控制功能访问
2. 不同等级的配额限制
3. VIP升级流程
4. 权限细化管理

### 增强功能
1. 邮箱验证
2. 密码重置
3. 社交登录
4. 多因素认证

## 维护说明

- 定期运行测试确保功能正常
- 监控用户注册和登录情况
- 根据业务需求调整权限配置
- 及时更新测试用例

## 技术栈

- **后端**: FastAPI, MongoDB, JWT, Pydantic
- **前端**: Vue 3, TypeScript, Element Plus, Pinia
- **测试**: Pytest, Vitest, Playwright
- **工具**: Docker, Git, Python 3.9+