# 股票分析专用引擎设计

## 📋 概述

本文档设计一个专门用于股票分析的引擎架构，解决当前系统的以下问题：

| 问题 | 当前状态 | 目标状态 |
|------|---------|---------|
| 数据存储 | 扁平化 State，字段混杂 | 分层存储，职责清晰 |
| 数据依赖 | 硬编码字段名 | 声明式数据契约 |
| 权限控制 | 无控制，任意访问 | 按阶段授权访问 |
| 数据追溯 | 无法追溯数据来源 | 完整的数据血缘 |

---

## 🏗️ 核心架构

### 数据分层模型

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AnalysisContext (分析上下文)                          │
├─────────────────────────────────────────────────────────────────────────┤
│  Layer 1: Context (基础信息)                                            │
│  ├── ticker          # 股票代码                                         │
│  ├── trade_date      # 交易日期                                         │
│  ├── market_type     # 市场类型 (A股/港股/美股)                          │
│  ├── currency        # 货币                                             │
│  └── company_name    # 公司名称                                         │
├─────────────────────────────────────────────────────────────────────────┤
│  Layer 2: RawData (原始数据) - 从 API 获取的原始数据                      │
│  ├── price_data      # OHLCV 价格数据                                   │
│  ├── news_data       # 新闻数据列表                                     │
│  ├── financial_data  # 财务报表数据                                     │
│  ├── index_data      # 指数数据                                         │
│  ├── sector_data     # 板块数据                                         │
│  └── social_data     # 社交媒体数据                                     │
├─────────────────────────────────────────────────────────────────────────┤
│  Layer 3: AnalysisData (分析数据) - 处理后的结构化数据                    │
│  ├── technical       # 技术指标 (MA/RSI/MACD/布林带)                    │
│  ├── sentiment       # 情绪评分和分布                                   │
│  ├── valuation       # 估值指标 (PE/PB/PS/PEG)                          │
│  ├── sector_ranking  # 板块排名和相对强弱                               │
│  └── market_breadth  # 市场宽度指标                                     │
├─────────────────────────────────────────────────────────────────────────┤
│  Layer 4: Reports (分析报告) - Agent 生成的文本报告                       │
│  ├── market_report        # 市场/技术分析报告                           │
│  ├── news_report          # 新闻分析报告                                │
│  ├── sentiment_report     # 情绪分析报告                                │
│  ├── fundamentals_report  # 基本面分析报告                              │
│  ├── sector_report        # 板块分析报告                                │
│  └── index_report         # 大盘分析报告                                │
├─────────────────────────────────────────────────────────────────────────┤
│  Layer 5: Decisions (决策结果) - 辩论和决策输出                           │
│  ├── investment_debate    # 投资辩论历史                                │
│  ├── investment_plan      # 投资计划                                    │
│  ├── trade_signal         # 交易信号 (买入/卖出/持有)                    │
│  ├── risk_assessment      # 风险评估结果                                │
│  └── final_decision       # 最终分析结果                                │
└─────────────────────────────────────────────────────────────────────────┘
```

### 执行阶段与数据权限

| 阶段 | Agent | 可读取层 | 可写入层 |
|------|-------|---------|---------|
| 0. 初始化 | System | - | Context |
| 1. 数据采集 | DataCollector | Context | RawData |
| 2. 分析师 | Analysts | Context, RawData | AnalysisData, Reports |
| 3. 研究辩论 | Researchers | Context, Reports | Decisions.debate |
| 4. 研究决策 | ResearchManager | Context, Reports, Decisions.debate | Decisions.plan |
| 5. 交易决策 | Trader | Context, Reports, Decisions.plan | Decisions.signal |
| 6. 风险评估 | RiskAgents | Context, Reports, Decisions | Decisions.risk |
| 7. 最终决策 | RiskManager | All | Decisions.final |

---

## 📝 数据契约设计

### AgentDataContract (Agent 数据契约)

```python
from pydantic import BaseModel
from typing import List, Set
from enum import Enum

class DataLayer(str, Enum):
    CONTEXT = "context"
    RAW_DATA = "raw_data"
    ANALYSIS_DATA = "analysis_data"
    REPORTS = "reports"
    DECISIONS = "decisions"

class DataAccess(BaseModel):
    """数据访问权限声明"""
    layer: DataLayer
    fields: List[str] = []  # 空表示整层访问
    required: bool = True   # 是否必须存在

class AgentDataContract(BaseModel):
    """Agent 数据契约"""
    agent_id: str
    
    # 输入声明：Agent 需要读取的数据
    inputs: List[DataAccess] = []
    
    # 输出声明：Agent 产出的数据
    outputs: List[DataAccess] = []
    
    # 依赖声明：必须在哪些 Agent 之后执行
    depends_on: Set[str] = set()
```

### 示例：分析师数据契约

```python
# 市场分析师契约
MARKET_ANALYST_CONTRACT = AgentDataContract(
    agent_id="market_analyst",
    inputs=[
        DataAccess(layer=DataLayer.CONTEXT, fields=["ticker", "trade_date"]),
        DataAccess(layer=DataLayer.RAW_DATA, fields=["price_data"]),
    ],
    outputs=[
        DataAccess(layer=DataLayer.ANALYSIS_DATA, fields=["technical"]),
        DataAccess(layer=DataLayer.REPORTS, fields=["market_report"]),
    ],
    depends_on={"data_collector"}
)

# 板块分析师契约
SECTOR_ANALYST_CONTRACT = AgentDataContract(
    agent_id="sector_analyst",
    inputs=[
        DataAccess(layer=DataLayer.CONTEXT, fields=["ticker", "trade_date", "market_type"]),
        DataAccess(layer=DataLayer.RAW_DATA, fields=["sector_data", "index_data"]),
    ],
    outputs=[
        DataAccess(layer=DataLayer.ANALYSIS_DATA, fields=["sector_ranking"]),
        DataAccess(layer=DataLayer.REPORTS, fields=["sector_report"]),
    ],
    depends_on={"data_collector"}
)

