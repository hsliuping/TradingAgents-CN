# 工具层设计 (Tool Layer Design)

## 概述

工具层是整个插件化架构的基础，负责管理所有可被 Agent 调用的工具函数。本设计实现工具的独立定义、自动注册、动态发现。

## 设计目标

1. **独立性**：每个工具独立文件，独立测试
2. **可发现**：自动扫描并注册工具
3. **可配置**：工具元数据支持运行时修改
4. **向后兼容**：兼容现有 Toolkit 类中的工具

## 目录结构

```
core/tools/
├── __init__.py
├── registry.py          # 工具注册中心（增强）
├── base.py              # 工具基类
├── factory.py           # 工具工厂（新增）
├── decorators.py        # 装饰器（新增）
├── config.py            # 工具元数据配置
├── loader.py            # 工具加载器（新增）
│
├── market/              # 市场数据工具
│   ├── __init__.py
│   ├── stock_data.py    # 股票数据工具
│   ├── kline_data.py    # K线数据工具
│   └── realtime.py      # 实时行情工具
│
├── news/                # 新闻数据工具
│   ├── __init__.py
│   ├── finnhub.py       # Finnhub 新闻
│   ├── reddit.py        # Reddit 新闻
│   └── china_news.py    # 中国新闻
│
├── fundamentals/        # 基本面数据工具
│   ├── __init__.py
│   ├── financial.py     # 财务数据
│   ├── sec_filings.py   # SEC 文件
│   └── company_info.py  # 公司信息
│
├── social/              # 社交情绪工具
│   ├── __init__.py
│   ├── sentiment.py     # 情绪分析
│   └── xueqiu.py        # 雪球数据
│
└── technical/           # 技术分析工具（新增）
    ├── __init__.py
    ├── indicators.py    # 技术指标
    └── patterns.py      # 形态识别
```

## 核心接口

### 1. BaseTool 基类

```python
# core/tools/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel

class ToolMetadata(BaseModel):
    """工具元数据"""
    id: str                          # 唯一标识
    name: str                        # 显示名称
    description: str                 # 工具描述
    category: str                    # 分类: market/news/fundamentals/social/technical
    version: str = "1.0.0"           # 版本号
    author: str = "system"           # 作者
    tags: list[str] = []             # 标签
    enabled: bool = True             # 是否启用
    parameters: Dict[str, Any] = {}  # 参数定义（JSON Schema）
    
class BaseTool(ABC):
    """工具基类"""
    
    metadata: ToolMetadata
    
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """执行工具"""
        pass
    
    def validate_params(self, **kwargs) -> bool:
        """验证参数"""
        pass
    
    def to_langchain_tool(self):
        """转换为 LangChain Tool"""
        from langchain_core.tools import tool
        
        @tool(name=self.metadata.id, description=self.metadata.description)
        def wrapper(**kwargs):
            return self.execute(**kwargs)
        
        return wrapper
```

### 2. @register_tool 装饰器

```python
# core/tools/decorators.py
from functools import wraps
from typing import Callable, Optional
from core.tools.registry import ToolRegistry

def register_tool(
    id: str,
    name: str,
    description: str,
    category: str,
    tags: list[str] = None,
    parameters: dict = None
):
    """
    工具注册装饰器
    
    用法:
        @register_tool(
            id="get_stock_market_data",
            name="股票市场数据",
            description="获取股票的历史和实时市场数据",
            category="market",
            tags=["stock", "market", "price"]
        )
        def get_stock_market_data(ticker: str, start_date: str, end_date: str) -> str:
            # 实现逻辑
            pass
    """
    def decorator(func: Callable):
        # 创建元数据
        metadata = ToolMetadata(
            id=id,
            name=name,
            description=description,
            category=category,
            tags=tags or [],
            parameters=parameters or {}
        )
        
        # 注册到 Registry
        ToolRegistry().register_function(id, func, metadata)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        wrapper._tool_metadata = metadata
        return wrapper
    
    return decorator
```

### 3. ToolRegistry 增强

```python
# core/tools/registry.py (增强版)
from typing import Dict, List, Optional, Callable, Any
from core.tools.base import ToolMetadata, BaseTool

class ToolRegistry:
    """工具注册中心（单例模式）"""
    
    _instance = None
    _tools: Dict[str, BaseTool] = {}           # 工具类实例
    _functions: Dict[str, Callable] = {}        # 工具函数
    _metadata: Dict[str, ToolMetadata] = {}     # 工具元数据
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(self, tool: BaseTool) -> None:
        """注册工具类实例"""
        self._tools[tool.metadata.id] = tool
        self._metadata[tool.metadata.id] = tool.metadata
    
    def register_function(self, id: str, func: Callable, metadata: ToolMetadata) -> None:
        """注册工具函数"""
        self._functions[id] = func
        self._metadata[id] = metadata
    
    def get(self, tool_id: str) -> Optional[BaseTool | Callable]:
        """获取工具（类实例或函数）"""
        if tool_id in self._tools:
            return self._tools[tool_id]
        return self._functions.get(tool_id)
    
    def get_langchain_tool(self, tool_id: str):
        """获取 LangChain 格式的工具"""
        tool = self.get(tool_id)
        if isinstance(tool, BaseTool):
            return tool.to_langchain_tool()
        elif callable(tool):
            # 函数已经通过装饰器包装
            from langchain_core.tools import tool as lc_tool
            metadata = self._metadata.get(tool_id)
            return lc_tool(name=metadata.id, description=metadata.description)(tool)
        return None
    
    def get_by_ids(self, tool_ids: List[str]) -> List[Any]:
        """批量获取工具"""
        return [self.get_langchain_tool(tid) for tid in tool_ids if self.get(tid)]
    
    def list_by_category(self, category: str) -> List[ToolMetadata]:
        """按分类列出工具"""
        return [m for m in self._metadata.values() if m.category == category]
    
    def list_all(self) -> List[ToolMetadata]:
        """列出所有工具"""
        return list(self._metadata.values())
```

