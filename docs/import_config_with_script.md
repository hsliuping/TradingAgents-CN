# 使用 Python 脚本导入配置数据

## 📋 概述

本文档说明如何使用 Python 脚本导入配置数据并创建默认管理员用户，适用于在新服务器上快速部署演示系统。

---

## 🎯 两个脚本

### 1. `import_config_and_create_user.py` - 完整导入脚本

**功能**：
- ✅ 导入配置数据（从导出的 JSON 文件）
- ✅ 创建默认管理员用户（admin/admin123）
- ✅ 支持选择性导入集合
- ✅ 支持覆盖或增量模式

**适用场景**：
- 在新服务器上部署演示系统
- 从旧系统迁移配置数据
- 批量导入多个集合

### 2. `create_default_admin.py` - 创建默认用户脚本

**功能**：
- ✅ 创建默认管理员用户
- ✅ 支持自定义用户名和密码
- ✅ 列出所有现有用户

**适用场景**：
- 全新部署，只需要创建管理员
- 忘记管理员密码，重新创建
- 创建额外的管理员账号

---

## 🚀 使用方法

### 方法 1：导入配置数据 + 创建默认用户

#### 步骤 1：导出配置数据（在原服务器）

使用前端界面导出配置数据：
1. 登录系统
2. 进入：`系统管理` → `数据库管理`
3. 选择：`配置数据（用于演示系统）`
4. 导出格式：`JSON`
5. 下载文件：`database_export_config_2025-10-16.json`

> **🔒 脱敏说明**：选择"配置数据（用于演示系统）"导出时，系统会自动进行脱敏处理：
> - ✅ 清空所有敏感字段（api_key、api_secret、password、token 等）
> - ✅ users 集合只导出结构，不导出实际用户数据
> - ✅ 导出的文件可以安全地用于演示、分享或公开发布
> - ⚠️ 导入后需要重新配置 API 密钥和创建用户

#### 步骤 2：传输文件到新服务器

```bash
# 使用 scp
scp database_export_config_2025-10-16.json user@new-server:/path/to/TradingAgents-CN/

# 或使用其他方式（FTP、云存储等）
```

#### 步骤 3：在新服务器上运行导入脚本

```bash
# 进入项目目录
cd /path/to/TradingAgents-CN

# 激活虚拟环境（如果使用）
source .venv/bin/activate  # Linux/Mac
.\.venv\Scripts\activate   # Windows

# 运行导入脚本
python scripts/import_config_and_create_user.py database_export_config_2025-10-16.json
```

**输出示例**：
```
================================================================================
📦 导入配置数据并创建默认用户
================================================================================

🔌 连接到 MongoDB...
✅ MongoDB 连接成功

📂 加载导出文件: database_export_config_2025-10-16.json
✅ 文件加载成功
   导出时间: 2025-10-16T10:30:00
   导出格式: json
   集合数量: 9

📋 准备导入 9 个集合:
   - system_configs: 1 个文档
   - users: 3 个文档
   - llm_providers: 5 个文档
   - market_categories: 10 个文档
   - user_tags: 8 个文档
   - datasource_groupings: 3 个文档
   - platform_configs: 1 个文档
   - user_configs: 2 个文档
   - model_catalog: 15 个文档

🚀 开始导入...
   模式: 增量

   导入 system_configs...
      ✅ 插入 1 个，跳过 0 个
   导入 users...
      ✅ 插入 3 个，跳过 0 个
   ...

📊 导入统计:
   插入: 48 个文档
   跳过: 0 个文档

👤 创建默认管理员用户...
✅ 默认管理员用户创建成功
   用户名: admin
   密码: admin123
   邮箱: admin@tradingagents.cn
   角色: 管理员

================================================================================
✅ 操作完成！
================================================================================

🔐 登录信息:
   用户名: admin
   密码: admin123

📝 后续步骤:
   1. 重启后端服务: docker restart tradingagents-backend
   2. 访问前端并使用默认账号登录
   3. 检查系统配置是否正确加载
```

#### 步骤 4：重启后端服务

