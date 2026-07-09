# v1.0.0-preview 安装测试指南

## 📋 概述

本文档提供 TradingAgents-CN v1.0.0-preview 各种安装模式的详细测试步骤和验证方法。

## 🎯 测试目标

- 验证各种安装模式的安装流程是否顺畅
- 验证安装后系统能否正常启动和运行
- 验证升级流程是否正确（数据和配置保留）
- 验证卸载/清理流程是否完整

## 📦 安装模式对比

| 安装模式 | 适用场景 | 难度 | 测试优先级 | 预计测试时间 |
|---------|---------|------|-----------|------------|
| 🟢 绿色版 | Windows 用户、快速体验 | ⭐ 简单 | P0 | 15 分钟 |
| 🐳 Docker 版 | 生产环境、跨平台 | ⭐⭐ 中等 | P0 | 30 分钟 |
| 💻 源码版 | 开发者、定制需求 | ⭐⭐⭐ 较难 | P1 | 60 分钟 |
| 🪟 Windows 安装版 | Windows 原生安装 | ⭐ 简单 | P2 | 20 分钟 |

---

## 🟢 测试 1：绿色版安装（Windows）

### 前置条件
- Windows 10 或 Windows 11
- 至少 4GB 可用内存
- 至少 10GB 可用磁盘空间
- 无需预装任何软件

### 测试步骤

#### 1.1 下载与解压
```powershell
# 测试点 1：下载绿色版压缩包
# - [ ] 下载链接可访问
# - [ ] 文件大小合理（约 500MB - 2GB）
# - [ ] 下载完整，无损坏

# 测试点 2：解压到指定目录
# - [ ] 解压成功，无错误
# - [ ] 目录结构完整
# - [ ] 路径中无中文字符（推荐）
```

**预期目录结构**：
```
TradingAgents-CN-v1.0.0-preview/
├── runtime/          # 运行时环境（MongoDB、Redis、Python 等）
├── app/              # 后端代码
├── frontend/         # 前端代码
├── data/             # 数据目录
├── logs/             # 日志目录
├── start_all.bat     # 启动脚本
├── stop_all.bat      # 停止脚本
└── README.txt        # 说明文档
```

#### 1.2 首次启动
```powershell
# 测试点 3：运行启动脚本
# 双击或运行 start_all.bat

# 验证点：
# - [ ] MongoDB 服务启动成功（端口 27017）
# - [ ] Redis 服务启动成功（端口 6379）
# - [ ] 后端服务启动成功（端口 8000）
# - [ ] 前端服务启动成功（端口 3000）
# - [ ] 浏览器自动打开 http://localhost:3000
# - [ ] 启动过程无严重错误（允许有警告）
```

**检查方法**：
```powershell
# 检查进程
tasklist | findstr "mongod redis-server python node"

# 检查端口
netstat -ano | findstr "27017 6379 8000 3000"

# 查看日志
type logs\backend.log
type logs\frontend.log
```

#### 1.3 功能验证
```
测试点 4：基本功能测试
- [ ] 访问 http://localhost:3000 页面正常加载
- [ ] 可以使用默认账号登录（admin/admin 或文档中的默认账号）
- [ ] 首页 Dashboard 显示正常
- [ ] 可以搜索股票（如：000001）
- [ ] 可以查看股票详情
- [ ] 可以发起一次简单分析（深度 1 级）
- [ ] 可以查看分析报告
- [ ] 可以导出报告（Markdown 格式）
```

#### 1.4 停止服务
```powershell
# 测试点 5：运行停止脚本
# 双击或运行 stop_all.bat

# 验证点：
# - [ ] 所有服务进程正常退出
# - [ ] 无残留进程（检查任务管理器）
# - [ ] 端口释放（27017、6379、8000、3000）
# - [ ] 数据文件完整（data/ 目录）
```

#### 1.5 重启测试
```
测试点 6：重新启动服务
- [ ] 再次运行 start_all.bat
- [ ] 所有服务正常启动
- [ ] 之前的数据保留（用户、配置、分析记录）
- [ ] 可以继续使用
```

