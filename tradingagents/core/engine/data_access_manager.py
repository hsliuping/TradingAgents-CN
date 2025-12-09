# tradingagents/core/engine/data_access_manager.py
"""
数据访问管理器

提供基于契约的数据访问控制，包括：
- 权限验证：根据契约验证读写权限
- 数据读取：按契约聚合输入数据
- 数据写入：按契约写入输出数据并记录血缘
- 访问日志：记录所有数据访问操作
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from tradingagents.core.engine.data_contract import AgentDataContract, DataAccess, DataLayer
from tradingagents.core.engine.analysis_context import AnalysisContext


@dataclass
class AccessLogEntry:
    """访问日志条目"""
    agent_id: str
    layer: str
    fields: List[str]
    action: str  # 'read' or 'write'
    timestamp: str
    success: bool = True
    error: Optional[str] = None


class DataAccessManager:
    """
    数据访问权限管理器
    
    基于 Agent 契约控制数据访问：
    - 读取时验证输入权限，聚合契约声明的数据
    - 写入时验证输出权限，记录数据血缘
    - 记录所有访问操作的日志
    
    Attributes:
        context: 分析上下文
        access_log: 访问日志列表
    """
    
    def __init__(self, context: AnalysisContext):
        """
        初始化数据访问管理器
        
        Args:
            context: 分析上下文实例
        """
        self.context = context
        self.access_log: List[AccessLogEntry] = []
    
    def get_data(self, agent_id: str, contract: AgentDataContract) -> Dict[str, Any]:
        """
        根据契约获取 Agent 的输入数据
        
        按契约声明的输入层和字段聚合数据：
        - 指定 fields 时只返回这些字段
        - fields 为空时返回整层所有数据
        
        Args:
            agent_id: Agent 标识
            contract: Agent 数据契约
            
        Returns:
            聚合的输入数据字典
            
        Raises:
            PermissionError: 如果访问了契约未声明的数据
        """
        data = {}
        
        for access in contract.inputs:
            layer_data = self.context.get_layer(access.layer)
            
            if access.fields:
                # 获取指定字段
                for field_name in access.fields:
                    if field_name in layer_data:
                        data[field_name] = layer_data[field_name]
                    elif access.required:
                        # 必需字段不存在时可以选择报错或返回 None
                        data[field_name] = None
            else:
                # 获取整层数据
                data.update(layer_data)
            
            # 记录访问日志
            self._log_access(agent_id, access.layer, access.fields or list(layer_data.keys()), "read")
        
        return data
    
    def set_data(
        self, 
        agent_id: str, 
        contract: AgentDataContract, 
        outputs: Dict[str, Any]
    ) -> None:
        """
        根据契约写入 Agent 产出的数据
        
        按契约声明的输出层和字段写入数据，并记录数据血缘。
        
        Args:
            agent_id: Agent 标识
            contract: Agent 数据契约
            outputs: 要写入的输出数据字典
            
        Raises:
            PermissionError: 如果写入了契约未声明的字段
        """
        for access in contract.outputs:
            for field_name in access.fields:
                if field_name in outputs:
                    # 写入数据并记录血缘
                    self.context.set(access.layer, field_name, outputs[field_name], agent_id)
                    self._log_access(agent_id, access.layer, [field_name], "write")
    
    def _log_access(
        self, 
        agent_id: str, 
        layer: DataLayer, 
        fields: List[str], 
        action: str,
        success: bool = True,
        error: str = None
    ) -> None:
        """记录数据访问日志"""
        entry = AccessLogEntry(
            agent_id=agent_id,
            layer=layer.value,
            fields=fields,
            action=action,
            timestamp=datetime.now().isoformat(),
            success=success,
            error=error
        )
        self.access_log.append(entry)
    
    def get_access_log(self, agent_id: str = None) -> List[AccessLogEntry]:
        """
        获取访问日志
        
        Args:
            agent_id: 可选，过滤指定 Agent 的日志
            
        Returns:
            访问日志列表
        """
        if agent_id:
            return [log for log in self.access_log if log.agent_id == agent_id]
        return self.access_log.copy()
    
    def get_data_lineage(self, layer: DataLayer = None, field_name: str = None) -> Dict[str, str]:
        """
        获取数据血缘信息

        Args:
            layer: 可选，过滤指定层
            field_name: 可选，过滤指定字段

        Returns:
            字段路径 -> 来源 Agent 的字典
        """
        lineage = self.context.data_lineage.copy()

        if layer:
            prefix = f"{layer.value}."
            lineage = {k: v for k, v in lineage.items() if k.startswith(prefix)}

        if field_name:
            lineage = {k: v for k, v in lineage.items() if k.endswith(f".{field_name}")}

        return lineage

    def validate_access(self, agent_id: str, contract: AgentDataContract,
                       layer: DataLayer, field_name: str, action: str) -> bool:
        """
        验证 Agent 是否有权访问指定字段

        Args:
            agent_id: Agent 标识
            contract: Agent 数据契约
            layer: 数据层
            field_name: 字段名
            action: 'read' 或 'write'

        Returns:
            是否有权限
        """
        if action == "read":
            return contract.has_input_access(layer, field_name)
        elif action == "write":
            return contract.has_output_access(layer, field_name)
        return False

    def get_all_reports(self) -> Dict[str, str]:
        """
        获取所有报告（便捷方法）

        Returns:
            报告名 -> 报告内容 的字典
        """
        return self.context.get_layer(DataLayer.REPORTS)

    def get_context_info(self) -> Dict[str, Any]:
        """
        获取上下文基础信息（便捷方法）

        Returns:
            包含 ticker, trade_date 等基础信息的字典
        """
        return self.context.get_layer(DataLayer.CONTEXT)

    def clear_access_log(self) -> None:
        """清空访问日志"""
        self.access_log.clear()

    def get_access_summary(self) -> Dict[str, Any]:
        """
        获取访问统计摘要

        Returns:
            包含读写次数、Agent 活动等统计信息
        """
        read_count = sum(1 for log in self.access_log if log.action == "read")
        write_count = sum(1 for log in self.access_log if log.action == "write")

        agents = set(log.agent_id for log in self.access_log)
        layers_accessed = set(log.layer for log in self.access_log)

        return {
            "total_operations": len(self.access_log),
            "read_count": read_count,
            "write_count": write_count,
            "unique_agents": len(agents),
            "agents": list(agents),
            "layers_accessed": list(layers_accessed),
        }

