# 在线工具配置指南

## 📋 概述

TradingAgents-CN 现在提供了更精细的在线工具控制机制，您可以通过环境变量灵活配置系统的在线/离线行为，而不再依赖于特定LLM提供商的启用状态。

## 🔧 配置字段说明

### 主要配置字段

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `ONLINE_TOOLS_ENABLED` | `false` | 在线工具总开关 |
| `ONLINE_NEWS_ENABLED` | `true` | 在线新闻工具开关 |
| `REALTIME_DATA_ENABLED` | `false` | 实时数据获取开关 |

### 配置优先级

1. **环境变量** (.env文件) - 最高优先级
2. **默认配置** (default_config.py) - 备用默认值

## 🎯 配置模式

### 1. 开发模式 (完全离线)
```bash
# .env 文件配置
ONLINE_TOOLS_ENABLED=false
ONLINE_NEWS_ENABLED=false
REALTIME_DATA_ENABLED=false
```

**特点:**
- ✅ 完全使用缓存数据
- ✅ 零API调用成本
- ✅ 适合开发和调试
- ❌ 数据可能不是最新的

### 2. 测试模式 (部分在线)
```bash
# .env 文件配置
ONLINE_TOOLS_ENABLED=false
ONLINE_NEWS_ENABLED=true
REALTIME_DATA_ENABLED=false
```

**特点:**
- ✅ 新闻数据实时获取
- ✅ 股价数据使用缓存
- ✅ 平衡功能和成本
- ✅ 适合功能测试

### 3. 生产模式 (完全在线)
```bash
# .env 文件配置
ONLINE_TOOLS_ENABLED=true
ONLINE_NEWS_ENABLED=true
REALTIME_DATA_ENABLED=true
```

**特点:**
- ✅ 获取最新实时数据
- ✅ 适合实盘交易
- ❌ API调用成本较高
- ❌ 需要稳定网络连接

## 🛠️ 配置方法

### 方法1: 修改 .env 文件
```bash
# 编辑 .env 文件
nano .env

# 添加或修改以下配置
ONLINE_TOOLS_ENABLED=true
ONLINE_NEWS_ENABLED=true
REALTIME_DATA_ENABLED=false
```

### 方法2: 环境变量设置
```bash
# Windows PowerShell
$env:ONLINE_TOOLS_ENABLED="true"
$env:ONLINE_NEWS_ENABLED="true"
$env:REALTIME_DATA_ENABLED="false"

# Linux/macOS
export ONLINE_TOOLS_ENABLED=true
export ONLINE_NEWS_ENABLED=true
export REALTIME_DATA_ENABLED=false
```

### 方法3: 代码中动态配置
```python
from tradingagents.default_config import DEFAULT_CONFIG

# 创建自定义配置
config = DEFAULT_CONFIG.copy()
config["online_tools"] = True
config["online_news"] = True
config["realtime_data"] = False

# 使用自定义配置
from tradingagents.graph.trading_graph import TradingAgentsGraph
ta = TradingAgentsGraph(config=config)
```

## 🔍 配置验证

### 使用测试脚本验证
```bash
python test_online_tools_config.py
```

### 手动验证配置
```python
from tradingagents.default_config import DEFAULT_CONFIG

print("当前配置:")
print(f"在线工具: {DEFAULT_CONFIG['online_tools']}")
print(f"在线新闻: {DEFAULT_CONFIG['online_news']}")
print(f"实时数据: {DEFAULT_CONFIG['realtime_data']}")
```

## 📊 工具影响范围

### 受 `ONLINE_TOOLS_ENABLED` 控制的工具
- 所有需要API调用的数据获取工具
- 实时股价数据获取
- 在线技术指标计算

### 受 `ONLINE_NEWS_ENABLED` 控制的工具
- `get_google_news` - Google新闻获取
- `get_reddit_news` - Reddit新闻获取
- `get_reddit_stock_info` - Reddit股票讨论
- `get_chinese_social_sentiment` - 中国社交媒体情绪

### 受 `REALTIME_DATA_ENABLED` 控制的工具
- 实时股价数据
- 实时市场指数
- 实时交易量数据

## ⚠️ 注意事项

### 1. 配置冲突处理
- 如果 `ONLINE_TOOLS_ENABLED=false` 但 `ONLINE_NEWS_ENABLED=true`，新闻工具仍然可用
- 这种设计允许更精细的控制

### 2. API配额管理
- 在线模式会消耗API配额
- 建议在开发阶段使用离线模式
- 生产环境根据需要选择合适的模式

### 3. 网络依赖
- 在线模式需要稳定的网络连接
- 网络异常时会自动回退到缓存数据

## 🔄 迁移指南

### 从旧配置迁移
如果您之前使用的是基于 `OPENAI_ENABLED` 的配置：

**旧方式:**
```bash
OPENAI_ENABLED=false  # 这会影响整个系统的在线状态
```

**新方式:**
```bash
OPENAI_ENABLED=false        # 只控制OpenAI模型
ONLINE_TOOLS_ENABLED=false  # 专门控制在线工具
ONLINE_NEWS_ENABLED=true    # 精细控制新闻工具
```

## 🎯 最佳实践

### 1. 开发阶段
```bash
ONLINE_TOOLS_ENABLED=false
ONLINE_NEWS_ENABLED=false
REALTIME_DATA_ENABLED=false
```

### 2. 测试阶段
```bash
ONLINE_TOOLS_ENABLED=false
ONLINE_NEWS_ENABLED=true
REALTIME_DATA_ENABLED=false
```

### 3. 生产环境
```bash
ONLINE_TOOLS_ENABLED=true
ONLINE_NEWS_ENABLED=true
REALTIME_DATA_ENABLED=true
```

## 🔧 故障排除

### 常见问题

1. **配置不生效**
   - 检查 .env 文件是否正确加载
   - 确认环境变量格式正确 (true/false)

2. **工具调用失败**
   - 检查相关API密钥是否配置
   - 确认网络连接是否正常

3. **数据不是最新的**
   - 确认 `REALTIME_DATA_ENABLED=true`
   - 检查数据源API是否正常

### 调试命令
```bash
# 检查当前配置
python -c "from tradingagents.default_config import DEFAULT_CONFIG; print(DEFAULT_CONFIG)"

# 测试配置系统
python test_online_tools_config.py

# 检查环境变量
echo $ONLINE_TOOLS_ENABLED
echo $ONLINE_NEWS_ENABLED
echo $REALTIME_DATA_ENABLED
```

---

通过这个新的配置系统，您可以更精确地控制TradingAgents-CN的在线行为，在功能需求和成本控制之间找到最佳平衡点。