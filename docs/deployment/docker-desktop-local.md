# 本机 Docker Desktop 部署

访问：http://localhost  
管理员：`admin` / `admin123`（首次登录后修改密码）。

## 启动

在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_docker_desktop.ps1
```

该脚本启动 Docker Desktop，显式使用 `desktop-linux`，启动服务并检查健康状态。
首次在空数据卷部署时添加 `-Initialize`，增量导入配置并创建账号。
不要直接运行镜像中的原始导入脚本：它使用硬编码数据库名，与本项目运行数据库不一致。

## 配置 DeepSeek

打开 http://localhost/settings/config ，在“厂家管理”中找到 DeepSeek，填写自己的 API Key。
随后在“大模型配置”中配置并启用 DeepSeek 模型，测试连接，再到“单股分析”选择模型运行分析。
本次未提供密钥，因此未执行模型调用和完整分析报告验证。

## 部署修正

- 使用 `docker-compose.hub.nginx.yml` 和 `docker-compose.desktop.yml` 两个文件。
- 原配置的 `v1.0.1` 标签不存在，采用官方仓库实际提供的 `v1.0.0-preview` 前后端镜像。
- MongoDB、Redis 不映射主机端口，避免与本机已有 27017、6379 服务冲突。
- 前端和网关健康检查使用 `127.0.0.1`，避免 `localhost` 解析为 IPv6 后连接失败。
- `scripts/init_desktop.py` 让官方初始化脚本使用运行环境指定的 `tradingagentscn` 数据库。
- 数据保存在 Docker 命名卷中；日志和应用数据分别挂载项目 `logs`、`data`。

## 日常管理

Docker Desktop 的 Containers 中可管理 `tradingagents-cn` 项目。
所有服务配置了 `restart: unless-stopped`，Docker Desktop 引擎启动后会自动恢复未手动停止的容器。

```powershell
docker --context desktop-linux compose -f docker-compose.hub.nginx.yml -f docker-compose.desktop.yml ps
docker --context desktop-linux compose -f docker-compose.hub.nginx.yml -f docker-compose.desktop.yml stop
```

## 验证记录

- 五个容器健康检查通过。
- `/api/health` 正常，管理员登录 API 成功。
- Chrome 实际登录成功，仪表板正常渲染。
- 配置管理页面成功加载，必需配置验证通过，DeepSeek 密钥显示未配置。
- 截图：`logs/docker-desktop-dashboard.png`。

用户提供的微信文章在当前网络无法读取；本次依据仓库自带 Docker 部署指南及实际镜像、运行结果完成部署。
