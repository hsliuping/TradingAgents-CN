"""测试创建护城河强度量化评分 skill"""

import asyncio
import logging
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)-8s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def _wait_for_completion(db, session_id: str, timeout: int = 600):
    """轮询数据库，等待 skill 生成完成（status 变为 completed/failed）"""
    collection = db["skill_creation_sessions"]
    start = asyncio.get_event_loop().time()
    last_stage = ""
    last_progress = 0.0
    while True:
        elapsed = asyncio.get_event_loop().time() - start
        if elapsed > timeout:
            logger.warning("⏰ 等待超时 (%ss)，退出轮询", timeout)
            return None
        doc = await collection.find_one({"session_id": session_id})
        if not doc:
            logger.warning("会话文档不存在: %s", session_id)
            return None
        status = doc.get("status", "")
        stage = doc.get("pipeline_stage", "")
        message = doc.get("pipeline_message", "")
        progress = doc.get("pipeline_progress", 0.0)
        iteration = doc.get("pipeline_iteration", 0)
        if stage != last_stage or abs(progress - last_progress) > 0.01:
            logger.info(
                "⏳ status=%s stage=%s progress=%.0f%% iter=%s msg=%s",
                status, stage, progress * 100, iteration, message[:80],
            )
            last_stage = stage
            last_progress = progress
        if status in ("completed", "failed"):
            logger.info("✅ 生成结束 status=%s 耗时=%.1fs", status, elapsed)
            return doc
        await asyncio.sleep(3)