# 研究员契约
BULL_RESEARCHER_CONTRACT = AgentDataContract(
    agent_id="bull_researcher",
    inputs=[
        DataAccess(layer=DataLayer.CONTEXT, fields=["ticker", "company_name"]),
        DataAccess(layer=DataLayer.REPORTS),  # 所有报告
        DataAccess(layer=DataLayer.DECISIONS, fields=["investment_debate"], required=False),
    ],
    outputs=[
        DataAccess(layer=DataLayer.DECISIONS, fields=["investment_debate"]),
    ],
    depends_on={"market_analyst", "news_analyst", "sentiment_analyst",
                "fundamentals_analyst", "sector_analyst", "index_analyst"}
)
```

---

## � 数据字典设计

### 设计原则

数据契约中的 `fields=["ticker", "company_name"]` 不是凭空定义的，需要有一个**数据字典**来管理所有合法字段。

为了避免硬编码，采用**混合方案**：

| 字段类型 | 管理方式 | 说明 |
|---------|---------|------|
| 核心字段 | 代码硬编码 | 系统必需，不会变 |
| Agent 输出字段 | 自动注册 | Agent 注册时自动添加 |
| 扩展字段 | YAML 配置 | 灵活可控，不依赖 Agent |

### 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DynamicDataSchema                              │
│                      (动态数据字典)                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│  │  CoreSchema     │  │  AgentSchema    │  │  ExtendSchema   │     │
│  │  (核心字段)      │  │  (Agent自注册)   │  │  (YAML配置)     │     │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤     │
│  │ context:        │  │ reports:        │  │ raw_data:       │     │
│  │   ticker ✓      │  │   market_report │  │   fund_flow     │     │
│  │   trade_date ✓  │  │   sector_report │  │   dragon_tiger  │     │
│  │   market_type   │  │   index_report  │  │   margin_data   │     │
│  │                 │  │   (动态添加...)  │  │   (配置添加...) │     │
│  │ decisions:      │  │                 │  │                 │     │
│  │   final_decision│  │ analysis_data:  │  │                 │     │
│  │                 │  │   technical     │  │                 │     │
│  │                 │  │   sentiment     │  │                 │     │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘     │
│           │                   │                   │                 │
│           └───────────────────┼───────────────────┘                 │
│                               ▼                                     │
│                    get_all_fields(layer)                            │
│                    → 合并三个来源的字段                               │
└─────────────────────────────────────────────────────────────────────┘
```

### 核心实现

```python
# core/engine/data_schema.py

from enum import Enum
from typing import Dict, Set, Any, Optional
from pathlib import Path
import yaml

class DataLayer(str, Enum):
    CONTEXT = "context"
    RAW_DATA = "raw_data"
    ANALYSIS_DATA = "analysis_data"
    REPORTS = "reports"
    DECISIONS = "decisions"


class FieldDefinition:
    """字段定义"""
    def __init__(
        self,
        name: str,
        field_type: str = "any",
        required: bool = False,
        default: Any = None,
        description: str = "",
        source: str = "",  # 哪个 Agent 产出
    ):
        self.name = name
        self.field_type = field_type
        self.required = required
        self.default = default
        self.description = description
        self.source = source


class DynamicDataSchema:
    """
    动态数据字典

    支持三种字段来源：
    1. 核心字段 - 代码硬编码，系统必需
    2. Agent 字段 - Agent 注册时自动添加
    3. 扩展字段 - YAML 配置文件定义
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 1️⃣ 核心字段（硬编码，系统必需）
        self._core_fields: Dict[DataLayer, Dict[str, FieldDefinition]] = {
            DataLayer.CONTEXT: {
                "ticker": FieldDefinition(
                    name="ticker",
                    field_type="string",
                    required=True,
                    description="股票代码，如 000858.SZ"
                ),
                "trade_date": FieldDefinition(
                    name="trade_date",
                    field_type="string",
                    required=True,
                    description="分析日期，格式 YYYY-MM-DD"
                ),
                "market_type": FieldDefinition(
                    name="market_type",
                    field_type="string",
                    default="A_SHARE",
                    description="市场类型: A_SHARE, HK, US"
                ),
                "company_name": FieldDefinition(
                    name="company_name",
                    field_type="string",
                    default="",
                    description="公司名称"
                ),
                "currency": FieldDefinition(
                    name="currency",
                    field_type="string",
                    default="CNY",
                    description="货币代码: CNY, HKD, USD"
                ),
            },
            DataLayer.DECISIONS: {
                "investment_debate": FieldDefinition(
                    name="investment_debate",
                    field_type="object",
                    description="投资辩论历史"
                ),
                "investment_plan": FieldDefinition(
                    name="investment_plan",
                    field_type="string",
                    description="投资计划"
                ),
                "trade_signal": FieldDefinition(
                    name="trade_signal",
                    field_type="object",
                    description="交易信号"
                ),
                "risk_assessment": FieldDefinition(
                    name="risk_assessment",
                    field_type="object",
                    description="风险评估"
                ),
                "final_decision": FieldDefinition(
                    name="final_decision",
                    field_type="string",
                    description="最终分析结果"
                ),
            },
        }

        # 2️⃣ Agent 动态字段（Agent 注册时添加）
        self._agent_fields: Dict[DataLayer, Dict[str, FieldDefinition]] = {
            layer: {} for layer in DataLayer
        }

        # 3️⃣ 扩展字段（从 YAML 加载）
        self._extend_fields: Dict[DataLayer, Dict[str, FieldDefinition]] = {
            layer: {} for layer in DataLayer
        }

        # 加载 YAML 配置
        self._load_extend_schema()

    def _load_extend_schema(self, config_path: str = "config/data_schema.yaml"):
        """从 YAML 配置文件加载扩展字段"""
        path = Path(config_path)
        if not path.exists():
            return

        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config or "layers" not in config:
            return

        for layer_name, layer_config in config["layers"].items():
            try:
                layer = DataLayer(layer_name)
            except ValueError:
                continue

            fields = layer_config.get("fields", {})
            for field_name, field_config in fields.items():
                # 跳过核心字段（不允许覆盖）
                if field_name in self._core_fields.get(layer, {}):
                    continue

                self._extend_fields[layer][field_name] = FieldDefinition(
                    name=field_name,
                    field_type=field_config.get("type", "any"),
                    required=field_config.get("required", False),
                    default=field_config.get("default"),
                    description=field_config.get("description", ""),
                    source=field_config.get("source", "config"),
                )

    def register_agent_fields(self, agent_id: str, outputs: list):
        """
        Agent 注册时，自动将其输出字段添加到数据字典

        Args:
            agent_id: Agent 标识
            outputs: Agent 的输出声明列表 [DataAccess, ...]
        """
        for access in outputs:
            for field_name in access.fields:
                # 跳过核心字段
                if field_name in self._core_fields.get(access.layer, {}):
                    continue

                self._agent_fields[access.layer][field_name] = FieldDefinition(
                    name=field_name,
                    field_type="dynamic",
                    source=agent_id,
                    description=f"由 {agent_id} 产出"
                )

    def get_all_fields(self, layer: DataLayer) -> Dict[str, FieldDefinition]:
        """
        获取某层的所有字段（合并三个来源）

        优先级：核心字段 > Agent 字段 > 扩展字段
        """
        result = {}

        # 先加载扩展字段（最低优先级）
        result.update(self._extend_fields.get(layer, {}))

        # 再加载 Agent 字段
        result.update(self._agent_fields.get(layer, {}))

        # 最后加载核心字段（最高优先级）
        result.update(self._core_fields.get(layer, {}))

        return result

    def get_field_names(self, layer: DataLayer) -> Set[str]:
        """获取某层的所有字段名"""
        return set(self.get_all_fields(layer).keys())

    def is_valid_field(self, layer: DataLayer, field_name: str) -> bool:
        """检查字段是否合法"""
        return field_name in self.get_field_names(layer)

    def get_field_info(self, layer: DataLayer, field_name: str) -> Optional[FieldDefinition]:
        """获取字段详细信息"""
        return self.get_all_fields(layer).get(field_name)

    def get_fields_by_source(self, source: str) -> Dict[DataLayer, list]:
        """获取某个 Agent 产出的所有字段"""
        result = {}
        for layer in DataLayer:
            fields = []
            for field_name, field_def in self.get_all_fields(layer).items():
                if field_def.source == source:
                    fields.append(field_name)
            if fields:
                result[layer] = fields
        return result


# 全局单例
data_schema = DynamicDataSchema()
```

