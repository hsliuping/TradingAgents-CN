# tradingagents/core/engine/data_schema.py
"""
动态数据字典

管理所有合法的数据字段定义，支持三种字段来源：
1. 核心字段 - 代码硬编码，系统必需
2. Agent 字段 - Agent 注册时自动添加
3. 扩展字段 - YAML 配置文件定义
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Any, Optional, List
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from tradingagents.core.engine.data_contract import DataLayer


@dataclass
class FieldDefinition:
    """
    字段定义
    
    Attributes:
        name: 字段名称
        field_type: 字段类型（string, object, array, number, boolean, any）
        required: 是否必填
        default: 默认值
        description: 字段描述
        source: 数据来源（Agent ID 或 'core' 或 'config'）
    """
    name: str
    field_type: str = "any"
    required: bool = False
    default: Any = None
    description: str = ""
    source: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "type": self.field_type,
            "required": self.required,
            "default": self.default,
            "description": self.description,
            "source": self.source,
        }


class DynamicDataSchema:
    """
    动态数据字典
    
    支持三种字段来源：
    1. 核心字段 - 代码硬编码，系统必需
    2. Agent 字段 - Agent 注册时自动添加
    3. 扩展字段 - YAML 配置文件定义
    
    使用单例模式，确保全局只有一个数据字典实例。
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
        self._core_fields: Dict[DataLayer, Dict[str, FieldDefinition]] = self._init_core_fields()
        
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
    
    def _init_core_fields(self) -> Dict[DataLayer, Dict[str, FieldDefinition]]:
        """初始化核心字段（硬编码）"""
        return {
            DataLayer.CONTEXT: {
                "ticker": FieldDefinition(
                    name="ticker",
                    field_type="string",
                    required=True,
                    description="股票代码，如 000858.SZ",
                    source="core"
                ),
                "trade_date": FieldDefinition(
                    name="trade_date",
                    field_type="string",
                    required=True,
                    description="分析日期，格式 YYYY-MM-DD",
                    source="core"
                ),
                "market_type": FieldDefinition(
                    name="market_type",
                    field_type="string",
                    default="A_SHARE",
                    description="市场类型: A_SHARE, HK, US",
                    source="core"
                ),
                "company_name": FieldDefinition(
                    name="company_name",
                    field_type="string",
                    default="",
                    description="公司名称",
                    source="core"
                ),
                "currency": FieldDefinition(
                    name="currency",
                    field_type="string",
                    default="CNY",
                    description="货币代码: CNY, HKD, USD",
                    source="core"
                ),
            },
            DataLayer.RAW_DATA: {},
            DataLayer.ANALYSIS_DATA: {},
            DataLayer.REPORTS: {},
            DataLayer.DECISIONS: {
                "investment_debate": FieldDefinition(
                    name="investment_debate",
                    field_type="object",
                    description="投资辩论历史",
                    source="core"
                ),
                "investment_plan": FieldDefinition(
                    name="investment_plan",
                    field_type="string",
                    description="投资计划",
                    source="core"
                ),
                "trade_signal": FieldDefinition(
                    name="trade_signal",
                    field_type="object",
                    description="交易信号",
                    source="core"
                ),
                "risk_assessment": FieldDefinition(
                    name="risk_assessment",
                    field_type="object",
                    description="风险评估",
                    source="core"
                ),
                "final_decision": FieldDefinition(
                    name="final_decision",
                    field_type="string",
                    description="最终交易决策",
                    source="core"
                ),
            },
        }

    def _load_extend_schema(self, config_path: str = None):
        """
        从 YAML 配置文件加载扩展字段

        Args:
            config_path: 配置文件路径，默认为 config/data_schema.yaml
        """
        if config_path is None:
            # 尝试多个可能的路径
            possible_paths = [
                Path("config/data_schema.yaml"),
                Path(__file__).parent.parent.parent.parent / "config" / "data_schema.yaml",
            ]
            for p in possible_paths:
                if p.exists():
                    config_path = str(p)
                    break

        if not config_path:
            return

        path = Path(config_path)
        if not path.exists():
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except Exception:
            return

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

    def register_agent_fields(self, agent_id: str, outputs: List) -> None:
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

        Args:
            layer: 数据层

        Returns:
            字段名 -> FieldDefinition 的字典
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

    def get_fields_by_source(self, source: str) -> Dict[DataLayer, List[str]]:
        """
        获取某个来源产出的所有字段

        Args:
            source: 数据来源（Agent ID 或 'core' 或 'config'）

        Returns:
            数据层 -> 字段名列表 的字典
        """
        result = {}
        for layer in DataLayer:
            fields = []
            for field_name, field_def in self.get_all_fields(layer).items():
                if field_def.source == source:
                    fields.append(field_name)
            if fields:
                result[layer] = fields
        return result

    def is_core_field(self, layer: DataLayer, field_name: str) -> bool:
        """检查是否为核心字段"""
        return field_name in self._core_fields.get(layer, {})

    def reset_agent_fields(self) -> None:
        """重置所有 Agent 动态字段（用于测试）"""
        self._agent_fields = {layer: {} for layer in DataLayer}

    def reload_extend_schema(self, config_path: str = None) -> None:
        """重新加载扩展字段配置"""
        self._extend_fields = {layer: {} for layer in DataLayer}
        self._load_extend_schema(config_path)


# 全局单例
data_schema = DynamicDataSchema()