#### 1.6 升级测试
```
测试点 7：模拟升级流程
1. 停止当前服务（stop_all.bat）
2. 备份 data/ 目录
3. 下载新版本绿色包
4. 解压到同一目录（覆盖旧文件）
5. 保留 data/ 目录（不覆盖）
6. 启动新版本（start_all.bat）

验证点：
- [ ] 新版本正常启动
- [ ] 旧数据保留（用户、配置、分析记录）
- [ ] 新功能可用
- [ ] 无数据丢失或损坏
```

### 常见问题

**问题 1**：启动失败，提示端口被占用
```powershell
# 解决方案：检查并关闭占用端口的进程
netstat -ano | findstr "27017"
taskkill /PID <进程ID> /F
```

**问题 2**：浏览器无法访问 http://localhost:3000
```
解决方案：
1. 检查防火墙设置
2. 检查前端服务是否启动（查看 logs/frontend.log）
3. 尝试访问 http://127.0.0.1:3000
```

**问题 3**：MongoDB 启动失败
```
解决方案：
1. 检查 data/mongodb/ 目录权限
2. 删除 data/mongodb/mongod.lock 文件
3. 重新启动
```

---

## 🐳 测试 2：Docker 版安装

### 前置条件
- Docker 20.10+ 已安装
- Docker Compose 2.0+ 已安装
- 至少 4GB 可用内存
- 至少 20GB 可用磁盘空间

### 测试步骤

#### 2.1 准备工作
```bash
# 测试点 1：克隆代码仓库或下载 docker-compose 文件
git clone https://github.com/your-org/TradingAgents-CN.git
cd TradingAgents-CN

# 或下载单独的 docker-compose 文件
curl -O https://raw.githubusercontent.com/your-org/TradingAgents-CN/main/docker-compose.hub.yml
curl -O https://raw.githubusercontent.com/your-org/TradingAgents-CN/main/.env.example

# 验证点：
# - [ ] 文件下载成功
# - [ ] docker-compose.yml 或 docker-compose.hub.yml 存在
# - [ ] .env.example 存在
```

#### 2.2 配置环境变量
```bash
# 测试点 2：配置 .env 文件
cp .env.example .env
# 编辑 .env 文件，配置必要的 API keys

# 验证点：
# - [ ] .env 文件创建成功
# - [ ] 至少配置了一个 LLM API key（如 DASHSCOPE_API_KEY）
# - [ ] 端口配置正确（如需修改）
```

#### 2.3 启动服务
```bash
# 测试点 3：使用 Docker Compose 启动服务
docker-compose up -d
# 或使用 Docker Hub 镜像
docker-compose -f docker-compose.hub.yml up -d

# 验证点：
# - [ ] 镜像拉取成功（首次启动）
# - [ ] 所有容器启动成功
# - [ ] 无错误日志
```

**检查容器状态**：
```bash
# 查看容器状态
docker-compose ps

# 预期输出：
# NAME                STATUS              PORTS
# backend             Up                  0.0.0.0:8000->8000/tcp
# frontend            Up                  0.0.0.0:3000->3000/tcp
# mongodb             Up                  0.0.0.0:27017->27017/tcp
# redis               Up                  0.0.0.0:6379->6379/tcp
# nginx               Up                  0.0.0.0:80->80/tcp

# 查看日志
docker-compose logs -f backend
docker-compose logs -f frontend
```

#### 2.4 功能验证
```
测试点 4：基本功能测试
- [ ] 访问 http://localhost 或 http://localhost:3000 页面正常加载
- [ ] 可以登录
- [ ] 可以搜索股票
- [ ] 可以发起分析
- [ ] 可以查看报告
```

#### 2.5 数据持久化测试
```bash
# 测试点 5：验证数据持久化
# 1. 创建一些数据（用户、配置、分析记录）
# 2. 停止容器
docker-compose stop

# 3. 重新启动容器
docker-compose start

# 验证点：
# - [ ] 容器重启成功
# - [ ] 之前的数据保留
# - [ ] 可以继续使用
```

