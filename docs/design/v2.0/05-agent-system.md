# 智能体系统设计

## 📋 概述

智能体系统的目标是：
1. 定义统一的智能体基类，消除代码重复
2. 智能体注册表，支持动态发现和管理
3. 可配置化，无需改代码即可调整行为

---

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      AgentRegistry                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  register(agent) / get(id) / list() / discover()   │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│                      AgentFactory                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  create(config, llm) -> BaseAgent                   │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│                       BaseAgent                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  execute(state) / get_tools() / get_prompt()       │    │
│  └─────────────────────────────────────────────────────┘    │
├──────────────┬──────────────┬──────────────┬────────────────┤
│   Analyst    │  Researcher  │    Trader    │   RiskAgent    │
│    Base      │     Base     │     Base     │      Base      │
├──────────────┼──────────────┼──────────────┼────────────────┤
│ MarketAna.   │ BullResear.  │   Trader     │ AggressiveRA   │
│ NewsAna.     │ BearResear.  │              │ ConservativeRA │
│ FundAna.     │              │              │ NeutralRA      │
│ SocialAna.   │              │              │                │
└──────────────┴──────────────┴──────────────┴────────────────┘
```

---

## 📝 核心数据模型

### AgentMetadata (智能体元数据)

```python
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from enum import Enum

class AgentCategory(str, Enum):
    ANALYST = "analyst"
    RESEARCHER = "researcher"
    TRADER = "trader"
    RISK = "risk"
    MANAGER = "manager"

class AgentMetadata(BaseModel):
    """智能体元数据 - 用于注册和发现"""
    id: str                          # 唯一标识: market_analyst
    name: str                        # 显示名称: 市场分析师
    description: str                 # 描述
    category: AgentCategory          # 分类
    version: str = "1.0.0"
    
    # 输入输出定义
    inputs: List[str] = []           # 需要的状态字段
    outputs: List[str] = []          # 产出的状态字段
    
    # 工具配置
    tools: List[str] = []            # 工具名称列表
    max_tool_calls: int = 3          # 最大工具调用次数
    
    # 提示词
    prompt_template_id: str = ""     # 关联的提示词模板ID
    
    # 显示配置 (用于可视化编辑器)
    icon: str = "robot"              # 图标
    color: str = "#1890ff"           # 颜色
    
    # 授权
    license_tier: str = "free"       # 需要的许可证级别

class AgentConfig(BaseModel):
    """智能体运行时配置"""
    metadata: AgentMetadata
    llm_config: Dict[str, Any] = {}  # LLM 相关配置
    tool_config: Dict[str, Any] = {} # 工具相关配置
    custom_params: Dict[str, Any] = {} # 自定义参数
```

---

## 🔧 核心类设计

### BaseAgent (智能体基类)

```python
from abc import ABC, abstractmethod

