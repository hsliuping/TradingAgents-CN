# Finnhub新闻数据配置指南

## 问题描述

如果您遇到以下错误信息：

```
[DEBUG] FinnhubNewsTool调用，股票代码: AAPL 
获取新闻数据失败: [Errno 2] No such file or directory: '/Users/yluo/Documents/Code/ScAI/FR1-data\\finnhub_data\\news_data\\AAPL_data_formatted.json'
```

这表明存在以下问题：
1. **路径配置错误**：混合了Unix和Windows路径分隔符
2. **数据文件不存在**：缺少Finnhub新闻数据文件
3. **数据目录配置**：数据目录路径不正确

## 解决方案

### 1. 路径修复（已自动修复）

我们已经修复了 `tradingagents/default_config.py` 中的路径配置：

```python
# 修复前（硬编码Unix路径）
"data_dir": "/Users/yluo/Documents/Code/ScAI/FR1-data",

# 修复后（跨平台兼容路径）
"data_dir": os.path.join(os.path.expanduser("~"), "Documents", "TradingAgents", "data"),
```

### 2. 数据目录结构

正确的数据目录结构应该是：

```
~/Documents/TradingAgents/data/
├── finnhub_data/
│   ├── news_data/
│   │   ├── AAPL_data_formatted.json
│   │   ├── TSLA_data_formatted.json
│   │   └── ...
│   ├── insider_senti/
│   ├── insider_trans/
│   └── ...
└── other_data/
```

### 3. 获取Finnhub数据

#### 方法一：使用API下载（推荐）

1. **配置Finnhub API密钥**
   ```bash
   # 在.env文件中添加
   FINNHUB_API_KEY=your_finnhub_api_key_here
   ```

2. **运行数据下载脚本**
   ```bash
   # 下载新闻数据
   python scripts/download_finnhub_data.py --data-type news --symbols AAPL,TSLA,MSFT

   # 下载所有类型数据
   python scripts/download_finnhub_data.py --all

   # 强制刷新已存在的数据
   python scripts/download_finnhub_data.py --force-refresh

   # 下载指定天数的新闻数据
   python scripts/download_finnhub_data.py --data-type news --days 30 --symbols AAPL
   ```

3. **脚本参数说明**
   - `--data-type`: 数据类型 (news, sentiment, transactions, all)
   - `--symbols`: 股票代码，用逗号分隔
   - `--days`: 新闻数据天数 (默认7天)
   - `--force-refresh`: 强制刷新已存在的数据
   - `--all`: 下载所有类型数据

#### 方法二：手动创建测试数据

如果您只是想测试功能，可以创建示例数据：

```bash
# 运行示例数据生成脚本
python scripts/development/download_finnhub_sample_data.py

# 或者运行测试脚本，会自动创建示例数据
python tests/test_finnhub_news_fix.py
```

### 4. 验证配置

运行以下命令验证配置是否正确：

```bash
# 验证路径修复
python tests/test_finnhub_news_fix.py

# 测试新闻数据获取
python -c "
from tradingagents.dataflows.interface import get_finnhub_news
result = get_finnhub_news('AAPL', '2025-01-02', 7)
print(result[:200])
"
```

## 错误处理改进

我们已经改进了错误处理，现在当数据文件不存在时，会显示详细的错误信息：

```
⚠️ 无法获取AAPL的新闻数据 (2024-12-26 到 2025-01-02)
可能的原因：
1. 数据文件不存在或路径配置错误
2. 指定日期范围内没有新闻数据
3. 需要先下载或更新Finnhub新闻数据
建议：检查数据目录配置或重新获取新闻数据
```

## 配置选项

### 自定义数据目录

如果您想使用自定义数据目录，可以在代码中设置：

```python
from tradingagents.dataflows.config import set_config

# 设置自定义数据目录
config = {
    "data_dir": "C:/your/custom/data/directory"
}
set_config(config)
```

### 环境变量配置

您也可以通过环境变量设置：

```bash
# Windows
set TRADINGAGENTS_DATA_DIR=C:\your\custom\data\directory

# Linux/Mac
export TRADINGAGENTS_DATA_DIR=/your/custom/data/directory
```

## 常见问题

### Q1: 数据目录权限问题

**问题**：无法创建或写入数据目录

**解决方案**：
```bash
# Windows（以管理员身份运行）
mkdir "C:\Users\%USERNAME%\Documents\TradingAgents\data"

# Linux/Mac
mkdir -p ~/Documents/TradingAgents/data
chmod 755 ~/Documents/TradingAgents/data
```

### Q2: Finnhub API配额限制

**问题**：API调用次数超限

**解决方案**：
1. 升级Finnhub API计划
2. 使用缓存减少API调用
3. 限制数据获取频率

### Q3: 数据格式错误

**问题**：JSON文件格式不正确

**解决方案**：
```bash
# 验证JSON格式
python -c "import json; print(json.load(open('path/to/file.json')))"

# 重新下载数据
python scripts/download_finnhub_data.py --force-refresh
```

## 技术细节

### 修复的文件

1. **`tradingagents/default_config.py`**
   - 修复硬编码的Unix路径
   - 使用跨平台兼容的路径构建

2. **`tradingagents/dataflows/finnhub_utils.py`**
   - 添加文件存在性检查
   - 改进错误处理和调试信息
   - 使用UTF-8编码读取文件

3. **`tradingagents/dataflows/interface.py`**
   - 改进get_finnhub_news函数的错误提示
   - 提供详细的故障排除建议

### 路径处理逻辑

```python
# 跨平台路径构建
data_path = os.path.join(
    data_dir, 
    "finnhub_data", 
    "news_data", 
    f"{ticker}_data_formatted.json"
)

# 文件存在性检查
if not os.path.exists(data_path):
    print(f"⚠️ [DEBUG] 数据文件不存在: {data_path}")
    return {}
```

## 联系支持

如果您仍然遇到问题，请：

1. 运行诊断脚本：`python tests/test_finnhub_news_fix.py`
2. 检查日志输出中的详细错误信息
3. 确认Finnhub API密钥配置正确
4. 提供完整的错误堆栈信息

---

**更新日期**：2025-01-02  
**版本**：v1.0  
**适用范围**：TradingAgents-CN v0.1.3+