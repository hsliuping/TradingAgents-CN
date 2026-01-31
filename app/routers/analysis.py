"""
股票分析API路由
增强版本，支持优先级、进度跟踪、任务管理等功能
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import time
import uuid
import asyncio

from app.routers.auth_db import get_current_user
from app.services.queue_service import get_queue_service, QueueService
from app.services.analysis_service import get_analysis_service
from app.services.simple_analysis_service import get_simple_analysis_service
from app.services.unified_analysis_service import get_unified_analysis_service
from app.services.websocket_manager import get_websocket_manager
from app.models.analysis import (
    SingleAnalysisRequest, BatchAnalysisRequest, AnalysisParameters,
    AnalysisTaskResponse, AnalysisBatchResponse, AnalysisHistoryQuery,
    AnalysisEngine,
)
from tradingagents.utils.stock_utils import StockUtils, StockMarket
from app.core.database import get_mongo_db
from bson import ObjectId

router = APIRouter()
logger = logging.getLogger("webapi")


# 🔥 统一的结果数据格式化函数
def normalize_result_data(result_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    统一格式化分析结果数据，确保所有接口返回一致的格式

    主要处理：
    1. recommendation 字段：使用合规术语，不包含具体价格
    2. key_points 字段：转换 JSON 字段名为中文描述
    3. decision 字段：支持新旧字段名
    4. action 字段：将旧术语（买入/卖出/持有）映射为合规术语（看涨/看跌/中性）
    """
    if not result_data:
        return result_data

    # 🔥 术语映射：将旧术语转换为合规术语
    ACTION_TRANSLATION = {
        'BUY': '看涨', 'SELL': '看跌', 'HOLD': '中性',
        'buy': '看涨', 'sell': '看跌', 'hold': '中性',
        '买入': '看涨', '卖出': '看跌', '持有': '中性',  # 兼容旧数据
        '看涨': '看涨', '看跌': '看跌', '中性': '中性',  # 保持新术语不变
    }

    # 1. 处理 decision 字段（支持新旧字段名）
    decision = result_data.get('decision', {})
    if isinstance(decision, dict):
        # 支持新旧字段名
        raw_action = decision.get('analysis_view') or decision.get('action')
        # 🔥 映射为合规术语
        action = ACTION_TRANSLATION.get(raw_action, raw_action) if raw_action else None

        # 🔥 更新 decision 对象中的 action 字段为合规术语
        if action and raw_action != action:
            decision['action'] = action
            # 如果有 analysis_view 字段，也更新它
            if 'analysis_view' in decision:
                decision['analysis_view'] = action

        price_range = decision.get('price_analysis_range') or decision.get('target_price')
        confidence = decision.get('confidence')
        risk_score = decision.get('risk_score')
        risk_level = decision.get('risk_level')
        reasoning = decision.get('reasoning', '')

        # 2. 格式化 recommendation（如果为空或包含旧术语）
        recommendation = result_data.get('recommendation', '')
        if not recommendation or '投资建议' in recommendation or '目标价格' in recommendation or '买入' in recommendation or '卖出' in recommendation:
            # 重新生成合规的 recommendation
            recommendation = f"分析观点：{action}；" if action else ""
            if reasoning and len(reasoning) < 100:
                recommendation += f"分析依据：{reasoning}"
            elif reasoning and reasoning != "暂无分析推理":
                short_reasoning = reasoning[:50] + "..." if len(reasoning) > 50 else reasoning
                recommendation += f"分析依据：{short_reasoning}"
            result_data['recommendation'] = recommendation

        # 3. 格式化 key_points（如果包含 JSON 字段名）
        key_points = result_data.get('key_points', [])
        if key_points and isinstance(key_points, list):
            # 检查是否包含 JSON 字段名（如 "analysis_view": "中性"）
            if any('"' in str(kp) and ':' in str(kp) for kp in key_points):
                # 重新生成 key_points
                new_key_points = []
                if action:
                    new_key_points.append(f"分析观点: {action}")
                if price_range:
                    if isinstance(price_range, (list, tuple)) and len(price_range) == 2:
                        new_key_points.append(f"价格分析区间: {price_range[0]}-{price_range[1]}元")
                    else:
                        new_key_points.append(f"参考价格: {price_range}元")
                if confidence is not None:
                    new_key_points.append(f"置信度: {confidence * 100:.1f}%" if confidence <= 1 else f"置信度: {confidence}%")
                if risk_level:
                    new_key_points.append(f"风险等级: {risk_level}")
                if risk_score is not None:
                    new_key_points.append(f"风险评分: {risk_score * 100:.1f}%" if risk_score <= 1 else f"风险评分: {risk_score}%")

                result_data['key_points'] = new_key_points[:5]

    return result_data


def get_market_type_from_symbol(symbol: str) -> str:
    """根据股票代码获取 market_type

    Args:
        symbol: 股票代码

    Returns:
        market_type: "cn" (A股), "hk" (港股), "us" (美股)
    """
    market = StockUtils.identify_stock_market(symbol)

    # 映射 StockMarket 枚举到 market_type 字符串
    market_type_mapping = {
        StockMarket.CHINA_A: "cn",
        StockMarket.HONG_KONG: "hk",
        StockMarket.US: "us",
        StockMarket.UNKNOWN: "cn"  # 默认为中国市场
    }

    return market_type_mapping.get(market, "cn")


async def get_user_risk_preference(user_id: str) -> str:
    """获取用户的风险偏好设置

    Args:
        user_id: 用户ID

    Returns:
        风险偏好: 'conservative'(保守) / 'neutral'(中性) / 'aggressive'(激进)
        默认返回 'neutral'
    """
    try:
        db = get_mongo_db()
        users_collection = db["users"]

        # 查询用户
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if user and "preferences" in user:
            risk_pref = user["preferences"].get("risk_preference", "neutral")
            logger.info(f"📊 获取用户 {user_id} 的风险偏好: {risk_pref}")
            return risk_pref

        logger.info(f"📊 用户 {user_id} 未设置风险偏好，使用默认值: neutral")
        return "neutral"
    except Exception as e:
        logger.warning(f"⚠️ 获取用户风险偏好失败: {e}，使用默认值: neutral")
        return "neutral"

# 兼容性：保留原有的请求模型
class SingleAnalyzeRequest(BaseModel):
    symbol: str
    parameters: dict = Field(default_factory=dict)

class BatchAnalyzeRequest(BaseModel):
    symbols: List[str]
    parameters: dict = Field(default_factory=dict)
    title: str = Field(default="批量分析", description="批次标题")
    description: Optional[str] = Field(None, description="批次描述")

