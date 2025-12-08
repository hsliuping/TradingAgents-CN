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