async def main():
    # 初始化数据库
    from app.core.database import init_database, get_mongo_db
    await init_database()
    db = get_mongo_db()

    # 初始化 LLM 配置
    from app.services.intelligent_assistant_service import (
        get_coding_llm_config,
        get_reasoning_llm_config,
    )
    from core.llm import UnifiedLLMClient

    reasoning_config = await get_reasoning_llm_config(db)
    reasoning_client = UnifiedLLMClient.from_config(reasoning_config) if reasoning_config else None

    coding_config = await get_coding_llm_config(db)
    coding_client = UnifiedLLMClient.from_config(coding_config) if coding_config else None

    logger.info("reasoning_client=%s, coding_client=%s", bool(reasoning_client), bool(coding_client))

    # 创建 SkillGenerationService
    from app.services.skill_generation_service import SkillGenerationService
    service = SkillGenerationService(
        db=db,
        reasoning_llm_client=reasoning_client,
        coding_llm_client=coding_client,
    )

    # Step 1: 启动会话
    description = (
        "创建一个护城河强度量化评分工具（Integrated Moat Scorer）。\n"
        "功能：从盈利能力持续性（ROIC趋势）、利润率稳定性、成长质量、现金流趋势、分红历史等维度，"
        "对 A 股上市公司进行定量护城河强度评分（0-100分），并输出护城河等级（宽阔/狭窄/无）和关键驱动因子。\n"
        "输入：symbol（股票代码）\n"
        "输出：JSON，包含 moat_score(0-100)、moat_grade(wide/narrow/none)、key_drivers(数组)、dimension_scores(对象)\n"
        "数据来源：使用项目中已有的 get_historical_financial_annual_series、get_margin_stability_metrics、"
        "get_growth_quality_metrics、get_financial_cashflow_quality_trend、dividend_history_reliability 等工具的数据。\n"
        "注意：评分维度参考 Morningstar 护城河方法论，但简化为可计算的定量指标。"
    )

    logger.info("=" * 60)
    logger.info("Step 1: 启动 skill 创建会话")
    logger.info("需求描述: %s", description[:100])
    logger.info("=" * 60)

    result = await service.start_session(
        description=description,
        user_id="test_user",
    )

    session_id = result["session_id"]
    logger.info("会话 ID: %s", session_id)
    logger.info("AI 消息: %s", result["ai_message"])
    logger.info("清晰度: %s", result["clarity_level"])
    logger.info("当前轮次: %s/%s", result["current_round"], result["expected_rounds"])

    # Step 2: 如果需要多轮对话，回应 AI 的问题
    current_round = result["current_round"]
    expected_rounds = result["expected_rounds"]

    if current_round < expected_rounds and result.get("clarity_level") != "high":
        logger.info("=" * 60)
        logger.info("Step 2: 回应 AI 澄清问题")
        logger.info("=" * 60)

        respond_result = await service.respond_to_session(
            session_id=session_id,
            user_message=(
                "评分维度如下：\n"
                "1. ROIC 持续性（25分）：近5年ROIC是否持续>15%\n"
                "2. 利润率稳定性（20分）：毛利率和净利率的标准差\n"
                "3. 营收成长质量（20分）：营收复合增长率与现金流增长的匹配度\n"
                "4. 现金流趋势（15分）：经营现金流/净利润比率趋势\n"
                "5. 分红持续性（10分）：近5年分红次数和派息率\n"
                "6. 资产轻重（10分）：总资产周转率趋势\n"
                "等级划分：>70=宽阔(wide)，40-70=狭窄(narrow)，<40=无(none)\n"
                "不需要输出买卖建议，仅输出量化评分和驱动因子。"
            ),
        )
        logger.info("AI 回复: %s", respond_result["ai_message"])
        logger.info("当前轮次: %s/%s", respond_result["current_round"], respond_result["expected_rounds"])
        current_round = respond_result["current_round"]

    # Step 3: 确认规格并触发代码生成（异步）
    logger.info("=" * 60)
    logger.info("Step 3: 确认规格并触发代码生成")
    logger.info("=" * 60)

    confirm_result = await service.confirm_spec(
        session_id=session_id,
        user_message="确认",
    )

    logger.info("确认结果状态: %s", confirm_result.get("status"))
    if confirm_result.get("spec"):
        spec = confirm_result["spec"]
        logger.info("Skill 名称: %s", spec.get("name"))
        logger.info("Tool ID: %s", spec.get("tool_id"))
        logger.info("描述: %s", spec.get("description"))
        logger.info("参数: %s", spec.get("parameters"))
    else:
        logger.error("规格生成失败: %s", confirm_result.get("message"))
        return

    # confirm_spec 是异步的，返回 status=generating，需要轮询等待完成
    logger.info("=" * 60)
    logger.info("Step 4: 等待异步代码生成完成（最多 10 分钟）")
    logger.info("=" * 60)

    final_doc = await _wait_for_completion(db, session_id, timeout=600)
    if not final_doc:
        logger.error("生成超时或会话不存在")
        return

    status = final_doc.get("status")
    pipeline_result = final_doc.get("pipeline_result") or {}

    logger.info("=" * 60)
    logger.info("代码生成结果:")
    logger.info("  会话状态: %s", status)
    logger.info("  success: %s", pipeline_result.get("success"))
    logger.info("  total_rounds: %s", pipeline_result.get("total_rounds"))
    logger.info("  total_time: %s", pipeline_result.get("total_time"))
    logger.info("  error: %s", pipeline_result.get("error", "无"))
    if pipeline_result.get("final_metadata"):
        meta = pipeline_result["final_metadata"]
        logger.info("  generation_engine: %s", meta.get("generation_engine"))
        logger.info("  verified_facts: %s", len(meta.get("verified_facts") or []))
    logger.info("=" * 60)

    if status != "completed" or not pipeline_result.get("success"):
        logger.error("❌ Skill 生成失败")
        # 打印迭代历史帮助诊断
        iterations = pipeline_result.get("iterations") or []
        for i, it in enumerate(iterations, 1):
            logger.info("  迭代 %d: decision=%s", i, it.get("decision"))
            if it.get("feedback"):
                logger.info("    feedback: %s", str(it.get("feedback"))[:200])
        return

    # Step 5: 测试生成的 skill
    logger.info("=" * 60)
    logger.info("Step 5: 测试生成的 skill（用 600519 茅台测试）")
    logger.info("=" * 60)

    await asyncio.sleep(2)

    # 从数据库加载 skill
    tool_id = confirm_result["spec"].get("tool_id")
    skill_doc = await db["external_skills"].find_one({"tool_id": tool_id})
    if skill_doc:
        logger.info("Skill 已保存到数据库: %s", skill_doc.get("tool_id"))
        logger.info("Status: %s", skill_doc.get("status"))
        logger.info("代码长度: %d 字符", len(skill_doc.get("code", "")))

        if skill_doc.get("status") == "active":
            from core.tools.external_skill_loader import register_single_external_skill
            from app.core.database import get_mongo_db_sync
            from core.tools.registry import get_tool_registry

            sync_db = get_mongo_db_sync()
            registry = get_tool_registry()
            register_single_external_skill(sync_db, registry, skill_doc)

            func = registry.get_function(tool_id)
            if func:
                logger.info("Skill 已注册到 ToolRegistry，开始调用...")
                try:
                    result_str = func(symbol="600519")
                    logger.info("调用结果: %s", str(result_str)[:800])
                except Exception as e:
                    logger.error("调用失败: %s", e, exc_info=True)
            else:
                logger.error("Skill 未注册到 ToolRegistry")
        else:
            logger.warning("Skill 状态不是 active: %s，跳过调用测试", skill_doc.get("status"))
    else:
        logger.error("Skill 未保存到数据库")

    logger.info("=" * 60)
    logger.info("测试完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