### YAML 配置文件示例

```yaml
# config/data_schema.yaml
# 扩展数据字段配置（不依赖 Agent 注册）

layers:
  raw_data:
    description: "原始数据层扩展字段"
    fields:
      # 资金流向数据（可能由多个 Agent 使用）
      fund_flow_data:
        type: object
        source: data_collector
        description: "主力资金流向数据"

      # 龙虎榜数据
      dragon_tiger_data:
        type: object
        source: data_collector
        description: "龙虎榜交易数据"

      # 融资融券数据
      margin_data:
        type: object
        source: data_collector
        description: "融资融券数据"

  analysis_data:
    description: "分析数据层扩展字段"
    fields:
      # 资金流向分析结果
      fund_flow_metrics:
        type: object
        description: "资金流向分析指标"

      # 筹码分布
      chip_distribution:
        type: object
        description: "筹码分布分析"
```

### Agent 自动注册示例

```python
# core/agents/analyst_registry.py (扩展)

from core.engine.data_schema import data_schema

class AnalystRegistry:
    """分析师注册表 - 扩展数据字典自动注册"""

    def register(self, agent_id: str, agent_class, metadata):
        """
        注册 Agent

        自动将 Agent 的输出字段添加到数据字典
        """
        # 1. 原有注册逻辑
        self._analysts[agent_id] = {
            "class": agent_class,
            "metadata": metadata,
        }

        # 2. 🆕 自动注册输出字段到数据字典
        if hasattr(agent_class, "contract"):
            data_schema.register_agent_fields(
                agent_id=agent_id,
                outputs=agent_class.contract.outputs
            )


# 使用示例：新增 Agent 时自动注册字段

@register_analyst
class FundFlowAnalyst:
    """资金流向分析师"""

    contract = AgentDataContract(
        agent_id="fund_flow_analyst",
        inputs=[
            DataAccess(layer=DataLayer.CONTEXT, fields=["ticker"]),
            DataAccess(layer=DataLayer.RAW_DATA, fields=["fund_flow_data"]),
        ],
        outputs=[
            # 🔥 这些字段会自动添加到数据字典
            DataAccess(layer=DataLayer.ANALYSIS_DATA, fields=["fund_flow_metrics"]),
            DataAccess(layer=DataLayer.REPORTS, fields=["fund_flow_report"]),
        ]
    )

# 注册后，数据字典自动包含：
# - analysis_data.fund_flow_metrics (source: fund_flow_analyst)
# - reports.fund_flow_report (source: fund_flow_analyst)
```

### 契约验证

```python
# core/engine/contract_validator.py

class ContractValidator:
    """数据契约验证器"""

    def __init__(self, schema: DynamicDataSchema):
        self.schema = schema

    def validate_contract(self, contract: AgentDataContract) -> list:
        """
        验证 Agent 契约的合法性

        Returns:
            错误列表，空表示验证通过
        """
        errors = []

        # 验证输入字段
        for access in contract.inputs:
            for field in access.fields:
                if not self.schema.is_valid_field(access.layer, field):
                    errors.append(
                        f"输入字段无效: {access.layer.value}.{field} "
                        f"(Agent: {contract.agent_id})"
                    )

        # 输出字段不需要预先存在（会自动注册）
        # 但可以检查是否与核心字段冲突
        for access in contract.outputs:
            for field in access.fields:
                core_fields = self.schema._core_fields.get(access.layer, {})
                if field in core_fields:
                    errors.append(
                        f"不能覆盖核心字段: {access.layer.value}.{field} "
                        f"(Agent: {contract.agent_id})"
                    )

        return errors

    def validate_all_contracts(self, contracts: list) -> dict:
        """验证所有 Agent 契约"""
        results = {}
        for contract in contracts:
            errors = self.validate_contract(contract)
            if errors:
                results[contract.agent_id] = errors
        return results
```

