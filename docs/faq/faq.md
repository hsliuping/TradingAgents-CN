# 常见问题解答 (FAQ)

## 概述

本文档收集了用户在使用 TradingAgents 框架时最常遇到的问题和解答，帮助您快速解决常见问题。

## 🚀 安装和配置

### Q1: 安装时出现依赖冲突怎么办？

**A:** 依赖冲突通常是由于不同包的版本要求不兼容导致的。解决方法：

```bash
# 方法1: 使用新的虚拟环境
conda create -n tradingagents-clean python=3.11
conda activate tradingagents-clean
pip install -r requirements.txt

# 方法2: 使用 pip-tools 解决冲突
pip install pip-tools
pip-compile requirements.in
pip-sync requirements.txt

# 方法3: 逐个安装核心依赖
pip install langchain-openai langgraph finnhub-python pandas
```

### Q2: API 密钥设置后仍然报错？

**A:** 检查以下几个方面：

1. **环境变量设置**：
```bash
# 检查环境变量是否正确设置
echo $OPENAI_API_KEY
echo $FINNHUB_API_KEY

# Windows 用户
echo %OPENAI_API_KEY%
echo %FINNHUB_API_KEY%
```

2. **密钥格式验证**：
```python
import os
# OpenAI 密钥应该以 'sk-' 开头
openai_key = os.getenv('OPENAI_API_KEY')
print(f"OpenAI Key: {openai_key[:10]}..." if openai_key else "Not set")

# FinnHub 密钥是字母数字组合
finnhub_key = os.getenv('FINNHUB_API_KEY')
print(f"FinnHub Key: {finnhub_key[:10]}..." if finnhub_key else "Not set")
```

3. **权限检查**：
```python
# 测试 API 连接
import openai
import finnhub

# 测试 OpenAI
try:
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=5
    )
    print("OpenAI API 连接成功")
except Exception as e:
    print(f"OpenAI API 错误: {e}")

# 测试 FinnHub
try:
    finnhub_client = finnhub.Client(api_key=os.getenv('FINNHUB_API_KEY'))
    quote = finnhub_client.quote('AAPL')
    print("FinnHub API 连接成功")
except Exception as e:
    print(f"FinnHub API 错误: {e}")
```

### Q3: 支持哪些 Python 版本？

**A:** TradingAgents 支持 Python 3.10, 3.11, 和 3.12。推荐使用 Python 3.11 以获得最佳性能和兼容性。

```bash
# 检查 Python 版本
python --version

# 如果版本不符合要求，使用 pyenv 安装
pyenv install 3.11.7
pyenv global 3.11.7
```

## 💰 成本和使用

### Q4: 使用 TradingAgents 的成本是多少？

**A:** 成本主要来自 LLM API 调用：

**典型成本估算**（单次分析）：
- **经济模式**：$0.01-0.05（使用 gpt-4o-mini）
- **标准模式**：$0.05-0.15（使用 gpt-4o）
- **高精度模式**：$0.10-0.30（使用 gpt-4o + 多轮辩论）

**成本优化建议**：
```python
# 低成本配置
cost_optimized_config = {
    "deep_think_llm": "gpt-4o-mini",
    "quick_think_llm": "gpt-4o-mini",
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "online_tools": False  # 使用缓存数据
}
```

### Q5: 如何控制 API 调用成本？

**A:** 多种成本控制策略：

1. **设置预算限制**：
```python
class BudgetController:
    def __init__(self, daily_budget=50):
        self.daily_budget = daily_budget
        self.current_usage = 0
    
    def check_budget(self, estimated_cost):
        if self.current_usage + estimated_cost > self.daily_budget:
            raise Exception("Daily budget exceeded")
        return True
```

2. **使用缓存**：
```python
config = {
    "online_tools": False,  # 使用缓存数据
    "cache_duration": 3600  # 1小时缓存
}
```

3. **选择性分析师**：
```python
# 只使用核心分析师
selected_analysts = ["market", "fundamentals"]  # 而不是全部四个
```

## 🔧 技术问题

### Q6: 分析速度太慢怎么办？

**A:** 多种优化方法：

1. **并行处理**：
```python
config = {
    "parallel_analysis": True,
    "max_workers": 4
}
```

2. **使用更快的模型**：
```python
config = {
    "deep_think_llm": "gpt-4o-mini",  # 更快的模型
    "quick_think_llm": "gpt-4o-mini"
}
```

3. **减少辩论轮次**：
```python
config = {
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1
}
```

4. **启用缓存**：
```python
config = {
    "online_tools": True,
    "cache_enabled": True
}
```

### Q7: 内存使用过高怎么解决？

**A:** 内存优化策略：

1. **限制缓存大小**：
```python
config = {
    "memory_cache": {
        "max_size": 500,  # 减少缓存项数量
        "cleanup_threshold": 0.7
    }
}
```

2. **分批处理**：
```python
# 分批分析多只股票
def batch_analysis(symbols, batch_size=5):
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i+batch_size]
        # 处理批次
        yield analyze_batch(batch)
```

3. **清理资源**：
```python
import gc

def analyze_with_cleanup(symbol, date):
    try:
        result = ta.propagate(symbol, date)
        return result
    finally:
        gc.collect()  # 强制垃圾回收
```

### Q8: 网络连接不稳定导致分析失败？

**A:** 网络问题解决方案：

1. **重试机制**：
```python
import time
from functools import wraps

def retry_on_failure(max_retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    time.sleep(delay * (2 ** attempt))
            return None
        return wrapper
    return decorator

@retry_on_failure(max_retries=3)
def robust_analysis(symbol, date):
    return ta.propagate(symbol, date)
```