# 新版API端点
@router.post("/single", response_model=Dict[str, Any])
async def submit_single_analysis(
    request: SingleAnalysisRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """
    提交单股分析任务 - 支持 AB 测试

    通过 request.parameters.engine 参数选择引擎:
    - legacy (默认): 使用旧引擎 TradingAgentsGraph
    - unified: 使用新的统一引擎 WorkflowEngine (LangGraph 动态构建)
    """
    try:
        logger.info("🎯 收到单股分析请求")
        logger.info(f"👤 用户信息: {user}")
        logger.info(f"📊 请求数据: {request}")

        # 判断使用哪个引擎
        engine_type = AnalysisEngine.LEGACY
        if request.parameters and hasattr(request.parameters, "engine"):
            engine_type = request.parameters.engine
            logger.info(f"🔍 [引擎判断] 从 request.parameters.engine 获取: {engine_type} (类型: {type(engine_type)})")
        else:
            logger.warning(f"⚠️ [引擎判断] request.parameters 中没有 engine 字段，使用默认引擎: {engine_type.value}")
            if request.parameters:
                logger.info(f"🔍 [引擎判断] request.parameters 类型: {type(request.parameters)}")
                logger.info(f"🔍 [引擎判断] request.parameters 内容: {request.parameters}")
                if hasattr(request.parameters, "model_dump"):
                    logger.info(f"🔍 [引擎判断] request.parameters.model_dump(): {request.parameters.model_dump()}")

        logger.info(f"🔧 [AB测试] 最终使用引擎: {engine_type.value} (枚举值: {engine_type})")

        # 根据引擎类型选择任务创建方式
        # 🔍 兼容性检查：同时支持枚举和字符串比较
        is_v2_engine = (
            engine_type == AnalysisEngine.V2 or 
            (isinstance(engine_type, str) and engine_type.lower() == "v2") or
            (hasattr(engine_type, "value") and engine_type.value == "v2")
        )
        
        if is_v2_engine:
            logger.info(f"✅ [引擎判断] 确认为 v2 引擎，使用统一任务服务")
            # v2 引擎：使用统一任务服务创建 UnifiedAnalysisTask
            from app.services.task_analysis_service import get_task_analysis_service
            from app.models.analysis import AnalysisTaskType
            from app.models.user import PyObjectId

            task_service = get_task_analysis_service()

            # 准备任务参数 - 将 parameters 的内容展开到顶层
            symbol = request.get_symbol()

            # 🔥 修复：根据股票代码自动识别市场类型
            market_type = get_market_type_from_symbol(symbol)
            logger.info(f"📊 [单股分析] 股票 {symbol} 识别为市场: {market_type}")

            task_params = {
                "symbol": symbol,
                "stock_code": symbol,
                "market_type": market_type,  # 🔑 根据股票代码自动识别市场类型
            }

            # 将 request.parameters 的所有字段合并到 task_params
            if request.parameters:
                params_dict = request.parameters.model_dump()
                # 移除 engine 字段（这是路由层使用的，不是任务参数）
                params_dict.pop("engine", None)
                task_params.update(params_dict)

            # 如果用户在 parameters 中指定了 market_type，优先使用用户指定的
            if request.parameters and hasattr(request.parameters, 'market_type') and request.parameters.market_type:
                task_params["market_type"] = request.parameters.market_type
                logger.info(f"📊 [单股分析] 使用用户指定的市场类型: {request.parameters.market_type}")

            logger.info(f"📦 v2任务参数: {task_params}")

            # 🔥 从用户偏好读取风险偏好设置
            preference_type = await get_user_risk_preference(user["id"])
            logger.info(f"📊 [单股分析] 使用用户风险偏好: {preference_type}")

            # 创建统一任务（不执行）
            task = await task_service.create_task(
                user_id=PyObjectId(user["id"]),
                task_type=AnalysisTaskType.STOCK_ANALYSIS,
                task_params=task_params,
                engine_type="auto",  # 自动选择引擎
                preference_type=preference_type  # 🔥 使用用户偏好设置
            )

            # 🔑 关键：同时在内存中创建任务状态（用于快速查询）
            from app.services.memory_state_manager import get_memory_state_manager
            memory_manager = get_memory_state_manager()
            await memory_manager.create_task(
                task_id=task.task_id,
                user_id=user["id"],
                stock_code=request.get_symbol(),
                parameters=task_params,
                stock_name=None  # 可以后续补充
            )
            logger.info(f"✅ [v2引擎] 任务已创建到内存: {task.task_id}")

            # 🔥 v2 引擎：将任务提交到队列，由 Worker 处理
            from app.services.queue_service import get_queue_service
            queue_service = get_queue_service()
            
            # 准备队列参数
            queue_params = {
                "engine": "v2",  # 标记为 v2 引擎
                "task_id": task.task_id,
                "symbol": symbol,
                "stock_code": symbol,
                "user_id": user["id"],
                **task_params  # 包含所有任务参数
            }
            
            # 提交到队列
            await queue_service.enqueue_task(
                user_id=user["id"],
                symbol=symbol,
                params=queue_params,
                batch_id=None,  # 单股分析没有批次ID
                task_id=task.task_id  # 使用已生成的任务ID
            )
            logger.info(f"✅ [v2引擎] 任务已提交到队列: {task.task_id}")

            result = {
                "task_id": task.task_id,  # 使用 UUID task_id，不是 ObjectId
                "status": task.status.value,
                "created_at": task.created_at.isoformat() if task.created_at else None
            }
            task_id = task.task_id  # 使用 UUID task_id
            user_id = user["id"]
        else:
            # legacy/unified 引擎：使用旧服务创建 AnalysisTask（已改为使用队列）
            legacy_service = get_simple_analysis_service()
            result = await legacy_service.create_analysis_task(user["id"], request)
            # 🔥 注意：create_analysis_task 内部已经将任务提交到队列，不需要后台执行

        # 🔥 所有引擎的任务都已提交到队列，由 Worker 进程处理
        # 不再需要在 API 进程中后台执行任务
        logger.info(f"✅ 分析任务已提交到队列: {result}")

        return {
            "success": True,
            "data": result,
            "message": f"分析任务已提交到队列，等待 Worker 处理 (引擎: {engine_type.value})"
        }
    except Exception as e:
        logger.error(f"❌ 提交单股分析任务失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# 测试路由 - 验证路由是否被正确注册
@router.get("/test-route")
async def test_route():
    """测试路由是否工作"""
    logger.info("🧪 测试路由被调用了！")
    return {"message": "测试路由工作正常", "timestamp": time.time()}

@router.get("/tasks/{task_id}/status", response_model=Dict[str, Any])
async def get_task_status_new(
    task_id: str,
    user: dict = Depends(get_current_user)
):
    """获取分析任务状态（新版异步实现）
    
    查询优先级：
    1. MongoDB (unified_analysis_tasks) - 真实数据源，Worker 进程会更新这里
    2. MongoDB (analysis_tasks) - 旧版任务
    3. 内存状态管理器 - 仅作为缓存（进程内，Worker 和 API 进程分开）
    """
    try:
        logger.info(f"🔍 [NEW ROUTE] 进入新版状态查询路由: {task_id}")
        logger.info(f"👤 [NEW ROUTE] 用户: {user}")

        # 🔥 优先从 MongoDB 查询（真实数据源，Worker 进程会更新这里）
        # 因为 Worker 进程和 API 进程是分开的，内存状态管理器不共享
        from app.core.database import get_mongo_db
        from bson import ObjectId
        db = get_mongo_db()

        # 首先尝试从 unified_analysis_tasks 集合中查找（v2 引擎任务）
        unified_task = await db.unified_analysis_tasks.find_one({"task_id": task_id})
        if unified_task:
            logger.info(f"✅ [STATUS] 从unified_analysis_tasks找到任务: {task_id}")

            # 🔑 关键：区分步骤名称和消息
            # current_step 存储的是简短的步骤名称（如 "市场分析师"）
            # message 存储的是详细的描述（如 "📈 市场分析师正在分析技术指标和市场趋势..."）
            current_step_name = unified_task.get("current_step", "")
            current_step_description = unified_task.get("message", current_step_name)

            # 获取状态，并做兼容性映射（前端期望 'running' 而不是 'processing'）
            backend_status = unified_task.get("status", "pending")
            # 🔥 状态映射：processing → running, cancelled → cancelled, failed → failed
            if backend_status == "processing":
                frontend_status = "running"
            elif backend_status == "cancelled":
                frontend_status = "cancelled"  # 保持 cancelled 状态
            else:
                frontend_status = backend_status

            # 🔧 计算时间估算（遵循旧版本逻辑）
            from app.services.progress.tracker import RedisProgressTracker
            from datetime import datetime, timezone

            # 获取任务参数
            task_params = unified_task.get("task_params", {})
            progress_pct = unified_task.get("progress", 0)
            start_time = unified_task.get("started_at")
            end_time = unified_task.get("completed_at")

            # 计算时间估算
            elapsed_time = 0
            remaining_time = 0
            estimated_total_time = 0

            if end_time:
                # 任务已完成，使用最终执行时间
                from dateutil import parser

                if isinstance(start_time, str):
                    try:
                        start_time = parser.parse(start_time)
                    except Exception as e:
                        logger.warning(f"⚠️ 无法解析开始时间: {start_time}, 错误: {e}")
                        start_time = None

                if isinstance(end_time, str):
                    try:
                        end_time = parser.parse(end_time)
                    except Exception as e:
                        logger.warning(f"⚠️ 无法解析结束时间: {end_time}, 错误: {e}")
                        end_time = None

                if start_time and end_time:
                    # 确保时区一致
                    if start_time.tzinfo is None:
                        start_time = start_time.replace(tzinfo=timezone.utc)
                    if end_time.tzinfo is None:
                        end_time = end_time.replace(tzinfo=timezone.utc)

                    elapsed_time = (end_time - start_time).total_seconds()
                    estimated_total_time = elapsed_time  # 已完成任务的总时长就是已用时间
                    remaining_time = 0

            elif start_time:
                # 任务进行中
                if isinstance(start_time, str):
                    try:
                        from dateutil import parser
                        start_time = parser.parse(start_time)
                    except Exception as e:
                        logger.warning(f"⚠️ 无法解析开始时间: {start_time}, 错误: {e}")
                        start_time = None

                if start_time:
                    # 确保使用本地时间（带时区）
                    current_time = datetime.now(timezone.utc)

                    # 确保 start_time 有时区信息
                    if start_time.tzinfo is None:
                        # 假设数据库中的时间是 UTC
                        start_time = start_time.replace(tzinfo=timezone.utc)

                    # 计算已用时间
                    elapsed_time = (current_time - start_time).total_seconds()

                    # 🔑 关键：使用任务创建时预估的总时长（固定值），而不是根据进度动态计算
                    # 获取分析师列表和研究深度
                    analysts = task_params.get("selected_analysts", [])
                    research_depth = task_params.get("research_depth", "快速")
                    llm_model = task_params.get("quick_analysis_model", "dashscope")
                    llm_provider = llm_model.split("-")[0] if llm_model else "dashscope"

                    # 使用 RedisProgressTracker 的内部方法计算基准时间（预估总时长）
                    temp_tracker = RedisProgressTracker(
                        task_id="temp",
                        analysts=analysts,
                        research_depth=research_depth,
                        llm_provider=llm_provider
                    )
                    estimated_total_time = temp_tracker._get_base_total_time()

                    # 预计剩余 = 预估总时长 - 已用时间
                    remaining_time = max(0, estimated_total_time - elapsed_time)

            # 🔑 尝试从 Redis 获取详细的步骤信息
            steps_info = []
            completed_steps = []
            try:
                from app.core.redis_client import get_redis_service, RedisKeys

                redis_service = get_redis_service()
                # 🔥 检查 Redis 是否已初始化
                try:
                    # 尝试访问 redis 属性，如果未初始化会抛出异常
                    _ = redis_service.redis
                except RuntimeError as redis_err:
                    # Redis 未初始化，跳过 Redis 查询，但不影响主流程
                    logger.debug(f"📊 [STATUS] Redis未初始化，跳过步骤信息查询: {redis_err}")
                else:
                    # Redis 已初始化，可以安全查询
                    progress_key = RedisKeys.TASK_PROGRESS.format(task_id=task_id)
                    progress_data = await redis_service.get_json(progress_key)

                    if progress_data and "steps" in progress_data:
                        steps_info = progress_data["steps"]
                        # 提取已完成的步骤名称
                        completed_steps = [
                            step["name"] for step in steps_info
                            if step.get("status") == "completed"
                        ]
                        logger.info(f"📊 [STATUS] 从Redis获取到步骤信息: {len(steps_info)}个步骤, {len(completed_steps)}个已完成")
            except Exception as e:
                # 其他异常（如连接错误等）只记录警告，不影响主流程
                logger.debug(f"📊 [STATUS] 从Redis获取步骤信息失败（不影响主流程）: {e}")

            # 🔥 构造消息：根据状态决定显示内容
            error_message = unified_task.get("error_message")
            if frontend_status == "cancelled":
                # 取消状态：显示取消消息
                display_message = error_message or "任务已被用户取消"
            elif frontend_status == "failed":
                # 失败状态：显示错误消息
                display_message = error_message or "任务执行失败"
            elif frontend_status == "completed":
                # 完成状态
                display_message = "分析完成"
            else:
                # 运行中：显示当前步骤
                display_message = current_step_description or f"任务{frontend_status}中..."

            # 构造状态响应（统一任务格式，兼容前端期望的字段名）
            status_data = {
                "task_id": unified_task.get("task_id"),
                "user_id": str(unified_task.get("user_id", "")),
                "status": frontend_status,  # 使用映射后的状态
                "progress": progress_pct,
                "message": display_message,  # 🔥 使用优化后的消息

                # 🔑 关键：区分步骤名称和描述
                "current_step_name": current_step_name,  # ✅ 简短的步骤名称（如 "市场分析师"）
                "current_step_description": current_step_description,  # ✅ 详细的描述（如 "📈 市场分析师正在分析..."）
                "current_step": current_step_name,  # 保留兼容性

                "start_time": unified_task.get("started_at"),
                "end_time": end_time,
                "elapsed_time": elapsed_time,  # ✅ 使用计算后的值
                "remaining_time": remaining_time,  # ✅ 使用计算后的值
                "estimated_total_time": estimated_total_time,  # ✅ 使用计算后的值
                "symbol": task_params.get("symbol") or task_params.get("stock_code"),
                "stock_code": task_params.get("stock_code") or task_params.get("symbol"),
                "stock_symbol": task_params.get("symbol") or task_params.get("stock_code"),
                "task_type": unified_task.get("task_type"),
                "source": "unified_tasks",  # 标记数据来源

                # 🆕 添加步骤信息
                "steps": steps_info,  # 所有步骤的详细信息
                "completed_steps": completed_steps,  # 已完成的步骤名称列表

                # 添加结果数据（如果有）
                "result_data": unified_task.get("result"),
                "error_message": error_message,  # 🔥 保留原始错误消息
                "parameters": task_params,  # 添加参数信息
                "execution_time": unified_task.get("execution_time"),
                "tokens_used": unified_task.get("tokens_used"),
            }

            # 🔥 格式化 result_data（如果存在）
            if status_data.get("result_data"):
                logger.info(f"📊 [STATUS] ========== unified_tasks result_data 格式化前 ==========")
                logger.info(f"📊 [STATUS] recommendation: {status_data['result_data'].get('recommendation', '')[:200]}")
                logger.info(f"📊 [STATUS] key_points: {status_data['result_data'].get('key_points', [])[:3]}")

                status_data["result_data"] = normalize_result_data(status_data["result_data"])

                logger.info(f"📊 [STATUS] ========== unified_tasks result_data 格式化后 ==========")
                logger.info(f"📊 [STATUS] recommendation: {status_data['result_data'].get('recommendation', '')[:200]}")
                logger.info(f"📊 [STATUS] key_points: {status_data['result_data'].get('key_points', [])[:3]}")

            logger.info(f"📊 [STATUS] 返回状态: status={status_data['status']}, progress={status_data['progress']}, step={status_data['current_step_name']}")

            return {
                "success": True,
                "data": status_data,
                "message": "任务状态获取成功"
            }

        # 然后从analysis_tasks集合中查找（旧版任务）
        task_result = await db.analysis_tasks.find_one({"task_id": task_id})

        if task_result:
                logger.info(f"✅ [STATUS] 从analysis_tasks找到任务: {task_id}")

                # 构造状态响应（正在进行的任务）
                status = task_result.get("status", "pending")
                progress = task_result.get("progress", 0)
                current_step = task_result.get("current_step", "")
                message = task_result.get("message", f"任务{status}中...")

                # 计算时间信息
                from datetime import datetime
                start_time = task_result.get("started_at") or task_result.get("created_at")

                # 如果是字符串，转换为 datetime
                if isinstance(start_time, str):
                    try:
                        from dateutil import parser
                        start_time = parser.parse(start_time)
                    except Exception as e:
                        logger.warning(f"⚠️ 无法解析开始时间: {start_time}, 错误: {e}")
                        start_time = None

                current_time = datetime.utcnow()
                elapsed_time = 0
                estimated_total_time = task_result.get("estimated_total_time", 225.0)  # 默认225秒
                remaining_time = 0

                if start_time:
                    # 确保 start_time 是 naive datetime（移除时区信息）
                    if start_time.tzinfo is not None:
                        start_time = start_time.replace(tzinfo=None)
                    elapsed_time = (current_time - start_time).total_seconds()

                    # 根据进度估算剩余时间
                    if progress > 0 and progress < 100:
                        remaining_time = max(0, estimated_total_time - elapsed_time)

                # 🔥 状态映射：processing → running（前端期望 running）
                frontend_status = "running" if status == "processing" else status

                # 获取参数信息
                parameters = task_result.get("parameters", {})

                status_data = {
                    "task_id": task_id,
                    "user_id": str(task_result.get("user_id", "")),
                    "status": frontend_status,
                    "progress": progress,
                    "message": message,
                    "current_step_name": current_step,
                    "current_step_description": message,
                    "current_step": current_step,
                    "start_time": start_time,
                    "end_time": task_result.get("completed_at"),
                    "elapsed_time": elapsed_time,
                    "remaining_time": remaining_time,
                    "estimated_total_time": estimated_total_time,
                    "symbol": task_result.get("symbol") or task_result.get("stock_code"),
                    "stock_code": task_result.get("symbol") or task_result.get("stock_code"),
                    "stock_symbol": task_result.get("symbol") or task_result.get("stock_code"),
                    "task_type": "stock_analysis",
                    "source": "analysis_tasks",  # 标记数据来源
                    "steps": [],
                    "completed_steps": [],
                    "result_data": None,
                    "error_message": task_result.get("error_message"),
                    "parameters": parameters,
                    "execution_time": task_result.get("execution_time", 0.0),
                    "tokens_used": task_result.get("tokens_used", 0)
                }

                return {
                    "success": True,
                    "data": status_data,
                    "message": "任务状态获取成功"
                }

        # 如果analysis_tasks中没有找到，再从analysis_reports集合中查找（已完成的任务）
        mongo_result = await db.analysis_reports.find_one({"task_id": task_id})

        if mongo_result:
            logger.info(f"✅ [STATUS] 从analysis_reports找到任务: {task_id}")

            # 构造状态响应（模拟已完成的任务）
            # 计算已完成任务的时间信息
            start_time = mongo_result.get("created_at")
            end_time = mongo_result.get("updated_at")
            elapsed_time = 0
            if start_time and end_time:
                elapsed_time = (end_time - start_time).total_seconds()

            status_data = {
                "task_id": task_id,
                "status": "completed",
                "progress": 100,
                "message": "分析完成（从历史记录恢复）",
                "current_step": "completed",
                "start_time": start_time,
                "end_time": end_time,
                "elapsed_time": elapsed_time,
                "remaining_time": 0,
                "estimated_total_time": elapsed_time,  # 已完成任务的总时长就是已用时间
                "stock_code": mongo_result.get("stock_symbol"),
                "stock_symbol": mongo_result.get("stock_symbol"),
                "analysts": mongo_result.get("analysts", []),
                "research_depth": mongo_result.get("research_depth", "快速"),
                "source": "mongodb_reports"  # 标记数据来源
            }

            return {
                "success": True,
                "data": status_data,
                "message": "任务状态获取成功（从历史记录恢复）"
            }
        else:
            logger.warning(f"❌ [STATUS] MongoDB中也未找到: {task_id} trace={task_id}")
            raise HTTPException(status_code=404, detail="任务不存在")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks/{task_id}/result", response_model=Dict[str, Any])
async def get_task_result(
    task_id: str,
    user: dict = Depends(get_current_user)
):
    """获取分析任务结果"""
    try:
        logger.info(f"🔍 [RESULT] 获取任务结果: {task_id}")
        logger.info(f"👤 [RESULT] 用户: {user}")

        analysis_service = get_simple_analysis_service()
        task_status = await analysis_service.get_task_status(task_id)

        result_data = None

        if task_status and task_status.get('status') == 'completed':
            # 从内存中获取结果数据
            result_data = task_status.get('result_data')
            logger.info(f"📊 [RESULT] 从内存中获取到结果数据")

            # 🔍 调试：检查内存中的数据结构
            if result_data:
                logger.info(f"📊 [RESULT] ========== 格式化前 ==========")
                logger.info(f"📊 [RESULT] 内存数据键: {list(result_data.keys())}")
                logger.info(f"📊 [RESULT] recommendation: {result_data.get('recommendation', '')[:200]}")
                logger.info(f"📊 [RESULT] key_points: {result_data.get('key_points', [])[:3]}")
                if result_data.get('decision'):
                    decision = result_data['decision']
                    logger.info(f"📊 [RESULT] decision: action={decision.get('action')}, analysis_view={decision.get('analysis_view')}, target_price={decision.get('target_price')}, price_analysis_range={decision.get('price_analysis_range')}")

                # 🔥 统一格式化结果数据
                result_data = normalize_result_data(result_data)

                logger.info(f"📊 [RESULT] ========== 格式化后 ==========")
                logger.info(f"📊 [RESULT] recommendation: {result_data.get('recommendation', '')[:200]}")
                logger.info(f"📊 [RESULT] key_points: {result_data.get('key_points', [])[:3]}")
            else:
                logger.warning(f"⚠️ [RESULT] 内存中result_data为空")

        if not result_data:
            # 内存中没有找到，尝试从MongoDB中查找
            logger.info(f"📊 [RESULT] 内存中未找到，尝试从MongoDB查找: {task_id}")

            from app.core.database import get_mongo_db
            db = get_mongo_db()

            # 🔧 首先从 unified_analysis_tasks 集合中查找（v2 引擎任务）
            unified_task = await db.unified_analysis_tasks.find_one({"task_id": task_id})
            if unified_task and unified_task.get("result"):
                logger.info(f"✅ [RESULT] 从unified_analysis_tasks找到结果: {task_id}")

                result = unified_task["result"]
                task_params = unified_task.get("task_params", {})

                # 计算执行时间
                execution_time = 0
                completed_at = unified_task.get("completed_at")
                started_at = unified_task.get("started_at")
                if completed_at and started_at:
                    try:
                        # 如果是 datetime 对象，直接相减
                        if hasattr(completed_at, 'timestamp') and hasattr(started_at, 'timestamp'):
                            execution_time = (completed_at - started_at).total_seconds()
                        # 如果是字符串，先解析
                        elif isinstance(completed_at, str) and isinstance(started_at, str):
                            from dateutil import parser
                            completed_dt = parser.parse(completed_at)
                            started_dt = parser.parse(started_at)
                            execution_time = (completed_dt - started_dt).total_seconds()
                    except Exception as e:
                        logger.warning(f"⚠️ 计算执行时间失败: {e}")
                        execution_time = 0

                # 构造结果数据（兼容前端期望的格式）
                result_data = {
                    "analysis_id": unified_task.get("task_id"),  # 使用 task_id 作为 analysis_id
                    "stock_symbol": task_params.get("symbol") or task_params.get("stock_code"),
                    "stock_code": task_params.get("stock_code") or task_params.get("symbol"),
                    "analysis_date": task_params.get("analysis_date"),
                    "summary": result.get("summary", ""),
                    "recommendation": result.get("recommendation", ""),
                    "confidence_score": result.get("confidence_score", 0.0),
                    "risk_level": result.get("risk_level", "中等"),
                    "key_points": result.get("key_points", []),
                    "execution_time": execution_time,
                    "tokens_used": result.get("tokens_used", 0),
                    "analysts": task_params.get("selected_analysts", []),
                    "research_depth": task_params.get("research_depth", "快速"),
                    "reports": result.get("reports", {}),
                    "state": result.get("state", {}),
                    "detailed_analysis": result.get("detailed_analysis", {}),
                    "created_at": unified_task.get("created_at"),
                    "updated_at": unified_task.get("completed_at"),
                    "status": "completed",
                    "decision": result.get("decision", {}),
                    "source": "unified_tasks"  # 标记数据来源
                }

                logger.info(f"📊 [RESULT] ========== unified_tasks 格式化前 ==========")
                logger.info(f"📊 [RESULT] recommendation: {result_data.get('recommendation', '')[:200]}")
                logger.info(f"📊 [RESULT] key_points: {result_data.get('key_points', [])[:3]}")
                if result_data.get('decision'):
                    decision = result_data['decision']
                    logger.info(f"📊 [RESULT] decision: action={decision.get('action')}, analysis_view={decision.get('analysis_view')}, target_price={decision.get('target_price')}, price_analysis_range={decision.get('price_analysis_range')}")

                # 🔥 统一格式化结果数据
                result_data = normalize_result_data(result_data)

                logger.info(f"📊 [RESULT] ========== unified_tasks 格式化后 ==========")
                logger.info(f"📊 [RESULT] recommendation: {result_data.get('recommendation', '')[:200]}")
                logger.info(f"📊 [RESULT] key_points: {result_data.get('key_points', [])[:3]}")

            # 如果 unified_analysis_tasks 中没有找到，再从 analysis_reports 集合中查找
            if not result_data:
                mongo_result = await db.analysis_reports.find_one({"task_id": task_id})

                if not mongo_result:
                    # 兼容旧数据：旧记录可能没有 task_id，但 analysis_id 存在于 analysis_tasks.result
                    tasks_doc_for_id = await db.analysis_tasks.find_one({"task_id": task_id}, {"result.analysis_id": 1})
                    analysis_id = tasks_doc_for_id.get("result", {}).get("analysis_id") if tasks_doc_for_id else None
                    if analysis_id:
                        logger.info(f"🔎 [RESULT] 按analysis_id兜底查询 analysis_reports: {analysis_id}")
                        mongo_result = await db.analysis_reports.find_one({"analysis_id": analysis_id})
            else:
                # 如果从 unified_analysis_tasks 找到了结果，就不需要查询 analysis_reports
                mongo_result = None

            if mongo_result:
                logger.info(f"✅ [RESULT] 从MongoDB找到结果: {task_id}")

                # 直接使用MongoDB中的数据结构（与web目录保持一致）
                result_data = {
                    "analysis_id": mongo_result.get("analysis_id"),
                    "stock_symbol": mongo_result.get("stock_symbol"),
                    "stock_code": mongo_result.get("stock_symbol"),  # 兼容性
                    "analysis_date": mongo_result.get("analysis_date"),
                    "summary": mongo_result.get("summary", ""),
                    "recommendation": mongo_result.get("recommendation", ""),
                    "confidence_score": mongo_result.get("confidence_score", 0.0),
                    "risk_level": mongo_result.get("risk_level", "中等"),
                    "key_points": mongo_result.get("key_points", []),
                    "execution_time": mongo_result.get("execution_time", 0),
                    "tokens_used": mongo_result.get("tokens_used", 0),
                    "analysts": mongo_result.get("analysts", []),
                    "research_depth": mongo_result.get("research_depth", "快速"),
                    "reports": mongo_result.get("reports", {}),
                    "created_at": mongo_result.get("created_at"),
                    "updated_at": mongo_result.get("updated_at"),
                    "status": mongo_result.get("status", "completed"),
                    "decision": mongo_result.get("decision", {}),
                    "source": "mongodb"  # 标记数据来源
                }

                logger.info(f"📊 [RESULT] ========== MongoDB 格式化前 ==========")
                logger.info(f"📊 [RESULT] recommendation: {result_data.get('recommendation', '')[:200]}")
                logger.info(f"📊 [RESULT] key_points: {result_data.get('key_points', [])[:3]}")
                if result_data.get('decision'):
                    decision = result_data['decision']
                    logger.info(f"📊 [RESULT] decision: action={decision.get('action')}, analysis_view={decision.get('analysis_view')}")

                # 🔥 统一格式化结果数据
                result_data = normalize_result_data(result_data)

                logger.info(f"📊 [RESULT] ========== MongoDB 格式化后 ==========")
                logger.info(f"📊 [RESULT] recommendation: {result_data.get('recommendation', '')[:200]}")
                logger.info(f"📊 [RESULT] key_points: {result_data.get('key_points', [])[:3]}")
            else:
                # 兜底：analysis_tasks 集合中的 result 字段
                tasks_doc = await db.analysis_tasks.find_one(
                    {"task_id": task_id},
                    {"result": 1, "symbol": 1, "stock_code": 1, "created_at": 1, "completed_at": 1}
                )
                if tasks_doc and tasks_doc.get("result"):
                    r = tasks_doc["result"] or {}
                    logger.info("✅ [RESULT] 从analysis_tasks.result 找到结果")
                    # 获取股票代码 (优先使用symbol)
                    symbol = (tasks_doc.get("symbol") or tasks_doc.get("stock_code") or
                             r.get("stock_symbol") or r.get("stock_code"))
                    result_data = {
                        "analysis_id": r.get("analysis_id"),
                        "stock_symbol": symbol,
                        "stock_code": symbol,  # 兼容字段
                        "analysis_date": r.get("analysis_date"),
                        "summary": r.get("summary", ""),
                        "recommendation": r.get("recommendation", ""),
                        "confidence_score": r.get("confidence_score", 0.0),
                        "risk_level": r.get("risk_level", "中等"),
                        "key_points": r.get("key_points", []),
                        "execution_time": r.get("execution_time", 0),
                        "tokens_used": r.get("tokens_used", 0),
                        "analysts": r.get("analysts", []),
                        "research_depth": r.get("research_depth", "快速"),
                        "reports": r.get("reports", {}),
                        "state": r.get("state", {}),
                        "detailed_analysis": r.get("detailed_analysis", {}),
                        "created_at": tasks_doc.get("created_at"),
                        "updated_at": tasks_doc.get("completed_at"),
                        "status": r.get("status", "completed"),
                        "decision": r.get("decision", {}),
                        "source": "analysis_tasks"  # 数据来源标记
                    }

                    logger.info(f"📊 [RESULT] ========== analysis_tasks 格式化前 ==========")
                    logger.info(f"📊 [RESULT] recommendation: {result_data.get('recommendation', '')[:200]}")
                    logger.info(f"📊 [RESULT] key_points: {result_data.get('key_points', [])[:3]}")
                    if result_data.get('decision'):
                        decision = result_data['decision']
                        logger.info(f"📊 [RESULT] decision: action={decision.get('action')}, analysis_view={decision.get('analysis_view')}")

                    # 🔥 统一格式化结果数据
                    result_data = normalize_result_data(result_data)

                    logger.info(f"📊 [RESULT] ========== analysis_tasks 格式化后 ==========")
                    logger.info(f"📊 [RESULT] recommendation: {result_data.get('recommendation', '')[:200]}")
                    logger.info(f"📊 [RESULT] key_points: {result_data.get('key_points', [])[:3]}")

        if not result_data:
            logger.warning(f"❌ [RESULT] 所有数据源都未找到结果: {task_id}")
            raise HTTPException(status_code=404, detail="分析结果不存在")

        if not result_data:
            raise HTTPException(status_code=404, detail="分析结果不存在")

        # 处理reports字段 - 如果没有reports字段，优先尝试从文件系统加载，其次从state中提取
        if 'reports' not in result_data or not result_data['reports']:
            import os
            from pathlib import Path

            stock_symbol = result_data.get('stock_symbol') or result_data.get('stock_code')
            # analysis_date 可能是日期或时间戳字符串，这里只取日期部分
            analysis_date_raw = result_data.get('analysis_date')
            analysis_date = str(analysis_date_raw)[:10] if analysis_date_raw else None

            loaded_reports = {}
            try:
                # 1) 尝试从环境变量 TRADINGAGENTS_RESULTS_DIR 指定的位置读取
                base_env = os.getenv('TRADINGAGENTS_RESULTS_DIR')
                project_root = Path.cwd()
                if base_env:
                    base_path = Path(base_env)
                    if not base_path.is_absolute():
                        base_path = project_root / base_env
                else:
                    base_path = project_root / 'results'

                candidate_dirs = []
                if stock_symbol and analysis_date:
                    candidate_dirs.append(base_path / stock_symbol / analysis_date / 'reports')
                # 2) 兼容其他保存路径
                if stock_symbol and analysis_date:
                    candidate_dirs.append(project_root / 'data' / 'analysis_results' / stock_symbol / analysis_date / 'reports')
                    candidate_dirs.append(project_root / 'data' / 'analysis_results' / 'detailed' / stock_symbol / analysis_date / 'reports')

                for d in candidate_dirs:
                    if d.exists() and d.is_dir():
                        for f in d.glob('*.md'):
                            try:
                                content = f.read_text(encoding='utf-8')
                                if content and content.strip():
                                    loaded_reports[f.stem] = content.strip()
                            except Exception:
                                pass
                if loaded_reports:
                    result_data['reports'] = loaded_reports
                    # 若 summary / recommendation 缺失，尝试从同名报告补全
                    if not result_data.get('summary') and loaded_reports.get('summary'):
                        result_data['summary'] = loaded_reports.get('summary')
                    if not result_data.get('recommendation') and loaded_reports.get('recommendation'):
                        result_data['recommendation'] = loaded_reports.get('recommendation')
                    logger.info(f"📁 [RESULT] 从文件系统加载到 {len(loaded_reports)} 个报告: {list(loaded_reports.keys())}")
            except Exception as fs_err:
                logger.warning(f"⚠️ [RESULT] 从文件系统加载报告失败: {fs_err}")

            if 'reports' not in result_data or not result_data['reports']:
                logger.info(f"📊 [RESULT] reports字段缺失，尝试从state中提取")

                # 从state中提取报告内容
                reports = {}
                state = result_data.get('state', {})

                if isinstance(state, dict):
                    # 定义所有可能的报告字段
                    report_fields = [
                        'market_report',
                        'sentiment_report',
                        'news_report',
                        'fundamentals_report',
                        'investment_plan',
                        'trader_investment_plan',
                        'final_trade_decision'
                    ]

                    # 从state中提取报告内容
                    for field in report_fields:
                        value = state.get(field, "")
                        if isinstance(value, str) and len(value.strip()) > 10:
                            reports[field] = value.strip()

                    # 处理研究团队辩论状态报告
                    investment_debate_state = state.get('investment_debate_state', {})
                    if isinstance(investment_debate_state, dict):
                        # 提取多头研究员历史
                        bull_content = investment_debate_state.get('bull_history', "")
                        if isinstance(bull_content, str) and len(bull_content.strip()) > 10:
                            reports['bull_researcher'] = bull_content.strip()

                        # 提取空头研究员历史
                        bear_content = investment_debate_state.get('bear_history', "")
                        if isinstance(bear_content, str) and len(bear_content.strip()) > 10:
                            reports['bear_researcher'] = bear_content.strip()

                        # 提取研究经理决策
                        judge_decision = investment_debate_state.get('judge_decision', "")
                        if isinstance(judge_decision, str) and len(judge_decision.strip()) > 10:
                            reports['research_team_decision'] = judge_decision.strip()

                    # 处理风险管理团队辩论状态报告
                    risk_debate_state = state.get('risk_debate_state', {})
                    if isinstance(risk_debate_state, dict):
                        # 提取激进分析师历史
                        risky_content = risk_debate_state.get('risky_history', "")
                        if isinstance(risky_content, str) and len(risky_content.strip()) > 10:
                            reports['risky_analyst'] = risky_content.strip()

                        # 提取保守分析师历史
                        safe_content = risk_debate_state.get('safe_history', "")
                        if isinstance(safe_content, str) and len(safe_content.strip()) > 10:
                            reports['safe_analyst'] = safe_content.strip()

                        # 提取中性分析师历史
                        neutral_content = risk_debate_state.get('neutral_history', "")
                        if isinstance(neutral_content, str) and len(neutral_content.strip()) > 10:
                            reports['neutral_analyst'] = neutral_content.strip()

                        # 提取投资组合经理决策
                        risk_decision = risk_debate_state.get('judge_decision', "")
                        if isinstance(risk_decision, str) and len(risk_decision.strip()) > 10:
                            reports['risk_management_decision'] = risk_decision.strip()

                    logger.info(f"📊 [RESULT] 从state中提取到 {len(reports)} 个报告: {list(reports.keys())}")
                    result_data['reports'] = reports
                else:
                    logger.warning(f"⚠️ [RESULT] state字段不是字典类型: {type(state)}")

        # 确保reports字段中的所有内容都是字符串类型
        if 'reports' in result_data and result_data['reports']:
            reports = result_data['reports']
            if isinstance(reports, dict):
                # 确保每个报告内容都是字符串且不为空
                cleaned_reports = {}
                for key, value in reports.items():
                    if isinstance(value, str) and value.strip():
                        # 确保字符串不为空
                        cleaned_reports[key] = value.strip()
                    elif value is not None:
                        # 如果不是字符串，转换为字符串
                        str_value = str(value).strip()
                        if str_value:  # 只保存非空字符串
                            cleaned_reports[key] = str_value
                    # 如果value为None或空字符串，则跳过该报告

                result_data['reports'] = cleaned_reports
                logger.info(f"📊 [RESULT] 清理reports字段，包含 {len(cleaned_reports)} 个有效报告")

                # 如果清理后没有有效报告，设置为空字典
                if not cleaned_reports:
                    logger.warning(f"⚠️ [RESULT] 清理后没有有效报告")
                    result_data['reports'] = {}
            else:
                logger.warning(f"⚠️ [RESULT] reports字段不是字典类型: {type(reports)}")
                result_data['reports'] = {}

        # 补全关键字段：recommendation/summary/key_points
        try:
            reports = result_data.get('reports', {}) or {}
            decision = result_data.get('decision', {}) or {}

            # recommendation 优先使用决策摘要或报告中的决策
            if not result_data.get('recommendation'):
                rec_candidates = []
                if isinstance(decision, dict):
                    # 🔥 合规修改：支持新旧字段名
                    action = decision.get('analysis_view') or decision.get('action')
                    price_range = decision.get('price_analysis_range') or decision.get('target_price')
                    confidence = decision.get('confidence')

                    if action:
                        parts = [
                            f"分析观点: {action}",
                            f"价格分析区间: {price_range}" if price_range else None,
                            f"置信度: {confidence}" if confidence is not None else None
                        ]
                        rec_candidates.append("；".join([p for p in parts if p]))
                # 从报告中兜底
                for k in ['final_trade_decision', 'investment_plan']:
                    v = reports.get(k)
                    if isinstance(v, str) and len(v.strip()) > 10:
                        rec_candidates.append(v.strip())
                if rec_candidates:
                    # 取最有信息量的一条（最长）
                    result_data['recommendation'] = max(rec_candidates, key=len)[:2000]

            # summary 从若干报告拼接生成
            if not result_data.get('summary'):
                sum_candidates = []
                for k in ['market_report', 'fundamentals_report', 'sentiment_report', 'news_report']:
                    v = reports.get(k)
                    if isinstance(v, str) and len(v.strip()) > 50:
                        sum_candidates.append(v.strip())
                if sum_candidates:
                    result_data['summary'] = ("\n\n".join(sum_candidates))[:3000]

            # key_points 兜底
            if not result_data.get('key_points'):
                kp = []
                if isinstance(decision, dict):
                    # 🔥 合规修改：支持新旧字段名和新术语
                    action = decision.get('analysis_view') or decision.get('action')
                    price_range = decision.get('price_analysis_range') or decision.get('target_price')
                    confidence = decision.get('confidence')
                    risk_level = decision.get('risk_level')

                    if action:
                        kp.append(f"分析观点: {action}")
                    if price_range:
                        # 处理价格区间（可能是列表或单个值）
                        if isinstance(price_range, (list, tuple)) and len(price_range) == 2:
                            kp.append(f"价格分析区间: {price_range[0]}-{price_range[1]}元")
                        else:
                            kp.append(f"参考价格: {price_range}元")
                    if confidence is not None:
                        kp.append(f"置信度: {confidence}")
                    if risk_level:
                        kp.append(f"风险等级: {risk_level}")
                # 从reports中截取前几句作为要点
                for k in ['investment_plan', 'final_trade_decision']:
                    v = reports.get(k)
                    if isinstance(v, str) and len(v.strip()) > 10:
                        kp.append(v.strip()[:120])
                if kp:
                    result_data['key_points'] = kp[:5]
        except Exception as fill_err:
            logger.warning(f"⚠️ [RESULT] 补全关键字段时出错: {fill_err}")


        # 进一步兜底：从 detailed_analysis 推断并补全
        try:
            if not result_data.get('summary') or not result_data.get('recommendation') or not result_data.get('reports'):
                da = result_data.get('detailed_analysis')
                # 若reports仍为空，放入一份原始详细分析，便于前端“查看报告详情”
                if (not result_data.get('reports')) and isinstance(da, str) and len(da.strip()) > 20:
                    result_data['reports'] = {'detailed_analysis': da.strip()}
                elif (not result_data.get('reports')) and isinstance(da, dict) and da:
                    # 将字典的长文本项放入reports
                    extracted = {}
                    for k, v in da.items():
                        if isinstance(v, str) and len(v.strip()) > 20:
                            extracted[k] = v.strip()
                    if extracted:
                        result_data['reports'] = extracted

                # 补 summary
                if not result_data.get('summary'):
                    if isinstance(da, str) and da.strip():
                        result_data['summary'] = da.strip()[:3000]
                    elif isinstance(da, dict) and da:
                        # 取最长的文本作为摘要
                        texts = [v.strip() for v in da.values() if isinstance(v, str) and v.strip()]
                        if texts:
                            result_data['summary'] = max(texts, key=len)[:3000]

                # 补 recommendation
                if not result_data.get('recommendation'):
                    rec = None
                    if isinstance(da, str):
                        # 简单基于关键字提取包含“建议”的段落
                        import re
                        m = re.search(r'(投资建议|建议|结论)[:：]?\s*(.+)', da)
                        if m:
                            rec = m.group(0)
                    elif isinstance(da, dict):
                        for key in ['final_trade_decision', 'investment_plan', '结论', '建议']:
                            v = da.get(key)
                            if isinstance(v, str) and len(v.strip()) > 10:
                                rec = v.strip()
                                break
                    if rec:
                        result_data['recommendation'] = rec[:2000]
        except Exception as da_err:
            logger.warning(f"⚠️ [RESULT] 从detailed_analysis补全失败: {da_err}")

        # 严格的数据格式化和验证
        def safe_string(value, default=""):
            """安全地转换为字符串"""
            if value is None:
                return default
            if isinstance(value, str):
                return value
            return str(value)

        def safe_number(value, default=0):
            """安全地转换为数字"""
            if value is None:
                return default
            if isinstance(value, (int, float)):
                return value
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        def safe_list(value, default=None):
            """安全地转换为列表"""
            if default is None:
                default = []
            if value is None:
                return default
            if isinstance(value, list):
                return value
            return default

        def safe_dict(value, default=None):
            """安全地转换为字典"""
            if default is None:
                default = {}
            if value is None:
                return default
            if isinstance(value, dict):
                return value
            return default

        # 🔍 调试：检查最终构建前的result_data
        logger.info(f"🔍 [FINAL] 构建最终结果前，result_data键: {list(result_data.keys())}")
        logger.info(f"🔍 [FINAL] result_data中有decision: {bool(result_data.get('decision'))}")
        if result_data.get('decision'):
            logger.info(f"🔍 [FINAL] decision内容: {result_data['decision']}")

        # 构建严格验证的结果数据
        final_result_data = {
            "analysis_id": safe_string(result_data.get("analysis_id"), "unknown"),
            "stock_symbol": safe_string(result_data.get("stock_symbol"), "UNKNOWN"),
            "stock_code": safe_string(result_data.get("stock_code"), "UNKNOWN"),
            "analysis_date": safe_string(result_data.get("analysis_date"), "2025-08-20"),
            "summary": safe_string(result_data.get("summary"), "分析摘要暂无"),
            "recommendation": safe_string(result_data.get("recommendation"), "投资建议暂无"),
            "confidence_score": safe_number(result_data.get("confidence_score"), 0.0),
            "risk_level": safe_string(result_data.get("risk_level"), "中等"),
            "key_points": safe_list(result_data.get("key_points")),
            "execution_time": safe_number(result_data.get("execution_time"), 0),
            "tokens_used": safe_number(result_data.get("tokens_used"), 0),
            "analysts": safe_list(result_data.get("analysts")),
            "research_depth": safe_string(result_data.get("research_depth"), "快速"),
            "detailed_analysis": safe_dict(result_data.get("detailed_analysis")),
            "state": safe_dict(result_data.get("state")),
            # 🔥 关键修复：添加decision字段！
            "decision": safe_dict(result_data.get("decision"))
        }

        # 特别处理reports字段 - 确保每个报告都是有效字符串
        reports_data = safe_dict(result_data.get("reports"))
        validated_reports = {}

        for report_key, report_content in reports_data.items():
            # 确保报告键是字符串
            safe_key = safe_string(report_key, "unknown_report")

            # 确保报告内容是非空字符串
            if report_content is None:
                validated_content = "报告内容暂无"
            elif isinstance(report_content, str):
                validated_content = report_content.strip() if report_content.strip() else "报告内容为空"
            else:
                validated_content = str(report_content).strip() if str(report_content).strip() else "报告内容格式错误"

            validated_reports[safe_key] = validated_content

        final_result_data["reports"] = validated_reports

        logger.info(f"✅ [RESULT] 成功获取任务结果: {task_id}")
        logger.info(f"📊 [RESULT] 最终返回 {len(final_result_data.get('reports', {}))} 个报告")
        logger.info(f"📊 [RESULT] 报告列表: {list(validated_reports.keys())}")

        # 🔍 调试：检查最终返回的数据
        logger.info(f"🔍 [FINAL] 最终返回数据键: {list(final_result_data.keys())}")
        logger.info(f"🔍 [FINAL] 最终返回中有decision: {bool(final_result_data.get('decision'))}")
        if final_result_data.get('decision'):
            logger.info(f"🔍 [FINAL] 最终decision内容: {final_result_data['decision']}")

        return {
            "success": True,
            "data": final_result_data,
            "message": "分析结果获取成功"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [RESULT] 获取任务结果失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/tasks/all", response_model=Dict[str, Any])
async def list_all_tasks(
    user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None, description="任务状态过滤"),
    limit: Optional[int] = Query(None, description="返回数量限制（可选，不设置则返回所有）"),
    offset: int = Query(0, ge=0, description="偏移量")
):
    """获取所有任务列表（不限用户）

    注意：如果不指定 limit，将返回所有记录，由前端处理分页
    """
    try:
        logger.info(f"📋 查询所有任务列表")

        # 如果没有指定 limit，则返回所有记录
        actual_limit = limit if limit is not None else 999999

        tasks = await get_simple_analysis_service().list_all_tasks(
            status=status,
            limit=actual_limit,
            offset=offset
        )

        return {
            "success": True,
            "data": {
                "tasks": tasks,
                "total": len(tasks),
                "limit": limit,
                "offset": offset
            },
            "message": "任务列表获取成功"
        }

    except Exception as e:
        logger.error(f"❌ 获取任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks", response_model=Dict[str, Any])
async def list_user_tasks(
    user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None, description="任务状态过滤"),
    limit: Optional[int] = Query(None, description="返回数量限制（可选，不设置则返回所有）"),
    offset: int = Query(0, ge=0, description="偏移量")
):
    """获取用户的任务列表

    注意：如果不指定 limit，将返回所有记录，由前端处理分页
    """
    try:
        logger.info(f"📋 查询用户任务列表: {user['id']}")

        # 如果没有指定 limit，则返回所有记录
        actual_limit = limit if limit is not None else 999999

        tasks = await get_simple_analysis_service().list_user_tasks(
            user_id=user["id"],
            status=status,
            limit=actual_limit,
            offset=offset
        )

        return {
            "success": True,
            "data": {
                "tasks": tasks,
                "total": len(tasks),
                "limit": limit,
                "offset": offset
            },
            "message": "任务列表获取成功"
        }

    except Exception as e:
        logger.error(f"❌ 获取任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch", response_model=Dict[str, Any])
async def submit_batch_analysis(
    request: BatchAnalysisRequest,
    user: dict = Depends(get_current_user)
):
    """
    提交批量分析任务（真正的并发执行）- 支持 AB 测试

    通过 request.parameters.engine 参数选择引擎:
    - legacy (默认): 使用旧引擎 TradingAgentsGraph
    - unified: 使用新的统一引擎 WorkflowEngine

    ⚠️ 注意：不使用 BackgroundTasks，因为它是串行执行的！
    改用 asyncio.create_task 实现真正的并发执行。
    """
    try:
        logger.info(f"🎯 [批量分析] 收到批量分析请求: title={request.title}")

        # 判断使用哪个引擎
        engine_type = AnalysisEngine.LEGACY
        if request.parameters and hasattr(request.parameters, "engine"):
            engine_type = request.parameters.engine

        logger.info(f"🔧 [AB测试-批量] 使用引擎: {engine_type.value}")

        simple_service = get_simple_analysis_service()
        unified_service = get_unified_analysis_service()
        batch_id = str(uuid.uuid4())
        task_ids: List[str] = []
        mapping: List[Dict[str, str]] = []

        # 获取股票代码列表 (兼容旧字段)
        stock_symbols = request.get_symbols()
        logger.info(f"📊 [批量分析] 股票代码列表: {stock_symbols}")

        # 验证股票代码列表
        if not stock_symbols:
            raise ValueError("股票代码列表不能为空")

        # 🔧 限制批量分析的股票数量（最多10个）
        MAX_BATCH_SIZE = 10
        if len(stock_symbols) > MAX_BATCH_SIZE:
            raise ValueError(f"批量分析最多支持 {MAX_BATCH_SIZE} 个股票，当前提交了 {len(stock_symbols)} 个")

        # 为每只股票创建单股分析任务
        for i, symbol in enumerate(stock_symbols):
            logger.info(f"📝 [批量分析] 正在创建第 {i+1}/{len(stock_symbols)} 个任务: {symbol}")

            single_req = SingleAnalysisRequest(
                symbol=symbol,
                stock_code=symbol,  # 兼容字段
                parameters=request.parameters
            )

            try:
                if engine_type == AnalysisEngine.V2:
                    # v2 引擎：使用统一任务服务
                    from app.services.task_analysis_service import get_task_analysis_service
                    from app.models.analysis import AnalysisTaskType
                    from app.models.user import PyObjectId

                    task_service = get_task_analysis_service()

                    # 🔥 修复：准备任务参数，确保包含必需的 market_type
                    # 根据股票代码自动识别市场类型
                    market_type = get_market_type_from_symbol(symbol)
                    logger.info(f"📊 [批量分析] 股票 {symbol} 识别为市场: {market_type}")

                    task_params = {
                        "symbol": symbol,
                        "stock_code": symbol,
                        "market_type": market_type,  # 🔑 根据股票代码自动识别市场类型
                    }

                    # 将 request.parameters 的所有字段合并到 task_params
                    if request.parameters:
                        params_dict = request.parameters.model_dump()
                        # 移除 engine 字段（这是路由层使用的，不是任务参数）
                        params_dict.pop("engine", None)
                        task_params.update(params_dict)

                    # 如果用户在 parameters 中指定了 market_type，优先使用用户指定的
                    if request.parameters and hasattr(request.parameters, 'market_type') and request.parameters.market_type:
                        task_params["market_type"] = request.parameters.market_type
                        logger.info(f"📊 [批量分析] 使用用户指定的市场类型: {request.parameters.market_type}")

                    # 🔥 从用户偏好读取风险偏好设置
                    preference_type = await get_user_risk_preference(user["id"])
                    logger.info(f"📊 [批量分析] 使用用户风险偏好: {preference_type}")

                    task = await task_service.create_task(
                        user_id=PyObjectId(user["id"]),
                        task_type=AnalysisTaskType.STOCK_ANALYSIS,
                        task_params=task_params,
                        engine_type="auto",
                        preference_type=preference_type  # 🔥 使用用户偏好设置
                    )
                    task_id = task.task_id  # 使用 UUID task_id，不是 ObjectId
                else:
                    # legacy/unified 引擎：使用旧服务
                    create_res = await simple_service.create_analysis_task(user["id"], single_req)
                    task_id = create_res.get("task_id")
                    if not task_id:
                        raise RuntimeError(f"创建任务失败：未返回task_id (symbol={symbol})")

                task_ids.append(task_id)
                mapping.append({"symbol": symbol, "stock_code": symbol, "task_id": task_id})
                logger.info(f"✅ [批量分析] 已创建任务: {task_id} - {symbol}")
            except Exception as create_error:
                logger.error(f"❌ [批量分析] 创建任务失败: {symbol}, 错误: {create_error}", exc_info=True)
                raise

        # 🔧 使用队列系统统一管理任务，自动控制并发
        # 不再使用 asyncio.create_task 直接并发，而是通过队列由 Worker 消费
        from app.services.queue_service import get_queue_service
        queue_service = get_queue_service()

        # 为每个任务准备队列参数
        for i, symbol in enumerate(stock_symbols):
            task_id = task_ids[i]
            
            # 准备队列参数
            queue_params = {
                "task_id": task_id,
                "symbol": symbol,
                "stock_code": symbol,
                "user_id": user["id"],
                "batch_id": batch_id,
                "engine": engine_type.value,  # 记录引擎类型，Worker 需要知道
            }
            
            # 添加分析参数
            if request.parameters:
                params_dict = request.parameters.model_dump()
                # 移除 engine 字段（已在 queue_params 中）
                params_dict.pop("engine", None)
                queue_params.update(params_dict)
            
            try:
                # 提交任务到队列（会自动检查并发限制）
                # 使用已有的 task_id，而不是让队列生成新的
                await queue_service.enqueue_task(
                    user_id=user["id"],
                    symbol=symbol,
                    params=queue_params,
                    batch_id=batch_id,
                    task_id=task_id  # 使用已创建的任务ID
                )
                logger.info(f"✅ [批量分析] 任务已入队: {task_id} - {symbol} (引擎: {engine_type.value})")
            except ValueError as e:
                # 并发限制错误
                logger.warning(f"⚠️ [批量分析] 任务入队失败（并发限制）: {task_id} - {symbol}, 错误: {e}")
                # 继续处理其他任务，失败的会留在队列中等待
            except Exception as e:
                logger.error(f"❌ [批量分析] 任务入队失败: {task_id} - {symbol}, 错误: {e}", exc_info=True)
        
        logger.info(f"🚀 [批量分析] 已提交 {len(task_ids)} 个任务到队列 (引擎: {engine_type.value})")

        return {
            "success": True,
            "data": {
                "batch_id": batch_id,
                "total_tasks": len(task_ids),
                "task_ids": task_ids,
                "mapping": mapping,
                "status": "submitted",
                "engine": engine_type.value
            },
            "message": f"批量分析任务已提交到队列，共{len(task_ids)}个股票，Worker将按并发限制自动执行 (引擎: {engine_type.value})"
        }
    except Exception as e:
        logger.error(f"❌ [批量分析] 提交失败: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))

# 兼容性：保留原有端点
@router.post("/analyze")
async def analyze_single(
    req: SingleAnalyzeRequest,
    user: dict = Depends(get_current_user),
    svc: QueueService = Depends(get_queue_service)
):
    """单股分析（兼容性端点）"""
    try:
        task_id = await svc.enqueue_task(
            user_id=user["id"],
            symbol=req.symbol,
            params=req.parameters
        )
        return {"task_id": task_id, "status": "queued"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/analyze/batch")
async def analyze_batch(
    req: BatchAnalyzeRequest,
    user: dict = Depends(get_current_user),
    svc: QueueService = Depends(get_queue_service)
):
    """批量分析（兼容性端点）"""
    try:
        batch_id, submitted = await svc.create_batch(
            user_id=user["id"],
            symbols=req.symbols,
            params=req.parameters
        )
        return {"batch_id": batch_id, "submitted": submitted}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/batches/{batch_id}")
async def get_batch(batch_id: str, user: dict = Depends(get_current_user), svc: QueueService = Depends(get_queue_service)):
    b = await svc.get_batch(batch_id)
    if not b or b.get("user") != user["id"]:
        raise HTTPException(status_code=404, detail="batch not found")
    return b

# 任务和批次查询端点
# 注意：这个路由被移到了 /tasks/{task_id}/status 之后，避免路由冲突
# @router.get("/tasks/{task_id}")
# async def get_task(
#     task_id: str,
#     user: dict = Depends(get_current_user),
#     svc: QueueService = Depends(get_queue_service)
# ):
#     """获取任务详情"""
#     t = await svc.get_task(task_id)
#     if not t or t.get("user") != user["id"]:
#         raise HTTPException(status_code=404, detail="任务不存在")
#     return t

# 原有的路由已被新的异步实现替代
# @router.get("/tasks/{task_id}/status")
# async def get_task_status_old(
#     task_id: str,
#     user: dict = Depends(get_current_user)
# ):
#     """获取任务状态和进度（旧版实现）"""
#     try:
#         status = await get_analysis_service().get_task_status(task_id)
#         if not status:
#             raise HTTPException(status_code=404, detail="任务不存在")
#         return {
#             "success": True,
#             "data": status
#         }
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))

@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    user: dict = Depends(get_current_user),
    svc: QueueService = Depends(get_queue_service)
):
    """取消任务"""
    try:
        # 验证任务所有权
        task = await svc.get_task(task_id)
        if not task or task.get("user") != user["id"]:
            raise HTTPException(status_code=404, detail="任务不存在")

        success = await svc.cancel_task(task_id)
        if success:
            return {"success": True, "message": "任务已取消"}
        else:
            raise HTTPException(status_code=400, detail="取消任务失败")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/user/queue-status")