### 字段查询 API

```python
# 查询数据字典

# 获取某层所有字段
context_fields = data_schema.get_field_names(DataLayer.CONTEXT)
# {'ticker', 'trade_date', 'market_type', 'company_name', 'currency'}

# 检查字段是否存在
is_valid = data_schema.is_valid_field(DataLayer.CONTEXT, "ticker")  # True
is_valid = data_schema.is_valid_field(DataLayer.CONTEXT, "xxx")     # False

# 获取字段详细信息
field_info = data_schema.get_field_info(DataLayer.CONTEXT, "ticker")
# FieldDefinition(name='ticker', type='string', required=True, ...)

# 获取某个 Agent 产出的所有字段
fund_flow_fields = data_schema.get_fields_by_source("fund_flow_analyst")
# {DataLayer.ANALYSIS_DATA: ['fund_flow_metrics'], DataLayer.REPORTS: ['fund_flow_report']}
```

---

## �🔧 核心组件设计

### AnalysisContext (分析上下文)

```python
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime

@dataclass
class AnalysisContext:
    """股票分析上下文 - 分层数据容器"""

    # Layer 1: Context
    context: Dict[str, Any] = field(default_factory=dict)

    # Layer 2: RawData
    raw_data: Dict[str, Any] = field(default_factory=dict)

    # Layer 3: AnalysisData
    analysis_data: Dict[str, Any] = field(default_factory=dict)

    # Layer 4: Reports
    reports: Dict[str, str] = field(default_factory=dict)

    # Layer 5: Decisions
    decisions: Dict[str, Any] = field(default_factory=dict)

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    data_lineage: Dict[str, str] = field(default_factory=dict)  # 数据血缘追踪

    def get(self, layer: DataLayer, field: str, default=None):
        """获取指定层的数据"""
        layer_data = getattr(self, layer.value, {})
        return layer_data.get(field, default)

    def set(self, layer: DataLayer, field: str, value: Any, source: str = None):
        """设置指定层的数据"""
        layer_data = getattr(self, layer.value)
        layer_data[field] = value
        self.updated_at = datetime.now()
        if source:
            self.data_lineage[f"{layer.value}.{field}"] = source

    def get_reports_for_phase(self, phase: int) -> Dict[str, str]:
        """根据阶段获取可访问的报告"""
        # 阶段 3+ 可以访问所有报告
        if phase >= 3:
            return self.reports.copy()
        return {}

    def to_legacy_state(self) -> Dict[str, Any]:
        """转换为旧版 AgentState 格式（向后兼容）"""
        return {
            "company_of_interest": self.context.get("ticker", ""),
            "trade_date": self.context.get("trade_date", ""),
            "market_report": self.reports.get("market_report", ""),
            "sentiment_report": self.reports.get("sentiment_report", ""),
            "news_report": self.reports.get("news_report", ""),
            "fundamentals_report": self.reports.get("fundamentals_report", ""),
            "sector_report": self.reports.get("sector_report", ""),
            "index_report": self.reports.get("index_report", ""),
            "investment_debate_state": self.decisions.get("investment_debate", {}),
            "investment_plan": self.decisions.get("investment_plan", ""),
            "trader_investment_plan": self.decisions.get("trade_signal", ""),
            "risk_debate_state": self.decisions.get("risk_assessment", {}),
            "final_trade_decision": self.decisions.get("final_decision", ""),
        }

    @classmethod
    def from_legacy_state(cls, state: Dict[str, Any]) -> "AnalysisContext":
        """从旧版 AgentState 创建（向后兼容）"""
        ctx = cls()
        ctx.context = {
            "ticker": state.get("company_of_interest", ""),
            "trade_date": state.get("trade_date", ""),
        }
        ctx.reports = {
            "market_report": state.get("market_report", ""),
            "sentiment_report": state.get("sentiment_report", ""),
            "news_report": state.get("news_report", ""),
            "fundamentals_report": state.get("fundamentals_report", ""),
            "sector_report": state.get("sector_report", ""),
            "index_report": state.get("index_report", ""),
        }
        ctx.decisions = {
            "investment_debate": state.get("investment_debate_state", {}),
            "investment_plan": state.get("investment_plan", ""),
            "trade_signal": state.get("trader_investment_plan", ""),
            "risk_assessment": state.get("risk_debate_state", {}),
            "final_decision": state.get("final_trade_decision", ""),
        }
        return ctx
```

### DataAccessManager (数据访问管理器)

```python
class DataAccessManager:
    """数据访问权限管理器"""

    def __init__(self, context: AnalysisContext):
        self.context = context
        self.access_log: List[Dict] = []  # 访问日志

    def check_access(
        self,
        agent_id: str,
        contract: AgentDataContract,
        phase: int
    ) -> bool:
        """检查 Agent 是否有权限访问声明的数据"""
        for access in contract.inputs:
            if not self._validate_access(agent_id, access, phase, "read"):
                return False
        return True

    def get_data(
        self,
        agent_id: str,
        contract: AgentDataContract
    ) -> Dict[str, Any]:
        """根据契约获取 Agent 可访问的数据"""
        data = {}
        for access in contract.inputs:
            layer_data = getattr(self.context, access.layer.value, {})
            if access.fields:
                # 只获取指定字段
                for field in access.fields:
                    if field in layer_data:
                        data[field] = layer_data[field]
            else:
                # 获取整层数据
                data.update(layer_data)

            # 记录访问日志
            self._log_access(agent_id, access.layer, access.fields, "read")

        return data

    def set_data(
        self,
        agent_id: str,
        contract: AgentDataContract,
        outputs: Dict[str, Any]
    ) -> None:
        """根据契约写入 Agent 产出的数据"""
        for access in contract.outputs:
            for field in access.fields:
                if field in outputs:
                    self.context.set(access.layer, field, outputs[field], agent_id)
                    self._log_access(agent_id, access.layer, [field], "write")

    def _log_access(self, agent_id, layer, fields, action):
        self.access_log.append({
            "agent_id": agent_id,
            "layer": layer.value,
            "fields": fields,
            "action": action,
            "timestamp": datetime.now().isoformat()
        })
```