### 4. ToolLoader 工具加载器

```python
# core/tools/loader.py
import importlib
import os
from pathlib import Path
from core.tools.registry import ToolRegistry

class ToolLoader:
    """工具加载器 - 自动扫描并加载工具"""

    def __init__(self, tools_dir: str = "core/tools"):
        self.tools_dir = Path(tools_dir)
        self.registry = ToolRegistry()

    def load_all(self) -> int:
        """加载所有工具，返回加载数量"""
        count = 0
        categories = ["market", "news", "fundamentals", "social", "technical"]

        for category in categories:
            category_dir = self.tools_dir / category
            if category_dir.exists():
                count += self._load_category(category_dir, category)

        return count

    def _load_category(self, category_dir: Path, category: str) -> int:
        """加载某个分类下的所有工具"""
        count = 0
        for py_file in category_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            module_name = f"core.tools.{category}.{py_file.stem}"
            try:
                importlib.import_module(module_name)
                count += 1
            except Exception as e:
                print(f"加载工具模块失败: {module_name}, 错误: {e}")

        return count
```

## 工具实现示例

### 市场数据工具

```python
# core/tools/market/stock_data.py
from core.tools.decorators import register_tool
from tradingagents.dataflows.interface import get_stock_data_unified

@register_tool(
    id="get_stock_market_data_unified",
    name="统一股票市场数据",
    description="获取股票的历史K线、实时价格等市场数据，自动识别A股/港股/美股",
    category="market",
    tags=["stock", "market", "price", "kline", "unified"],
    parameters={
        "ticker": {"type": "string", "description": "股票代码"},
        "start_date": {"type": "string", "description": "开始日期 yyyy-mm-dd"},
        "end_date": {"type": "string", "description": "结束日期 yyyy-mm-dd"}
    }
)
def get_stock_market_data_unified(ticker: str, start_date: str, end_date: str) -> str:
    """
    获取统一的股票市场数据

    自动识别股票类型（A股/港股/美股）并调用相应的数据源
    """
    return get_stock_data_unified(ticker, start_date, end_date)
```

### 新闻数据工具

```python
# core/tools/news/finnhub.py
from core.tools.decorators import register_tool
from tradingagents.dataflows.interface import get_finnhub_news

@register_tool(
    id="get_finnhub_news",
    name="Finnhub 新闻",
    description="从 Finnhub 获取股票相关新闻",
    category="news",
    tags=["news", "finnhub", "stock"]
)
def get_finnhub_news_tool(ticker: str, start_date: str, end_date: str) -> str:
    """获取 Finnhub 新闻"""
    from datetime import datetime
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    look_back_days = (end_dt - start_dt).days

    return get_finnhub_news(ticker, end_date, look_back_days)
```

## 兼容性设计

### 兼容现有 Toolkit 类

为了向后兼容，提供一个适配器将现有 Toolkit 方法注册为新格式工具：

```python
# core/tools/legacy_adapter.py
from tradingagents.agents.utils.agent_utils import Toolkit
from core.tools.registry import ToolRegistry
from core.tools.base import ToolMetadata

class LegacyToolkitAdapter:
    """旧版 Toolkit 适配器"""

    TOOL_MAPPING = {
        "get_stock_market_data_unified": {
            "name": "统一股票市场数据",
            "category": "market",
            "description": "获取股票的历史K线、实时价格等市场数据"
        },
        "get_finnhub_news": {
            "name": "Finnhub 新闻",
            "category": "news",
            "description": "从 Finnhub 获取股票相关新闻"
        },
        # ... 其他工具映射
    }

    @classmethod
    def register_all(cls):
        """将 Toolkit 中的所有工具注册到新 Registry"""
        toolkit = Toolkit()
        registry = ToolRegistry()

        for method_name, info in cls.TOOL_MAPPING.items():
            if hasattr(toolkit, method_name):
                method = getattr(toolkit, method_name)
                metadata = ToolMetadata(
                    id=method_name,
                    name=info["name"],
                    description=info["description"],
                    category=info["category"],
                    tags=["legacy"]
                )
                registry.register_function(method_name, method, metadata)
```

## 数据库配置

工具的启用/禁用状态存储在 MongoDB 中：

```javascript
// Collection: tool_configs
{
    "_id": ObjectId(),
    "tool_id": "get_stock_market_data_unified",
    "enabled": true,
    "priority": 1,           // 同类工具的优先级
    "config": {              // 工具特定配置
        "timeout": 30,
        "retry_count": 3
    },
    "created_at": ISODate(),
    "updated_at": ISODate()
}
```

## API 接口

### REST API

```
GET  /api/v1/tools                 # 列出所有工具
GET  /api/v1/tools/{tool_id}       # 获取工具详情
GET  /api/v1/tools?category=market # 按分类筛选
PUT  /api/v1/tools/{tool_id}       # 更新工具配置
```

## 总结

工具层设计的核心是：

1. **独立定义**：每个工具在独立文件中定义
2. **自动注册**：通过 `@register_tool` 装饰器自动注册
3. **统一接口**：所有工具通过 `ToolRegistry` 统一管理
4. **兼容旧版**：通过适配器兼容现有 Toolkit 类
5. **配置化**：工具状态可通过数据库配置