async def get_user_queue_status(
    user: dict = Depends(get_current_user),
    svc: QueueService = Depends(get_queue_service)
):
    """获取用户队列状态"""
    try:
        status = await svc.get_user_queue_status(user["id"])
        return {
            "success": True,
            "data": status
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/user/history")
async def get_user_analysis_history(
    user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None, description="任务状态过滤"),
    start_date: Optional[str] = Query(None, description="开始日期，YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，YYYY-MM-DD"),
    symbol: Optional[str] = Query(None, description="股票代码"),
    stock_code: Optional[str] = Query(None, description="股票代码(已废弃,使用symbol)"),
    market_type: Optional[str] = Query(None, description="市场类型"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小")
):
    """获取用户分析历史（支持基础筛选与分页）"""
    try:
        # 先获取用户任务列表（内存优先，MongoDB兜底）
        raw_tasks = await get_simple_analysis_service().list_user_tasks(
            user_id=user["id"],
            status=status,
            limit=page_size,
            offset=(page - 1) * page_size
        )

        # 进行基础筛选
        from datetime import datetime
        def in_date_range(t: Optional[str]) -> bool:
            if not t:
                return True
            try:
                dt = datetime.fromisoformat(t.replace('Z', '+00:00')) if 'Z' in t else datetime.fromisoformat(t)
            except Exception:
                return True
            ok = True
            if start_date:
                try:
                    ok = ok and (dt.date() >= datetime.fromisoformat(start_date).date())
                except Exception:
                    pass
            if end_date:
                try:
                    ok = ok and (dt.date() <= datetime.fromisoformat(end_date).date())
                except Exception:
                    pass
            return ok

        # 获取查询的股票代码 (兼容旧字段)
        query_symbol = symbol or stock_code

        filtered = []
        for x in raw_tasks:
            if query_symbol:
                task_symbol = x.get("symbol") or x.get("stock_code") or x.get("stock_symbol")
                if task_symbol not in [query_symbol]:
                    continue
            # 市场类型暂时从参数内判断（如有）
            if market_type:
                params = x.get("parameters") or {}
                if params.get("market_type") != market_type:
                    continue
            # 时间范围（使用 start_time 或 created_at）
            t = x.get("start_time") or x.get("created_at")
            if not in_date_range(t):
                continue
            filtered.append(x)

        return {
            "success": True,
            "data": {
                "tasks": filtered,
                "total": len(filtered),
                "page": page,
                "page_size": page_size
            },
            "message": "历史查询成功"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# WebSocket 端点
@router.websocket("/ws/task/{task_id}")
async def websocket_task_progress(websocket: WebSocket, task_id: str):
    """WebSocket 端点：实时获取任务进度"""
    import json
    websocket_manager = get_websocket_manager()

    try:
        await websocket_manager.connect(websocket, task_id)

        # 发送连接确认消息
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "task_id": task_id,
            "message": "WebSocket 连接已建立"
        }))

        # 保持连接活跃
        while True:
            try:
                # 接收客户端的心跳消息
                data = await websocket.receive_text()
                # 可以处理客户端发送的消息
                logger.debug(f"📡 收到 WebSocket 消息: {data}")
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning(f"⚠️ WebSocket 消息处理错误: {e}")
                break

    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket 客户端断开连接: {task_id}")
    except Exception as e:
        logger.error(f"❌ WebSocket 连接错误: {e}")
    finally:
        await websocket_manager.disconnect(websocket, task_id)

