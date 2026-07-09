# 数据目录配置指南 | Data Directory Configuration Guide

本指南详细说明如何在TradingAgents中配置数据目录路径，解决路径相关问题，并提供多种配置方式。

This guide explains how to configure data directory paths in TradingAgents, resolve path-related issues, and provides multiple configuration methods.

## 概述 | Overview

TradingAgents支持灵活的数据目录配置，允许用户：
- 自定义数据存储位置
- 通过环境变量配置
- 使用CLI命令管理
- 自动创建必要的目录结构

TradingAgents supports flexible data directory configuration, allowing users to:
- Customize data storage locations
- Configure via environment variables
- Manage through CLI commands
- Automatically create necessary directory structures

## 配置方法 | Configuration Methods

### 1. CLI命令配置 | CLI Command Configuration

#### 查看当前配置 | View Current Configuration
```bash
# 显示当前数据目录配置
python -m cli.main data-config
python -m cli.main data-config --show
```

#### 设置自定义数据目录 | Set Custom Data Directory
```bash
# Windows
python -m cli.main data-config --set "C:\MyTradingData"

# Linux/macOS
python -m cli.main data-config --set "/home/user/trading-data"
```

#### 重置为默认配置 | Reset to Default Configuration
```bash
python -m cli.main data-config --reset
```

### 2. 环境变量配置 | Environment Variable Configuration

#### Windows
```cmd
# 设置数据目录
set TRADINGAGENTS_DATA_DIR=C:\MyTradingData

# 设置缓存目录
set TRADINGAGENTS_CACHE_DIR=C:\MyTradingData\cache

# 设置结果目录
set TRADINGAGENTS_RESULTS_DIR=C:\MyTradingData\results
```

#### Linux/macOS
```bash
# 设置数据目录
export TRADINGAGENTS_DATA_DIR="/home/user/trading-data"

# 设置缓存目录
export TRADINGAGENTS_CACHE_DIR="/home/user/trading-data/cache"

# 设置结果目录
export TRADINGAGENTS_RESULTS_DIR="/home/user/trading-data/results"
```

#### .env文件配置 | .env File Configuration
```env
# 在项目根目录创建.env文件
TRADINGAGENTS_DATA_DIR=/path/to/your/data
TRADINGAGENTS_CACHE_DIR=/path/to/your/cache
TRADINGAGENTS_RESULTS_DIR=/path/to/your/results
```

### 3. 程序化配置 | Programmatic Configuration

```python
from tradingagents.dataflows.config import set_data_dir, get_data_dir
from tradingagents.config.config_manager import config_manager

# 设置数据目录
set_data_dir("/path/to/custom/data")

# 获取当前数据目录
current_dir = get_data_dir()
print(f"当前数据目录: {current_dir}")

# 确保目录存在
config_manager.ensure_directories_exist()
```

## 目录结构 | Directory Structure

配置数据目录后，系统会自动创建以下目录结构：

After configuring the data directory, the system automatically creates the following directory structure:

```
data/
├── cache/                          # 缓存目录 | Cache directory
├── finnhub_data/                   # Finnhub数据目录 | Finnhub data directory
│   ├── news_data/                  # 新闻数据 | News data
│   ├── insider_sentiment/          # 内部人情绪数据 | Insider sentiment data
│   └── insider_transactions/       # 内部人交易数据 | Insider transaction data
└── results/                        # 分析结果 | Analysis results
```

## 配置优先级 | Configuration Priority

配置的优先级从高到低：

Configuration priority from high to low:

1. **环境变量** | Environment Variables
2. **CLI设置** | CLI Settings
3. **默认配置** | Default Configuration

## 默认配置 | Default Configuration

如果没有自定义配置，系统使用以下默认路径：

If no custom configuration is provided, the system uses the following default paths:

- **Windows**: `C:\Users\{username}\Documents\TradingAgents\data`
- **Linux/macOS**: `~/Documents/TradingAgents/data`

## 常见问题解决 | Troubleshooting

### 问题1：路径不存在错误 | Issue 1: Path Not Found Error

**错误信息** | Error Message:
```
No such file or directory: '/data/finnhub_data/news_data'
```

**解决方案** | Solution:
```bash
# 使用CLI重新配置数据目录
python -m cli.main data-config --set "C:\YourDataPath"

# 或重置为默认配置
python -m cli.main data-config --reset
```

### 问题2：权限不足 | Issue 2: Permission Denied

**解决方案** | Solution:
1. 确保对目标目录有写权限
2. 选择用户目录下的路径
3. 在Windows上以管理员身份运行

### 问题3：跨平台路径问题 | Issue 3: Cross-Platform Path Issues

**解决方案** | Solution:
- 使用正斜杠 `/` 或双反斜杠 `\\` 在Windows上
- 避免硬编码路径分隔符
- 使用环境变量进行跨平台配置

## 验证配置 | Verify Configuration

### 1. 使用CLI验证 | Verify Using CLI
```bash
python -m cli.main data-config --show
```

### 2. 使用测试脚本验证 | Verify Using Test Script
```bash
python test_data_config_cli.py
```

### 3. 使用演示脚本验证 | Verify Using Demo Script
```bash
python examples/data_dir_config_demo.py
```

## 最佳实践 | Best Practices

1. **使用绝对路径** | Use Absolute Paths
   - 避免相对路径可能导致的问题
   - Avoid issues that relative paths might cause

2. **定期备份数据** | Regular Data Backup
   - 重要的分析结果应定期备份
   - Important analysis results should be backed up regularly

3. **环境隔离** | Environment Isolation
   - 不同项目使用不同的数据目录
   - Use different data directories for different projects

4. **权限管理** | Permission Management
   - 确保应用程序对数据目录有适当权限
   - Ensure the application has appropriate permissions to the data directory

## 高级配置 | Advanced Configuration

### 自定义子目录结构 | Custom Subdirectory Structure

```python
from tradingagents.config.config_manager import config_manager

# 自定义目录结构
custom_dirs = {
    'custom_data': 'my_custom_data',
    'reports': 'analysis_reports',
    'logs': 'application_logs'
}

# 创建自定义目录
for dir_name, dir_path in custom_dirs.items():
    full_path = os.path.join(config_manager.get_data_dir(), dir_path)
    os.makedirs(full_path, exist_ok=True)
```

### 动态配置更新 | Dynamic Configuration Updates

```python
# 运行时更新配置
config_manager.set_data_dir('/new/data/path')
config_manager.ensure_directories_exist()

# 验证更新
print(f"新数据目录: {config_manager.get_data_dir()}")
```

## 相关文件 | Related Files

- `tradingagents/config/config_manager.py` - 配置管理器
- `tradingagents/dataflows/config.py` - 数据流配置
- `cli/main.py` - CLI命令实现
- `examples/data_dir_config_demo.py` - 配置演示脚本
- `test_data_config_cli.py` - 配置测试脚本

## 技术支持 | Technical Support

如果遇到配置问题，请：
1. 查看错误日志
2. 运行诊断脚本
3. 检查权限设置
4. 参考故障排除指南

If you encounter configuration issues, please:
1. Check error logs
2. Run diagnostic scripts
3. Check permission settings
4. Refer to the troubleshooting guide