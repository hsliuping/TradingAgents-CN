# Agent 层设计 (Agent Layer Design)

## 概述

Agent 层负责管理智能体的定义、工具绑定和执行。本设计实现 Agent 与 Tool 的动态绑定，支持运行时配置 Agent 使用哪些工具。

## 设计目标

1. **动态绑定**：Agent 使用的工具列表由配置决定，非硬编码
2. **统一接口**：所有 Agent 继承统一基类，实现标准接口
3. **可扩展**：轻松添加新 Agent 类型
4. **提示词分离**：Agent 逻辑与提示词模板分离

## 目录结构

```
core/agents/
├── __init__.py
├── registry.py          # Agent 注册中心（增强）
├── base.py              # Agent 基类（增强）
├── factory.py           # Agent 工厂（新增）
├── decorators.py        # 装饰器
├── config.py            # Agent 元数据配置
│
├── analysts/            # 分析师 Agent
│   ├── __init__.py
│   ├── market_analyst.py
│   ├── news_analyst.py
│   ├── fundamentals_analyst.py
│   └── social_analyst.py
│
├── researchers/         # 研究员 Agent
│   ├── __init__.py
│   ├── bull_researcher.py
│   └── bear_researcher.py
│
├── traders/             # 交易员 Agent
│   ├── __init__.py
│   └── risky_trader.py
│
├── managers/            # 管理者 Agent
│   ├── __init__.py
│   └── risk_manager.py
│
└── position/            # 持仓分析 Agent（新增）
    ├── __init__.py
    ├── technical_analyst.py
    ├── fundamental_analyst.py
    ├── risk_assessor.py
    └── action_advisor.py
```

## 核心接口

### 1. AgentMetadata 元数据

```python
# core/agents/config.py
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class AgentMetadata(BaseModel):
    """Agent 元数据"""
    id: str                              # 唯一标识
    name: str                            # 显示名称
    description: str                     # Agent 描述
    category: str                        # 分类: analysts/researchers/traders/managers/position
    version: str = "1.0.0"               # 版本号
    
    # 工具配置 - 核心改动点
    tools: List[str] = []                # 可用工具ID列表（从配置加载）
    default_tools: List[str] = []        # 默认工具（首选）
    required_tools: List[str] = []       # 必需工具（缺失则报错）
    
    # 提示词配置
    prompt_template_type: str = ""       # 提示词模板类型
    prompt_template_name: str = ""       # 提示词模板名称
    
    # 执行配置
    max_iterations: int = 3              # 最大迭代次数
    timeout: int = 120                   # 超时时间（秒）
    
    # 扩展配置
    tags: List[str] = []
    enabled: bool = True
    config: Dict[str, Any] = {}          # 自定义配置
```

### 2. BaseAgent 基类

```python
# core/agents/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from langchain_core.language_models import BaseChatModel
from core.tools.registry import ToolRegistry
from core.agents.config import AgentMetadata

class BaseAgent(ABC):
    """Agent 基类 - 所有 Agent 必须继承此类"""
    
    def __init__(
        self,
        agent_id: str,
        llm: BaseChatModel,
        tool_ids: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.agent_id = agent_id
        self.llm = llm
        self.config = config or {}
        
        # 从 Registry 加载元数据
        from core.agents.registry import AgentRegistry
        self.metadata = AgentRegistry().get_metadata(agent_id)
        
        # 动态加载工具 - 核心改动
        self._tool_ids = tool_ids or self._load_tools_from_config()
        self._tools = self._create_tools()
    
    def _load_tools_from_config(self) -> List[str]:
        """从配置加载工具列表"""
        # 优先从数据库配置加载
        from core.config.binding_manager import BindingManager
        bindings = BindingManager().get_tools_for_agent(self.agent_id)
        
        if bindings:
            return [b["tool_id"] for b in bindings]
        
        # 降级：使用元数据中的默认工具
        return self.metadata.default_tools or self.metadata.tools
    
    def _create_tools(self) -> List:
        """创建工具实例"""
        registry = ToolRegistry()
        tools = []
        
        for tool_id in self._tool_ids:
            tool = registry.get_langchain_tool(tool_id)
            if tool:
                tools.append(tool)
        
        # 检查必需工具
        for required in self.metadata.required_tools:
            if required not in self._tool_ids:
                raise ValueError(f"Agent {self.agent_id} 缺少必需工具: {required}")
        
        return tools
    
    @property
    def tools(self) -> List:
        """获取绑定的工具列表"""
        return self._tools
    
    def bind_tools(self, tool_ids: List[str]) -> None:
        """动态绑定工具"""
        self._tool_ids = tool_ids
        self._tools = self._create_tools()
    
    @abstractmethod
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行 Agent 逻辑"""
        pass
    
    def get_prompt(self, variables: Dict[str, Any]) -> str:
        """获取提示词"""
        from tradingagents.utils.template_client import get_agent_prompt
        return get_agent_prompt(
            agent_type=self.metadata.prompt_template_type,
            agent_name=self.metadata.prompt_template_name,
            variables=variables
        )
    
    def create_node(self):
        """创建 LangGraph 节点"""
        return self.execute
```