# 任务详情查询路由（放在最后避免与 /tasks/{task_id}/status 冲突）
@router.get("/tasks/{task_id}/details")
async def get_task_details(
    task_id: str,
    user: dict = Depends(get_current_user),
    svc: QueueService = Depends(get_queue_service)
):
    """获取任务详情（使用不同的路径避免冲突）"""
    t = await svc.get_task(task_id)
    if not t or t.get("user") != user["id"]:
        raise HTTPException(status_code=404, detail="任务不存在")
    return t


# ==================== 僵尸任务管理 ====================

@router.get("/admin/zombie-tasks")
async def get_zombie_tasks(
    max_running_hours: int = Query(default=2, ge=1, le=72, description="最大运行时长（小时）"),
    user: dict = Depends(get_current_user)
):
    """获取僵尸任务列表（仅管理员）

    僵尸任务：长时间处于 processing/running/pending 状态的任务
    """
    # 检查管理员权限
    if user.get("username") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    try:
        svc = get_simple_analysis_service()
        zombie_tasks = await svc.get_zombie_tasks(max_running_hours)

        return {
            "success": True,
            "data": zombie_tasks,
            "total": len(zombie_tasks),
            "max_running_hours": max_running_hours
        }
    except Exception as e:
        logger.error(f"❌ 获取僵尸任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取僵尸任务失败: {str(e)}")