---

## 📊 数据流设计

### 设计原则

**Agent 数据获取与结果共享分离**：
- **数据获取**：Agent 通过各自的 tools 从 `dataflows` 获取所需数据
- **结果共享**：Agent 将分析结果写入 `AnalysisContext` 供其他 Agent 读取

这种设计保持了 Agent 的自主性，同时实现了结果的结构化共享。

### 完整数据流图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   阶段 1: 初始化 (DataCollectionPhase)                   │
├─────────────────────────────────────────────────────────────────────────┤
│  功能: 验证参数、规范化 ticker、检测市场类型                              │
│  输入: ticker="000858", trade_date="2025-01-17"                         │
│  写入: context.ticker, context.trade_date, context.market_type          │
│  注意: 不进行实际数据采集，Agent 通过 tools 自行获取数据                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐
│ MarketAnalyst     │    │ NewsAnalyst       │    │ FundamentalsAnalyst│
├───────────────────┤    ├───────────────────┤    ├───────────────────┤
│tools: 调用        │    │tools: 调用        │    │tools: 调用         │
│  dataflows 获取   │    │  dataflows 获取   │    │  dataflows 获取    │
│  行情数据         │    │  新闻数据         │    │  财务数据          │
│写: analysis_data. │    │写: reports.       │    │写: analysis_data.  │
│    technical      │    │    news_report    │    │    valuation       │
│    reports.market │    │                   │    │    reports.fund    │
└───────────────────┘    └───────────────────┘    └───────────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐
│ SentimentAnalyst  │    │ IndexAnalyst      │    │ SectorAnalyst     │
├───────────────────┤    ├───────────────────┤    ├───────────────────┤
│tools: 调用        │    │tools: 调用        │    │tools: 调用         │
│  dataflows 获取   │    │  dataflows 获取   │    │  dataflows 获取    │
│  社交/情绪数据    │    │  指数数据         │    │  板块数据          │
│写: analysis_data. │    │写: analysis_data. │    │写: analysis_data.  │
│    sentiment      │    │    market_breadth │    │    sector_ranking  │
│    reports.sent   │    │    reports.index  │    │    reports.sector  │
└───────────────────┘    └───────────────────┘    └───────────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    阶段 3: 研究辩论 (Researchers)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  读取: reports.* (所有分析师报告)                                        │
│  辩论: BullResearcher ←→ BearResearcher                                 │
│  写入: decisions.investment_debate (辩论历史)                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    阶段 4: 研究决策 (ResearchManager)                     │
├─────────────────────────────────────────────────────────────────────────┤
│  读取: reports.*, decisions.investment_debate                           │
│  判断: 综合多空观点，做出投资建议                                         │
│  写入: decisions.investment_plan                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    阶段 5: 交易决策 (Trader)                             │
├─────────────────────────────────────────────────────────────────────────┤
│  读取: reports.*, decisions.investment_plan                             │
│  决策: 具体的买入/卖出/持有建议                                          │
│  写入: decisions.trade_signal                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    阶段 6: 风险评估 (RiskAgents)                          │
├─────────────────────────────────────────────────────────────────────────┤
│  读取: reports.*, decisions.trade_signal                                │
│  辩论: RiskyRisk ←→ SafeRisk ←→ NeutralRisk                            │
│  写入: decisions.risk_assessment                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    阶段 7: 最终决策 (RiskManager)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  读取: ALL                                                              │
│  决策: 综合风险评估，做出最终分析结果                                     │
│  写入: decisions.final_decision                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 数据依赖矩阵

| Agent | 数据来源 | 读取 Context | 写入 Context |
|-------|---------|-------------|-------------|
| InitPhase | - | - | context.ticker, context.trade_date, context.market_type |
| MarketAnalyst | tools → dataflows | context.* | analysis_data.technical, reports.market |
| NewsAnalyst | tools → dataflows | context.* | reports.news |
| SentimentAnalyst | tools → dataflows | context.* | analysis_data.sentiment, reports.sentiment |
| FundamentalsAnalyst | tools → dataflows | context.* | analysis_data.valuation, reports.fundamentals |
| IndexAnalyst | tools → dataflows | context.* | analysis_data.market_breadth, reports.index |
| SectorAnalyst | tools → dataflows | context.* | analysis_data.sector_ranking, reports.sector |
| BullResearcher | reports.* | reports.* | decisions.debate |
| BearResearcher | reports.* | reports.* | decisions.debate |
| ResearchManager | decisions.* | reports.*, decisions.debate | decisions.plan |
| Trader | decisions.* | reports.*, decisions.plan | decisions.signal |
| RiskAgents | decisions.* | reports.*, decisions.signal | decisions.risk |
| RiskManager | ALL | ALL | decisions.final |

**说明**：
- **数据来源**：Agent 通过 tools 调用 dataflows 获取原始数据，或从 Context 读取其他 Agent 的分析结果
- **读取 Context**：Agent 从 AnalysisContext 读取的数据
- **写入 Context**：Agent 将分析结果写入 AnalysisContext 供后续 Agent 使用

---

## � 数据共享示例

### 场景：分析五粮液（000858.SZ）

以下示例展示各 Agent 如何通过 `DataAccessManager` 共享数据：

### 示例1: DataCollector 采集数据

