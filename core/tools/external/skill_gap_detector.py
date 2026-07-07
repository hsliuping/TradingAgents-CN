"""
Skill 缺口检测器

在 Agent 执行工具调用失败时，异步上报缺口到 SkillGapService，
并通过 NotificationsService 推送实时通知给用户。

设计原则：
- fire-and-forget：不阻塞当前分析任务
- 30 分钟内同一 tool_name 不重复上报
- 用户 dismiss 后 30 天内不再上报同名工具
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SkillGapDetector:
    """Skill 缺口检测器（单例）"""

    _instance: Optional["SkillGapDetector"] = None

    # 去重缓存: tool_name -> 最近上报时间
    _recent_reports: Dict[str, datetime] = {}
    # 已忽略缓存: tool_name -> 忽略时间
    _dismissed_tools: Dict[str, datetime] = {}

    DEDUP_MINUTES = 30       # 同一工具 30 分钟去重
    DISMISS_DAYS = 30        # dismiss 后 30 天不再上报

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def _should_report(cls, tool_name: str) -> bool:
        """去重 + 忽略检查（同步，快速）"""
        now = datetime.utcnow()

        # 检查是否已被忽略
        if tool_name in cls._dismissed_tools:
            dismissed_at = cls._dismissed_tools[tool_name]
            if now - dismissed_at < timedelta(days=cls.DISMISS_DAYS):
                logger.debug(f"[SkillGapDetector] {tool_name} 已被忽略，跳过上报")
                return False
            else:
                # 忽略已过期，清除
                del cls._dismissed_tools[tool_name]

        # 检查去重
        if tool_name in cls._recent_reports:
            last_reported = cls._recent_reports[tool_name]
            if now - last_reported < timedelta(minutes=cls.DEDUP_MINUTES):
                logger.debug(f"[SkillGapDetector] {tool_name} {cls.DEDUP_MINUTES} 分钟内已上报，跳过")
                return False

        return True

    @classmethod
    def mark_dismissed(cls, tool_name: str) -> None:
        """标记工具已被用户忽略（由 SkillGapService.dismiss_gap 调用）"""
        cls._dismissed_tools[tool_name] = datetime.utcnow()
        logger.info(f"[SkillGapDetector] {tool_name} 已标记为忽略")

    @classmethod
    def report_gap(
        cls,
        gap_type: str,
        tool_name: str,
        agent_id: str,
        error: str = "",
        context: Optional[dict] = None,
        user_id: str = "admin",
    ) -> None:
        """
        上报工具缺口（fire-and-forget）。

        在同步上下文中调用，内部使用 asyncio.create_task / ensure_future
        将实际处理提交到后台，不阻塞调用方。
        """
        if not cls._should_report(tool_name):
            return

        # 记录本次上报时间（立即写入，防止并发重复）
        cls._recent_reports[tool_name] = datetime.utcnow()

        # 提交后台任务
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                cls._create_report(gap_type, tool_name, agent_id, error, context or {}, user_id)
            )
        except RuntimeError:
            # 没有运行中的事件循环（测试环境等），直接忽略
            logger.debug("[SkillGapDetector] 没有运行中的事件循环，跳过后台任务")

    @classmethod
    async def _create_report(
        cls,
        gap_type: str,
        tool_name: str,
        agent_id: str,
        error: str,
        context: dict,
        user_id: str,
    ) -> None:
        """异步：创建缺口报告并触发通知（在后台运行）"""
        try:
            from app.services.skill_gap_service import get_skill_gap_service
            svc = get_skill_gap_service()
            await svc.create_report(
                gap_type=gap_type,
                tool_name=tool_name,
                agent_id=agent_id,
                error=error,
                context=context,
                user_id=user_id,
            )
            logger.info(f"[SkillGapDetector] 缺口报告已创建: tool={tool_name}, agent={agent_id}")
        except Exception as e:
            logger.warning(f"[SkillGapDetector] 创建缺口报告失败（已忽略）: {e}")

