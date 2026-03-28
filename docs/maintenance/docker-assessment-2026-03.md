# Docker 部署静态评估（2026-03）

本文档记录当前仓库 Docker 部署方案的静态检查结果。

说明：

- 本次检查时间：2026-03-28
- 当前执行环境没有安装 `docker` 命令，因此**没有完成真实容器构建/启动回测**
- 结论基于以下文件的静态核查：
  - `docker-compose.yml`
  - `Dockerfile.backend`
  - `Dockerfile.frontend`
  - `.env.docker`
  - `docs/deployment/docker/DOCKER_FILES_README.md`
  - `docs/deployment/v1.0.0-source-installation.md`

## 1. 结论摘要

当前仓库的 Docker 方案不能算“已在本机实测直接可用”，但也不能直接判定为完全不可用。

更准确的判断是：

- Docker 文件主体仍然存在，且前后端/Redis/MongoDB 的基础编排逻辑是完整的
- 但文档、文件名、前端包管理器、运行时环境文件的假设之间已经出现明显偏差
- 如果用户完全照旧文档执行，**很可能会在入口文件名和环境配置层面先踩坑**

## 2. 关键发现

### 2.1 Docker 文档主入口与当前仓库文件不一致

`docs/deployment/docker/DOCKER_FILES_README.md` 多处把 `docker-compose.v1.0.0.yml` 作为主入口文件，但当前仓库根目录实际存在的是：

- `docker-compose.yml`
- `docker-compose.hub.nginx.yml`
- `docker-compose.hub.nginx.arm.yml`

并不存在文档里反复引用的 `docker-compose.v1.0.0.yml`。

这意味着：

- 按文档直接执行 `docker-compose -f docker-compose.v1.0.0.yml up -d` 会失败
- 这属于**文档已失效**，不是用户环境问题

### 2.2 Frontend Docker 仍然固定使用 Yarn，而当前本地公开启动脚本已转为“优先 pnpm”

`Dockerfile.frontend` 当前仍然是：

- `corepack prepare yarn@1.22.22 --activate`
- `COPY frontend/package.json frontend/yarn.lock frontend/.yarnrc ./`
- `RUN yarn install ...`
- `RUN yarn vite build`

而当前仓库本地公开启动脚本 `scripts/startup/start_local_stack.sh` 已改为：

- 优先 `pnpm`
- 没有 `pnpm` 再回退 `corepack + yarn`

判断：

- 这不一定会导致 Docker 失败，因为仓库里仍有 `frontend/yarn.lock`
- 但说明**Docker 构建链和本地开发链已经不是同一套假设**
- 我们这次为了本地跑通而做的 `pnpm` 优先调整，**不是 Docker 必需条件**

### 2.3 `docker-compose.yml` 与 `.env.docker` / `.env` 的职责存在混用

当前情况：

- `Dockerfile.backend` 会把 `.env.docker` 复制到镜像内的 `.env`
- 但 `docker-compose.yml` 运行时又要求主机侧提供 `env_file: .env`

这会带来两个问题：

- 用户以为镜像里已经带了 `.env.docker`，实际运行时仍可能被主机 `.env` 覆盖
- 如果用户没有准备主机 `.env`，按当前 compose 入口运行时会出现额外不确定性

判断：

- 这不是必然致命错误
- 但属于**部署口径不清晰**
- 更好的做法应是二选一：
  - 要么 compose 明确只依赖主机 `.env`
  - 要么镜像内固定 `.env.docker`，compose 不再额外引入主机 `.env`

### 2.4 Compose 会把宿主机 `config/` 挂载进容器，可能覆盖镜像内配置目录

`docker-compose.yml` 中后端挂载：

- `./config:/app/config`

而当前仓库里 `config/*.json` 大多属于运行时生成物或被忽略文件。

潜在影响：

- 镜像构建阶段复制进去的 `/app/config` 可能被宿主机空目录或不完整目录覆盖
- 如果后端运行时仍依赖某些 JSON 配置文件，这会引入“镜像内有、运行时反而没有”的问题

这类问题是否会触发，取决于当前运行路径是否完全切到数据库/环境变量。

### 2.5 Backend Dockerfile 构建过程依赖外网二进制下载，失败面较大

`Dockerfile.backend` 当前会在构建阶段：

- 从 GitHub 下载 `pandoc` deb 包
- 从 GitHub 下载 `wkhtmltopdf` deb 包
- 从清华镜像装 Python 包

这意味着 Docker 构建是否顺利，除了代码本身，还依赖：

- GitHub 可访问性
- 架构识别是否准确
- Bookworm 对应二进制是否仍可用
- 构建时网络稳定性

因此即使代码没问题，Docker 首次构建依然有较高环境波动风险。

## 3. 原版 Docker 部署是不是“直接可用”？

基于当前静态核查，我的判断是：

- **不能把它认定为“现在直接可用”**
- 但也不是“完全报废”

更准确地说：

- Docker 文件本身还在维护路径上
- 但文档主入口已失效
- 运行时环境文件职责不够清晰
- 构建链与当前本地启动链存在分叉

如果用户完全依赖旧文档操作，成功率不会高。

## 4. 我们这次为了本地启动做的改动，哪些是 Docker 必需，哪些不是

### 4.1 不属于 Docker 必需的改动

以下更偏“本地开发栈”而不是 Docker 必需：

- `scripts/startup/start_local_stack.sh`
- `scripts/startup/bootstrap_local_env.py`
- `scripts/startup/init_local_env_db.py`
- `pnpm` 优先、`corepack+yarn` 回退的本地前端安装策略
- `codex` 本地专用脚本分层整理

这些改动的作用主要是：

- 降低本地部署成本
- 固化 MongoDB / Redis / 配置初始化流程
- 让公开版启动脚本不依赖 `~/.codex`

### 4.2 对 Docker 仍然有价值的改动

以下改动即使不走 Docker，也属于通用稳定性收益，Docker 同样受益：

- 后端分析报告链路稳定性修复
- 数据同步 / 自选股 / 标签 / 港股行情展示修复
- 配置管理与密钥来源展示修复
- 默认测试套件整理
- 示例密钥与敏感值清理

这些是“应用级修复”，不是“启动方式专属修复”。

## 5. 建议的后续动作

如果后续要把 Docker 也整理到可公开交付状态，建议按这个顺序做：

1. 统一文档入口
   - 明确当前唯一受支持的 compose 文件名
   - 删除或标记过期文档中的 `docker-compose.v1.0.0.yml`

2. 明确环境变量来源
   - 统一为“宿主机 `.env`”或“镜像内 `.env.docker`”
   - 避免双来源混用

3. 明确前端包管理器策略
   - 继续维持 Docker 用 Yarn 也可以
   - 但需要在文档里明确说明 Docker 与本地脚本口径不同
   - 或统一改成 pnpm，并补全 `pnpm-lock.yaml`

4. 真机回测
   - `docker compose build`
   - `docker compose up -d`
   - 健康检查
   - 登录 / 分析 / 导出 / Mongo / Redis 基本验证

## 6. 当前可落地结论

截至 2026-03-28：

- **无法在当前机器上完成 Docker 实测**，因为环境没有安装 `docker`
- **可以确定旧 Docker 文档存在失效点**
- **可以确定我们之前为本地跑通所做的改动并非全部都是 Docker 必需**
- 若要最终确认“原版 Docker 是否直接可用”，还需要在具备 Docker 的环境做一次真实构建与启动验证
