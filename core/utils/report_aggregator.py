"""
报告聚合器

动态获取所有分析报告，替代硬编码字段获取

用法:
    from core.utils.report_aggregator import ReportAggregator, get_all_reports
    
    # 方式1：使用便捷函数
    reports = get_all_reports(state)
    curr_situation = reports.to_text()
    
    # 方式2：使用类
    aggregator = ReportAggregator()
    reports = aggregator.aggregate(state)
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from ..agents.analyst_registry import get_analyst_registry
from ..agents.config import AgentMetadata, BUILTIN_AGENTS

# 导入日志
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


@dataclass
class AggregatedReports:
    """聚合后的报告集合"""
    
    reports: Dict[str, str] = field(default_factory=dict)  # {field_name: content}
    labels: Dict[str, str] = field(default_factory=dict)   # {field_name: label}
    order: List[str] = field(default_factory=list)         # 按执行顺序排列的字段名
    
    def get(self, field_name: str, default: str = "") -> str:
        """获取指定报告"""
        return self.reports.get(field_name, default)
    
    def to_dict(self) -> Dict[str, str]:
        """转换为字典"""
        return self.reports.copy()
    
    def to_text(self, separator: str = "\n\n") -> str:
        """
        转换为文本（按执行顺序，带标签）
        
        Returns:
            格式化的报告文本
        """
        parts = []
        for field_name in self.order:
            content = self.reports.get(field_name, "")
            if content:
                label = self.labels.get(field_name, "")
                if label:
                    parts.append(f"{label}\n{content}")
                else:
                    parts.append(content)
        return separator.join(parts)
    
    def to_text_simple(self, separator: str = "\n\n") -> str:
        """
        转换为文本（不带标签，用于向后兼容）
        """
        parts = []
        for field_name in self.order:
            content = self.reports.get(field_name, "")
            if content:
                parts.append(content)
        return separator.join(parts)
    
    def __len__(self) -> int:
        return len([r for r in self.reports.values() if r])


class ReportAggregator:
    """
    报告聚合器
    
    从 state 中动态获取所有分析报告
    """
    
    # 默认的报告字段（向后兼容）
    DEFAULT_FIELDS = [
        ("index_report", "【宏观大盘分析】", 1),
        ("sector_report", "【行业板块分析】", 5),
        ("market_report", "【技术分析】", 10),
        ("sentiment_report", "【舆情分析】", 20),
        ("news_report", "【新闻分析】", 30),
        ("fundamentals_report", "【基本面分析】", 40),
    ]
    
    def __init__(self, use_registry: bool = True):
        """
        初始化聚合器
        
        Args:
            use_registry: 是否使用注册表获取字段（False 则使用默认字段）
        """
        self.use_registry = use_registry
        self._field_config: Optional[List[tuple]] = None
    
    def _get_field_config(self) -> List[tuple]:
        """获取字段配置 [(field_name, label, order), ...]"""
        if self._field_config is not None:
            return self._field_config
        
        if self.use_registry:
            config = []
            # 从内置 Agent 元数据获取
            for agent_id, metadata in BUILTIN_AGENTS.items():
                if metadata.output_field:
                    config.append((
                        metadata.output_field,
                        metadata.report_label or "",
                        metadata.execution_order
                    ))
            
            # 从注册表获取额外的（如果有）
            registry = get_analyst_registry()
            for analyst_id in registry.list_all():
                meta = registry.get_analyst_metadata(analyst_id)
                if meta and meta.output_field:
                    # 避免重复
                    if not any(f[0] == meta.output_field for f in config):
                        config.append((
                            meta.output_field,
                            meta.report_label or "",
                            meta.execution_order
                        ))
            
            # 按执行顺序排序
            self._field_config = sorted(config, key=lambda x: x[2])
        else:
            self._field_config = self.DEFAULT_FIELDS
        
        return self._field_config
    
    def aggregate(self, state: Dict[str, Any]) -> AggregatedReports:
        """
        从 state 聚合所有报告
        
        Args:
            state: 工作流状态字典
            
        Returns:
            AggregatedReports 实例
        """
        result = AggregatedReports()
        
        for field_name, label, order in self._get_field_config():
            content = state.get(field_name, "")
            if content:
                result.reports[field_name] = content
                result.labels[field_name] = label
                result.order.append(field_name)
        
        logger.debug(f"📊 [报告聚合] 获取到 {len(result)} 份报告")
        return result
    
    def get_report_fields(self) -> List[str]:
        """获取所有报告字段名"""
        return [f[0] for f in self._get_field_config()]


# 全局实例
_aggregator: Optional[ReportAggregator] = None


def get_aggregator() -> ReportAggregator:
    """获取全局聚合器实例"""
    global _aggregator
    if _aggregator is None:
        _aggregator = ReportAggregator()
    return _aggregator


def get_all_reports(state: Dict[str, Any]) -> AggregatedReports:
    """
    便捷函数：从 state 获取所有报告
    
    用法:
        reports = get_all_reports(state)
        curr_situation = reports.to_text()
    """
    return get_aggregator().aggregate(state)