#### 2.6 容器管理测试
```bash
# 测试点 6：容器管理命令
# 停止服务
docker-compose stop
# - [ ] 所有容器正常停止

# 重启服务
docker-compose restart
# - [ ] 所有容器正常重启

# 查看日志
docker-compose logs backend
# - [ ] 日志正常显示

# 清理容器（保留数据卷）
docker-compose down
# - [ ] 容器删除成功
# - [ ] 数据卷保留（docker volume ls）

# 完全清理（包括数据卷）
docker-compose down -v
# - [ ] 容器和数据卷全部删除
```

#### 2.7 升级测试
```bash
# 测试点 7：升级到新版本
# 1. 拉取新版本镜像
docker-compose pull

# 2. 停止旧容器
docker-compose down

# 3. 启动新容器
docker-compose up -d

# 验证点：
# - [ ] 新镜像拉取成功
# - [ ] 新容器启动成功
# - [ ] 数据卷保留（如果使用了数据卷）
# - [ ] 配置保留
# - [ ] 新功能可用
```

### 常见问题

**问题 1**：容器启动失败，提示端口被占用
```bash
# 解决方案：修改 docker-compose.yml 中的端口映射
# 或停止占用端口的服务
```

**问题 2**：MongoDB 容器无法启动
```bash
# 解决方案：检查数据卷权限
docker volume inspect tradingagents_mongodb_data
# 删除数据卷重新创建
docker volume rm tradingagents_mongodb_data
```

**问题 3**：前端无法连接后端
```bash
# 解决方案：检查网络配置
docker network ls
docker network inspect tradingagents_default
# 确认所有容器在同一网络中
```

---

## 💻 测试 3：源码版安装

### 前置条件
- Python 3.10+ 已安装
- Node.js 18+ 已安装
- MongoDB 5.0+ 已安装并启动
- Redis 6.0+ 已安装并启动
- Git 已安装

### 测试步骤

#### 3.1 克隆代码
```bash
# 测试点 1：克隆代码仓库
git clone https://github.com/your-org/TradingAgents-CN.git
cd TradingAgents-CN

# 验证点：
# - [ ] 代码克隆成功
# - [ ] 目录结构完整
```

#### 3.2 后端安装
```bash
# 测试点 2：创建 Python 虚拟环境
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 验证点：
# - [ ] 虚拟环境创建成功
# - [ ] 虚拟环境激活成功

# 测试点 3：安装 Python 依赖
pip install -r requirements.txt

# 验证点：
# - [ ] 依赖安装成功
# - [ ] 无严重错误（允许有警告）
# - [ ] 关键包已安装（fastapi、uvicorn、pymongo、redis 等）

# 测试点 4：配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 验证点：
# - [ ] .env 文件创建成功
# - [ ] MongoDB 连接字符串正确
# - [ ] Redis 连接字符串正确
# - [ ] LLM API keys 配置正确

# 测试点 5：初始化数据库
python scripts/setup/init_database.py

# 验证点：
# - [ ] 数据库初始化成功
# - [ ] 集合创建成功
# - [ ] 索引创建成功

# 测试点 6：启动后端服务
python -m app.main
# 或
uvicorn app.main:app --reload

# 验证点：
# - [ ] 后端服务启动成功
# - [ ] 监听 http://localhost:8000
# - [ ] API 文档可访问（http://localhost:8000/docs）
# - [ ] 无严重错误日志
```

#### 3.3 前端安装
```bash
# 测试点 7：安装 Node.js 依赖
cd frontend
npm install
# 或使用 pnpm
pnpm install

# 验证点：
# - [ ] 依赖安装成功
# - [ ] node_modules 目录创建
# - [ ] 无严重错误

# 测试点 8：配置前端环境变量
cp .env.example .env.local
# 编辑 .env.local 文件

# 验证点：
# - [ ] .env.local 文件创建成功
# - [ ] 后端 API 地址配置正确

# 测试点 9：启动前端开发服务器
npm run dev

# 验证点：
# - [ ] 前端服务启动成功
# - [ ] 监听 http://localhost:3000
# - [ ] 页面可访问
# - [ ] 热重载功能正常
```

