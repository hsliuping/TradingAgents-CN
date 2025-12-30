#!/usr/bin/env python
"""
为持仓分析路由添加详细日志
"""

import sys
from pathlib import Path

# 读取文件
portfolio_file = Path("app/routers/portfolio.py")
with open(portfolio_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 定义要替换的内容
old_code = '''    try:
        from app.services.unified_analysis_service import get_unified_analysis_service

        unified_service = get_unified_analysis_service()

        # 准备任务参数
        task_params = {
            "research_depth": data.research_depth,
            "include_add_position": data.include_add_position,
            "target_profit_pct": data.target_profit_pct,
            "total_capital": data.total_capital,
            "max_position_pct": data.max_position_pct,
            "max_loss_pct": data.max_loss_pct,
            "risk_tolerance": data.risk_tolerance,
            "investment_horizon": data.investment_horizon,
            "analysis_focus": data.analysis_focus,
            "position_type": data.position_type,
        }

        # 创建统一分析任务
        result = await unified_service.create_position_analysis_task(
            user_id=current_user["id"],
            code=data.code,
            market=data.market,
            task_params=task_params
        )

        # 后台执行分析
        asyncio.create_task(
            unified_service.execute_position_analysis(
                task_id=result["task_id"],
                user_id=current_user["id"],
                code=data.code,
                market=data.market,
                task_params=task_params
            )
        )

        return ok(data=result, message="持仓分析任务已提交，预计需要2-5分钟完成")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建持仓分析任务失败: {e}", exc_info=True)'''

new_code = '''    try:
        logger.info(f"📥 [持仓分析路由] 收到请求: code={data.code}, market={data.market}, user_id={current_user['id']}")
        
        from app.services.unified_analysis_service import get_unified_analysis_service

        unified_service = get_unified_analysis_service()
        logger.info(f"✅ [持仓分析路由] 获取到 UnifiedAnalysisService 实例")

        # 准备任务参数
        task_params = {
            "research_depth": data.research_depth,
            "include_add_position": data.include_add_position,
            "target_profit_pct": data.target_profit_pct,
            "total_capital": data.total_capital,
            "max_position_pct": data.max_position_pct,
            "max_loss_pct": data.max_loss_pct,
            "risk_tolerance": data.risk_tolerance,
            "investment_horizon": data.investment_horizon,
            "analysis_focus": data.analysis_focus,
            "position_type": data.position_type,
        }
        logger.info(f"📋 [持仓分析路由] 任务参数准备完成: {list(task_params.keys())}")

        # 创建统一分析任务
        logger.info(f"🔄 [持仓分析路由] 开始创建任务...")
        result = await unified_service.create_position_analysis_task(
            user_id=current_user["id"],
            code=data.code,
            market=data.market,
            task_params=task_params
        )
        logger.info(f"✅ [持仓分析路由] 任务创建成功: task_id={result['task_id']}")

        # 后台执行分析
        logger.info(f"🚀 [持仓分析路由] 启动后台任务执行...")
        asyncio.create_task(
            unified_service.execute_position_analysis(
                task_id=result["task_id"],
                user_id=current_user["id"],
                code=data.code,
                market=data.market,
                task_params=task_params
            )
        )
        logger.info(f"✅ [持仓分析路由] 后台任务已启动")

        return ok(data=result, message="持仓分析任务已提交，预计需要2-5分钟完成")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [持仓分析路由] 创建任务失败: {e}", exc_info=True)'''

# 替换内容
if old_code in content:
    content = content.replace(old_code, new_code)
    print("✅ 找到并替换了目标代码")
else:
    print("❌ 未找到目标代码，尝试部分匹配...")
    # 尝试查找关键行
    if "from app.services.unified_analysis_service import get_unified_analysis_service" in content:
        print("✅ 找到了 unified_analysis_service 导入")
    if "unified_service.create_position_analysis_task" in content:
        print("✅ 找到了 create_position_analysis_task 调用")
    sys.exit(1)

# 写回文件
with open(portfolio_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ 文件修改完成！")

