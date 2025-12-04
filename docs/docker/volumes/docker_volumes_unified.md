# Docker 数据卷统一配置

## 📋 修改内容

### 统一的数据卷名称

所有 docker-compose 文件现在使用统一的数据卷名称：

| 数据卷用途 | 统一名称 |
|-----------|---------|
| **MongoDB 数据** | `tradingagents_mongodb_data` |
| **Redis 数据** | `tradingagents_redis_data` |

---

## 📝 修改的文件

### 1. `docker-compose.yml`

**状态**: ✅ 已经使用正确的名称，无需修改

```yaml
volumes:
  mongodb_data:
    driver: local
    name: tradingagents_mongodb_data
  redis_data:
    driver: local
    name: tradingagents_redis_data
```

---

### 2. `docker-compose.split.yml`

**状态**: ✅ 已经使用正确的名称，无需修改

```yaml
volumes:
  mongodb_data:
    driver: local
    name: tradingagents_mongodb_data
  redis_data:
    driver: local
    name: tradingagents_redis_data
```

---

### 3. `docker-compose.v1.0.0.yml`

**修改前**:
```yaml
volumes:
  mongodb_data:
    driver: local
    name: tradingagents_mongodb_data_v1  # ❌ 旧名称
  redis_data:
    driver: local
    name: tradingagents_redis_data_v1    # ❌ 旧名称
```

**修改后**:
```yaml
volumes:
  mongodb_data:
    driver: local
    name: tradingagents_mongodb_data     # ✅ 统一名称
  redis_data:
    driver: local
    name: tradingagents_redis_data       # ✅ 统一名称
```

---

### 4. `docker-compose.hub.yml`

**修改前**:
```yaml
mongodb:
  volumes:
    - tradingagents_mongodb_data_v1:/data/db  # ❌ 旧名称

redis:
  volumes:
    - tradingagents_redis_data_v1:/data       # ❌ 旧名称

volumes:
  tradingagents_mongodb_data_v1:              # ❌ 旧名称
  tradingagents_redis_data_v1:                # ❌ 旧名称
```

**修改后**:
```yaml
mongodb:
  volumes:
    - tradingagents_mongodb_data:/data/db     # ✅ 统一名称

redis:
  volumes:
    - tradingagents_redis_data:/data          # ✅ 统一名称

volumes:
  tradingagents_mongodb_data:                 # ✅ 统一名称
    external: true                            # 使用外部已存在的数据卷
  tradingagents_redis_data:                   # ✅ 统一名称
    external: true                            # 使用外部已存在的数据卷
```

---

### 5. `docker-compose.hub.dev.yml`

**修改前**:
```yaml
mongodb:
  volumes:
    - tradingagents_mongodb_data_v1:/data/db  # ❌ 旧名称

redis:
  volumes:
    - tradingagents_redis_data_v1:/data       # ❌ 旧名称

volumes:
  tradingagents_mongodb_data_v1:              # ❌ 旧名称
  tradingagents_redis_data_v1:                # ❌ 旧名称
```

**修改后**:
```yaml
mongodb:
  volumes:
    - tradingagents_mongodb_data:/data/db     # ✅ 统一名称

redis:
  volumes:
    - tradingagents_redis_data:/data          # ✅ 统一名称

volumes:
  tradingagents_mongodb_data:                 # ✅ 统一名称
    external: true                            # 使用外部已存在的数据卷
  tradingagents_redis_data:                   # ✅ 统一名称
    external: true                            # 使用外部已存在的数据卷
```

---

## 🔍 `external: true` 的作用

在 `docker-compose.hub.yml` 和 `docker-compose.hub.dev.yml` 中，我们使用了 `external: true`：

```yaml
volumes:
  tradingagents_mongodb_data:
    external: true
```

**作用**：
- 告诉 Docker Compose 这个数据卷已经存在，不要创建新的
- 避免 Docker Compose 自动添加项目名称前缀（例如 `tradingagents-cn_`）
- 确保所有 docker-compose 文件使用同一个数据卷

**对比**：

| 配置 | 实际数据卷名称 |
|------|---------------|
| `name: tradingagents_mongodb_data` | `tradingagents_mongodb_data` |
| `name: tradingagents_mongodb_data` + `external: true` | `tradingagents_mongodb_data` |
| 不指定 `name` | `<项目名>_mongodb_data`（例如 `tradingagents-cn_mongodb_data`） |

---

## 🗑️ 需要清理的旧数据卷

### 旧数据卷列表

| 数据卷名称 | 状态 | 操作 |
|-----------|------|------|
| `tradingagents_mongodb_data_v1` | ⚠️ 未使用 | 🗑️ 删除 |
| `tradingagents_redis_data_v1` | ⚠️ 未使用 | 🗑️ 删除 |
| `tradingagents-cn_tradingagents_mongodb_data_v1` | ⚠️ 未使用 | 🗑️ 删除 |
| `tradingagents-cn_tradingagents_redis_data_v1` | ⚠️ 未使用 | 🗑️ 删除 |
| 匿名数据卷（10+ 个） | ⚠️ 未使用 | 🗑️ 删除 |

