# 🔄 TradingAgents-CN 升级指南

## 📋 概述

本指南提供TradingAgents-CN各版本之间的升级方法，确保用户能够安全、顺利地升级到最新版本。

## 🎯 升级前准备

### 1. 备份重要数据

```bash
# 备份配置文件
cp .env .env.backup.$(date +%Y%m%d)

# 备份数据库 (如果使用MongoDB)
mongodump --out backup_$(date +%Y%m%d)

# 备份Redis数据 (如果使用Redis)
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb backup_redis_$(date +%Y%m%d).rdb

# 备份自定义配置
cp -r config config_backup_$(date +%Y%m%d)
```

### 2. 检查系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|---------|----------|
| **Python** | 3.10+ | 3.11+ |
| **内存** | 4GB | 8GB+ |
| **磁盘空间** | 5GB | 10GB+ |
| **Docker** | 20.0+ | 最新版 |
| **Docker Compose** | 2.0+ | 最新版 |

### 3. 检查当前版本

```bash
# 检查当前版本
cat VERSION

# 或在Python中检查
python -c "
import sys
sys.path.append('.')
from tradingagents import __version__
print(f'当前版本: {__version__}')
"
```

## 🚀 升级到v0.1.7

### 从v0.1.6升级 (推荐路径)

#### 步骤1: 停止当前服务

```bash
# 如果使用Docker
docker-compose down

# 如果使用本地部署
# 停止Streamlit应用 (Ctrl+C)
```

#### 步骤2: 更新代码

```bash
# 拉取最新代码
git fetch origin
git checkout main
git pull origin main

# 检查更新内容
git log --oneline v0.1.6..v0.1.7
```

#### 步骤3: 更新配置

```bash
# 比较配置文件差异
diff .env.example .env

# 添加新的配置项
cat >> .env << 'EOF'

# === v0.1.7 新增配置 ===
# DeepSeek配置
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_ENABLED=true

# 报告导出配置
EXPORT_ENABLED=true
EXPORT_DEFAULT_FORMAT=word,pdf

# Docker环境配置 (如果使用Docker)
MONGODB_URL=mongodb://mongodb:27017/tradingagents
REDIS_URL=redis://redis:6379
EOF
```

#### 步骤4: 选择部署方式

**选项A: Docker部署 (推荐)**

```bash
# 安装Docker (如果未安装)
# Windows: 下载Docker Desktop
# Linux: sudo apt install docker.io docker-compose

# 启动服务
docker-compose up -d

# 验证服务状态
docker-compose ps
```

**选项B: 本地部署**

```bash
# 更新依赖
pip install -r requirements.txt

# 启动应用
streamlit run web/app.py
```

#### 步骤5: 验证升级

```bash
# 检查版本
curl http://localhost:8501/health

# 测试核心功能
# 1. 访问Web界面: http://localhost:8501
# 2. 进行一次股票分析
# 3. 测试报告导出功能
# 4. 检查数据库连接 (如果使用)
```

### 从v0.1.5及以下升级

#### 重要提醒
⚠️ **建议全新安装**: 由于架构变化较大，建议全新安装而非直接升级

#### 步骤1: 导出重要数据

```bash
# 导出分析历史 (如果有)
python -c "
import json
from tradingagents.config.config_manager import config_manager
history = config_manager.get_analysis_history()
with open('analysis_history_backup.json', 'w') as f:
    json.dump(history, f, indent=2)
"

# 导出自定义配置
cp .env custom_config_backup.env
```

#### 步骤2: 全新安装

```bash
# 创建新目录
mkdir TradingAgents-CN-v0.1.7
cd TradingAgents-CN-v0.1.7

# 克隆最新版本
git clone https://github.com/hsliuping/TradingAgents-CN.git .

# 恢复配置
cp ../custom_config_backup.env .env
# 手动调整配置以适应新版本
```

#### 步骤3: 迁移数据

```bash
# 如果使用MongoDB，导入历史数据
mongorestore backup_20250713/

# 如果使用文件存储，复制数据文件
cp -r ../old_version/data/ ./data/
```

## 🐳 Docker升级专门指南

### 首次使用Docker

```bash
# 1. 确保Docker已安装
docker --version
docker-compose --version

# 2. 停止本地服务
# 停止本地Streamlit、MongoDB、Redis等服务

# 3. 配置环境变量
cp .env.example .env
# 编辑.env文件，注意Docker环境的特殊配置

# 4. 启动Docker服务
docker-compose up -d

# 5. 访问服务
# Web界面: http://localhost:8501
# 数据库管理: http://localhost:8081
# 缓存管理: http://localhost:8082
```