2. **超时设置**：
```python
config = {
    "timeout": 60,  # 60秒超时
    "connect_timeout": 10
}
```

3. **代理设置**：
```python
import os
os.environ['HTTP_PROXY'] = 'http://proxy.company.com:8080'
os.environ['HTTPS_PROXY'] = 'https://proxy.company.com:8080'
```

## 📊 数据和分析

### Q9: 某些股票无法获取数据？

**A:** 数据获取问题排查：

1. **检查股票代码**：
```python
# 确保使用正确的股票代码格式
symbols = {
    "US": "AAPL",           # 美股
    "HK": "0700.HK",        # 港股
    "CN": "000001.SZ"       # A股
}
```

2. **验证数据源**：
```python
def check_data_availability(symbol):
    try:
        # 检查 FinnHub
        finnhub_data = finnhub_client.quote(symbol)
        print(f"FinnHub: {symbol} - OK")
    except:
        print(f"FinnHub: {symbol} - Failed")
    
    try:
        # 检查 Yahoo Finance
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info
        print(f"Yahoo: {symbol} - OK")
    except:
        print(f"Yahoo: {symbol} - Failed")
```

3. **使用备用数据源**：
```python
config = {
    "data_sources": {
        "primary": "finnhub",
        "fallback": ["yahoo", "alpha_vantage"]
    }
}
```

### Q10: 分析结果不准确或不合理？

**A:** 提高分析准确性的方法：

1. **增加辩论轮次**：
```python
config = {
    "max_debate_rounds": 3,  # 增加辩论轮次
    "max_risk_discuss_rounds": 2
}
```

2. **使用更强的模型**：
```python
config = {
    "deep_think_llm": "gpt-4o",  # 使用更强的模型
    "quick_think_llm": "gpt-4o-mini"
}
```

3. **调整分析师权重**：
```python
config = {
    "analyst_weights": {
        "fundamentals": 0.4,  # 增加基本面权重
        "technical": 0.3,
        "news": 0.2,
        "social": 0.1
    }
}
```

4. **启用更多数据源**：
```python
config = {
    "online_tools": True,
    "data_sources": ["finnhub", "yahoo", "reddit", "google_news"]
}
```

## 🛠️ 开发和扩展

### Q11: 如何创建自定义智能体？

**A:** 创建自定义智能体的步骤：

1. **继承基础类**：
```python
from tradingagents.agents.analysts.base_analyst import BaseAnalyst

class CustomAnalyst(BaseAnalyst):
    def __init__(self, llm, config):
        super().__init__(llm, config)
        self.custom_tools = self._initialize_custom_tools()
    
    def perform_analysis(self, data: Dict) -> Dict:
        # 实现自定义分析逻辑
        return {
            "custom_score": 0.75,
            "custom_insights": ["insight1", "insight2"],
            "recommendation": "buy"
        }
```

2. **注册到框架**：
```python
# 在配置中添加自定义智能体
config = {
    "custom_analysts": {
        "custom": CustomAnalyst
    }
}
```

### Q12: 如何集成新的数据源？

**A:** 集成新数据源的方法：

1. **创建数据提供器**：
```python
class CustomDataProvider:
    def __init__(self, api_key):
        self.api_key = api_key
    
    def get_data(self, symbol):
        # 实现数据获取逻辑
        return {"custom_metric": 0.85}
```

2. **注册数据源**：
```python
config = {
    "custom_data_sources": {
        "custom_provider": CustomDataProvider
    }
}
```

## 🚨 错误处理

### Q13: 常见错误代码及解决方法

**A:** 主要错误类型和解决方案：

| 错误类型 | 原因 | 解决方法 |
|---------|------|---------|
| `API_KEY_INVALID` | API密钥无效 | 检查密钥格式和权限 |
| `RATE_LIMIT_EXCEEDED` | 超过API限制 | 降低调用频率或升级账户 |
| `NETWORK_TIMEOUT` | 网络超时 | 检查网络连接，增加超时时间 |
| `DATA_NOT_FOUND` | 数据不存在 | 检查股票代码，使用备用数据源 |
| `INSUFFICIENT_MEMORY` | 内存不足 | 减少缓存大小，分批处理 |

### Q14: 如何启用调试模式？

**A:** 调试模式配置：

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 启用调试模式
config = {
    "debug": True,
    "log_level": "DEBUG",
    "save_intermediate_results": True
}

# 使用调试配置
ta = TradingAgentsGraph(debug=True, config=config)
```

## 📞 获取帮助

### Q15: 在哪里可以获得更多帮助？

**A:** 多种获取帮助的渠道：

1. **官方文档**: [docs/README.md](../README.md)
2. **GitHub Issues**: [提交问题](https://github.com/TauricResearch/TradingAgents/issues)
3. **Discord 社区**: [加入讨论](https://discord.com/invite/hk9PGKShPK)
4. **邮箱支持**: support@tauric.ai

### Q16: 如何报告 Bug？

**A:** Bug 报告模板：

```markdown
## Bug 描述
简要描述遇到的问题

## 复现步骤
1. 执行的代码
2. 使用的配置
3. 输入的参数

## 预期行为
描述期望的结果

## 实际行为
描述实际发生的情况

## 环境信息
- Python 版本:
- TradingAgents 版本:
- 操作系统:
- 相关依赖版本:

## 错误日志
粘贴完整的错误信息
```

如果您的问题没有在这里找到答案，请通过上述渠道联系我们获取帮助。