### 3. @register_agent 装饰器

```python
# core/agents/decorators.py
from functools import wraps
from typing import Type
from core.agents.base import BaseAgent
from core.agents.registry import AgentRegistry
from core.agents.config import AgentMetadata

def register_agent(
    id: str,
    name: str,
    description: str,
    category: str,
    tools: list[str] = None,
    default_tools: list[str] = None,
    prompt_template_type: str = "",
    prompt_template_name: str = "",
    **kwargs
):
    """
    Agent 注册装饰器

    用法:
        @register_agent(
            id="market_analyst",
            name="市场分析师",
            description="分析市场数据和价格趋势",
            category="analysts",
            tools=["get_stock_market_data_unified", "get_kline_data"],
            default_tools=["get_stock_market_data_unified"],
            prompt_template_type="analysts",
            prompt_template_name="market_analyst"
        )
        class MarketAnalyst(BaseAgent):
            def execute(self, state):
                # 实现逻辑
                pass
    """
    def decorator(cls: Type[BaseAgent]):
        metadata = AgentMetadata(
            id=id,
            name=name,
            description=description,
            category=category,
            tools=tools or [],
            default_tools=default_tools or [],
            prompt_template_type=prompt_template_type,
            prompt_template_name=prompt_template_name,
            **kwargs
        )

        # 注册到 Registry
        AgentRegistry().register(id, cls, metadata)

        return cls

    return decorator
```

### 4. AgentFactory 工厂

```python
# core/agents/factory.py
from typing import Dict, Any, Optional, List
from langchain_core.language_models import BaseChatModel
from core.agents.registry import AgentRegistry
from core.agents.base import BaseAgent

class AgentFactory:
    """Agent 工厂 - 根据配置创建 Agent 实例"""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        self.registry = AgentRegistry()

    def create(
        self,
        agent_id: str,
        tool_ids: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> BaseAgent:
        """
        创建 Agent 实例

        Args:
            agent_id: Agent 标识
            tool_ids: 工具列表（可选，不传则从配置加载）
            config: 额外配置

        Returns:
            BaseAgent 实例
        """
        agent_cls = self.registry.get(agent_id)
        if not agent_cls:
            raise ValueError(f"未找到 Agent: {agent_id}")

        return agent_cls(
            agent_id=agent_id,
            llm=self.llm,
            tool_ids=tool_ids,
            config=config
        )

    def create_batch(
        self,
        agent_ids: List[str],
        tool_overrides: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, BaseAgent]:
        """
        批量创建 Agent

        Args:
            agent_ids: Agent ID 列表
            tool_overrides: 工具覆盖配置 {agent_id: [tool_ids]}

        Returns:
            {agent_id: BaseAgent} 字典
        """
        tool_overrides = tool_overrides or {}
        agents = {}

        for agent_id in agent_ids:
            tool_ids = tool_overrides.get(agent_id)
            agents[agent_id] = self.create(agent_id, tool_ids)

        return agents
```

### 5. AgentRegistry 增强

```python
# core/agents/registry.py (增强版)
from typing import Dict, List, Optional, Type
from core.agents.config import AgentMetadata

class AgentRegistry:
    """Agent 注册中心（单例模式）"""

    _instance = None
    _agents: Dict[str, Type] = {}           # Agent 类
    _metadata: Dict[str, AgentMetadata] = {} # Agent 元数据

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, agent_id: str, agent_cls: Type, metadata: AgentMetadata) -> None:
        """注册 Agent"""
        self._agents[agent_id] = agent_cls
        self._metadata[agent_id] = metadata

    def get(self, agent_id: str) -> Optional[Type]:
        """获取 Agent 类"""
        return self._agents.get(agent_id)

    def get_metadata(self, agent_id: str) -> Optional[AgentMetadata]:
        """获取 Agent 元数据"""
        return self._metadata.get(agent_id)

    def list_all(self) -> List[AgentMetadata]:
        """列出所有 Agent"""
        return list(self._metadata.values())

    def list_by_category(self, category: str) -> List[AgentMetadata]:
        """按分类列出 Agent"""
        return [m for m in self._metadata.values() if m.category == category]

    def get_tools_for_agent(self, agent_id: str) -> List[str]:
        """获取 Agent 的工具列表"""
        metadata = self.get_metadata(agent_id)
        if metadata:
            return metadata.tools
        return []
```

