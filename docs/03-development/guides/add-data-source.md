# 添加新数据源指南

本文档说明如何在系统中添加新的数据源。

---

## 📋 概述

系统使用**统一的数据源编码管理**，所有数据源的编码定义都集中在一个文件中：

```
tradingagents/constants/data_sources.py
```

---

## 🚀 添加新数据源的步骤

### 步骤 1：在数据源编码枚举中添加新编码

**文件**：`tradingagents/constants/data_sources.py`

```python
class DataSourceCode(str, Enum):
    """数据源编码枚举"""
    
    # ... 现有数据源 ...
    
    # 添加新数据源
    YOUR_NEW_SOURCE = "your_new_source"  # 使用小写字母和下划线
```

**命名规范**：
- 枚举名：使用大写字母和下划线（例如：`ALPHA_VANTAGE`）
- 枚举值：使用小写字母和下划线（例如：`alpha_vantage`）
- 保持简洁明了

---

### 步骤 2：在数据源注册表中注册信息

**文件**：`tradingagents/constants/data_sources.py`

```python
DATA_SOURCE_REGISTRY: Dict[str, DataSourceInfo] = {
    # ... 现有数据源 ...
    
    # 注册新数据源
    DataSourceCode.YOUR_NEW_SOURCE: DataSourceInfo(
        code=DataSourceCode.YOUR_NEW_SOURCE,
        name="YourNewSource",
        display_name="你的新数据源",
        provider="提供商名称",
        description="数据源描述",
        supported_markets=["a_shares", "us_stocks", "hk_stocks"],  # 支持的市场
        requires_api_key=True,  # 是否需要 API 密钥
        is_free=False,  # 是否免费
        official_website="https://example.com",
        documentation_url="https://example.com/docs",
        features=["特性1", "特性2", "特性3"],
    ),
}
```

**字段说明**：
- `code`：数据源编码（必填）
- `name`：数据源名称（必填）
- `display_name`：显示名称（必填）
- `provider`：提供商（必填）
- `description`：描述（必填）
- `supported_markets`：支持的市场列表（必填）
  - `a_shares`：A股
  - `us_stocks`：美股
  - `hk_stocks`：港股
  - `crypto`：数字货币
  - `futures`：期货
- `requires_api_key`：是否需要 API 密钥（必填）
- `is_free`：是否免费（必填）
- `official_website`：官方网站（可选）
- `documentation_url`：文档地址（可选）
- `features`：特性列表（可选）

---

### 步骤 3：更新后端数据源类型枚举

**文件**：`app/models/config.py`

```python
class DataSourceType(str, Enum):
    """数据源类型枚举"""
    # ... 现有数据源 ...
    
    # 添加新数据源（使用统一编码）
    YOUR_NEW_SOURCE = "your_new_source"
```

---

### 步骤 4：实现数据源 Provider

**创建文件**：`tradingagents/dataflows/providers/{market}/your_new_source.py`

例如，如果是美股数据源：
```
tradingagents/dataflows/providers/us/your_new_source.py
```

**实现示例**：

```python
"""
YourNewSource 数据提供器
"""

import requests
from typing import Dict, List, Optional, Any
from tradingagents.utils.logging_init import get_logger

logger = get_logger("default")


class YourNewSourceProvider:
    """YourNewSource 数据提供器"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化
        
        Args:
            api_key: API 密钥
        """
        self.api_key = api_key
        self.base_url = "https://api.example.com"
    
    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        获取股票历史数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）
        
        Returns:
            股票数据字典
        """
        try:
            # 实现数据获取逻辑
            url = f"{self.base_url}/stock/{symbol}"
            params = {
                "start": start_date,
                "end": end_date,
                "apikey": self.api_key
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"✅ [YourNewSource] 获取 {symbol} 数据成功")
            return data
        except Exception as e:
            logger.error(f"❌ [YourNewSource] 获取 {symbol} 数据失败: {e}")
            raise
    
    # 实现其他必要的方法...


# 全局实例
_provider_instance = None


def get_your_new_source_provider() -> YourNewSourceProvider:
    """获取 YourNewSource 提供器实例"""
    global _provider_instance
    if _provider_instance is None:
        import os
        api_key = os.getenv("YOUR_NEW_SOURCE_API_KEY")
        _provider_instance = YourNewSourceProvider(api_key=api_key)
    return _provider_instance
```

---

### 步骤 5：在数据源管理器中集成

**文件**：`tradingagents/dataflows/data_source_manager.py`

#### 5.1 更新数据源枚举（如果是中国市场）

```python
class ChinaDataSource(Enum):
    """中国股票数据源枚举"""
    # ... 现有数据源 ...
    YOUR_NEW_SOURCE = "your_new_source"
```

#### 5.2 更新可用数据源检测

```python
def _check_available_sources(self) -> List[ChinaDataSource]:
    """检查可用的数据源"""
    available = []
    
    # ... 现有检测逻辑 ...
    
    # 检查新数据源
    try:
        from .providers.china.your_new_source import get_your_new_source_provider
        provider = get_your_new_source_provider()
        if provider:
            available.append(ChinaDataSource.YOUR_NEW_SOURCE)
            logger.info("✅ YourNewSource 数据源可用")
    except Exception as e:
        logger.warning(f"⚠️ YourNewSource 数据源不可用: {e}")
    
    return available
```

#### 5.3 添加数据获取方法

