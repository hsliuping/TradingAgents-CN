"""
邮件通知服务
提供分析结果邮件推送功能
"""

import smtplib
import uuid
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from app.core.config import settings
from app.core.database import get_mongo_db
from app.models.email import (
    EmailRecord, EmailRecordCreate, EmailStatus, EmailType,
    EmailNotificationSettings, SMTPConfig
)
from app.utils.timezone import now_tz

logger = logging.getLogger(__name__)

# SMTP配置集合名
SMTP_CONFIG_COLLECTION = "smtp_config"


class EmailService:
    """邮件发送服务"""

    def __init__(self):
        self.collection = "email_records"
        self.user_collection = "users"
        self._smtp_config_cache: Optional[Dict[str, Any]] = None
        # 初始化模板引擎
        try:
            self.template_env = Environment(
                loader=FileSystemLoader("prompts/email_templates"),
                autoescape=True
            )
        except Exception as e:
            logger.warning(f"邮件模板目录不存在，将使用简单文本邮件: {e}")
            self.template_env = None

    async def get_smtp_config(self) -> Optional[Dict[str, Any]]:
        """
        获取 SMTP 配置
        优先从数据库读取，如果没有则使用 .env 配置
        """
        db = get_mongo_db()

        # 从数据库获取配置
        db_config = await db[SMTP_CONFIG_COLLECTION].find_one({"_id": "default"})

        if db_config and db_config.get("enabled"):
            return {
                "enabled": True,
                "host": db_config.get("host"),
                "port": db_config.get("port", 587),
                "username": db_config.get("username"),
                "password": db_config.get("password"),
                "from_email": db_config.get("from_email"),
                "from_name": db_config.get("from_name", "TradingAgents-CN"),
                "use_tls": db_config.get("use_tls", True),
                "use_ssl": db_config.get("use_ssl", False),
                "source": "database"
            }

        # 回退到 .env 配置
        if settings.SMTP_ENABLED and settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            return {
                "enabled": True,
                "host": settings.SMTP_HOST,
                "port": settings.SMTP_PORT,
                "username": settings.SMTP_USERNAME,
                "password": settings.SMTP_PASSWORD,
                "from_email": settings.SMTP_FROM_EMAIL,
                "from_name": settings.SMTP_FROM_NAME,
                "use_tls": settings.SMTP_USE_TLS,
                "use_ssl": settings.SMTP_USE_SSL,
                "source": "env"
            }

        return None

    async def save_smtp_config(self, config: Dict[str, Any]) -> bool:
        """保存 SMTP 配置到数据库"""
        db = get_mongo_db()

        doc = {
            "_id": "default",
            "enabled": config.get("enabled", True),
            "host": config.get("host"),
            "port": config.get("port", 587),
            "username": config.get("username"),
            "password": config.get("password"),
            "from_email": config.get("from_email"),
            "from_name": config.get("from_name", "TradingAgents-CN"),
            "use_tls": config.get("use_tls", True),
            "use_ssl": config.get("use_ssl", False),
            "updated_at": now_tz().isoformat()
        }

        await db[SMTP_CONFIG_COLLECTION].replace_one(
            {"_id": "default"},
            doc,
            upsert=True
        )

        # 清除缓存
        self._smtp_config_cache = None
        return True

    async def test_smtp_connection(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """测试 SMTP 连接"""
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, self._test_smtp_sync, config
        )

    def _test_smtp_sync(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """同步测试 SMTP 连接"""
        try:
            if config.get("use_ssl"):
                server = smtplib.SMTP_SSL(config["host"], config["port"], timeout=10)
            else:
                server = smtplib.SMTP(config["host"], config["port"], timeout=10)
                if config.get("use_tls"):
                    server.starttls()

            server.login(config["username"], config["password"])
            server.quit()

            return {"success": True, "message": "SMTP 连接测试成功"}
        except smtplib.SMTPAuthenticationError:
            return {"success": False, "message": "SMTP 认证失败，请检查用户名和密码"}
        except smtplib.SMTPConnectError:
            return {"success": False, "message": "无法连接 SMTP 服务器，请检查地址和端口"}
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)}"}

    async def send_analysis_email(
        self,
        user_id: str,
        email_type: EmailType,
        template_name: str,
        template_data: Dict[str, Any],
        reference_id: Optional[str] = None,
        reference_type: Optional[str] = None,
        attachments: Optional[List[Tuple[str, bytes, str]]] = None
    ) -> Optional[str]:
        """
        发送分析结果邮件

        Args:
            user_id: 用户ID
            email_type: 邮件类型
            template_name: 模板名称
            template_data: 模板数据
            reference_id: 关联ID
            reference_type: 关联类型
            attachments: 附件列表，每个元素为 (文件名, 文件内容bytes, MIME类型)
        """

        # 1. 获取 SMTP 配置
        smtp_config = await self.get_smtp_config()
        if not smtp_config:
            logger.debug("SMTP未配置，跳过邮件发送")
            return None

        # 2. 获取用户邮件设置
        user = await self._get_user(user_id)
        if not user:
            logger.warning(f"用户 {user_id} 不存在")
            return None

        email_settings = self._get_email_settings(user)

        if not email_settings.enabled:
            logger.debug(f"用户 {user_id} 未开启邮件通知")
            return None

        # 3. 检查该类型通知是否开启
        if not self._is_type_enabled(email_settings, email_type):
            logger.debug(f"用户 {user_id} 未开启 {email_type.value} 类型通知")
            return None

        # 4. 检查免打扰时段
        if self._is_quiet_hours(email_settings):
            logger.debug(f"当前处于免打扰时段，跳过邮件发送")
            return None

        # 5. 频率限制检查
        if not await self._check_rate_limit(user_id, email_type, reference_id):
            logger.debug(f"触发频率限制，跳过发送")
            return None

        # 6. 确定收件邮箱
        to_email = email_settings.email_address or user.get("email")
        if not to_email:
            logger.warning(f"用户 {user_id} 没有配置邮箱")
            return None

        # 7. 渲染邮件内容
        subject, html_content, text_content = self._render_template(
            template_name, template_data, email_settings.language
        )

        # 8. 创建邮件记录
        record_id = await self._create_record(
            user_id=user_id,
            to_email=to_email,
            subject=subject,
            template_name=template_name,
            email_type=email_type,
            reference_id=reference_id,
            reference_type=reference_type
        )

        # 9. 发送邮件（带附件）
        success = await self._send_smtp(
            to_email, subject, html_content, text_content, smtp_config, attachments
        )

        # 10. 更新发送状态
        if success:
            await self._update_status(record_id, EmailStatus.SENT)
            logger.info(f"✅ 邮件发送成功: {to_email}, 类型: {email_type.value}")
        else:
            await self._update_status(record_id, EmailStatus.FAILED, "SMTP发送失败")
            logger.error(f"❌ 邮件发送失败: {to_email}")

        return record_id
    
    async def send_test_email(self, user_id: str) -> bool:
        """发送测试邮件"""
        result = await self.send_analysis_email(
            user_id=user_id,
            email_type=EmailType.TEST_EMAIL,
            template_name="test_email",
            template_data={
                "test_time": now_tz().strftime("%Y-%m-%d %H:%M:%S"),
                "message": "这是一封测试邮件，用于验证邮件通知功能是否正常工作。"
            }
        )
        return result is not None
    
    async def get_email_history(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """获取邮件发送历史"""
        db = get_mongo_db()
        skip = (page - 1) * page_size
        
        query = {"user_id": user_id}
        
        total = await db[self.collection].count_documents(query)
        cursor = db[self.collection].find(query).sort("created_at", -1).skip(skip).limit(page_size)
        records = await cursor.to_list(length=page_size)
        
        # 转换 _id 为字符串
        for record in records:
            record["id"] = str(record.pop("_id"))
        
        return {
            "items": records,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def _get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户信息"""
        db = get_mongo_db()
        from bson import ObjectId
        try:
            user = await db[self.user_collection].find_one({"_id": ObjectId(user_id)})
            return user
        except Exception:
            return None

    def _get_email_settings(self, user: Dict[str, Any]) -> EmailNotificationSettings:
        """获取用户邮件设置"""
        preferences = user.get("preferences", {})
        email_settings = preferences.get("email_notifications", {})
        return EmailNotificationSettings(**email_settings) if email_settings else EmailNotificationSettings()

    def _is_type_enabled(self, settings: EmailNotificationSettings, email_type: EmailType) -> bool:
        """检查邮件类型是否启用"""
        type_map = {
            EmailType.SINGLE_ANALYSIS: settings.single_analysis,
            EmailType.BATCH_ANALYSIS: settings.batch_analysis,
            EmailType.SCHEDULED_ANALYSIS: settings.scheduled_analysis,
            EmailType.IMPORTANT_SIGNAL: settings.important_signals,
            EmailType.SYSTEM_NOTIFICATION: settings.system_notifications,
            EmailType.TEST_EMAIL: True,  # 测试邮件始终允许
        }
        return type_map.get(email_type, False)

    def _is_quiet_hours(self, email_settings: EmailNotificationSettings) -> bool:
        """检查是否在免打扰时段"""
        if not email_settings.quiet_hours_enabled:
            return False

        now = now_tz()
        current_time = now.strftime("%H:%M")
        start = email_settings.quiet_hours_start
        end = email_settings.quiet_hours_end

        # 处理跨天情况（如22:00 - 08:00）
        if start > end:
            return current_time >= start or current_time < end
        else:
            return start <= current_time < end

    async def _check_rate_limit(
        self,
        user_id: str,
        email_type: EmailType,
        reference_id: Optional[str]
    ) -> bool:
        """检查频率限制"""
        db = get_mongo_db()

        # 定义不同类型的限制
        limits = {
            EmailType.SINGLE_ANALYSIS: {"hours": 1, "same_ref": True},
            EmailType.BATCH_ANALYSIS: {"hours": 0, "same_ref": False},
            EmailType.SCHEDULED_ANALYSIS: {"hours": 0, "same_ref": False},
            EmailType.IMPORTANT_SIGNAL: {"hours": 24, "same_ref": True},
            EmailType.SYSTEM_NOTIFICATION: {"hours": 72, "same_ref": True},
            EmailType.TEST_EMAIL: {"hours": 0, "same_ref": False},
        }

        limit_config = limits.get(email_type, {"hours": 1, "same_ref": False})

        if limit_config["hours"] == 0:
            return True

        query = {
            "user_id": user_id,
            "email_type": email_type.value,
            "status": {"$in": [EmailStatus.SENT.value, EmailStatus.PENDING.value, EmailStatus.SENDING.value]},
            "created_at": {
                "$gte": now_tz() - timedelta(hours=limit_config["hours"])
            }
        }

        if limit_config["same_ref"] and reference_id:
            query["reference_id"] = reference_id

        count = await db[self.collection].count_documents(query)
        return count == 0

    def _render_template(
        self,
        template_name: str,
        data: Dict[str, Any],
        language: str = "zh"
    ) -> tuple:
        """渲染邮件模板"""
        subject = data.get("subject", "TradingAgents-CN 通知")

        # 尝试加载HTML模板
        html_content = None
        if self.template_env:
            try:
                html_template = self.template_env.get_template(f"{language}/{template_name}.html")
                html_content = html_template.render(**data)
            except TemplateNotFound:
                logger.debug(f"未找到模板 {language}/{template_name}.html，使用简单格式")

        # 如果没有模板，生成简单HTML
        if not html_content:
            html_content = self._generate_simple_html(template_name, data)

        # 生成纯文本版本
        text_content = self._html_to_text(html_content)

        return subject, html_content, text_content

    def _generate_simple_html(self, template_name: str, data: Dict[str, Any]) -> str:
        """生成简单的HTML邮件内容"""
        title = data.get("title", "TradingAgents-CN 通知")
        content = data.get("content", data.get("message", ""))

        return f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: 'Microsoft YaHei', sans-serif; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333;">{title}</h2>
                <div style="color: #555; line-height: 1.6;">{content}</div>
                <hr style="margin: 20px 0; border: none; border-top: 1px solid #eee;">
                <p style="font-size: 12px; color: #999;">
                    此邮件由 TradingAgents-CN 自动发送<br>
                    ⚠️ 免责声明：以上内容仅供参考，不构成投资建议。
                </p>
            </div>
        </body>
        </html>
        """

    def _html_to_text(self, html: str) -> str:
        """将HTML转换为纯文本"""
        import re
        # 简单处理：移除HTML标签
        text = re.sub(r'<[^>]+>', '', html)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    async def _create_record(
        self,
        user_id: str,
        to_email: str,
        subject: str,
        template_name: str,
        email_type: EmailType,
        reference_id: Optional[str] = None,
        reference_type: Optional[str] = None
    ) -> str:
        """创建邮件发送记录"""
        db = get_mongo_db()

        record_id = str(uuid.uuid4())
        record = {
            "_id": record_id,
            "user_id": user_id,
            "to_email": to_email,
            "subject": subject,
            "template_name": template_name,
            "email_type": email_type.value,
            "reference_id": reference_id,
            "reference_type": reference_type,
            "status": EmailStatus.PENDING.value,
            "retry_count": 0,
            "max_retries": 3,
            "created_at": now_tz().isoformat(),
            "sent_at": None,
            "error_message": None
        }

        await db[self.collection].insert_one(record)
        return record_id

    async def _update_status(
        self,
        record_id: str,
        status: EmailStatus,
        error_message: Optional[str] = None
    ):
        """更新邮件发送状态"""
        db = get_mongo_db()

        update_data = {"status": status.value}
        if status == EmailStatus.SENT:
            update_data["sent_at"] = now_tz().isoformat()
        if error_message:
            update_data["error_message"] = error_message

        await db[self.collection].update_one(
            {"_id": record_id},
            {"$set": update_data}
        )

    async def _send_smtp(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
        smtp_config: Dict[str, Any],
        attachments: Optional[List[Tuple[str, bytes, str]]] = None
    ) -> bool:
        """通过SMTP发送邮件（在线程池中执行同步操作）"""
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None,
            self._send_smtp_sync,
            to_email, subject, html_content, text_content, smtp_config, attachments
        )

    def _send_smtp_sync(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
        smtp_config: Dict[str, Any],
        attachments: Optional[List[Tuple[str, bytes, str]]] = None
    ) -> bool:
        """同步SMTP发送（支持附件）"""
        try:
            # 如果有附件，使用 mixed 类型；否则使用 alternative
            if attachments:
                msg = MIMEMultipart("mixed")
                # 创建正文部分
                body_part = MIMEMultipart("alternative")
                body_part.attach(MIMEText(text_content, "plain", "utf-8"))
                body_part.attach(MIMEText(html_content, "html", "utf-8"))
                msg.attach(body_part)

                # 添加附件
                for filename, content, mime_type in attachments:
                    try:
                        main_type, sub_type = mime_type.split("/", 1)
                        attachment = MIMEBase(main_type, sub_type)
                        attachment.set_payload(content)
                        encoders.encode_base64(attachment)
                        attachment.add_header(
                            "Content-Disposition",
                            "attachment",
                            filename=filename
                        )
                        msg.attach(attachment)
                        logger.info(f"📎 添加附件: {filename} ({len(content)} bytes)")
                    except Exception as att_err:
                        logger.warning(f"⚠️ 添加附件 {filename} 失败: {att_err}")
            else:
                msg = MIMEMultipart("alternative")
                msg.attach(MIMEText(text_content, "plain", "utf-8"))
                msg.attach(MIMEText(html_content, "html", "utf-8"))

            msg["Subject"] = subject
            msg["From"] = f"{smtp_config['from_name']} <{smtp_config['from_email']}>"
            msg["To"] = to_email

            # 发送邮件
            if smtp_config.get("use_ssl"):
                server = smtplib.SMTP_SSL(smtp_config["host"], smtp_config["port"])
            else:
                server = smtplib.SMTP(smtp_config["host"], smtp_config["port"])
                if smtp_config.get("use_tls"):
                    server.starttls()

            server.login(smtp_config["username"], smtp_config["password"])
            server.send_message(msg)
            server.quit()

            return True

        except Exception as e:
            logger.error(f"SMTP发送失败: {e}")
            return False


# 全局实例
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """获取邮件服务实例"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service

