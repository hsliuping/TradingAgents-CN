# 离线许可证缓存机制

## 📋 概述

TradingAgents-CN Pro 实现了**7天离线许可证缓存**机制，确保用户在网络不稳定或无法连接授权服务器时，仍然可以继续使用已授权的功能。

---

## 🎯 功能特性

### 1. 双层缓存架构

```
在线验证成功
    ↓
内存缓存（1小时） + 持久化缓存（7天）
    ↓
网络断开时自动切换到离线模式
    ↓
使用持久化缓存（7天有效期）
```

### 2. 机器绑定

- **硬件指纹**：基于 MAC 地址、CPU 架构、操作系统、处理器信息生成唯一机器ID
- **防止复制**：缓存绑定机器ID，复制到其他机器无效
- **SHA256 加密**：机器ID使用 SHA256 加密存储

### 3. 安全性

- **Token 哈希**：不直接存储 Token，使用 SHA256 哈希
- **过期自动清理**：MongoDB TTL 索引自动删除过期缓存
- **验证服务器硬编码**：防止用户搭建假服务器绕过验证

---

## 🔧 技术实现

### 数据库集合：`license_cache`

```javascript
{
  "_id": ObjectId("..."),
  "token_hash": "sha256(token)",           // Token 的 SHA256 哈希
  "machine_id": "sha256(hardware_info)",   // 机器ID（硬件指纹）
  "email": "user@example.com",             // 用户邮箱
  "plan": "pro",                           // 计划类型
  "features": [],                          // 功能列表
  "device_registered": true,               // 设备是否已注册
  "verified_at": ISODate("..."),           // 验证时间
  "trial_end_at": "2026-01-15T00:00:00",   // 试用到期时间
  "pro_expire_at": "2027-01-01T00:00:00",  // PRO 到期时间
  "cache_expires_at": ISODate("..."),      // 缓存过期时间（7天后）
  "updated_at": ISODate("...")             // 更新时间
}
```

### 索引

```python
# 1. 复合唯一索引（token_hash + machine_id）
db.license_cache.create_index(
    [("token_hash", 1), ("machine_id", 1)],
    unique=True
)

# 2. TTL 索引（自动清理过期缓存）
db.license_cache.create_index(
    [("cache_expires_at", 1)],
    expireAfterSeconds=0
)

# 3. 更新时间索引
db.license_cache.create_index(
    [("updated_at", -1)]
)
```

---

## 📊 工作流程

### 在线验证成功

```python
1. 用户登录 → 验证 App Token
2. 授权服务器返回授权信息
3. 保存到内存缓存（1小时）
4. 保存到持久化缓存（7天）
   - 绑定机器ID
   - 设置过期时间
```

### 离线模式

```python
1. 网络断开 → 无法连接授权服务器
2. 检查内存缓存（1小时有效）
3. 检查持久化缓存（7天有效）
   - 验证机器ID是否匹配
   - 验证缓存是否过期
4. 返回缓存的授权信息
   - 标记为离线模式
   - 显示剩余天数
```

---

## 🎨 用户体验

### 在线模式

```
✅ Token 验证成功: user@example.com, plan=pro
```

### 离线模式（有缓存）

```
⚠️ 无法连接授权服务器，当前使用离线缓存（高级学员资格，剩余 5 天）
```

### 离线模式（无缓存）

```
⚠️ 无法连接授权服务器，当前使用离线模式，部分功能可能受限
```

---

## 🛠️ 管理命令

### 创建索引

```bash
python scripts/create_license_cache_indexes.py
```

### 清理过期缓存（手动）

```python
from app.core.database import get_mongo_db
from datetime import datetime

db = get_mongo_db()
result = await db.license_cache.delete_many({
    "cache_expires_at": {"$lt": datetime.now()}
})
print(f"清理了 {result.deleted_count} 条过期缓存")
```

### 查看缓存状态

```python
from app.services.license_service import get_license_service

service = get_license_service()
print(f"机器ID: {service._machine_id[:16]}...")
```

---

## ⚠️ 注意事项

1. **首次使用需要在线验证**：必须至少成功验证一次才能使用离线模式
2. **7天后必须重新验证**：离线缓存有效期为7天，过期后需要重新连接授权服务器
3. **更换机器需要重新验证**：缓存绑定机器ID，更换机器后需要重新在线验证
4. **不要删除数据库**：删除 `license_cache` 集合会导致离线模式失效

---

## 🔐 安全考虑

1. **Token 不直接存储**：使用 SHA256 哈希，即使数据库泄露也无法获取原始 Token
2. **机器绑定**：防止用户复制缓存到其他机器使用
3. **验证服务器硬编码**：防止用户修改环境变量绕过验证
4. **自动过期**：MongoDB TTL 索引自动清理过期缓存，减少数据库占用

---

## 📝 相关文件

- `app/services/license_service.py` - 许可证服务实现
- `scripts/create_license_cache_indexes.py` - 创建索引脚本
- `frontend/src/components/Layout/LicenseAlert.vue` - 前端提示组件
- `frontend/src/stores/license.ts` - 前端许可证状态管理

---

**最后更新**: 2026-01-09  
**版本**: v1.0.1

