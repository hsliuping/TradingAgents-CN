# Docker 自动初始化功能说明

## 📋 功能概述

Docker 版本现在支持**自动数据库初始化**，与绿色版（`start_all.ps1`）保持一致的行为。

## 🚀 工作原理

1. **首次启动检测**：容器启动时检查 `/app/runtime/.config_imported` 标记文件
2. **自动初始化**：如果标记文件不存在，自动执行以下操作：
   - 等待 MongoDB 和 Redis 服务就绪
   - 查找最新的配置文件（`install/database_export_config_*.json`）
   - 执行 `scripts/import_config_and_create_user.py` 导入配置数据
   - 创建默认管理员用户（admin/admin123）
   - 创建标记文件，避免重复初始化
3. **后续启动**：如果标记文件存在，跳过初始化步骤，直接启动服务

## 📁 相关文件

- **Entrypoint 脚本**: `docker/scripts/docker-entrypoint.sh`
- **Dockerfile**: `Dockerfile.backend` 和 `docker/Dockerfile.backend.compiled.ubuntu`
- **标记文件**: `runtime/.config_imported`（容器内路径：`/app/runtime/.config_imported`）

## 🔧 使用方法

### 标准 Docker Compose 部署

```bash
# 1. 启动服务（首次启动会自动初始化）
docker-compose up -d

# 2. 查看初始化日志
docker-compose logs backend | grep -i "初始化\|init\|import"

# 3. 验证初始化是否成功
docker exec -it tradingagents-backend ls -la /app/runtime/.config_imported
```

### 编译版 Docker Compose 部署

```bash
# 1. 启动服务（首次启动会自动初始化）
docker-compose -f docker/docker-compose.compiled.yml up -d

# 2. 查看初始化日志
docker-compose -f docker/docker-compose.compiled.yml logs backend | grep -i "初始化\|init\|import"
```

## 🔄 强制重新初始化

如果需要强制重新初始化（例如更新配置数据）：

```bash
# 方法1: 删除标记文件并重启容器
docker exec -it tradingagents-backend rm /app/runtime/.config_imported
docker-compose restart backend

# 方法2: 手动运行初始化脚本（带 --overwrite 参数）
docker exec -it tradingagents-backend python scripts/import_config_and_create_user.py --overwrite
```

## ⚙️ 配置说明

### 标记文件位置

- **容器内路径**: `/app/runtime/.config_imported`
- **宿主机路径**: `./runtime/.config_imported`（通过 volume 挂载）

### 配置文件查找

脚本会自动查找 `install/` 目录下最新的配置文件：
- 模式: `database_export_config_*.json`
- 选择: 按文件名排序，使用最新的文件

### 数据库连接

初始化脚本使用 Docker 内部服务名连接：
- **MongoDB**: `mongodb://admin:tradingagents123@mongodb:27017/tradingagents?authSource=admin`
- **Redis**: `redis://:tradingagents123@redis:6379`

## 🐛 故障排查

### 问题1: 初始化失败但服务仍启动

**现象**: 日志显示初始化失败，但后端服务正常启动

**原因**: Entrypoint 脚本设计为"优雅失败"，即使初始化失败也会继续启动服务

**解决**: 手动运行初始化脚本
```bash
docker exec -it tradingagents-backend python scripts/import_config_and_create_user.py
```

### 问题2: 找不到配置文件

**现象**: 日志显示 "未找到配置文件"

**原因**: `install/` 目录中没有 `database_export_config_*.json` 文件

**解决**: 
1. 确保配置文件已复制到镜像中（检查 Dockerfile 的 COPY 指令）
2. 或使用 `--create-user-only` 参数只创建用户：
   ```bash
   docker exec -it tradingagents-backend python scripts/import_config_and_create_user.py --create-user-only
   ```

### 问题3: MongoDB 连接超时

**现象**: 日志显示 "MongoDB 连接超时"

**原因**: MongoDB 容器启动较慢，或网络配置问题

**解决**: 
1. 检查 MongoDB 容器状态：`docker-compose ps mongodb`
2. 检查网络连接：`docker network inspect tradingagents-network`
3. 增加等待时间（修改 `docker-entrypoint.sh` 中的 `MAX_RETRIES`）

## 📝 与绿色版的对比

| 特性 | 绿色版 (start_all.ps1) | Docker 版 (docker-entrypoint.sh) |
|------|----------------------|--------------------------------|
| **自动检测** | ✅ 检查标记文件 | ✅ 检查标记文件 |
| **初始化脚本** | `import_config_and_create_user.py --host` | `import_config_and_create_user.py` |
| **标记文件** | `runtime\.config_imported` | `/app/runtime/.config_imported` |
| **强制重新导入** | `-ForceImport` 参数 | 删除标记文件或手动运行 |
| **等待数据库** | 固定 3 秒 | 动态检测（最多 60 秒） |

## ✅ 验证清单

首次部署后，请验证以下项目：

- [ ] 查看后端日志，确认初始化成功
- [ ] 检查标记文件是否存在：`docker exec tradingagents-backend ls -la /app/runtime/.config_imported`
- [ ] 尝试登录系统（用户名：admin，密码：admin123）
- [ ] 验证配置数据已导入（检查系统配置、LLM 提供商等）

## 🔗 相关文档

- [Docker 部署指南](../docs/deployment/docker/docker_deployment_guide.md)
- [配置导入脚本说明](../scripts/README_import_config.md)
- [Docker 初始化脚本](../scripts/docker_deployment_init.py)