### 保留的数据卷

| 数据卷名称 | 状态 | 说明 |
|-----------|------|------|
| `tradingagents_mongodb_data` | ✅ 使用中 | 包含完整的配置数据（15个LLM） |
| `tradingagents_redis_data` | ✅ 使用中 | Redis 缓存数据 |

---

## 🚀 清理步骤

### 方法 1：使用自动清理脚本（推荐）

```powershell
# 运行清理脚本
.\scripts\cleanup_unused_volumes.ps1
```

脚本会：
1. 显示所有数据卷
2. 识别正在使用的数据卷
3. 列出可以删除的数据卷
4. 询问确认后删除
5. 清理匿名数据卷

---

### 方法 2：手动清理

#### 步骤 1：停止所有容器（可选）

```powershell
docker-compose down
```

#### 步骤 2：删除旧数据卷

```powershell
# 删除 _v1 后缀的数据卷
docker volume rm tradingagents_mongodb_data_v1
docker volume rm tradingagents_redis_data_v1

# 删除带项目前缀的数据卷
docker volume rm tradingagents-cn_tradingagents_mongodb_data_v1
docker volume rm tradingagents-cn_tradingagents_redis_data_v1
```

#### 步骤 3：清理匿名数据卷

```powershell
# 删除所有未使用的匿名数据卷
docker volume prune -f
```

#### 步骤 4：验证清理结果

```powershell
# 查看剩余的数据卷
docker volume ls

# 应该只看到：
# tradingagents_mongodb_data
# tradingagents_redis_data
```

#### 步骤 5：重新启动容器

```powershell
# 使用任意 docker-compose 文件启动
docker-compose up -d

# 或
docker-compose -f docker-compose.hub.yml up -d
```

---

## ✅ 验证清单

清理完成后，请验证以下内容：

- [ ] 所有 docker-compose 文件使用统一的数据卷名称
- [ ] 旧数据卷（`_v1` 后缀）已删除
- [ ] 匿名数据卷已清理
- [ ] 只保留 `tradingagents_mongodb_data` 和 `tradingagents_redis_data`
- [ ] MongoDB 容器正常运行
- [ ] Redis 容器正常运行
- [ ] 数据库包含完整数据（15个LLM配置）
- [ ] 后端服务能正常连接数据库

---

## 📊 清理前后对比

### 清理前

```
数据卷总数: 16 个
  - tradingagents_mongodb_data (有数据)
  - tradingagents_mongodb_data_v1 (空)
  - tradingagents-cn_tradingagents_mongodb_data_v1 (空)
  - tradingagents_redis_data (有数据)
  - tradingagents_redis_data_v1 (空)
  - tradingagents-cn_tradingagents_redis_data_v1 (空)
  - 10+ 个匿名数据卷
```

### 清理后

```
数据卷总数: 2 个
  - tradingagents_mongodb_data (有数据)
  - tradingagents_redis_data (有数据)
```

**节省空间**: 约 4-5 GB（取决于匿名数据卷的大小）

---

## 🔧 常见问题

### Q1: 删除数据卷后数据会丢失吗？

**A**: 只有删除 `tradingagents_mongodb_data` 和 `tradingagents_redis_data` 才会丢失数据。其他 `_v1` 后缀的数据卷是空的或包含过时数据，可以安全删除。

---

### Q2: 如果误删了重要数据卷怎么办？

**A**: 
1. 如果有备份，可以从备份恢复
2. 如果没有备份，数据将永久丢失
3. 建议在删除前先备份：
   ```powershell
   docker run --rm -v tradingagents_mongodb_data:/data -v ${PWD}:/backup alpine tar czf /backup/mongodb_backup.tar.gz /data
   ```

---

### Q3: 为什么使用 `external: true`？

**A**: 
- 避免 Docker Compose 自动添加项目名称前缀
- 确保所有 docker-compose 文件使用同一个数据卷
- 防止意外创建新的数据卷

---

### Q4: 如何查看数据卷的大小？

**A**:
```powershell
# 查看数据卷详细信息
docker volume inspect tradingagents_mongodb_data

# 查看数据卷大小（需要启动临时容器）
docker run --rm -v tradingagents_mongodb_data:/data alpine du -sh /data
```

---

## 📝 总结

| 操作 | 状态 |
|------|------|
| **统一数据卷名称** | ✅ 完成 |
| **修改 docker-compose 文件** | ✅ 完成（5个文件） |
| **创建清理脚本** | ✅ 完成 |
| **清理旧数据卷** | ⏳ 待执行 |

**下一步**：
1. 运行清理脚本：`.\scripts\cleanup_unused_volumes.ps1`
2. 验证数据卷清理结果
3. 重新启动容器并验证数据完整性

**关键点**：
- ✅ 所有 docker-compose 文件现在使用统一的数据卷名称
- ✅ 使用 `external: true` 避免创建重复数据卷
- 🗑️ 可以安全删除 `_v1` 后缀的旧数据卷
- 💾 保留 `tradingagents_mongodb_data` 和 `tradingagents_redis_data`

