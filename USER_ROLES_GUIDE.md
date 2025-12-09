# 用户角色权限管理指南

## 功能概述

现在系统支持两种用户角色：
- **普通用户 (user)**：只能访问个人设置功能
- **管理员 (admin)**：可以访问所有设置功能，包括系统设置和系统管理

## 权限控制机制

### 1. 后端权限控制

#### 用户模型
- 用户表包含 `is_admin` 字段（布尔值）
- 新注册用户默认 `is_admin = false`（普通用户）
- 管理员用户 `is_admin = true`

#### API权限检查
- 所有管理员API都通过 `get_current_user()` 依赖检查 `is_admin` 字段
- 非管理员用户访问管理员API时返回 403 Forbidden

### 2. 前端权限控制

#### Auth Store
- `isAdmin` 计算属性：基于用户的 `is_admin` 字段判断
- 登录时自动设置正确的角色和权限信息

#### 设置页面权限
- **普通用户**：只能看到个人设置标签（通用设置、外观设置、分析偏好、通知设置、安全设置）
- **管理员用户**：可以看到所有设置，包括：
  - 个人设置
  - 系统设置（系统配置、使用统计、缓存管理）
  - 系统管理（数据库管理、操作日志、多数据源同步）

## 使用方法

### 1. 创建管理员用户

#### 方法一：使用服务函数
```python
from app.services.user_service import user_service

# 创建管理员用户
admin_user = await user_service.create_admin_user(
    username="admin",
    password="admin123",
    email="admin@example.com"
)
```

#### 方法二：通过API创建（需要现有管理员权限）
```bash
curl -X POST "http://localhost:8000/auth/create-user" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newadmin",
    "email": "newadmin@example.com",
    "password": "password123",
    "is_admin": true
  }'
```

### 2. 创建普通用户

#### 通过注册接口
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "normaluser",
    "email": "user@example.com",
    "password": "password123"
  }'
```

#### 管理员创建普通用户
```bash
curl -X POST "http://localhost:8000/auth/create-user" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com",
    "password": "password123",
    "is_admin": false
  }'
```

## 测试验证

运行测试脚本验证角色功能：

```bash
python test_user_roles.py
```

## 界面表现

### 普通用户界面
- 设置页面只显示个人设置相关标签
- 不显示"系统配置"和"系统管理"两个特殊区域
- 如果尝试直接访问管理员URL，会自动重定向到个人设置页面

### 管理员界面
- 设置页面显示完整的导航菜单
- 包含分隔线和管理员专用菜单项
- 可以访问所有系统配置和管理功能

## 安全考虑

1. **默认安全**：新注册用户默认为普通用户，需要手动提升权限
2. **双重检查**：前后端都有权限验证，确保安全性
3. **Token验证**：管理员操作需要有效的管理员token
4. **审计日志**：所有操作都有详细的日志记录

## 管理员专属功能

### 系统配置
- LLM配置管理
- 数据源配置
- 使用统计查看
- 缓存管理

### 系统管理
- 数据库管理
- 操作日志查看
- 多数据源同步
- 用户管理（创建、禁用、激活用户）