```bash
docker restart tradingagents-backend
```

#### 步骤 5：验证

1. 访问前端：`http://new-server:3000`
2. 使用默认账号登录：
   - 用户名：`admin`
   - 密码：`admin123`
3. 检查系统配置页面，确认 LLM 配置已导入

---

### 方法 2：只创建默认管理员用户

如果您只需要创建默认管理员用户（不导入配置数据）：

```bash
# 创建默认管理员（admin/admin123）
python scripts/create_default_admin.py
```

**输出示例**：
```
================================================================================
👤 创建默认管理员用户
================================================================================

🔌 连接到 MongoDB...
✅ MongoDB 连接成功

✅ 管理员用户创建成功
   用户名: admin
   密码: admin123
   邮箱: admin@tradingagents.cn
   角色: 管理员
   配额: 10000 次/天
   并发: 10 个

📋 当前用户列表 (1 个):
用户名          邮箱                           角色       状态       创建时间
------------------------------------------------------------------------------------------
admin           admin@tradingagents.cn         管理员     激活       2025-10-16 10:30

================================================================================
✅ 操作完成！
================================================================================

🔐 登录信息:
   用户名: admin
   密码: admin123

📝 后续步骤:
   1. 访问前端并使用上述账号登录
   2. 建议登录后立即修改密码
```

---

## 📖 高级用法

### 1. 覆盖已存在的数据

```bash
# 覆盖模式：删除现有数据后导入
python scripts/import_config_and_create_user.py export.json --overwrite
```

⚠️ **警告**：覆盖模式会删除新服务器上的同名集合，请谨慎使用！

### 2. 只导入指定的集合

```bash
# 只导入系统配置和用户数据
python scripts/import_config_and_create_user.py export.json --collections system_configs users
```

### 3. 只导入数据，不创建默认用户

```bash
# 跳过创建默认用户
python scripts/import_config_and_create_user.py export.json --skip-user
```

### 4. 只创建默认用户，不导入数据

```bash
# 只创建默认用户
python scripts/import_config_and_create_user.py --create-user-only
```

### 5. 创建自定义管理员

```bash
# 创建自定义管理员
python scripts/create_default_admin.py --username myuser --password mypass123 --email myuser@example.com
```

### 6. 覆盖已存在的用户

```bash
# 覆盖已存在的 admin 用户
python scripts/create_default_admin.py --overwrite
```

### 7. 列出所有用户

```bash
# 列出所有用户
python scripts/create_default_admin.py --list
```

---

## 🔧 配置说明

### MongoDB 连接配置

脚本默认使用以下连接配置：

```python
MONGO_URI = "mongodb://admin:tradingagents123@localhost:27017/tradingagents?authSource=admin"
DB_NAME = "tradingagents"
```

如果您的 MongoDB 配置不同，请修改脚本中的配置：

```python
# 修改 scripts/import_config_and_create_user.py
# 或 scripts/create_default_admin.py

MONGO_URI = "mongodb://your_user:your_pass@your_host:27017/your_db?authSource=admin"
DB_NAME = "your_db"
```

### 默认管理员配置

脚本默认创建以下管理员用户：

```python
DEFAULT_ADMIN = {
    "username": "admin",
    "password": "admin123",
    "email": "admin@tradingagents.cn"
}
```

用户属性：
- ✅ 管理员权限（`is_admin: true`）
- ✅ 已激活（`is_active: true`）
- ✅ 已验证（`is_verified: true`）
- ✅ 每日配额：10000 次
- ✅ 并发限制：10 个

---

## ⚠️ 注意事项

### 1. MongoDB 必须正在运行

确保 MongoDB 容器正在运行：

```bash
# 检查 MongoDB 状态
docker ps | grep mongodb

# 如果未运行，启动 MongoDB
docker start tradingagents-mongodb
```

### 2. 密码哈希算法

脚本使用 **SHA256** 哈希密码，与系统保持一致：

```python
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()
```

### 3. 数据格式转换

脚本会自动转换以下数据类型：
- ✅ ObjectId（`_id` 字段）
- ✅ 日期时间（`*_at` 字段）
- ✅ 嵌套文档和数组