class BaseAgent(ABC):
    """智能体基类 - 模板方法模式"""
    
    def __init__(
        self,
        config: AgentConfig,
        llm_client: UnifiedLLMClient,
        prompt_manager: PromptManager,
        tool_registry: ToolRegistry
    ):
        self.config = config
        self.llm = llm_client
        self.prompt_manager = prompt_manager
        self.tool_registry = tool_registry
        self._tool_call_count = 0
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行智能体 (模板方法)"""
        # 1. 重置工具调用计数
        self._tool_call_count = 0
        
        # 2. 准备上下文
        context = self._prepare_context(state)
        
        # 3. 获取提示词
        prompt = await self._get_prompt(context)
        
        # 4. 获取工具
        tools = self._get_tools()
        
        # 5. 构建消息
        messages = self._build_messages(prompt, state)
        
        # 6. 调用 LLM
        response = await self.llm.ainvoke(messages, tools)
        
        # 7. 处理工具调用 (如果有)
        while response.tool_calls and self._should_continue_tool_calls():
            response = await self._handle_tool_calls(response, state)
        
        # 8. 生成最终输出
        output = self._generate_output(response, state)
        
        # 9. 更新状态
        return self._update_state(state, output)
    
    def _should_continue_tool_calls(self) -> bool:
        """是否继续工具调用 (防止死循环)"""
        return self._tool_call_count < self.config.metadata.max_tool_calls
    
    async def _handle_tool_calls(
        self, 
        response: LLMResponse, 
        state: Dict
    ) -> LLMResponse:
        """统一工具调用处理"""
        self._tool_call_count += 1
        
        tool_results = []
        for tool_call in response.tool_calls:
            tool = self.tool_registry.get(tool_call.name)
            result = await tool.ainvoke(tool_call.arguments)
            tool_results.append(ToolMessage(
                content=str(result),
                tool_call_id=tool_call.id
            ))
        
        # 继续调用 LLM
        messages = self._build_continuation_messages(response, tool_results)
        return await self.llm.ainvoke(messages)
    
    @abstractmethod
    def _prepare_context(self, state: Dict) -> Dict:
        """准备上下文 (子类实现)"""
        pass
    
    @abstractmethod
    def _get_output_field(self) -> str:
        """返回输出字段名 (子类实现)"""
        pass

    @classmethod
    def get_metadata(cls) -> AgentMetadata:
        """返回元数据 (用于注册)"""
        raise NotImplementedError
```

### AgentRegistry (智能体注册表)

```python
class AgentRegistry:
    """智能体注册表 - 管理所有可用智能体"""
    
    def __init__(self):
        self._agents: Dict[str, Type[BaseAgent]] = {}
        self._metadata: Dict[str, AgentMetadata] = {}
    
    def register(self, agent_class: Type[BaseAgent]) -> None:
        """注册智能体"""
        metadata = agent_class.get_metadata()
        self._agents[metadata.id] = agent_class
        self._metadata[metadata.id] = metadata
    
    def get(self, agent_id: str) -> Type[BaseAgent]:
        """获取智能体类"""
        if agent_id not in self._agents:
            raise AgentNotFoundError(f"Agent not found: {agent_id}")
        return self._agents[agent_id]
    
    def list(self, category: Optional[AgentCategory] = None) -> List[AgentMetadata]:
        """列出所有智能体"""
        agents = list(self._metadata.values())
        if category:
            agents = [a for a in agents if a.category == category]
        return agents
    
    def discover(self, package: str = "core.agents.builtin") -> None:
        """自动发现并注册智能体"""
        # 扫描包中的所有 BaseAgent 子类
        pass
```

---

## 📊 内置智能体清单

| ID | 名称 | 类别 | 许可证 |
|----|------|------|--------|
| market_analyst | 市场分析师 | analyst | free |
| news_analyst | 新闻分析师 | analyst | free |
| fundamentals_analyst | 基本面分析师 | analyst | free |
| social_analyst | 社交媒体分析师 | analyst | free |
| bull_researcher | 看涨研究员 | researcher | free |
| bear_researcher | 看跌研究员 | researcher | free |
| trader | 交易员 | trader | free |
| aggressive_risk | 激进风险评估 | risk | free |
| conservative_risk | 保守风险评估 | risk | free |
| neutral_risk | 中性风险评估 | risk | free |
| research_manager | 研究经理 | manager | free |
| risk_manager | 风险经理 | manager | free |
| sector_analyst | 行业/板块分析师 | analyst | pro |
| index_analyst | 大盘/指数分析师 | analyst | pro |

---

## 🔌 Agent 插件架构

### 设计目标

传统方式每新增一个 Agent，需要修改多处代码：
- `tradingagents/graph/setup.py` - 添加节点创建和边连接逻辑
- `tradingagents/agents/researchers/*.py` - 添加新报告字段获取
- `tradingagents/agents/managers/*.py` - 添加新报告字段获取

**插件架构目标**：新增 Agent 只需注册，无需修改引擎源码。

### 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    core/ 扩展层                              │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │              AnalystRegistry                         │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │ register(id, class, factory, metadata)      │    │   │
│  │  │ get_analyst_class(id) -> Type[BaseAgent]    │    │   │
│  │  │ get_analysts_ordered() -> List[Metadata]    │    │   │
│  │  │ get_output_fields() -> Dict[id, field]      │    │   │
│  │  │ is_registered(id) -> bool                   │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              ReportAggregator                        │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │ aggregate(state) -> AggregatedReports       │    │   │
│  │  │ to_text() / to_dict()                       │    │   │
│  │  │ 动态获取所有 *_report 字段                   │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                 tradingagents/ 核心引擎                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  GraphSetup._load_extension_analysts()              │   │
│  │  - 从 AnalystRegistry 动态加载扩展分析师             │   │
│  │  - 自动处理 requires_tools=False 的分析师           │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### AgentMetadata 工作流字段扩展

```python
class AgentMetadata(BaseModel):
    # ... 现有字段 ...

    # 🆕 工作流集成配置
    requires_tools: bool = True       # 是否需要工具调用循环
    output_field: str = ""            # 输出状态字段名，如 "sector_report"
    report_label: str = ""            # 报告标签，如 "【行业板块分析】"
    node_name: str = ""               # 工作流节点名称
    execution_order: int = 100        # 执行顺序（越小越先执行）
```

### AnalystRegistry (分析师注册表)

```python
# 文件: core/agents/analyst_registry.py

class AnalystRegistry:
    """分析师专用注册表，提供工作流构建相关功能"""

    _instance = None  # 单例

    def register(
        self,
        analyst_id: str,
        agent_class: Optional[Type[BaseAgent]] = None,
        factory: Optional[Callable] = None,
        metadata: Optional[AgentMetadata] = None,
    ) -> None:
        """注册分析师"""
        pass

    def get_analyst_class(self, analyst_id: str) -> Optional[Type[BaseAgent]]:
        """获取分析师类"""
        pass

    def get_analysts_ordered(self, selected: List[str] = None) -> List[AgentMetadata]:
        """获取分析师列表（按 execution_order 排序）"""
        pass

    def get_output_fields(self) -> Dict[str, str]:
        """获取所有分析师的输出字段映射 {analyst_id: output_field}"""
        pass

    def is_registered(self, analyst_id: str) -> bool:
        """检查分析师是否已注册实现"""
        pass


def get_analyst_registry() -> AnalystRegistry:
    """获取全局注册表实例"""
    pass
```

### ReportAggregator (报告聚合器)

```python
# 文件: core/utils/report_aggregator.py

@dataclass
class AggregatedReports:
    """聚合后的报告集合"""
    reports: Dict[str, str]   # {field_name: content}
    labels: Dict[str, str]    # {field_name: label}
    order: List[str]          # 按执行顺序排列的字段名

    def get(self, field_name: str, default: str = "") -> str:
        """获取指定报告"""
        pass

    def to_text(self, separator: str = "\n\n") -> str:
        """转换为文本（按执行顺序，带标签）"""
        pass

    def to_dict(self) -> Dict[str, str]:
        """转换为字典"""
        pass


class ReportAggregator:
    """报告聚合器，从 state 中动态获取所有分析报告"""

    def aggregate(self, state: Dict[str, Any]) -> AggregatedReports:
        """从 state 聚合所有报告"""
        pass


def get_all_reports(state: Dict[str, Any]) -> AggregatedReports:
    """便捷函数：从 state 获取所有报告"""
    pass
```

### 新增 Agent 的标准流程

**以前（每次新增都要改源码）**：
```python
# 1. setup.py - 硬编码导入和节点创建
from core.agents.adapters.sector_analyst import SectorAnalystAgent
if "sector" in selected_analysts:
    sector_agent = SectorAnalystAgent()
    analyst_nodes["sector"] = lambda state: sector_agent.execute(state)

# 2. bull_researcher.py - 硬编码字段获取
sector_report = state.get("sector_report", "")
index_report = state.get("index_report", "")
```

**现在（只需注册）**：
```python
# 1. 创建 Agent 类
@register_agent
class NewAnalystAgent(BaseAgent):
    metadata = BUILTIN_AGENTS["new_analyst"]

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # 实现分析逻辑
        return {**state, "new_report": report}

# 2. 在 adapters/__init__.py 中注册
registry.register("new_analyst", NewAnalystAgent, metadata)

# 3. 完成！
# - 工作流自动加载（通过 _load_extension_analysts）
# - 下游自动获取报告（通过 get_all_reports）
```

### 已实现的扩展分析师

| 分析师 | ID | requires_tools | output_field | execution_order |
|--------|-----|---------------|--------------|-----------------|
| 大盘分析师 | index_analyst | False | index_report | 1 |
| 板块分析师 | sector_analyst | False | sector_report | 5 |
| 市场分析师 | market_analyst | True | market_report | 10 |
| 舆情分析师 | social_analyst | True | sentiment_report | 20 |
| 新闻分析师 | news_analyst | True | news_report | 30 |
| 基本面分析师 | fundamentals_analyst | True | fundamentals_report | 40 |

### 文件结构

```
core/
├── agents/
│   ├── analyst_registry.py      # 分析师注册表
│   ├── config.py                # AgentMetadata 扩展
│   └── adapters/
│       ├── __init__.py          # 自动注册扩展分析师
│       ├── sector_analyst.py    # 板块分析师
│       └── index_analyst.py     # 大盘分析师
├── utils/
│   ├── __init__.py
│   └── report_aggregator.py     # 报告聚合器
└── workflow/
    └── analyst_extension.py     # 工作流扩展器

tradingagents/
└── graph/
    └── setup.py                 # _load_extension_analysts() 动态加载
```

