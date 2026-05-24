# 部署模式切换指南

项目支持两种部署方式，共用同一份 `.env`（API 密钥、业务配置不变），仅数据库地址、路径、DEBUG 等随模式变化。

## 快速切换

```powershell
# 查看当前模式
.\scripts\switch_env.ps1 status

# 混合部署：Docker 只跑 MongoDB + Redis，本地跑后端/前端（改代码立即生效）
.\scripts\switch_env.ps1 hybrid

# 全 Docker：所有服务容器化（生产/稳定运行）
.\scripts\switch_env.ps1 docker
```

切换前会自动备份 `.env` → `.env.backup`。

## 两种模式对比

| 项目 | hybrid（混合） | docker（全容器） |
|------|----------------|------------------|
| MongoDB/Redis | Docker 容器，地址 `localhost` | 容器内服务名 `mongodb` / `redis` |
| 后端 | 本地 `python -m app` | 容器 backend |
| 前端 | 本地 `npm run dev` → :3000 | Nginx → :80 |
| DEBUG | `true`（有 /docs） | `false` |
| 改源码 | 直接生效 | 需 rebuild 镜像 |
| 访问地址 | http://localhost:3000 | http://localhost |

## 混合部署启动步骤

```powershell
docker start tradingagents-mongodb tradingagents-redis
.\scripts\switch_env.ps1 hybrid
.\venv\Scripts\Activate.ps1
python -m app

# 另开终端
cd frontend
npm run dev
```

## 全 Docker 启动步骤

```powershell
.\scripts\switch_env.ps1 docker
docker compose -f docker-compose.hub.nginx.yml up -d
```

源码改动后：

```powershell
docker compose -f docker-compose.hub.nginx.yml build backend
docker compose -f docker-compose.hub.nginx.yml up -d backend
```

## 共用部分（无需重复配置）

- API 密钥（DeepSeek、DashScope 等）
- MongoDB 数据（同一 Docker 卷，切换模式不丢数据）
- MongoDB 运行时配置（数据源优先级、LLM 模型等，见 `.claude/CHANGES.md`）

## 注意事项

1. **Compose 会覆盖数据库主机名**：全 Docker 时 `docker-compose.hub.nginx.yml` 的 `environment` 会强制 `MONGODB_HOST=mongodb`，与 `.env` 中写 localhost 不冲突。
2. **混合模式本地跑后端时**：`.env` 必须为 `localhost`，否则连不上数据库。
3. **首次部署**：无论哪种模式，都需执行一次 `python scripts/import_config_and_create_user.py --host`（混合）或在容器内执行等价命令。
