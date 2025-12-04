# TradingAgents-CN Windows 便携版安装与使用

本指南说明如何使用“一步到位”的 Windows 便携包进行安装与启动。该方案旨在让普通用户无需预装依赖，解压即可运行，并通过脚本完成首次配置与服务编排。

## 包含组件
- 后端：FastAPI（Python，随包包含 `venv` 或使用系统 Python）
- 前端：已构建的 `frontend/dist`（由后端挂载或 Nginx 提供）
- MongoDB（可选，分发目录 `vendors/mongodb`）
- Redis（可选，分发目录 `vendors/redis`）
- Nginx（可选，分发目录 `vendors/nginx`）
- 脚本：`scripts/installer/setup.ps1`、`start_all.ps1`、`stop_all.ps1`

> 说明：MongoDB、Redis 与 Nginx 可执行文件需按许可获得并放置到 `vendors/` 目录。若未包含，将在启动时跳过相应组件。

## 目录结构
```
TradingAgentsCN-portable/
├── app/
├── frontend/dist/
├── venv/ (可选)
├── config/
├── .env.example
├── vendors/
│   ├── mongodb/
│   ├── redis/
│   └── nginx/
├── scripts/
│   └── installer/
│       ├── setup.ps1
│       ├── start_all.ps1
│       └── stop_all.ps1
└── runtime/ (运行期生成)
```

## 安装与首次运行
1. 解压整个目录到任意路径（避免太长路径与中文/空格路径以减少兼容问题）
2. 右键以管理员身份打开 PowerShell，进入解压目录根路径
3. 运行初始化脚本：
   ```
   powershell -ExecutionPolicy Bypass -File scripts/installer/setup.ps1
   ```
   - 该脚本将：
     - 复制 `.env.example` → `.env`
     - 生成强随机 `JWT_SECRET` / `CSRF_SECRET`
     - 设置默认 `HOST=127.0.0.1`、`PORT=8000`（可在交互中修改）
     - 设置 `SERVE_FRONTEND=true`、`FRONTEND_STATIC=frontend/dist`、`AUTO_OPEN_BROWSER=true`
     - 创建数据目录：`data/mongodb/db`、`data/redis/data`、日志目录与 `runtime`

4. 启动全部服务：
   ```
   powershell -ExecutionPolicy Bypass -File scripts/installer/start_all.ps1
   ```
   - 脚本将按 `.env` 启动后端，并尝试启动 vendors 中的 MongoDB、Redis（如存在）与 Nginx（可选）
   - 如端口被占用，将进行运行时回退（不修改 `.env`），并在控制台提示最终端口
   - 若 `AUTO_OPEN_BROWSER=true`，将自动打开浏览器到主页

5. 停止所有服务：
   ```
   powershell -ExecutionPolicy Bypass -File scripts/installer/stop_all.ps1
   ```

## 常见配置项（.env）
- `HOST=127.0.0.1`：后端监听地址；建议保留本机以确保安全
- `PORT=8000`：后端端口；占用时运行时回退（例如 8001）
- `SERVE_FRONTEND=true`、`FRONTEND_STATIC=frontend/dist`：启用后端静态挂载与 SPA fallback
- `AUTO_OPEN_BROWSER=true`：启动后自动打开浏览器
- `JWT_SECRET`、`CSRF_SECRET`：强随机密钥（安装脚本生成）
- `MONGODB_HOST=127.0.0.1`、`MONGODB_PORT=27017`、`MONGODB_DATABASE=tradingagents`
- `REDIS_HOST=127.0.0.1`、`REDIS_PORT=6379`
- `NGINX_ENABLE=false`、`NGINX_PORT=8080`：可选启用 Nginx 反向代理

## 注意与建议
- 安全性：默认仅监听本机地址；若要外网访问，请理解相关安全风险并配置防火墙与强密钥
- 许可与分发：MongoDB（SSPL）与 Redis 的 Windows 版本分发需遵循各自许可；请在 vendors 中包含许可文件
- 杀软与签名：某些环境可能提示或阻止运行，可考虑对分发包进行签名或加入白名单
- 更新策略：建议采用“增量替换”策略，仅替换 `app/`、`frontend/dist/` 与 `venv` 指定包，保留 `data/` 以保存用户数据

## 编码与终端兼容性（中文 Windows）

- 为避免在 GBK/GB2312 终端出现乱码，安装与启动脚本采用 ASCII 字符输出，不含 emoji 或特殊符号；功能不受影响。
- `.env` 的写入采用 ASCII 追加方式，仅追加键值对，不重写整份文件，以避免破坏原始示例文件中的中文注释与编码。
- 如需在控制台显示中文提示，建议使用支持 UTF-8 的终端（Windows Terminal/PowerShell 7），或在命令行中执行 `chcp 65001` 切换到 UTF-8 代码页（旧版控制台兼容性可能受限）。
- 文档与源代码仍使用 UTF-8 编码；脚本在 GBK/GB2312 环境下也可正常工作。

## 构建发行包（开发者）
在项目根目录运行：
```
powershell -ExecutionPolicy Bypass -File scripts/deployment/assemble_portable_release.ps1 -ReleaseDir .\release\TradingAgentsCN-portable -BuildFrontend -RecreateVenv
```
执行后，`release/TradingAgentsCN-portable` 目录即为可分发的便携版安装包。