# 2025-10-24 运维指南：从 Docker Hub 更新 TradingAgents‑CN 镜像（含清理数据卷）

**日期**: 2025-10-24  
**作者**: TradingAgents-CN 开发团队  
**标签**: `deployment`, `docker`, `how-to`, `maintenance`

---

## 概述

本文基于仓库根目录的 `docker-compose.hub.nginx.yml`，面向已经“用我的 Docker 镜像试用部署”的用户，提供一份可直接执行的“更新镜像并按需清理旧数据（干净重装）”指南。本编排采用 Nginx 统一入口（监听 80 端口），前端与后端 API 通过反向代理访问，无跨域问题。

涉及的服务：
- MongoDB（`mongo:4.4`）
- Redis（`redis:7-alpine`）
- Backend（`hsliup/tradingagents-backend:latest`）
- Frontend（`hsliup/tradingagents-frontend:latest`）
- Nginx（`nginx:alpine`，挂载 `./nginx/nginx.conf`）

重要提示：
- 生产环境请修改默认账户/密码、JWT/CORS 等安全参数
- 删除数据卷会清空 MongoDB 和 Redis 的所有数据（不可恢复），请先备份
- 如果只想“更新镜像不动数据”，跳过“清理数据卷”步骤即可

---

## 快速上手（命令速查）

Windows PowerShell：

```powershell
cd d:\code\TradingAgents-CN
# 拉取最新镜像
docker-compose -f docker-compose.hub.nginx.yml pull
# 停止并清理容器（保留数据）
docker-compose -f docker-compose.hub.nginx.yml down
# 可选：删除数据卷，做干净重装（会清空数据！）
docker volume ls | findstr tradingagents
docker volume rm tradingagents_mongodb_data tradingagents_redis_data
# 重新启动
docker-compose -f docker-compose.hub.nginx.yml up -d
# 查看状态与日志
docker-compose -f docker-compose.hub.nginx.yml ps
docker-compose -f docker-compose.hub.nginx.yml logs -f --tail=100
```

Linux/macOS（Bash）：

```bash
cd /path/to/TradingAgents-CN
# 拉取最新镜像
docker compose -f docker-compose.hub.nginx.yml pull
# 停止并清理容器（保留数据）
docker compose -f docker-compose.hub.nginx.yml down
# 可选：删除数据卷，做干净重装（会清空数据！）
docker volume ls | grep tradingagents
docker volume rm tradingagents_mongodb_data tradingagents_redis_data
# 重新启动
docker compose -f docker-compose.hub.nginx.yml up -d
# 查看状态与日志
docker compose -f docker-compose.hub.nginx.yml ps
docker compose -f docker-compose.hub.nginx.yml logs -f --tail=100
```

---

## 步骤一：备份数据（强烈建议）

若计划“清理数据卷”或担心升级影响数据，请先备份。

MongoDB 备份（默认 root 账户：`admin` / `tradingagents123`；认证库 `admin`）：

```bash
# 导出到容器内 /dump
docker exec tradingagents-mongodb sh -c \
  'mongodump -u admin -p "tradingagents123" --authenticationDatabase admin -o /dump'
# 拷贝到宿主机（按需修改目标路径）
docker cp tradingagents-mongodb:/dump ./backup/mongo-$(date +%F)
```

Redis（如果你有持久化需求；默认配置已启用 AOF）：

```bash
# 拷贝 Redis 数据目录（AOF/RDB）
docker cp tradingagents-redis:/data ./backup/redis-$(date +%F)
```

提示：试用环境常把 Redis 当缓存使用，可不备份；生产请谨慎操作。

---

## 步骤二：拉取最新镜像

```bash
docker-compose -f docker-compose.hub.nginx.yml pull
# 或者（Compose V2）：
docker compose -f docker-compose.hub.nginx.yml pull
```

说明：后端/前端使用 `:latest` 标签，便于快速跟进更新。若需要“可回滚”的稳定升级，建议在后续将 `latest` 固定为具体版本标签。

---

## 步骤三：停止并清理旧容器

```bash
docker-compose -f docker-compose.hub.nginx.yml down
# 或 docker compose -f docker-compose.hub.nginx.yml down
```

这会停止并移除当前编排下的容器与网络（不删除命名卷）。

---