@router.post("/admin/cleanup-zombie-tasks")
async def cleanup_zombie_tasks(
    max_running_hours: int = Query(default=2, ge=1, le=72, description="最大运行时长（小时）"),
    user: dict = Depends(get_current_user)
):
    """清理僵尸任务（仅管理员）

    将长时间处于 processing/running/pending 状态的任务标记为失败
    """
    # 检查管理员权限
    if user.get("username") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    try:
        svc = get_simple_analysis_service()
        result = await svc.cleanup_zombie_tasks(max_running_hours)

        return {
            "success": True,
            "data": result,
            "message": f"已清理 {result.get('total_cleaned', 0)} 个僵尸任务"
        }
    except Exception as e:
        logger.error(f"❌ 清理僵尸任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理僵尸任务失败: {str(e)}")


@router.post("/tasks/{task_id}/mark-failed")
async def mark_task_as_failed(
    task_id: str,
    user: dict = Depends(get_current_user)
):
    """将指定任务标记为失败

    用于手动清理卡住的任务
    """
    try:
        svc = get_simple_analysis_service()

        # 更新内存中的任务状态
        from app.services.memory_state_manager import TaskStatus
        await svc.memory_manager.update_task_status(
            task_id=task_id,
            status=TaskStatus.FAILED,
            message="手动标记为失败",
            error_message="用户手动标记为失败"
        )

        # 更新 MongoDB 中的任务状态
        from app.core.database import get_mongo_db
        from datetime import datetime
        db = get_mongo_db()

        result = await db.analysis_tasks.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    "status": "failed",
                    "last_error": "用户手动标记为失败",
                    "completed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if result.modified_count > 0:
            logger.info(f"✅ 任务 {task_id} 已标记为失败")
            return {
                "success": True,
                "message": "任务已标记为失败"
            }
        else:
            logger.warning(f"⚠️ 任务 {task_id} 未找到或已是失败状态")
            return {
                "success": True,
                "message": "任务未找到或已是失败状态"
            }
    except Exception as e:
        logger.error(f"❌ 标记任务失败: {task_id} - {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"标记任务失败: {str(e)}"
        )


