# 美股数据源升级计划

> **目标**: 参考原版 TradingAgents 实现，为美股添加 yfinance 和 Alpha Vantage 支持，提高数据准确性

**创建日期**: 2025-11-10  
**状态**: 规划中  
**优先级**: 高

---

## 📋 背景

原版 TradingAgents 已经从 Finnhub 切换到 yfinance + Alpha Vantage 的组合：
- **yfinance**: 用于股票价格和技术指标数据
- **Alpha Vantage**: 用于基本面和新闻数据（准确度更高）

这个升级显著提高了新闻数据的准确性和可靠性。

---

## 🎯 目标

1. ✅ 为美股添加 yfinance 数据源支持
2. ✅ 为美股添加 Alpha Vantage 数据源支持（基本面 + 新闻）
3. ✅ 实现灵活的数据源配置机制
4. ✅ 保持与现有 A股/港股数据源的兼容性
5. ✅ 提供数据源切换和降级机制

---

## 🏗️ 原版架构分析

### 1. 数据源文件结构

```
tradingagents/dataflows/
├── y_finance.py                    # yfinance 实现
├── yfin_utils.py                   # yfinance 工具函数
├── alpha_vantage.py                # Alpha Vantage 入口
├── alpha_vantage_common.py         # Alpha Vantage 公共函数
├── alpha_vantage_stock.py          # Alpha Vantage 股票数据
├── alpha_vantage_fundamentals.py   # Alpha Vantage 基本面数据
├── alpha_vantage_news.py           # Alpha Vantage 新闻数据
├── alpha_vantage_indicator.py      # Alpha Vantage 技术指标
├── interface.py                    # 统一接口层
├── config.py                       # 数据源配置
└── ...
```

### 2. 配置机制

原版使用两级配置：

```python
DEFAULT_CONFIG = {
    # 类别级配置（默认）
    "data_vendors": {
        "core_stock_apis": "yfinance",       # 股票价格数据
        "technical_indicators": "yfinance",  # 技术指标
        "fundamental_data": "alpha_vantage", # 基本面数据
        "news_data": "alpha_vantage",        # 新闻数据
    },
    # 工具级配置（优先级更高）
    "tool_vendors": {
        # 可以覆盖特定工具的数据源
        # "get_stock_data": "alpha_vantage",
        # "get_news": "openai",
    },
}
```

### 3. 数据源选择逻辑

```python
def get_vendor(tool_name, category, config):
    """
    获取工具的数据源
    1. 优先使用 tool_vendors 中的配置
    2. 其次使用 data_vendors 中的类别配置
    3. 最后使用默认值
    """
    tool_vendors = config.get("tool_vendors", {})
    data_vendors = config.get("data_vendors", {})
    
    # 工具级配置优先
    if tool_name in tool_vendors:
        return tool_vendors[tool_name]
    
    # 类别级配置
    if category in data_vendors:
        return data_vendors[category]
    
    # 默认值
    return "yfinance"
```

---

## 📦 实现计划

### 阶段 1: 添加 yfinance 支持 ⏳

**目标**: 实现 yfinance 作为美股数据源

#### 1.1 创建 yfinance 数据提供者

**文件**: `tradingagents/dataflows/providers/us/yfinance_provider.py`

**功能**:
- ✅ 获取股票价格数据（OHLCV）
- ✅ 获取技术指标（MA、MACD、RSI、BOLL 等）
- ✅ 获取公司基本信息
- ✅ 数据格式化和标准化

**参考**: 原版 `tradingagents/dataflows/y_finance.py`

#### 1.2 创建 yfinance 工具函数

**文件**: `tradingagents/dataflows/providers/us/yfinance_utils.py`

**功能**:
- ✅ 数据获取辅助函数
- ✅ 错误处理和重试机制
- ✅ 数据缓存机制

**参考**: 原版 `tradingagents/dataflows/yfin_utils.py`

---

### 阶段 2: 添加 Alpha Vantage 支持 ⏳

**目标**: 实现 Alpha Vantage 获取基本面和新闻数据

#### 2.1 创建 Alpha Vantage 公共模块

**文件**: `tradingagents/dataflows/providers/us/alpha_vantage_common.py`

**功能**:
- ✅ API 请求封装
- ✅ 错误处理和重试
- ✅ 速率限制处理
- ✅ 响应解析

**参考**: 原版 `tradingagents/dataflows/alpha_vantage_common.py`

#### 2.2 创建 Alpha Vantage 基本面数据提供者

