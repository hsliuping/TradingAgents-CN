# Mac 部署与 OTA 指南

面向 fork 私人部署：Apple Silicon Mac 通过 Docker Compose 运行，发版 tag 后目标机器自动 OTA 更新。

## 架构概览

```
协作者 GitHub PR merge
        ↓
发版负责人 git tag vX.Y.Z
        ↓
GitHub Actions → Docker Hub（你的账号/tradingagents-*）
              → Gitee update-manifest.json
        ↓
部署 Mac 启动 → update.sh 检查 manifest → pull 新镜像 → 重启
```

## 一、一次性配置（仓库管理员）

### 1. GitHub Secrets

fork 仓库 → **Settings → Secrets and variables → Actions → New repository secret**

| Secret | 说明 |
|--------|------|
| `DOCKERHUB_USERNAME` | 你的 Docker Hub 用户名 |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token（Read & Write，用于 CI push） |
| `GITEE_TOKEN` | Gitee 私人令牌 |
| `GITEE_OWNER` | Gitee 用户名或组织名 |
| `GITEE_REPO` | Gitee OTA 小仓库名，如 `TradingAgents-OTA` |

Docker Hub 为 **Public** 时，部署 Mac **不需要** Docker 登录凭证。

### 2. Gitee OTA 仓库

1. 在 Gitee 新建仓库 `TradingAgents-OTA`（可为私有）
2. 首次可为空；发版 tag 后 CI 会自动创建 `update-manifest.json`
3. 部署 Mac 使用的 manifest 地址：

```
https://gitee.com/YOUR_USER/TradingAgents-OTA/raw/main/update-manifest.json
```

### 3. Workflows

fork 已包含：

- `.github/workflows/docker-publish.yml` — tag 触发，构建并 push 镜像到你的 Docker Hub
- `.github/workflows/sync-ota-manifest.yml` — tag 触发，同步 manifest 到 Gitee

## 二、Mac 首次部署

在 **Apple Silicon Mac** 上：

```bash
# 1. 克隆你的 fork
git clone https://github.com/YOUR_USER/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 安装 Docker Desktop 并启动

# 3. 运行部署向导
bash scripts/mac/bootstrap.sh
```

向导会：

- 创建 `~/Applications/TradingAgents-CN/`
- 复制 compose、nginx、启动脚本
- 询问 Docker Hub 用户名、Gitee manifest URL
- 生成 `.env`（含 `BACKEND_IMAGE`、`FRONTEND_IMAGE`、`MANIFEST_URL`）
- 在桌面创建 `TradingAgents-CN.command` 快捷方式

**日常使用**：双击桌面 **TradingAgents-CN.command** → 浏览器打开 http://localhost

### 安装目录结构

```
~/Applications/TradingAgents-CN/
├── docker-compose.hub.nginx.arm.yml
├── nginx/nginx.conf
├── .env                    # API Key + 镜像地址 + MANIFEST_URL（OTA 不覆盖 API Key）
├── VERSION                 # 当前版本
├── start.command
├── update.sh
├── logs/
└── data/
```

## 三、协作发版流程

```bash
# 协作者日常：PR merge 到 main（不触发部署 Mac 更新）

# 发版负责人
git checkout main && git pull
git tag v1.0.2
git push origin v1.0.2

# 在 GitHub Actions 确认两个 workflow 成功：
# - Docker Publish to Docker Hub
# - Sync OTA Manifest to Gitee
```

部署 Mac **下次启动**时会自动检查 Gitee manifest 并更新。

也可手动更新：

```bash
bash ~/Applications/TradingAgents-CN/update.sh --now
```

## 四、manifest 格式

[`release/update-manifest.json`](../../release/update-manifest.json) 为模板；CI 发版时自动生成并推送到 Gitee：

```json
{
  "version": "v1.0.2",
  "images": {
    "backend": "YOUR_DOCKERHUB/tradingagents-backend:v1.0.2",
    "frontend": "YOUR_DOCKERHUB/tradingagents-frontend:v1.0.2"
  }
}
```

## 五、与上游隔离

| 项目 | 上游 hsliup | 你的 fork |
|------|-------------|-----------|
| Docker 镜像 | `hsliup/tradingagents-*` | `YOUR/tradingagents-*` |
| GitHub Secrets | 上游私有 | 你的 fork 单独配置 |
| 部署 Mac `.env` | — | 指向你的镜像与 Gitee manifest |

compose 默认 fallback 仍为上游镜像；你的 `.env` 中 `BACKEND_IMAGE` / `FRONTEND_IMAGE` 会覆盖。

## 六、故障排查

| 现象 | 处理 |
|------|------|
| Docker 未启动 | 打开 Docker Desktop，重新运行启动脚本 |
| OTA 不更新 | 检查 `.env` 中 `MANIFEST_URL`；Gitee 上 manifest 版本是否高于本地 `VERSION` |
| pull 失败 | 确认 Docker Hub 上该 tag 镜像已构建；Public 镜像无需 login |
| 更新后服务异常 | 查看 `~/Applications/TradingAgents-CN/logs/update.log`；用 `.env.bak.*` 恢复 |
| CI push 失败 | 检查 `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` |
| Gitee 同步失败 | 检查 `GITEE_TOKEN` / `GITEE_OWNER` / `GITEE_REPO` |

查看当前版本：

```bash
curl -s http://localhost/api/health | python3 -m json.tool
cat ~/Applications/TradingAgents-CN/VERSION
```

## 七、可选增强

- **定时 OTA**：用 launchd 定期执行 `update.sh --check`（默认仅在启动时检查）
- **Private 镜像**：在 `.env` 增加 `DOCKER_HUB_USER` 和 `DOCKER_HUB_TOKEN`，`update.sh` 会在 pull 前 login