```python
def _get_your_new_source_data(self, symbol: str, start_date: str, end_date: str, period: str = "daily") -> str:
    """使用 YourNewSource 获取数据"""
    try:
        from .providers.china.your_new_source import get_your_new_source_provider
        provider = get_your_new_source_provider()
        
        data = provider.get_stock_data(symbol, start_date, end_date)
        
        # 转换为标准格式
        # ... 数据转换逻辑 ...
        
        return formatted_data
    except Exception as e:
        logger.error(f"❌ YourNewSource 获取数据失败: {e}")
        return f"❌ YourNewSource 获取数据失败: {e}"
```

#### 5.4 更新数据源映射

```python
def _get_data_source_priority_order(self, symbol: Optional[str] = None) -> List[ChinaDataSource]:
    """从数据库获取数据源优先级顺序"""
    # ...
    
    # 转换为 ChinaDataSource 枚举
    source_mapping = {
        'tushare': ChinaDataSource.TUSHARE,
        'akshare': ChinaDataSource.AKSHARE,
        'baostock': ChinaDataSource.BAOSTOCK,
        'your_new_source': ChinaDataSource.YOUR_NEW_SOURCE,  # 添加新数据源
    }
    
    # ...
```

#### 5.5 更新降级逻辑

```python
def _try_fallback_sources(self, symbol: str, start_date: str, end_date: str, period: str = "daily") -> str:
    """尝试备用数据源"""
    # ...
    
    for source in fallback_order:
        if source != self.current_source and source in self.available_sources:
            try:
                # ... 现有数据源 ...
                
                # 添加新数据源
                elif source == ChinaDataSource.YOUR_NEW_SOURCE:
                    result = self._get_your_new_source_data(symbol, start_date, end_date, period)
                
                # ...
```

---

### 步骤 6：更新前端配置

#### 6.1 更新数据源类型选项

**文件**：`frontend/src/views/Settings/components/DataSourceConfigDialog.vue`

```typescript
const dataSourceTypes = [
  { label: 'AKShare', value: 'akshare' },
  { label: 'Tushare', value: 'tushare' },
  // ... 现有数据源 ...
  { label: 'YourNewSource', value: 'your_new_source' },  // 添加新数据源
]
```

#### 6.2 更新 API 常量

**文件**：`frontend/src/api/config.ts`

```typescript
export const DATA_SOURCE_TYPES = {
  AKSHARE: 'akshare',
  TUSHARE: 'tushare',
  // ... 现有数据源 ...
  YOUR_NEW_SOURCE: 'your_new_source',  // 添加新数据源
} as const
```

---

### 步骤 7：添加环境变量配置

**文件**：`.env.example`

```bash
# YourNewSource API 配置
YOUR_NEW_SOURCE_API_KEY=your_api_key_here
YOUR_NEW_SOURCE_ENABLED=true
```

---

### 步骤 8：更新文档

#### 8.1 更新数据源文档

**文件**：`docs/integration/data-sources/YOUR_NEW_SOURCE.md`

创建新数据源的使用文档，包括：
- 数据源介绍
- 获取 API 密钥的步骤
- 配置方法
- 使用示例
- 注意事项

#### 8.2 更新 README

在 `README.md` 中添加新数据源的说明。

---

## ✅ 测试清单

添加新数据源后，请确保完成以下测试：

- [ ] 数据源编码已在 `data_sources.py` 中定义
- [ ] 数据源信息已在 `DATA_SOURCE_REGISTRY` 中注册
- [ ] Provider 已实现并可以正常获取数据
- [ ] 数据源管理器可以检测到新数据源
- [ ] 数据源可以正常切换和使用
- [ ] 降级逻辑包含新数据源
- [ ] 前端可以配置新数据源
- [ ] 环境变量配置正确
- [ ] 文档已更新

---

## 📝 示例：添加 Polygon.io 数据源

### 1. 添加编码

```python
# tradingagents/constants/data_sources.py
class DataSourceCode(str, Enum):
    # ...
    POLYGON = "polygon"
```

### 2. 注册信息

```python
DATA_SOURCE_REGISTRY = {
    # ...
    DataSourceCode.POLYGON: DataSourceInfo(
        code=DataSourceCode.POLYGON,
        name="Polygon",
        display_name="Polygon.io",
        provider="Polygon.io",
        description="美股实时和历史数据接口",
        supported_markets=["us_stocks"],
        requires_api_key=True,
        is_free=True,
        official_website="https://polygon.io",
        documentation_url="https://polygon.io/docs",
        features=["实时行情", "历史数据", "期权数据", "新闻资讯"],
    ),
}
```

### 3. 实现 Provider

```python
# tradingagents/dataflows/providers/us/polygon.py
class PolygonProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
    
    def get_stock_data(self, symbol: str, start_date: str, end_date: str):
        # 实现数据获取逻辑
        pass
```

### 4. 集成到数据源管理器

```python
# tradingagents/dataflows/data_source_manager.py
source_mapping = {
    # ...
    'polygon': ChinaDataSource.POLYGON,
}
```

---

## 🎯 最佳实践

1. **统一编码**：始终使用 `tradingagents/constants/data_sources.py` 中定义的编码
2. **完整注册**：确保在 `DATA_SOURCE_REGISTRY` 中提供完整的数据源信息
3. **错误处理**：Provider 中要有完善的错误处理和日志记录
4. **数据标准化**：确保返回的数据格式符合系统标准
5. **文档完善**：提供清晰的使用文档和示例
6. **测试充分**：添加单元测试和集成测试

---

## 📚 相关文档

- [数据源编码定义](../../tradingagents/constants/data_sources.py)
- [数据源管理器](../../tradingagents/dataflows/data_source_manager.py)
- [数据源配置模型](../../app/models/config.py)

---

**添加完成后，记得提交代码并更新 CHANGELOG！** 🎉