```python
class DataCollector:
    """数据采集器 - 只能读 Context，写 RawData"""

    contract = AgentDataContract(
        agent_id="data_collector",
        inputs=[
            DataAccess(layer=DataLayer.CONTEXT, fields=["ticker", "trade_date", "market_type"])
        ],
        outputs=[
            DataAccess(layer=DataLayer.RAW_DATA, fields=["price_data", "sector_data", "index_data"])
        ]
    )

    def run(self, ctx: AnalysisContext, access: DataAccessManager):
        # 1️⃣ 通过 access manager 读取输入（自动验证权限）
        inputs = access.get_data(self.contract.agent_id, self.contract)
        # inputs = {"ticker": "000858.SZ", "trade_date": "2025-01-17", "market_type": "A_SHARE"}

        # 2️⃣ 调用 API 获取原始数据
        price_data = tushare_api.get_daily(inputs["ticker"], inputs["trade_date"])
        sector_data = tushare_api.get_sector_info(inputs["ticker"])
        index_data = tushare_api.get_index_daily("000001.SH", inputs["trade_date"])

        # 3️⃣ 通过 access manager 写入输出（自动记录数据血缘）
        access.set_data(self.contract.agent_id, self.contract, {
            "price_data": price_data,      # OHLCV 数据
            "sector_data": sector_data,    # 板块数据
            "index_data": index_data       # 指数数据
        })
        # 自动记录: data_lineage["raw_data.price_data"] = "data_collector"
```

### 示例2: MarketAnalyst 技术分析

```python
class MarketAnalyst:
    """市场分析师 - 读 Context+RawData，写 AnalysisData+Reports"""

    contract = AgentDataContract(
        agent_id="market_analyst",
        inputs=[
            DataAccess(layer=DataLayer.CONTEXT, fields=["ticker", "company_name"]),
            DataAccess(layer=DataLayer.RAW_DATA, fields=["price_data"])  # 只读价格数据
        ],
        outputs=[
            DataAccess(layer=DataLayer.ANALYSIS_DATA, fields=["technical"]),
            DataAccess(layer=DataLayer.REPORTS, fields=["market_report"])
        ],
        depends_on={"data_collector"}  # 依赖数据采集完成
    )

    def run(self, ctx: AnalysisContext, access: DataAccessManager):
        # 1️⃣ 获取输入数据（只能获取契约声明的字段）
        inputs = access.get_data(self.contract.agent_id, self.contract)
        # inputs = {
        #     "ticker": "000858.SZ",
        #     "company_name": "五粮液",
        #     "price_data": {"close": [168.5, 167.2, ...], "volume": [...]}
        # }

        # ❌ 无法访问未声明的字段
        # sector_data = inputs.get("sector_data")  # None，因为契约未声明

        # 2️⃣ 计算技术指标（结构化数据）
        technical = {
            "ma5": 168.5,
            "ma10": 165.3,
            "ma20": 162.8,
            "rsi": 45.2,
            "macd": {"dif": 1.2, "dea": 0.8, "histogram": 0.4}
        }

        # 3️⃣ 生成文本报告（调用 LLM）
        market_report = self.llm.generate_report(inputs, technical)

        # 4️⃣ 写入输出（只能写入契约声明的字段）
        access.set_data(self.contract.agent_id, self.contract, {
            "technical": technical,        # → analysis_data.technical
            "market_report": market_report # → reports.market_report
        })
```

### 示例3: BullResearcher 读取所有报告

```python
class BullResearcher:
    """看涨研究员 - 读所有 Reports，写 Decisions"""

    contract = AgentDataContract(
        agent_id="bull_researcher",
        inputs=[
            DataAccess(layer=DataLayer.CONTEXT, fields=["ticker", "company_name"]),
            DataAccess(layer=DataLayer.REPORTS),  # 🔥 空 fields = 读取整层所有数据
            DataAccess(layer=DataLayer.DECISIONS, fields=["investment_debate"], required=False)
        ],
        outputs=[
            DataAccess(layer=DataLayer.DECISIONS, fields=["investment_debate"])
        ],
        depends_on={"market_analyst", "news_analyst", "sector_analyst", "index_analyst"}
    )

    def run(self, ctx: AnalysisContext, access: DataAccessManager):
        # 1️⃣ 获取所有报告（自动聚合，无需知道具体字段名）
        inputs = access.get_data(self.contract.agent_id, self.contract)
        # inputs = {
        #     "ticker": "000858.SZ",
        #     "company_name": "五粮液",
        #     # 🔥 所有报告自动聚合，新增分析师的报告也会自动包含
        #     "market_report": "技术分析报告...",
        #     "news_report": "新闻分析报告...",
        #     "sector_report": "板块分析报告...",
        #     "index_report": "大盘分析报告...",
        #     "fundamentals_report": "基本面报告...",
        #     "sentiment_report": "情绪分析报告...",
        #     "fund_flow_report": "资金流向报告...",  # 🆕 新增分析师的报告自动出现
        #     "investment_debate": {...}  # 之前的辩论历史（可选）
        # }

        # 2️⃣ 构建看涨论点
        bull_argument = self.llm.generate_bull_case(inputs)

        # 3️⃣ 更新辩论状态
        debate = inputs.get("investment_debate", {"history": "", "bull_history": ""})
        debate["bull_history"] = debate.get("bull_history", "") + "\n" + bull_argument
        debate["history"] = debate.get("history", "") + "\n" + f"Bull: {bull_argument}"

        access.set_data(self.contract.agent_id, self.contract, {
            "investment_debate": debate
        })
```

### 示例4: Trader 使用结构化数据

