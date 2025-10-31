# 认证系统迁移指南

## 迁移完成

✅ 认证系统已成功从配置文件迁移到数据库！

## 主要变化

### 1. 用户数据存储
- **之前**: 存储在 `config/admin_password.json` 和 `web/config/users.json`
- **现在**: 存储在 MongoDB 数据库的 `users` 集合中

### 2. 密码安全性
- **之前**: 明文存储（后端）或 SHA-256 哈希（Web）
- **现在**: 统一使用 SHA-256 哈希存储

### 3. API 端点
- **新的认证 API**: `/api/auth-db/` 前缀
- **支持的操作**:
  - 登录: `POST /api/auth-db/login`
  - 刷新令牌: `POST /api/auth-db/refresh`
  - 修改密码: `POST /api/auth-db/change-password`
  - 重置密码: `POST /api/auth-db/reset-password` (管理员)
  - 创建用户: `POST /api/auth-db/create-user` (管理员)
  - 用户列表: `GET /api/auth-db/users` (管理员)

## 使用新的认证系统

### 1. 更新前端配置
将前端的认证 API 端点从 `/api/auth/` 更改为 `/api/auth-db/`

### 2. 管理用户
现在可以通过 API 动态创建、管理用户，不再需要手动编辑配置文件。

### 3. 密码管理
- 用户可以通过 API 修改自己的密码
- 管理员可以重置任何用户的密码

## 备份文件
原配置文件已备份到 `config/backup/` 目录，包含时间戳。

## 安全建议
1. 立即修改默认密码
2. 为其他用户设置强密码
3. 定期备份数据库
4. 考虑启用更强的密码哈希算法（如 bcrypt）

## 回滚方案
如果需要回滚到原系统：
1. 停止使用新的 `/api/auth-db/` 端点
2. 从 `config/backup/` 恢复配置文件
3. 重新使用原有的 `/api/auth/` 端点