## Agent 实现示例

### 市场分析师

```python
# core/agents/analysts/market_analyst.py
from core.agents.base import BaseAgent
from core.agents.decorators import register_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

@register_agent(
    id="market_analyst",
    name="市场分析师",
    description="分析股票市场数据、价格走势、技术指标",
    category="analysts",
    tools=["get_stock_market_data_unified", "get_kline_data", "get_realtime_price"],
    default_tools=["get_stock_market_data_unified"],
    required_tools=["get_stock_market_data_unified"],
    prompt_template_type="analysts",
    prompt_template_name="market_analyst"
)
class MarketAnalyst(BaseAgent):
    """市场分析师 Agent"""

    def execute(self, state: dict) -> dict:
        ticker = state["company_of_interest"]
        current_date = state["trade_date"]

        # 获取提示词
        prompt_text = self.get_prompt({
            "ticker": ticker,
            "current_date": current_date,
            "tool_names": ", ".join([t.name for t in self.tools])
        })

        # 创建提示模板
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_text),
            MessagesPlaceholder(variable_name="messages")
        ])

        # 执行 LLM 调用
        chain = prompt | self.llm.bind_tools(self.tools)
        result = chain.invoke({"messages": state["messages"]})

        # 处理工具调用...
        # (省略具体实现)

        return {
            "messages": [result],
            "market_report": result.content
        }
```

## 工具绑定配置

### 数据库配置表

```javascript
// Collection: tool_agent_bindings
{
    "_id": ObjectId(),
    "agent_id": "market_analyst",
    "tool_id": "get_stock_market_data_unified",
    "priority": 1,           // 优先级
    "enabled": true,         // 是否启用
    "config": {},            // 特定配置
    "created_at": ISODate(),
    "updated_at": ISODate()
}
```

### BindingManager 绑定管理器

```python
# core/config/binding_manager.py
from typing import List, Dict, Any, Optional
from app.core.database import get_mongo_db

class BindingManager:
    """工具-Agent 绑定管理器"""

    def __init__(self):
        self.db = get_mongo_db()
        self.collection = self.db.tool_agent_bindings

    def get_tools_for_agent(self, agent_id: str) -> List[Dict[str, Any]]:
        """获取 Agent 绑定的工具列表"""
        bindings = self.collection.find({
            "agent_id": agent_id,
            "enabled": True
        }).sort("priority", 1)

        return list(bindings)

    def bind_tool(self, agent_id: str, tool_id: str, priority: int = 1) -> None:
        """绑定工具到 Agent"""
        self.collection.update_one(
            {"agent_id": agent_id, "tool_id": tool_id},
            {"$set": {
                "agent_id": agent_id,
                "tool_id": tool_id,
                "priority": priority,
                "enabled": True,
                "updated_at": datetime.utcnow()
            }},
            upsert=True
        )

    def unbind_tool(self, agent_id: str, tool_id: str) -> None:
        """解绑工具"""
        self.collection.update_one(
            {"agent_id": agent_id, "tool_id": tool_id},
            {"$set": {"enabled": False}}
        )

    def list_bindings(self, agent_id: str = None) -> List[Dict[str, Any]]:
        """列出绑定关系"""
        query = {"enabled": True}
        if agent_id:
            query["agent_id"] = agent_id
        return list(self.collection.find(query))
```

## API 接口

```
GET  /api/v1/agents                      # 列出所有 Agent
GET  /api/v1/agents/{agent_id}           # 获取 Agent 详情
GET  /api/v1/agents/{agent_id}/tools     # 获取 Agent 的工具列表

POST /api/v1/agents/{agent_id}/tools     # 绑定工具
     Body: {"tool_id": "xxx", "priority": 1}

DELETE /api/v1/agents/{agent_id}/tools/{tool_id}  # 解绑工具

PUT  /api/v1/agents/{agent_id}/tools     # 批量更新工具绑定
     Body: {"tools": ["tool1", "tool2", "tool3"]}
```

## 总结

Agent 层设计的核心是：

1. **动态绑定**：工具列表从配置/数据库加载，非硬编码
2. **统一基类**：所有 Agent 继承 BaseAgent，实现标准接口
3. **工厂模式**：通过 AgentFactory 创建 Agent 实例
4. **绑定管理**：通过 BindingManager 管理工具-Agent 绑定
5. **提示词分离**：提示词通过模板系统加载