#### 3.4 功能验证
```
测试点 10：基本功能测试
- [ ] 前后端联调正常
- [ ] 可以登录
- [ ] 可以搜索股票
- [ ] 可以发起分析
- [ ] 可以查看报告
- [ ] 修改代码后热重载生效
```

#### 3.5 生产构建测试
```bash
# 测试点 11：前端生产构建
cd frontend
npm run build

# 验证点：
# - [ ] 构建成功
# - [ ] dist 目录生成
# - [ ] 静态文件完整

# 测试点 12：后端生产模式启动
cd ..
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 验证点：
# - [ ] 后端以生产模式启动
# - [ ] 性能符合预期
# - [ ] 日志级别正确
```

### 常见问题

**问题 1**：Python 依赖安装失败
```bash
# 解决方案：升级 pip
pip install --upgrade pip
# 使用国内镜像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**问题 2**：MongoDB 连接失败
```bash
# 解决方案：检查 MongoDB 是否启动
# Windows
net start MongoDB
# Linux
sudo systemctl start mongod
# 检查连接字符串
```

**问题 3**：前端依赖安装失败
```bash
# 解决方案：清理缓存
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

---

## 🪟 测试 4：Windows 安装版（如果有）

### 前置条件
- Windows 10 或 Windows 11
- 管理员权限（用于安装）

### 测试步骤

#### 4.1 安装程序测试
```
测试点 1：运行安装程序
- [ ] 双击 .exe 或 .msi 安装包
- [ ] 安装向导启动
- [ ] 可以选择安装路径
- [ ] 可以选择组件（如有）
- [ ] 安装过程无错误
- [ ] 安装完成提示
```

#### 4.2 安装后验证
```
测试点 2：安装后检查
- [ ] 桌面快捷方式创建
- [ ] 开始菜单项创建
- [ ] 安装目录文件完整
```

#### 4.3 启动测试
```
测试点 3：启动应用
- [ ] 双击桌面快捷方式
- [ ] 所有服务自动启动
- [ ] 系统托盘图标显示
- [ ] 浏览器自动打开应用页面
```

#### 4.4 功能验证
```
测试点 4：基本功能测试
- [ ] 可以登录
- [ ] 可以搜索股票
- [ ] 可以发起分析
- [ ] 可以查看报告
```

#### 4.5 卸载测试
```
测试点 5：卸载应用
- [ ] 运行卸载程序（控制面板或开始菜单）
- [ ] 卸载向导启动
- [ ] 可以选择是否保留数据
- [ ] 卸载完成
- [ ] 所有文件删除（或按选项保留数据）
- [ ] 快捷方式删除
- [ ] 注册表项清理（如有）
```

---

## 📊 测试结果记录

### 测试环境信息
- 操作系统：
- 测试日期：
- 测试人员：
- 版本号：v1.0.0-preview

### 测试结果汇总

| 安装模式 | 测试状态 | 通过率 | 主要问题 | 备注 |
|---------|---------|-------|---------|------|
| 🟢 绿色版 | ✅ / ❌ | __% | | |
| 🐳 Docker 版 | ✅ / ❌ | __% | | |
| 💻 源码版 | ✅ / ❌ | __% | | |
| 🪟 Windows 安装版 | ✅ / ❌ | __% | | |

### 问题列表

| 问题编号 | 安装模式 | 问题描述 | 严重程度 | 状态 |
|---------|---------|---------|---------|------|
| #1 | | | P0/P1/P2 | 待修复/已修复 |
| #2 | | | P0/P1/P2 | 待修复/已修复 |

---

## 📚 相关文档

- [v1.0.0-preview 测试计划](./v1.0.0-preview-test-plan.md)
- [v1.0.0-preview 测试用例](./test-cases.md)
- [绿色版安装指南](https://mp.weixin.qq.com/s/eoo_HeIGxaQZVT76LBbRJQ)
- [Docker 部署指南](https://mp.weixin.qq.com/s/JkA0cOu8xJnoY_3LC5oXNw)
- [源码安装指南](https://mp.weixin.qq.com/s/cqUGf-sAzcBV19gdI4sYfA)

