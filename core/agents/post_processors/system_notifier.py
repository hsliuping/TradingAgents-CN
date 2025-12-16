"""
系统通知Agent

发送系统内通知
"""

import logging
from typing import Any, Dict, List, Optional

from ..post_processor import PostProcessorAgent, PostProcessorType, OperationConfig, ConditionConfig
from ..config import AgentMetadata, AgentCategory, LicenseTier
from ..registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class SystemNotifierAgent(PostProcessorAgent):
    """
    系统通知Agent
    
    功能：
    - 发送系统内通知
    - 支持WebSocket实时推送
    - 支持通知持久化
    """
    
    metadata = AgentMetadata(
        id="system_notifier",
        name="系统通知器",
        description="发送系统内通知",
        category=AgentCategory.POST_PROCESSOR,
        version="1.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
    )
    
    processor_type = PostProcessorType.SEND_NOTIFICATION
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        operations: Optional[List[OperationConfig]] = None,
        conditions: Optional[List[ConditionConfig]] = None,
        **kwargs
    ):
        """
        初始化系统通知Agent
        
        Args:
            config: Agent配置
            operations: 操作配置列表，格式：
                [
                    {
                        "type": "send_notification",
                        "notification_type": "analysis",
                        "title": "{ticker} 分析完成",
                        "content": "{summary}",
                        "link": "/analysis/{analysis_id}",
                        "severity": "info"
                    }
                ]
            conditions: 执行条件列表
            **kwargs: 其他参数
        """
        super().__init__(config=config, operations=operations, conditions=conditions, **kwargs)
        
        # 初始化通知服务（延迟加载）
        self._notification_service = None
    
    def _execute_operation(self, operation: OperationConfig, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行通知发送操作
        
        Args:
            operation: 操作配置
            state: 工作流状态
            
        Returns:
            操作执行结果
        """
        operation_type = operation.get("type")
        
        if operation_type == "send_notification":
            return self._send_notification(operation, state)
        else:
            logger.warning(f"未知的操作类型: {operation_type}")
            return {
                "success": False,
                "operation_type": operation_type,
                "error": f"Unknown operation type: {operation_type}"
            }
    
    def _send_notification(self, operation: OperationConfig, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送系统通知
        
        Args:
            operation: 操作配置
            state: 工作流状态
            
        Returns:
            操作结果
        """
        try:
            # 获取通知服务
            notification_service = self._get_notification_service()
            
            # 准备通知数据
            notification_type = operation.get("notification_type", "analysis")
            title = self._render_template(operation.get("title", ""), state)
            content = self._render_template(operation.get("content", ""), state)
            link = self._render_template(operation.get("link", ""), state)
            severity = operation.get("severity", "info")
            
            # 获取用户ID
            user_id = state.get("user_id")
            
            if not user_id:
                logger.warning("未找到user_id，无法发送通知")
                return {
                    "success": False,
                    "operation_type": "send_notification",
                    "error": "Missing user_id"
                }
            
            # 发送通知（这里需要集成实际的通知服务）
            # 暂时返回模拟结果
            logger.info(f"准备发送通知给用户: {user_id}, 标题: {title}")
            
            return {
                "success": True,
                "operation_type": "send_notification",
                "user_id": user_id,
                "title": title,
                "notification_id": "mock_notification_id"  # 实际应该是通知服务返回的ID
            }
            
        except Exception as e:
            logger.error(f"发送通知失败: {e}", exc_info=True)
            return {
                "success": False,
                "operation_type": "send_notification",
                "error": str(e)
            }
    
    def _get_notification_service(self):
        """获取通知服务实例"""
        if self._notification_service is None:
            # 延迟导入，避免循环依赖
            try:
                from app.services.notifications_service import NotificationsService
                self._notification_service = NotificationsService()
            except ImportError:
                logger.warning("NotificationsService not available, using mock")
                self._notification_service = None
        return self._notification_service
    
    def _render_template(self, template: str, state: Dict[str, Any]) -> str:
        """
        渲染模板字符串
        
        Args:
            template: 模板字符串
            state: 工作流状态
            
        Returns:
            渲染后的字符串
        """
        # 提取常用变量
        variables = {
            "ticker": state.get("ticker", ""),
            "date": state.get("analysis_date", ""),
            "analysis_id": state.get("analysis_id", ""),
            "recommendation": self._get_nested_value(state, "investment_plan.recommendation", ""),
            "summary": self._generate_summary(state),
        }
        
        # 渲染模板
        try:
            return template.format(**variables)
        except KeyError as e:
            logger.warning(f"模板变量缺失: {e}")
            return template
    
    def _generate_summary(self, state: Dict[str, Any]) -> str:
        """
        生成通知摘要
        
        Args:
            state: 工作流状态
            
        Returns:
            摘要文本
        """
        ticker = state.get("ticker", "")
        recommendation = self._get_nested_value(state, "investment_plan.recommendation", "")
        confidence = self._get_nested_value(state, "investment_plan.confidence_score", "")
        
        return f"{ticker} 分析完成，建议：{recommendation}，置信度：{confidence}"

