"""
邮件通知Agent

根据条件发送邮件通知
"""

import logging
from typing import Any, Dict, List, Optional

from ..post_processor import PostProcessorAgent, PostProcessorType, OperationConfig, ConditionConfig
from ..config import AgentMetadata, AgentCategory, LicenseTier
from ..registry import register_agent

logger = logging.getLogger(__name__)


@register_agent
class EmailNotifierAgent(PostProcessorAgent):
    """
    邮件通知Agent
    
    功能：
    - 发送分析完成通知邮件
    - 支持模板渲染
    - 支持附件
    - 可选使用LLM生成邮件摘要
    """
    
    metadata = AgentMetadata(
        id="email_notifier",
        name="邮件通知器",
        description="根据条件发送邮件通知",
        category=AgentCategory.POST_PROCESSOR,
        version="1.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
    )
    
    processor_type = PostProcessorType.SEND_EMAIL
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        operations: Optional[List[OperationConfig]] = None,
        conditions: Optional[List[ConditionConfig]] = None,
        **kwargs
    ):
        """
        初始化邮件通知Agent
        
        Args:
            config: Agent配置
            operations: 操作配置列表，格式：
                [
                    {
                        "type": "send_email",
                        "template": "analysis_complete",
                        "to": "{user.email}",
                        "subject": "{ticker} 分析完成",
                        "use_llm_summary": true,
                        "attachments": [...]
                    }
                ]
            conditions: 执行条件列表
            **kwargs: 其他参数
        """
        super().__init__(config=config, operations=operations, conditions=conditions, **kwargs)
        
        # 初始化邮件服务（延迟加载）
        self._email_service = None
    
    def _execute_operation(self, operation: OperationConfig, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行邮件发送操作
        
        Args:
            operation: 操作配置
            state: 工作流状态
            
        Returns:
            操作执行结果
        """
        operation_type = operation.get("type")
        
        if operation_type == "send_email":
            return self._send_email(operation, state)
        else:
            logger.warning(f"未知的操作类型: {operation_type}")
            return {
                "success": False,
                "operation_type": operation_type,
                "error": f"Unknown operation type: {operation_type}"
            }
    
    def _send_email(self, operation: OperationConfig, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送邮件
        
        Args:
            operation: 操作配置
            state: 工作流状态
            
        Returns:
            操作结果
        """
        try:
            # 获取邮件服务
            email_service = self._get_email_service()
            
            # 准备邮件数据
            to_email = self._render_template(operation.get("to", ""), state)
            subject = self._render_template(operation.get("subject", ""), state)
            template_name = operation.get("template", "analysis_complete")
            use_llm_summary = operation.get("use_llm_summary", False)
            
            # 准备模板数据
            template_data = self._prepare_template_data(state, use_llm_summary)
            
            # 准备附件
            attachments = self._prepare_attachments(operation.get("attachments", []), state)
            
            # 发送邮件（这里需要集成实际的邮件服务）
            # 暂时返回模拟结果
            logger.info(f"准备发送邮件到: {to_email}, 主题: {subject}")
            
            return {
                "success": True,
                "operation_type": "send_email",
                "to": to_email,
                "subject": subject,
                "template": template_name,
                "email_id": "mock_email_id"  # 实际应该是邮件服务返回的ID
            }
            
        except Exception as e:
            logger.error(f"发送邮件失败: {e}", exc_info=True)
            return {
                "success": False,
                "operation_type": "send_email",
                "error": str(e)
            }
    
    def _get_email_service(self):
        """获取邮件服务实例"""
        if self._email_service is None:
            # 延迟导入，避免循环依赖
            try:
                from app.services.email_service import EmailService
                self._email_service = EmailService()
            except ImportError:
                logger.warning("EmailService not available, using mock")
                self._email_service = None
        return self._email_service
    
    def _render_template(self, template: str, state: Dict[str, Any]) -> str:
        """
        渲染模板字符串

        Args:
            template: 模板字符串，如 "{ticker} 分析完成"
            state: 工作流状态

        Returns:
            渲染后的字符串
        """
        # 提取常用变量
        variables = {
            "ticker": state.get("ticker", ""),
            "date": state.get("analysis_date", ""),
            "recommendation": self._get_nested_value(state, "investment_plan.recommendation", ""),
            "confidence": self._get_nested_value(state, "investment_plan.confidence_score", ""),
        }

        # 渲染模板
        try:
            return template.format(**variables)
        except KeyError as e:
            logger.warning(f"模板变量缺失: {e}")
            return template

    def _prepare_template_data(self, state: Dict[str, Any], use_llm_summary: bool = False) -> Dict[str, Any]:
        """
        准备邮件模板数据

        Args:
            state: 工作流状态
            use_llm_summary: 是否使用LLM生成摘要

        Returns:
            模板数据字典
        """
        template_data = {
            "ticker": state.get("ticker"),
            "analysis_date": state.get("analysis_date"),
            "recommendation": self._get_nested_value(state, "investment_plan.recommendation"),
            "confidence_score": self._get_nested_value(state, "investment_plan.confidence_score"),
            "reports": {
                "market": state.get("market_report"),
                "news": state.get("news_report"),
                "fundamentals": state.get("fundamentals_report"),
            }
        }

        # 如果需要LLM摘要
        if use_llm_summary and self._llm:
            summary = self._generate_llm_summary(state)
            template_data["llm_summary"] = summary

        return template_data

    def _generate_llm_summary(self, state: Dict[str, Any]) -> str:
        """
        使用LLM生成邮件摘要

        Args:
            state: 工作流状态

        Returns:
            摘要文本
        """
        try:
            from langchain_core.messages import HumanMessage

            # 构建提示词
            prompt = f"""请用3句话总结以下股票分析报告的核心观点：

股票代码：{state.get('ticker')}
投资建议：{self._get_nested_value(state, 'investment_plan.recommendation')}
置信度：{self._get_nested_value(state, 'investment_plan.confidence_score')}

请简洁明了地总结关键信息。"""

            # 调用LLM
            response = self._llm.invoke([HumanMessage(content=prompt)])
            return response.content

        except Exception as e:
            logger.error(f"生成LLM摘要失败: {e}")
            return "摘要生成失败"

    def _prepare_attachments(self, attachments_config: List[Dict], state: Dict[str, Any]) -> List[tuple]:
        """
        准备邮件附件

        Args:
            attachments_config: 附件配置列表，格式：
                [
                    {
                        "type": "pdf",
                        "source": "state['pdf_report']",
                        "filename": "report.pdf"
                    }
                ]
            state: 工作流状态

        Returns:
            附件列表，格式：[(filename, content, content_type), ...]
        """
        attachments = []

        for config in attachments_config:
            try:
                attachment_type = config.get("type")
                source = config.get("source")
                filename = config.get("filename", f"attachment.{attachment_type}")

                # 从state获取附件内容
                content = self._get_nested_value(state, source)

                if content:
                    # 确定content_type
                    content_type = self._get_content_type(attachment_type)
                    attachments.append((filename, content, content_type))

            except Exception as e:
                logger.error(f"准备附件失败: {e}")

        return attachments

    def _get_content_type(self, file_type: str) -> str:
        """获取文件的content_type"""
        content_types = {
            "pdf": "application/pdf",
            "json": "application/json",
            "csv": "text/csv",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        return content_types.get(file_type, "application/octet-stream")

