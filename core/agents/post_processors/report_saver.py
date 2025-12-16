"""
报告保存Agent

将分析报告保存到多个目标（MongoDB、文件系统、S3等）
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..post_processor import PostProcessorAgent, PostProcessorType, OperationConfig, ConditionConfig
from ..config import AgentMetadata, AgentCategory, LicenseTier
from ..registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class ReportSaverAgent(PostProcessorAgent):
    """
    报告保存Agent
    
    支持保存到：
    - MongoDB
    - 文件系统（JSON、YAML等）
    - S3/OSS（未来支持）
    """
    
    metadata = AgentMetadata(
        id="report_saver",
        name="报告保存器",
        description="将分析报告保存到多个目标（MongoDB、文件系统等）",
        category=AgentCategory.POST_PROCESSOR,
        version="1.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],  # 后处理Agent不需要工具
    )
    
    processor_type = PostProcessorType.SAVE_REPORT
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        operations: Optional[List[OperationConfig]] = None,
        conditions: Optional[List[ConditionConfig]] = None,
        **kwargs
    ):
        """
        初始化报告保存Agent
        
        Args:
            config: Agent配置
            operations: 操作配置列表，格式：
                [
                    {
                        "type": "save_to_mongodb",
                        "collection": "analysis_reports",
                        "fields": ["analysis_id", "stock_symbol", "reports"]
                    },
                    {
                        "type": "save_to_file",
                        "path": "data/reports/{ticker}_{date}.json",
                        "format": "json"
                    }
                ]
            conditions: 执行条件列表
            **kwargs: 其他参数
        """
        super().__init__(config=config, operations=operations, conditions=conditions, **kwargs)
        
        # 初始化MongoDB连接（延迟加载）
        self._mongodb_client = None
    
    def _execute_operation(self, operation: OperationConfig, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行保存操作
        
        Args:
            operation: 操作配置
            state: 工作流状态
            
        Returns:
            操作执行结果
        """
        operation_type = operation.get("type")
        
        if operation_type == "save_to_mongodb":
            return self._save_to_mongodb(operation, state)
        elif operation_type == "save_to_file":
            return self._save_to_file(operation, state)
        elif operation_type == "save_to_s3":
            return self._save_to_s3(operation, state)
        else:
            logger.warning(f"未知的操作类型: {operation_type}")
            return {
                "success": False,
                "operation_type": operation_type,
                "error": f"Unknown operation type: {operation_type}"
            }
    
    def _save_to_mongodb(self, operation: OperationConfig, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        保存到MongoDB
        
        Args:
            operation: 操作配置
            state: 工作流状态
            
        Returns:
            操作结果
        """
        try:
            from tradingagents.config.mongodb_storage import MongoDBStorage
            
            collection_name = operation.get("collection", "analysis_reports")
            fields = operation.get("fields", [])
            
            # 构建要保存的文档
            document = {}
            for field in fields:
                value = self._get_nested_value(state, field)
                if value is not None:
                    document[field] = value
            
            # 添加时间戳
            document["created_at"] = datetime.now()
            document["updated_at"] = datetime.now()
            
            # 保存到MongoDB
            storage = MongoDBStorage()
            result = storage.save_document(collection_name, document)
            
            logger.info(f"报告已保存到MongoDB: {collection_name}")
            
            return {
                "success": True,
                "operation_type": "save_to_mongodb",
                "collection": collection_name,
                "document_id": str(result.inserted_id) if result else None
            }
            
        except Exception as e:
            logger.error(f"保存到MongoDB失败: {e}", exc_info=True)
            return {
                "success": False,
                "operation_type": "save_to_mongodb",
                "error": str(e)
            }
    
    def _save_to_file(self, operation: OperationConfig, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        保存到文件系统

        Args:
            operation: 操作配置，格式：
                {
                    "type": "save_to_file",
                    "path": "data/reports/{ticker}_{date}.json",
                    "format": "json"
                }
            state: 工作流状态

        Returns:
            操作结果
        """
        try:
            path_template = operation.get("path")
            file_format = operation.get("format", "json")

            if not path_template:
                raise ValueError("Missing 'path' in operation config")

            # 替换路径中的变量
            file_path = self._render_path(path_template, state)

            # 确保目录存在
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)

            # 准备要保存的数据
            data = self._prepare_save_data(state)

            # 根据格式保存
            if file_format == "json":
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            elif file_format == "yaml":
                import yaml
                with open(file_path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, allow_unicode=True)
            else:
                raise ValueError(f"Unsupported format: {file_format}")

            logger.info(f"报告已保存到文件: {file_path}")

            return {
                "success": True,
                "operation_type": "save_to_file",
                "file_path": file_path,
                "format": file_format
            }

        except Exception as e:
            logger.error(f"保存到文件失败: {e}", exc_info=True)
            return {
                "success": False,
                "operation_type": "save_to_file",
                "error": str(e)
            }

    def _render_path(self, path_template: str, state: Dict[str, Any]) -> str:
        """
        渲染路径模板

        Args:
            path_template: 路径模板，如 "data/reports/{ticker}_{date}.json"
            state: 工作流状态

        Returns:
            渲染后的路径
        """
        # 提取常用变量
        variables = {
            "ticker": state.get("ticker", "unknown"),
            "date": state.get("analysis_date", datetime.now().strftime("%Y%m%d")),
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        }

        # 渲染路径
        try:
            return path_template.format(**variables)
        except KeyError as e:
            logger.warning(f"路径模板变量缺失: {e}")
            return path_template

    def _prepare_save_data(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        准备要保存的数据

        Args:
            state: 工作流状态

        Returns:
            要保存的数据字典
        """
        # 默认保存整个state，子类可以覆盖此方法
        return {
            "ticker": state.get("ticker"),
            "analysis_date": state.get("analysis_date"),
            "reports": {
                "market_report": state.get("market_report"),
                "news_report": state.get("news_report"),
                "fundamentals_report": state.get("fundamentals_report"),
                "bull_report": state.get("bull_report"),
                "bear_report": state.get("bear_report"),
                "investment_plan": state.get("investment_plan"),
                "trading_plan": state.get("trading_plan"),
            },
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "workflow_id": state.get("workflow_id"),
            }
        }
    
    def _save_to_s3(self, operation: OperationConfig, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        保存到S3/OSS
        
        Args:
            operation: 操作配置
            state: 工作流状态
            
        Returns:
            操作结果
        """
        pass  # 未来实现