**文件**: `tradingagents/dataflows/providers/us/alpha_vantage_fundamentals.py`

**功能**:
- ✅ 获取公司概况（Company Overview）
- ✅ 获取财务报表（Income Statement, Balance Sheet, Cash Flow）
- ✅ 获取估值指标（PE、PB、EPS 等）
- ✅ 数据格式化

**参考**: 原版 `tradingagents/dataflows/alpha_vantage_fundamentals.py`

#### 2.3 创建 Alpha Vantage 新闻数据提供者

**文件**: `tradingagents/dataflows/providers/us/alpha_vantage_news.py`

**功能**:
- ✅ 获取公司新闻
- ✅ 新闻过滤和排序
- ✅ 情感分析数据
- ✅ 新闻格式化

**参考**: 原版 `tradingagents/dataflows/alpha_vantage_news.py`

---

### 阶段 3: 实现数据源配置机制 ⏳

**目标**: 实现灵活的数据源切换机制

#### 3.1 扩展配置系统

**文件**: `app/core/config.py`

**新增配置**:
```python
class Settings(BaseSettings):
    # ... 现有配置 ...
    
    # 美股数据源配置
    US_DATA_VENDORS: Dict[str, str] = Field(
        default={
            "core_stock_apis": "yfinance",
            "technical_indicators": "yfinance",
            "fundamental_data": "alpha_vantage",
            "news_data": "alpha_vantage",
        },
        description="美股数据源配置"
    )
    
    # 工具级数据源配置（可选，优先级更高）
    US_TOOL_VENDORS: Dict[str, str] = Field(
        default={},
        description="美股工具级数据源配置"
    )
    
    # Alpha Vantage API 配置
    ALPHA_VANTAGE_API_KEY: Optional[str] = Field(
        default=None,
        description="Alpha Vantage API Key"
    )
    ALPHA_VANTAGE_BASE_URL: str = Field(
        default="https://www.alphavantage.co/query",
        description="Alpha Vantage API Base URL"
    )
```

#### 3.2 创建数据源管理器

**文件**: `tradingagents/dataflows/providers/us/data_source_manager.py`

**功能**:
- ✅ 数据源选择逻辑
- ✅ 数据源降级机制（主数据源失败时切换到备用数据源）
- ✅ 数据源健康检查
- ✅ 统一的错误处理

**示例**:
```python
class USDataSourceManager:
    def __init__(self, config):
        self.config = config
        self.vendors = {
            "yfinance": YFinanceProvider(),
            "alpha_vantage": AlphaVantageProvider(),
            "finnhub": FinnhubProvider(),  # 保留作为备用
        }
    
    def get_vendor(self, tool_name, category):
        """获取工具的数据源"""
        # 1. 工具级配置优先
        tool_vendors = self.config.get("US_TOOL_VENDORS", {})
        if tool_name in tool_vendors:
            return self.vendors[tool_vendors[tool_name]]
        
        # 2. 类别级配置
        data_vendors = self.config.get("US_DATA_VENDORS", {})
        if category in data_vendors:
            return self.vendors[data_vendors[category]]
        
        # 3. 默认值
        return self.vendors["yfinance"]
    
    def get_stock_data(self, ticker, start_date, end_date):
        """获取股票数据，支持降级"""
        vendor = self.get_vendor("get_stock_data", "core_stock_apis")
        
        try:
            return vendor.get_stock_data(ticker, start_date, end_date)
        except Exception as e:
            logger.warning(f"主数据源失败: {e}，尝试备用数据源")
            # 降级到备用数据源
            fallback_vendor = self.vendors["finnhub"]
            return fallback_vendor.get_stock_data(ticker, start_date, end_date)
```

---

### 阶段 4: 集成到现有系统 ⏳

**目标**: 将新数据源集成到现有的美股数据流中

#### 4.1 更新美股数据接口

**文件**: `tradingagents/dataflows/providers/us/optimized.py`

**修改**:
- ✅ 使用数据源管理器替代直接调用 Finnhub
- ✅ 保持接口兼容性
- ✅ 添加数据源选择日志

#### 4.2 更新工具定义

**文件**: `tradingagents/tools/stock_tools.py`

**修改**:
- ✅ 更新工具描述，说明支持的数据源
- ✅ 添加数据源参数（可选）

---

### 阶段 5: 测试和验证 ⏳

**目标**: 确保新数据源的准确性和稳定性

#### 5.1 单元测试