## 步骤四（可选）：删除数据卷，做“干净重装”

警告：这会清空所有业务数据！仅在你确实要“归零重建”或此前数据异常时执行。

- 本编排声明的命名卷：
  - `tradingagents_mongodb_data`
  - `tradingagents_redis_data`

方式 A（精确删除，推荐）：

```bash
# 查阅含 tradingagents 的卷名
docker volume ls | grep tradingagents  # Windows 用 findstr
# 删除两个命名卷
docker volume rm tradingagents_mongodb_data tradingagents_redis_data
```

方式 B（一次性删除 Compose 声明卷）：

```bash
docker-compose -f docker-compose.hub.nginx.yml down -v
# 或 docker compose -f docker-compose.hub.nginx.yml down -v
```

注意：`-v` 会删除当前 Compose 文件声明并正在使用的命名卷。

---

## 步骤五：使用新镜像启动

```bash
docker-compose -f docker-compose.hub.nginx.yml up -d
# 或 docker compose -f docker-compose.hub.nginx.yml up -d
```

启动后：
- Nginx 监听 `80`，作为统一入口
- 前端通过 `/` 提供页面；后端 API 通过 `/api/` 代理（WebSocket 已在 Nginx 配置启用）
- 日志、配置、数据分别挂载到 `./logs`、`./config`、`./data`

---

## 步骤六：验证服务健康

快速检查：

```bash
# 查看容器状态
docker-compose -f docker-compose.hub.nginx.yml ps
# 跟随关键服务日志（可切换 nginx/backend/frontend）
docker-compose -f docker-compose.hub.nginx.yml logs -f --tail=100 nginx

# HTTP 健康检查（替换为你的域名或 IP）
curl -I http://your-server/health
curl    http://your-server/api/health
```

预期结果：
- 打开 `http://your-server/` 能看到前端
- `http://your-server/api/health` 返回后端健康信息
- `http://your-server/health` 返回 `healthy`（Nginx 层心跳）

---

## 常见问题排查（FAQ）

1) 80 端口被占用
- 修改 `nginx` 服务的端口映射，例如 `"8080:80"`，然后重新 `up -d`

2) Nginx 启动失败
- 确认存在并正确挂载 `./nginx/nginx.conf`
- 查看 `nginx` 容器日志定位语法错误

3) .env 未生效或密钥缺失
- 确保 `.env` 与 `docker-compose.hub.nginx.yml` 在同一目录
- 本编排为覆盖镜像占位符，显式声明了多项环境变量；值来源于 `.env`

4) 后端无法连接 MongoDB/Redis
- 检查 `MONGODB_URL` 与 `REDIS_URL`（编排中已使用内网服务名 `mongodb`/`redis`）
- 容器间网络走 `tradingagents-network`，无需使用宿主 IP

5) 只更新前端/后端，保留数据库

```bash
# 只拉取并重启前端与后端
docker-compose -f docker-compose.hub.nginx.yml pull backend frontend
docker-compose -f docker-compose.hub.nginx.yml up -d backend frontend
```

---

## 安全与版本建议

- 为生产环境设置强密码与密钥（Mongo/Redis/JWT/CSRF 等）
- 尽量固定镜像版本标签（而非 `latest`），以便排障/回滚
- 删除数据卷仅用于“干净重装”或异常修复，日常升级不建议清空数据

---

## 附录：文件与关键点速览

- 编排文件：`docker-compose.hub.nginx.yml`
- 关键挂载：
  - Nginx 配置：`./nginx/nginx.conf:/etc/nginx/nginx.conf:ro`
  - 后端日志/配置/数据：`./logs`、`./config`、`./data`
- 健康检查：
  - Backend：`/api/health`
  - Nginx：`/health`
- 命名卷：`tradingagents_mongodb_data`、`tradingagents_redis_data`

---

## 总结

- 常规升级：`pull → down → up -d`（保留数据卷）
- 干净重装：`pull → down → 删除数据卷 → up -d`（清空 Mongo/Redis）
- 验证：访问首页与 `/api/health`，结合 `ps` 与 `logs` 确认健康状态

如果你需要，我可以把本文步骤固化为“一键脚本”（Windows/Linux 双版），并放入 `scripts/` 目录，便于后续重复使用和团队内传播。