### 4. 增量 vs 覆盖模式

| 模式 | 行为 | 适用场景 |
|------|------|---------|
| **增量**（默认） | 跳过已存在的文档 | 首次导入、追加数据 |
| **覆盖**（`--overwrite`） | 删除现有数据后导入 | 完全替换、重新部署 |

### 5. 用户唯一性检查

脚本根据以下字段检查文档是否已存在：
- `_id`（如果存在）
- `username`（用户集合）
- `name`（其他集合）

---

## 🐛 故障排除

### 问题 1：MongoDB 连接失败

**错误信息**：
```
❌ 错误: MongoDB 连接失败: ...
```

**解决方案**：
```bash
# 1. 检查 MongoDB 是否运行
docker ps | grep mongodb

# 2. 检查 MongoDB 日志
docker logs tradingagents-mongodb --tail 50

# 3. 测试连接
docker exec -it tradingagents-mongodb mongo -u admin -p tradingagents123 --authenticationDatabase admin
```

### 问题 2：文件格式错误

**错误信息**：
```
❌ 错误: 文件格式不正确，缺少 export_info 或 data 字段
```

**解决方案**：
- 确保使用系统导出的 JSON 文件
- 检查文件是否完整（未损坏）
- 使用文本编辑器查看文件结构

### 问题 3：用户已存在

**错误信息**：
```
⚠️  用户 'admin' 已存在
```

**解决方案**：
```bash
# 方法 1：使用覆盖模式
python scripts/create_default_admin.py --overwrite

# 方法 2：创建不同的用户名
python scripts/create_default_admin.py --username admin2 --password admin123

# 方法 3：手动删除用户
docker exec -it tradingagents-mongodb mongo tradingagents \
  -u admin -p tradingagents123 --authenticationDatabase admin \
  --eval "db.users.deleteOne({username: 'admin'})"
```

### 问题 4：导入后配置不生效

**解决方案**：
```bash
# 1. 重启后端服务
docker restart tradingagents-backend

# 2. 检查后端日志
docker logs tradingagents-backend --tail 100

# 3. 验证数据是否导入
docker exec -it tradingagents-mongodb mongo tradingagents \
  -u admin -p tradingagents123 --authenticationDatabase admin \
  --eval "db.system_configs.countDocuments()"
```

---

## 📚 相关文档

- [导出配置数据用于演示系统](./export_config_for_demo.md)
- [数据库管理](./database_management.md)
- [用户管理](./user_management.md)

---

## 💡 最佳实践

### 1. 导入前备份

```bash
# 在新服务器上导入前，先备份现有数据
docker exec tradingagents-mongodb mongodump \
  -u admin -p tradingagents123 --authenticationDatabase admin \
  -d tradingagents -o /tmp/backup

docker cp tradingagents-mongodb:/tmp/backup ./backup_before_import
```

### 2. 验证导入结果

```bash
# 检查集合数量
docker exec -it tradingagents-mongodb mongo tradingagents \
  -u admin -p tradingagents123 --authenticationDatabase admin \
  --eval "db.getCollectionNames().length"

# 检查 LLM 配置
docker exec -it tradingagents-mongodb mongo tradingagents \
  -u admin -p tradingagents123 --authenticationDatabase admin \
  --eval "var config = db.system_configs.findOne({is_active: true}); print('LLM 数量: ' + config.llm_configs.filter(c => c.enabled).length);"
```

### 3. 修改默认密码

导入后，建议立即修改默认管理员密码：
1. 登录系统
2. 进入：`个人中心` → `修改密码`
3. 输入新密码并保存

---

## 🎉 总结

使用 Python 脚本导入配置数据的优势：

✅ **自动化**：无需手动操作前端界面  
✅ **批量处理**：一次导入多个集合  
✅ **灵活控制**：支持增量/覆盖模式  
✅ **默认用户**：自动创建管理员账号  
✅ **易于集成**：可集成到部署脚本中  

现在您可以使用 Python 脚本快速在新服务器上部署演示系统了！🚀

