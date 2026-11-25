# -*- coding: utf-8 -*-
"""S8 system prompt 治理（A11 §7 并行工作项）单测。

覆盖：
- 分层结构完整性（核心身份/领域边界/数据纪律/合规/工具指引）
- 动态注入机制不受重组影响（日期/IM/记忆指引/主题/usage_helper 分流）
- 字数缩减验收（基线 8317 字符，验收线 ≤5822 即 ≥30% 缩减，防膨胀回弹）
- 关键行为锚点存在（与 A 类防线、§5.1 回归测试集对应）
"""
import re

from app.services.intelligent_assistant_service import _get_system_prompt

# 阶段 4 重写前的静态规则文本基线（2026-09-13 实测）
_BASELINE_CHARS = 8317
# 验收线：字数缩减 ≥30%（2026-09-15 上调至 6050：新增表格 Excel 导出工具说明、
# 数据纪律第 14/15 条——导出透传与"复用对话已有结果"防重复拉数规则）
_MAX_CHARS = 6050


class TestSystemPromptS8:
    def test_layered_blocks_present(self):
        """分层重组后的核心区块齐全"""
        prompt = _get_system_prompt()
        for block in (
            "【角色定位】",
            "【系统能力说明】",
            "【诚实与能力边界】",
            "【领域边界】",
            "【数据纪律（核心，逐条强制）】",
            "【合规原则】",
            "【先确认再执行】",
            "【数据概念区分（必须严格区分）】",
            "【工具与数据获取】",
            "【长期记忆管理】",
        ):
            assert block in prompt, f"缺少分层区块：{block}"

    def test_dynamic_date_injection(self):
        """当前日期与最近交易日动态注入保持"""
        prompt = _get_system_prompt()
        assert "【当前日期】" in prompt
        assert "【最近交易日】" in prompt
        # 两处均为 YYYY-MM-DD
        dates = re.findall(r"【(?:当前日期|最近交易日)】(\d{4}-\d{2}-\d{2})", prompt)
        assert len(dates) == 2, f"日期注入异常：{dates}"

    def test_im_block_injection(self):
        """IM 渠道格式规范按需注入"""
        assert "【IM 消息格式规范】" not in _get_system_prompt()
        assert "【IM 消息格式规范】" in _get_system_prompt(is_im=True)

    def test_memory_directive_injection(self):
        """记忆块注入时附带多交易计划处理规则"""
        prompt = _get_system_prompt(memory_block="【历史记忆】\n- 用户偏好测试")
        assert "【历史记忆】" in prompt
        assert "多交易计划处理规则" in prompt
        # 无记忆时不注入该指引
        assert "多交易计划处理规则" not in _get_system_prompt()

    def test_topic_block_injection(self):
        """外部会话主题注入保持"""
        prompt = _get_system_prompt(current_topic_title="新能源车产业链")
        assert "当前研究主题：新能源车产业链" in prompt

    def test_usage_helper_branch_unchanged(self):
        """使用问答机器人分流保持（不走通用分析助理 prompt）"""
        prompt = _get_system_prompt(assistant_role="usage_helper")
        assert "使用问答助手" in prompt
        assert "【数据纪律（核心，逐条强制）】" not in prompt

    def test_size_reduction_acceptance(self):
        """验收：静态规则文本较基线缩减 ≥30%（防膨胀回弹）"""
        prompt = _get_system_prompt()
        assert len(prompt) <= _MAX_CHARS, (
            f"prompt 长度 {len(prompt)} 超过验收线 {_MAX_CHARS}"
            f"（基线 {_BASELINE_CHARS} 的 70%），缩减率不足 30%"
        )

    def test_data_discipline_anchors(self):
        """数据纪律 13 条关键锚点（A 类防线对齐）"""
        prompt = _get_system_prompt()
        anchors = (
            "数字只能来自工具返回",
            "严禁\"约\"字包装编造",
            "严禁编造来源",
            "严禁伪造工具调用痕迹",
            "web_search 摘要里没有的数字不能编",
            "行业实时数据禁用记忆",
            "估值分位数须数据支撑",
            "单位与换算逐字核对",
            "空数据如实告知",
            "数据日期如实声明",
            "工具结果忠实原样呈现",
            "时间逻辑基于当前日期",
            "估值 Excel 交付物",
            "15764.6万=1.58亿",  # 换算行为锚点
            "0.37% 而非 37%",  # ratio 字段锚点
        )
        for a in anchors:
            assert a in prompt, f"缺少数据纪律锚点：{a}"

    def test_compliance_and_tool_anchors(self):
        """合规与工具指引关键锚点（§5.1 案例 4/5/6 相关）"""
        prompt = _get_system_prompt()
        anchors = (
            "我无法提供'是否值得入手'这类投资建议",  # 案例 4 合规话术
            "严禁给出具体止损价/止盈价/提醒价位",
            "编号承接",  # 案例 5 裸编号回复
            "必须传入上述交易日",
            "严禁用 search_recent_information/web_search 网页搜索代替",  # 走势禁搜索
            "严禁为\"给点参考\"推荐不符合条件的股票",  # 筛选空结果
            "watchlist_groups 只是分组/组织方式",  # 三概念区分
            "user_favorites",
        )
        for a in anchors:
            assert a in prompt, f"缺少合规/工具锚点：{a}"

    def test_personalization_injection(self):
        """助理个性化设置注入保持"""
        prompt = _get_system_prompt(
            assistant_settings={"name": "小助手", "tone": "friendly", "custom_instructions": "多用表格"}
        )
        assert "小助手" in prompt
        assert "轻松友好" in prompt  # friendly 语气映射
        assert "多用表格" in prompt