@router.post("/tasks/{task_id}/retry")
async def retry_task(
    task_id: str,
    user: dict = Depends(get_current_user)
):
    """重新创建失败的分析任务

    使用相同的参数重新创建任务，用于复现问题或验证修复。
    
    Returns:
        {
            "success": True,
            "task_id": "新任务的ID",
            "message": "任务已重新创建"
        }
    """
    try:
        from app.core.database import get_mongo_db
        from bson import ObjectId
        from app.services.task_analysis_service import get_task_analysis_service
        from app.models.analysis import AnalysisTaskType
        from app.models.user import PyObjectId
        
        db = get_mongo_db()
        
        # 查找失败的任务
        failed_task = await db.unified_analysis_tasks.find_one({
            "task_id": task_id,
            "user_id": ObjectId(user["id"])
        })
        
        if not failed_task:
            # 尝试从旧的任务集合查找
            old_task = await db.analysis_tasks.find_one({
                "task_id": task_id,
                "user_id": ObjectId(user["id"])
            })
            if not old_task:
                raise HTTPException(
                    status_code=404,
                    detail="任务不存在或不属于当前用户"
                )
            
            # 旧任务格式：需要转换为新格式
            logger.info(f"🔄 [重试任务] 找到旧格式任务: {task_id}")
            
            # 从旧任务中提取参数
            task_params = old_task.get("parameters", {})
            symbol = task_params.get("symbol") or task_params.get("stock_code") or old_task.get("stock_code")
            market_type = task_params.get("market_type") or old_task.get("market_type", "cn")
            
            if not symbol:
                raise HTTPException(
                    status_code=400,
                    detail="无法从旧任务中提取股票代码"
                )
            
            # 🔥 从用户偏好读取风险偏好设置
            preference_type = await get_user_risk_preference(user["id"])
            logger.info(f"📊 [重试任务] 使用用户风险偏好: {preference_type}")

            # 创建新任务
            task_service = get_task_analysis_service()
            new_task = await task_service.create_task(
                user_id=PyObjectId(user["id"]),
                task_type=AnalysisTaskType.STOCK_ANALYSIS,
                task_params={
                    "symbol": symbol,
                    "stock_code": symbol,
                    "market_type": market_type,
                    **task_params  # 合并其他参数
                },
                engine_type="auto",
                preference_type=preference_type  # 🔥 使用用户偏好设置
            )
            
            logger.info(f"✅ [重试任务] 旧格式任务已重新创建: {task_id} -> {new_task.task_id}")
            
            # 🔑 关键：将任务加入队列执行
            from app.services.queue_service import get_queue_service
            queue_service = get_queue_service()
            
            # 准备队列参数
            queue_params = {
                "engine": "v2",  # 使用v2引擎
                "symbol": symbol,
                "stock_code": symbol,
                "market_type": market_type,
                **task_params  # 合并其他参数
            }
            
            try:
                await queue_service.enqueue_task(
                    user_id=user["id"],
                    symbol=symbol,
                    params=queue_params,
                    task_id=new_task.task_id  # 使用已创建的任务ID
                )
                logger.info(f"✅ [重试任务] 旧格式任务已加入队列: {new_task.task_id}")
            except Exception as e:
                logger.error(f"⚠️ [重试任务] 旧格式任务加入队列失败: {new_task.task_id} - {e}", exc_info=True)
                # 即使入队失败，也返回成功（任务已创建，可以手动触发）
            
            return {
                "success": True,
                "task_id": new_task.task_id,
                "message": "任务已重新创建并加入队列"
            }
        
        # 检查任务状态
        task_status = failed_task.get("status")
        if isinstance(task_status, str):
            status_str = task_status
        elif hasattr(task_status, "value"):
            status_str = task_status.value
        else:
            status_str = str(task_status)
        
        if status_str not in ["failed", "cancelled"]:
            raise HTTPException(
                status_code=400,
                detail=f"只能重新创建失败或已取消的任务，当前状态: {status_str}"
            )
        
        # 获取任务参数
        task_params = failed_task.get("task_params", {})
        task_type_str = failed_task.get("task_type")
        
        # 转换 task_type
        if isinstance(task_type_str, str):
            try:
                task_type = AnalysisTaskType(task_type_str)
            except ValueError:
                # 默认使用股票分析
                task_type = AnalysisTaskType.STOCK_ANALYSIS
                logger.warning(f"⚠️ [重试任务] 未知的任务类型: {task_type_str}，使用默认类型: STOCK_ANALYSIS")
        else:
            task_type = AnalysisTaskType.STOCK_ANALYSIS
        
        # 确保必要的参数存在
        symbol = task_params.get("symbol") or task_params.get("stock_code")
        if not symbol:
            raise HTTPException(
                status_code=400,
                detail="任务参数中缺少股票代码"
            )
        
        # 🔥 从用户偏好读取风险偏好设置
        preference_type = await get_user_risk_preference(user["id"])
        logger.info(f"📊 [重试任务] 使用用户风险偏好: {preference_type}")

        # 创建新任务（使用相同的参数）
        task_service = get_task_analysis_service()
        new_task = await task_service.create_task(
            user_id=PyObjectId(user["id"]),
            task_type=task_type,
            task_params=task_params,  # 使用原始参数
            engine_type="auto",
            preference_type=preference_type  # 🔥 使用用户偏好设置
        )
        
        logger.info(f"✅ [重试任务] 任务已重新创建: {task_id} -> {new_task.task_id}")
        
        # 🔑 关键：将任务加入队列执行
        from app.services.queue_service import get_queue_service
        queue_service = get_queue_service()
        
        # 准备队列参数
        symbol = task_params.get("symbol") or task_params.get("stock_code")
        queue_params = {
            "engine": "v2",  # 使用v2引擎
            **task_params  # 合并所有任务参数
        }
        
        try:
            await queue_service.enqueue_task(
                user_id=user["id"],
                symbol=symbol,
                params=queue_params,
                task_id=new_task.task_id  # 使用已创建的任务ID
            )
            logger.info(f"✅ [重试任务] 任务已加入队列: {new_task.task_id}")
        except Exception as e:
            logger.error(f"⚠️ [重试任务] 任务加入队列失败: {new_task.task_id} - {e}", exc_info=True)
            # 即使入队失败，也返回成功（任务已创建，可以手动触发）
        
        return {
            "success": True,
            "task_id": new_task.task_id,
            "message": "任务已重新创建并加入队列"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [重试任务] 重新创建任务失败: {task_id} - {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"重新创建任务失败: {str(e)}"
        )
    except Exception as e:
        logger.error(f"❌ 标记任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"标记任务失败: {str(e)}")


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    user: dict = Depends(get_current_user)
):
    """删除指定任务

    从内存和数据库中删除任务记录
    """
    try:
        svc = get_simple_analysis_service()

        # 从内存中删除任务
        await svc.memory_manager.remove_task(task_id)

        # 从 MongoDB 中删除任务
        from app.core.database import get_mongo_db
        db = get_mongo_db()

        result = await db.analysis_tasks.delete_one({"task_id": task_id})

        if result.deleted_count > 0:
            logger.info(f"✅ 任务 {task_id} 已删除")
            return {
                "success": True,
                "message": "任务已删除"
            }
        else:
            logger.warning(f"⚠️ 任务 {task_id} 未找到")
            return {
                "success": True,
                "message": "任务未找到"
            }
    except Exception as e:
        logger.error(f"❌ 删除任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除任务失败: {str(e)}")
