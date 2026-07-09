"""
测试生成"现金流质量分析"skill
验证向量搜索 + 侦察 + 代码生成 + 测试的完整链路
"""
import asyncio
import time
import sys

async def main():
    from app.core.database import init_database, get_mongo_db
    from app.services.skill_generation_service import SkillGenerationService
    from app.services.intelligent_assistant_service import (
        get_coding_llm_config,
        get_reasoning_llm_config,
    )
    from core.llm import UnifiedLLMClient

    await init_database()
    db = get_mongo_db()

    # 配置 LLM
    reasoning_config = await get_reasoning_llm_config(db)
    coding_config = await get_coding_llm_config(db)
    reasoning_client = UnifiedLLMClient.from_config(reasoning_config) if reasoning_config else None
    coding_client = UnifiedLLMClient.from_config(coding_config) if coding_config else None

    svc = SkillGenerationService(
        db=db,
        reasoning_llm_client=reasoning_client,
        coding_llm_client=coding_client,
        provider="deepseek",
    )

    # ===== 步骤 1: 提交需求 =====
    print("=" * 60)
    print("步骤 1: 提交需求")
    print("=" * 60)
    description = (
        "现金流质量分析工具：评估公司现金流的真实性和可持续性。"
        "分析经营现金流净额/净利润比率（利润含金量）、自由现金流趋势、"
        "现金流波动性、收现比等指标，识别利润操纵风险。"
    )
    result = await svc.start_session(description=description, user_id="test")
    session_id = result.get("session_id")
    print(f"session_id: {session_id}")
    print(f"AI 回复: {result.get('ai_message', '')[:200]}...")

    # ===== 步骤 2: 补充细节 =====
    print("\n" + "=" * 60)
    print("步骤 2: 补充细节")
    print("=" * 60)
    detail = (
        "需要分析的维度：\n"
        "1. 利润含金量：经营现金流净额/净利润比率（>1为优，<0.5为差）\n"
        "2. 自由现金流趋势：FCF 近 5 年的变化趋势和稳定性\n"
        "3. 现金流波动性：经营现金流的变异系数\n"
        "4. 收现比：销售商品收到的现金/营业收入\n"
        "5. 异常信号：净利润为正但经营现金流为负、大额资本化支出等\n"
        "输入参数：股票代码、分析年数（默认 5 年）"
    )
    result2 = await svc.respond_to_session(session_id, detail)
    print(f"AI 回复: {result2.get('ai_message', '')[:200]}...")

    # ===== 步骤 3: 确认规格，触发生成 =====
    print("\n" + "=" * 60)
    print("步骤 3: 确认规格，触发生成")
    print("=" * 60)
    confirm_result = await svc.confirm_spec(session_id, "确认")
    print(f"status: {confirm_result.get('status')}")
    print(f"session_id: {confirm_result.get('session_id')}")

    # ===== 步骤 4: 轮询等待生成完成 =====
    print("\n" + "=" * 60)
    print("步骤 4: 等待生成完成")
    print("=" * 60)
    max_wait = 900  # 最多等 15 分钟（10 轮迭代可能需要较长时间）
    start_time = time.time()
    final_status = None
    while time.time() - start_time < max_wait:
        session = await svc.get_session(session_id)
        status = session.get("status")
        elapsed = int(time.time() - start_time)
        print(f"  [{elapsed}s] 状态: {status}")
        if status in ("completed", "failed"):
            final_status = status
            break
        await asyncio.sleep(10)

    if final_status != "completed":
        print(f"\n❌ 生成失败: status={final_status}")
        session = await svc.get_session(session_id)
        pipeline_result = session.get("pipeline_result") or {}
        print(f"错误: {pipeline_result.get('error', 'unknown')}")
        # 打印每轮的失败摘要
        for r in pipeline_result.get("iterations", []):
            print(f"  轮次 {r.get('round_number')}: decision={r.get('decision')}, feedback={r.get('feedback', '')[:150]}")
        return

    print(f"\n✅ 生成完成 (耗时 {int(time.time() - start_time)}s)")

    # ===== 步骤 5: 查看生成结果 =====
    print("\n" + "=" * 60)
    print("步骤 5: 查看生成结果")
    print("=" * 60)
    session = await svc.get_session(session_id)
    pipeline_result = session.get("pipeline_result") or {}
    print(f"success: {pipeline_result.get('success')}")
    print(f"total_rounds: {pipeline_result.get('total_rounds')}")
    total_time = pipeline_result.get('total_time') or 0
    print(f"total_time: {total_time:.1f}s")
    # final_score 在 pipeline_result 顶层不存在，需要从 iterations 里取
    iterations = pipeline_result.get("iterations") or []
    final_score = None
    if iterations:
        last_iter = iterations[-1]
        eval_score = last_iter.get("eval_score") or {}
        final_score = eval_score.get("total")
    print(f"final_score: {final_score}")

    # 查看 spec
    spec = session.get("spec", {})
    tool_id = spec.get("tool_id")
    print(f"tool_id: {tool_id}")
    print(f"display_name: {spec.get('display_name')}")

    # 查看生成的 skill 代码（external_skills 是实际存储集合）
    skill_doc = await db["external_skills"].find_one({"tool_id": tool_id})
    if skill_doc:
        code = skill_doc.get("code", "")
        print(f"代码行数: {len(code.split(chr(10)))}")
        print(f"\n代码前 30 行:")
        for i, line in enumerate(code.split("\n")[:30], 1):
            print(f"  {i:3d} | {line}")

        # ===== 步骤 6: 测试 skill =====
        print("\n" + "=" * 60)
        print("步骤 6: 测试 skill（贵州茅台 600519）")
        print("=" * 60)
        test_result = await svc.test_skill(tool_id, {"symbol": "600519"})
        print(f"success: {test_result.get('success')}")
        if test_result.get("success"):
            output = test_result.get("output")
            if output:
                import json
                try:
                    if isinstance(output, str):
                        output = json.loads(output)
                    print(f"输出（格式化）:")
                    print(json.dumps(output, ensure_ascii=False, indent=2)[:2000])
                except Exception:
                    print(f"输出（原始）: {str(output)[:1500]}")
            print(f"\n执行时间: {test_result.get('execution_time')}s")
        else:
            print(f"错误: {test_result.get('error')}")
            print(f"stderr: {test_result.get('stderr', '')[:500]}")
    else:
        print(f"❌ 未找到 skill 文档 (tool_id={tool_id})")

if __name__ == "__main__":
    asyncio.run(main())