```python
class Trader:
    """交易员 - 读 Reports + AnalysisData + Decisions，写交易信号"""

    contract = AgentDataContract(
        agent_id="trader",
        inputs=[
            DataAccess(layer=DataLayer.CONTEXT, fields=["ticker", "company_name"]),
            DataAccess(layer=DataLayer.REPORTS),  # 所有报告
            DataAccess(layer=DataLayer.ANALYSIS_DATA, fields=["technical", "valuation"]),  # 🔥 结构化数据
            DataAccess(layer=DataLayer.DECISIONS, fields=["investment_plan"])
        ],
        outputs=[
            DataAccess(layer=DataLayer.DECISIONS, fields=["trade_signal"])
        ],
        depends_on={"research_manager"}
    )

    def run(self, ctx: AnalysisContext, access: DataAccessManager):
        inputs = access.get_data(self.contract.agent_id, self.contract)
        # inputs = {
        #     "ticker": "000858.SZ",
        #     "company_name": "五粮液",
        #     "market_report": "...",
        #     "technical": {"ma5": 168.5, "rsi": 45.2, ...},  # 🔥 结构化数据可直接使用
        #     "valuation": {"pe": 25.3, "pb": 3.2, ...},
        #     "investment_plan": "综合分析建议买入，目标价180元..."
        # }

        # 🔥 可以直接使用结构化的技术指标，无需解析文本报告
        technical = inputs.get("technical", {})
        valuation = inputs.get("valuation", {})

        # 基于结构化数据做量化判断
        if technical.get("rsi", 50) < 30 and valuation.get("pe", 100) < 20:
            signal_action = "STRONG_BUY"
            reason = f"RSI={technical['rsi']}处于超卖区间，PE={valuation['pe']}估值合理"
        elif technical.get("rsi", 50) > 70:
            signal_action = "SELL"
            reason = f"RSI={technical['rsi']}处于超买区间"
        else:
            # 结合 LLM 分析
            signal_action = self.llm.generate_signal(inputs)
            reason = "综合分析结果"

        access.set_data(self.contract.agent_id, self.contract, {
            "trade_signal": {
                "action": signal_action,
                "ticker": inputs["ticker"],
                "price": technical.get("ma5", 0),
                "quantity_pct": 0.1,  # 建议仓位
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            }
        })
```

### 数据共享机制总结