**文件**: `tests/test_us_data_sources.py`

**测试内容**:
- ✅ yfinance 数据获取
- ✅ Alpha Vantage 数据获取
- ✅ 数据源切换机制
- ✅ 降级机制
- ✅ 错误处理

#### 5.2 集成测试

**文件**: `tests/test_us_stock_analysis.py`

**测试内容**:
- ✅ 完整的美股分析流程
- ✅ 不同数据源的对比
- ✅ 性能测试

#### 5.3 数据质量验证

**对比项目**:
- ✅ 股票价格数据准确性
- ✅ 技术指标计算准确性
- ✅ 基本面数据完整性
- ✅ 新闻数据相关性和时效性

---

### 阶段 6: 文档和配置 ⏳

**目标**: 完善文档和配置示例

#### 6.1 更新文档

**文件**: 
- `docs/integration/data-sources/US_DATA_SOURCES.md` - 美股数据源说明
- `docs/guides/INSTALLATION_GUIDE_V1.md` - 更新安装指南
- `README.md` - 更新功能说明

**内容**:
- ✅ 数据源选项说明
- ✅ API 密钥获取方法
- ✅ 配置示例
- ✅ 最佳实践

#### 6.2 更新配置示例

**文件**: `.env.example`

**新增**:
```env
# ==================== Alpha Vantage API 配置 ====================
# Alpha Vantage API Key（用于美股基本面和新闻数据）
# 获取地址: https://www.alphavantage.co/support/#api-key
# 免费版: 60 requests/minute, 无每日限制（TradingAgents 用户）
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key_here

# ==================== 美股数据源配置 ====================
# 数据源选项: yfinance, alpha_vantage, finnhub
US_CORE_STOCK_APIS=yfinance
US_TECHNICAL_INDICATORS=yfinance
US_FUNDAMENTAL_DATA=alpha_vantage
US_NEWS_DATA=alpha_vantage
```

---

## 📊 数据源对比

| 数据类型 | Finnhub (旧) | yfinance (新) | Alpha Vantage (新) | 推荐 |
|---------|-------------|---------------|-------------------|------|
| **股票价格** | ✅ 支持 | ✅ 支持 | ✅ 支持 | yfinance |
| **技术指标** | ⚠️ 需计算 | ✅ 内置 | ✅ API | yfinance |
| **基本面数据** | ⚠️ 有限 | ⚠️ 有限 | ✅ 完整 | Alpha Vantage |
| **新闻数据** | ⚠️ 准确度低 | ❌ 不支持 | ✅ 准确度高 | Alpha Vantage |
| **免费额度** | 60/min | 无限制 | 60/min (TradingAgents) | - |
| **数据质量** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | - |

---

## 🚀 实施时间表

| 阶段 | 任务 | 预计时间 | 状态 |
|------|------|---------|------|
| 1 | yfinance 支持 | 2-3 天 | ⏳ 待开始 |
| 2 | Alpha Vantage 支持 | 3-4 天 | ⏳ 待开始 |
| 3 | 数据源配置机制 | 1-2 天 | ⏳ 待开始 |
| 4 | 系统集成 | 1-2 天 | ⏳ 待开始 |
| 5 | 测试和验证 | 2-3 天 | ⏳ 待开始 |
| 6 | 文档和配置 | 1 天 | ⏳ 待开始 |
| **总计** | | **10-15 天** | |

---

## ⚠️ 注意事项

1. **API 密钥管理**:
   - Alpha Vantage 需要 API Key
   - 免费版有速率限制（60 requests/minute）
   - TradingAgents 用户有特殊额度支持

2. **向后兼容性**:
   - 保留 Finnhub 作为备用数据源
   - 默认配置使用新数据源
   - 用户可以通过配置切换回旧数据源

3. **数据一致性**:
   - 不同数据源的数据格式可能不同
   - 需要统一的数据标准化层
   - 注意时区和日期格式

4. **错误处理**:
   - 实现降级机制
   - 记录详细的错误日志
   - 提供友好的错误提示

---

## 📚 参考资源

- **原版 TradingAgents**: https://github.com/TauricResearch/TradingAgents
- **yfinance 文档**: https://pypi.org/project/yfinance/
- **Alpha Vantage 文档**: https://www.alphavantage.co/documentation/
- **Alpha Vantage API Key**: https://www.alphavantage.co/support/#api-key

---

**最后更新**: 2025-11-10  
**负责人**: AI Assistant  
**审核人**: 待定