### Docker环境配置调整

```bash
# 数据库连接配置调整
sed -i 's/localhost:27017/mongodb:27017/g' .env
sed -i 's/localhost:6379/redis:6379/g' .env

# 或手动编辑.env文件
MONGODB_URL=mongodb://mongodb:27017/tradingagents
REDIS_URL=redis://redis:6379
```

## 🔧 常见升级问题

### 问题1: 依赖冲突

**症状**: `pip install` 失败，依赖版本冲突

**解决方案**:
```bash
# 创建新的虚拟环境
python -m venv env_new
source env_new/bin/activate  # Linux/macOS
# env_new\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 问题2: 配置文件格式变化

**症状**: 应用启动失败，配置错误

**解决方案**:
```bash
# 使用新的配置模板
cp .env .env.old
cp .env.example .env

# 手动迁移配置
# 对比.env.old和.env，迁移必要的配置
```

### 问题3: 数据库连接失败

**症状**: MongoDB/Redis连接失败

**解决方案**:
```bash
# Docker环境
# 确保使用容器服务名
MONGODB_URL=mongodb://mongodb:27017/tradingagents
REDIS_URL=redis://redis:6379

# 本地环境
# 确保使用localhost
MONGODB_URL=mongodb://localhost:27017/tradingagents
REDIS_URL=redis://localhost:6379
```

### 问题4: 端口冲突

**症状**: 服务启动失败，端口被占用

**解决方案**:
```bash
# 检查端口占用
netstat -tulpn | grep :8501

# 修改端口配置
# 编辑docker-compose.yml或.env文件
WEB_PORT=8502
MONGODB_PORT=27018
```

### 问题5: 权限问题

**症状**: Docker容器无法访问文件

**解决方案**:
```bash
# Linux/macOS
sudo chown -R $USER:$USER .
chmod -R 755 .

# Windows
# 确保Docker Desktop有足够权限
```

## 📊 升级验证清单

### 功能验证

- [ ] **Web界面正常访问** (http://localhost:8501)
- [ ] **股票分析功能正常**
  - [ ] A股分析 (如: 000001)
  - [ ] 美股分析 (如: AAPL)
- [ ] **LLM模型正常工作**
  - [ ] DeepSeek模型 (v0.1.7新增)
  - [ ] 阿里百炼模型
  - [ ] Google AI模型
- [ ] **数据库连接正常**
  - [ ] MongoDB连接
  - [ ] Redis连接
- [ ] **报告导出功能** (v0.1.7新增)
  - [ ] Markdown导出
  - [ ] Word导出
  - [ ] PDF导出
- [ ] **Docker服务正常** (如果使用)
  - [ ] 所有容器运行正常
  - [ ] 管理界面可访问

### 性能验证

- [ ] **响应速度**: 分析时间在预期范围内
- [ ] **内存使用**: 系统内存使用正常
- [ ] **错误处理**: 异常情况处理正常
- [ ] **数据持久化**: 数据正确保存和读取

## 🔄 回滚方案

### 如果升级失败

```bash
# 1. 停止新版本服务
docker-compose down
# 或停止本地服务

# 2. 恢复代码
git checkout v0.1.6  # 或之前的版本

# 3. 恢复配置
cp .env.backup .env

# 4. 恢复数据
mongorestore backup_20250713/

# 5. 重启服务
docker-compose up -d
# 或启动本地服务
```

## 📞 获取帮助

### 升级支持

如果在升级过程中遇到问题，可以通过以下方式获取帮助：

- 🐛 [GitHub Issues](https://github.com/hsliuping/TradingAgents-CN/issues)
- 💬 [GitHub Discussions](https://github.com/hsliuping/TradingAgents-CN/discussions)
- 📚 [完整文档](https://github.com/hsliuping/TradingAgents-CN/tree/main/docs)

### 提交问题时请包含

1. **当前版本**: 升级前的版本号
2. **目标版本**: 要升级到的版本号
3. **部署方式**: Docker或本地部署
4. **错误信息**: 完整的错误日志
5. **系统环境**: 操作系统、Python版本等

---

*最后更新: 2025-07-13*  
*版本: cn-0.1.7*  
*维护团队: TradingAgents-CN开发团队*