```
┌─────────────────────────────────────────────────────────────────────┐
│                        数据共享流程                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Agent                    DataAccessManager              Context    │
│    │                            │                           │       │
│    │  1. get_data(contract)     │                           │       │
│    │ ───────────────────────────>                           │       │
│    │                            │  2. 验证契约权限           │       │
│    │                            │  3. 读取数据               │       │
│    │                            │ ───────────────────────────>       │
│    │                            │ <───────────────────────────       │
│    │                            │  4. 记录访问日志           │       │
│    │ <───────────────────────────                           │       │
│    │     返回 inputs dict       │                           │       │
│    │                            │                           │       │
│    │  ... Agent 处理数据 ...     │                           │       │
│    │                            │                           │       │
│    │  5. set_data(contract, outputs)                        │       │
│    │ ───────────────────────────>                           │       │
│    │                            │  6. 验证输出权限           │       │
│    │                            │  7. 写入数据               │       │
│    │                            │ ───────────────────────────>       │
│    │                            │  8. 记录数据血缘           │       │
│    │                            │     lineage[field]=agent   │       │
│    │ <───────────────────────────                           │       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 与当前系统的对比

| 对比项 | 当前方式 | 新设计方式 |
|--------|---------|-----------|
| **数据读取** | `state.get("xxx_report")` 硬编码 | `access.get_data(contract)` 按契约获取 |
| **数据写入** | `return {"xxx": value}` 直接写 | `access.set_data(contract, outputs)` 带验证 |
| **新增报告** | 修改多处代码添加字段 | 契约声明 `Reports` 层，自动聚合 |
| **结构化数据** | 只有文本报告 | 支持 `AnalysisData` 层存储结构化数据 |
| **数据追溯** | 无法追溯 | `data_lineage` 记录每个字段来源 |
| **权限控制** | 无，任意读写 | 按契约验证读写权限 |

---

## �🔌 与现有系统集成

### 兼容性设计

```python
class StockAnalysisEngine:
    """股票分析专用引擎 - 兼容现有 TradingAgentsGraph"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.context: Optional[AnalysisContext] = None
        self.access_manager: Optional[DataAccessManager] = None

        # 向后兼容：可以使用旧引擎
        self._legacy_graph: Optional[TradingAgentsGraph] = None

    def analyze(
        self,
        ticker: str,
        trade_date: str,
        use_legacy: bool = False
    ) -> Dict[str, Any]:
        """执行股票分析"""
        if use_legacy:
            # 使用旧引擎
            return self._run_legacy(ticker, trade_date)

        # 使用新引擎
        return self._run_new_engine(ticker, trade_date)

    def _run_new_engine(self, ticker: str, trade_date: str) -> Dict[str, Any]:
        """使用新分层架构执行分析"""
        # 1. 初始化上下文
        self.context = AnalysisContext()
        self.context.context = {
            "ticker": ticker,
            "trade_date": trade_date,
            "market_type": self._detect_market_type(ticker),
        }
        self.access_manager = DataAccessManager(self.context)

        # 2. 按阶段执行
        self._run_phase_1_data_collection()
        self._run_phase_2_analysts()
        self._run_phase_3_research_debate()
        self._run_phase_4_research_decision()
        self._run_phase_5_trade_decision()
        self._run_phase_6_risk_assessment()
        self._run_phase_7_final_decision()

        # 3. 返回结果（兼容旧格式）
        return self.context.to_legacy_state()

    def _run_legacy(self, ticker: str, trade_date: str) -> Dict[str, Any]:
        """使用旧引擎执行（向后兼容）"""
        if not self._legacy_graph:
            self._legacy_graph = TradingAgentsGraph(self.config)
        return self._legacy_graph.propagate(ticker, trade_date)
```

### 渐进式迁移策略

| 阶段 | 内容 | 影响范围 |
|------|------|---------|
| 1 | 定义 AnalysisContext 和 DataContract | 新增代码，无影响 |
| 2 | 实现 DataAccessManager | 新增代码，无影响 |
| 3 | 包装现有 Agent，添加契约声明 | 轻微修改现有代码 |
| 4 | 实现 StockAnalysisEngine | 新增代码，可选使用 |
| 5 | 迁移 DataCollector 到新架构 | 新引擎专用 |
| 6 | 逐步迁移其他 Agent | 新引擎专用 |
| 7 | 默认使用新引擎 | 全面切换 |

---

## 📁 目录结构

```
core/
├── engine/                          # 🆕 股票分析引擎
│   ├── __init__.py
│   ├── analysis_context.py          # AnalysisContext 实现
│   ├── data_contract.py             # 数据契约定义
│   ├── data_schema.py               # 🆕 动态数据字典
│   ├── contract_validator.py        # 🆕 契约验证器
│   ├── data_access_manager.py       # 数据访问管理器
│   ├── stock_analysis_engine.py     # 主引擎类
│   └── phase_executors/             # 阶段执行器
│       ├── data_collection.py       # 阶段1: 数据采集
│       ├── analysts.py              # 阶段2: 分析师
│       ├── research_debate.py       # 阶段3: 研究辩论
│       ├── research_decision.py     # 阶段4: 研究决策
│       ├── trade_decision.py        # 阶段5: 交易决策
│       ├── risk_assessment.py       # 阶段6: 风险评估
│       └── final_decision.py        # 阶段7: 最终决策
│
├── contracts/                       # 🆕 数据契约定义
│   ├── __init__.py
│   ├── analysts.py                  # 分析师契约
│   ├── researchers.py               # 研究员契约
│   ├── traders.py                   # 交易员契约
│   └── risk_managers.py             # 风险管理契约
│
├── agents/                          # 现有 Agent（逐步迁移）
│   ├── analyst_registry.py          # ✅ 已实现
│   ├── config.py                    # ✅ 已实现
│   └── adapters/                    # ✅ 已实现
│
└── utils/
    ├── report_aggregator.py         # ✅ 已实现
    └── data_lineage.py              # 🆕 数据血缘追踪

config/
├── data_schema.yaml                 # 🆕 扩展数据字段配置
└── ...
```

---

## 📋 实现计划

### Phase 1: 基础设施 (预计 4-6 天)

1. **定义数据模型** `core/engine/analysis_context.py`
   - [ ] AnalysisContext 类
   - [ ] 分层数据结构
   - [ ] to_legacy_state() / from_legacy_state() 转换

2. **定义数据契约** `core/engine/data_contract.py`
   - [ ] DataLayer 枚举
   - [ ] DataAccess 类
   - [ ] AgentDataContract 类

3. **实现动态数据字典** `core/engine/data_schema.py`
   - [ ] FieldDefinition 类
   - [ ] DynamicDataSchema 类（单例模式）
   - [ ] 核心字段硬编码
   - [ ] YAML 配置加载（扩展字段）
   - [ ] Agent 字段自动注册接口

4. **创建数据字典配置** `config/data_schema.yaml`
   - [ ] raw_data 层扩展字段
   - [ ] analysis_data 层扩展字段

5. **实现契约验证器** `core/engine/contract_validator.py`
   - [ ] validate_contract() 方法
   - [ ] validate_all_contracts() 方法
   - [ ] 核心字段冲突检测

6. **实现数据访问管理器** `core/engine/data_access_manager.py`
   - [ ] 权限检查（结合数据字典）
   - [ ] 数据读写
   - [ ] 访问日志
   - [ ] 数据血缘记录

### Phase 2: 契约定义 (预计 2-3 天)

1. **分析师契约** `core/contracts/analysts.py`
   - [ ] MARKET_ANALYST_CONTRACT
   - [ ] NEWS_ANALYST_CONTRACT
   - [ ] SENTIMENT_ANALYST_CONTRACT
   - [ ] FUNDAMENTALS_ANALYST_CONTRACT
   - [ ] SECTOR_ANALYST_CONTRACT
   - [ ] INDEX_ANALYST_CONTRACT

2. **研究员契约** `core/contracts/researchers.py`
   - [ ] BULL_RESEARCHER_CONTRACT
   - [ ] BEAR_RESEARCHER_CONTRACT
   - [ ] RESEARCH_MANAGER_CONTRACT

3. **交易和风控契约** `core/contracts/traders.py` / `risk_managers.py`
   - [ ] TRADER_CONTRACT
   - [ ] RISKY_RISK_CONTRACT
   - [ ] SAFE_RISK_CONTRACT
   - [ ] NEUTRAL_RISK_CONTRACT
   - [ ] RISK_MANAGER_CONTRACT

### Phase 3: 引擎实现 (预计 5-7 天)

1. **扩展 AnalystRegistry** `core/agents/analyst_registry.py`
   - [ ] 注册时自动将输出字段添加到数据字典
   - [ ] 注册时验证契约合法性

2. **主引擎类** `core/engine/stock_analysis_engine.py`
   - [ ] analyze() 主方法
   - [ ] 阶段调度器
   - [ ] 错误处理
   - [ ] 数据字典初始化

3. **阶段执行器** `core/engine/phase_executors/`
   - [ ] DataCollectionPhase
   - [ ] AnalystsPhase
   - [ ] ResearchDebatePhase
   - [ ] TradeDecisionPhase
   - [ ] RiskAssessmentPhase

### Phase 4: 集成测试 (预计 3-5 天)

1. **单元测试**
   - [ ] DynamicDataSchema 测试
   - [ ] ContractValidator 测试
   - [ ] AnalysisContext 测试
   - [ ] DataAccessManager 测试
   - [ ] 各阶段执行器测试

2. **集成测试**
   - [ ] 完整流程测试
   - [ ] 数据血缘测试
   - [ ] Agent 自动注册测试
   - [ ] 向后兼容性测试

---

## 🎯 预期收益

| 收益 | 说明 |
|------|------|
| **可扩展性** | 新增 Agent 只需定义契约，无需修改引擎 |
| **可维护性** | 数据依赖清晰，问题定位更容易 |
| **可测试性** | 契约化接口便于 Mock 测试 |
| **可追溯性** | 数据血缘追踪，知道每个数据的来源 |
| **可审计性** | 访问日志记录所有数据操作 |
| **向后兼容** | 支持渐进式迁移，不影响现有功能 |

---

## 🔗 相关文档

- [Agent 系统设计](./05-agent-system.md) - Agent 基础架构
- [新 Agent 实现计划](./new-agents-implementation-plan.md) - SectorAnalyst/IndexAnalyst 实现
- [工作流集成设计](./workflow-integration-design.md) - 工作流引擎集成

