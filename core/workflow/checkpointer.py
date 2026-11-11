"""工作流 MongoDB 断点续跑 checkpointer（v4.0 第一波 T1）

设计要点（docs/05-design/v4.0/v4.0-master-plan.md §5.1）：
- workflow.compile() 挂 MongoDBSaver，thread_id = 分析运行 task_id
- 进程中断后可从最后完成的节点恢复，MongoDB 可查执行轨迹
- 降级铁律：Mongo 不可用 / 包缺失时返回 None，编译裸图，分析流程不受影响
- 连接复用 app.core.database 的统一同步客户端（不自建 MongoClient）

checkpoint 数据落主库（settings.MONGO_DB），集合名用 langgraph 默认
（checkpoints / checkpoint_writes），与业务集合天然隔离。
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_checkpointer: Optional[Any] = None
_init_attempted = False


def get_workflow_checkpointer() -> Optional[Any]:
    """获取全局 MongoDBSaver（懒加载 + 失败降级）

    Returns:
        MongoDBSaver 实例；不可用时返回 None（调用方裸编译，不阻断分析）
    """
    global _checkpointer, _init_attempted
    if _init_attempted:
        return _checkpointer
    _init_attempted = True
    try:
        from langgraph.checkpoint.mongodb import MongoDBSaver  # langgraph-checkpoint-mongodb
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

        from app.core.database import get_mongo_db_sync

        db = get_mongo_db_sync()
        # 工作流状态里带有自定义 AgentContext 对象，需显式登记才可反序列化。
        # 不登记时当前版本只告警放行，未来版本（严格模式）会阻断，导致断点恢复失败。
        serde = JsonPlusSerializer(
            allowed_msgpack_modules=[
                ("tradingagents.agents.utils.agent_context", "AgentContext"),
            ]
        )
        _checkpointer = MongoDBSaver(db.client, db_name=db.name, serde=serde)
        logger.info(f"[checkpointer] MongoDBSaver 就绪: db={db.name}")
    except Exception as e:
        _checkpointer = None
        logger.warning(
            f"[checkpointer] 初始化失败，本次进程断点续跑不可用（分析不受影响）: {e}"
        )
    return _checkpointer


def build_thread_config(task_id: str) -> dict:
    """构造 LangGraph thread 配置（thread_id = 分析运行 ID）"""
    return {"configurable": {"thread_id": task_id}}


def list_checkpoints(task_id: str, limit: int = 500) -> list[dict]:
    """读取某分析运行的执行轨迹（按时间正序，供可观测性 API 使用）

    每个 checkpoint 代表一个 superstep 完成后的快照。节点名来自
    `checkpoint_writes.task_path`（格式 `~__pregel_pull, <node_name>`），
    写入归属上一个 checkpoint，因此第 i 步的节点取第 i-1 个 checkpoint 的写入。

    Args:
        task_id: 分析运行 ID（thread_id）
        limit: 最多读取的 checkpoint 数（按最新优先截断）

    Returns:
        轨迹列表，每项含 step / timestamp / elapsed_seconds / nodes / source / updated_channels；
        checkpointer 不可用或无轨迹时返回空列表
    """
    cp = get_workflow_checkpointer()
    if cp is None or not task_id:
        return []

    try:
        tuples = list(cp.list(build_thread_config(task_id), limit=limit))
    except Exception as e:
        logger.warning(f"[checkpointer] 读取轨迹失败 task_id={task_id}: {e}")
        return []
    if not tuples:
        return []

    # 最新在前 → 反转成正序
    tuples.reverse()

    # 节点归属：同一 checkpoint_id 下可能有多条写入（并行分支/join）
    writes_by_cp: dict[str, list[str]] = {}
    try:
        from app.core.database import get_mongo_db_sync

        db = get_mongo_db_sync()
        cursor = db.checkpoint_writes.find(
            {"thread_id": task_id}, {"checkpoint_id": 1, "task_path": 1}
        )
        for w in cursor:
            path = w.get("task_path") or ""
            node = path.rsplit(",", 1)[-1].strip()
            if not node or node.startswith("__"):
                continue
            writes_by_cp.setdefault(w.get("checkpoint_id"), [])
            if node not in writes_by_cp[w.get("checkpoint_id")]:
                writes_by_cp[w.get("checkpoint_id")].append(node)
    except Exception as e:
        logger.warning(f"[checkpointer] 读取节点归属失败 task_id={task_id}: {e}")

    from datetime import datetime

    steps: list[dict] = []
    prev_ts: Optional[datetime] = None
    prev_id: Optional[str] = None

    for idx, t in enumerate(tuples):
        configurable = (t.config or {}).get("configurable", {})
        checkpoint_id = configurable.get("checkpoint_id")
        ts_raw = (t.checkpoint or {}).get("ts")
        try:
            ts = datetime.fromisoformat(ts_raw) if isinstance(ts_raw, str) else None
        except ValueError:
            ts = None

        steps.append({
            "step": (t.metadata or {}).get("step", idx),
            "checkpoint_id": checkpoint_id,
            "timestamp": ts.isoformat() if ts else None,
            "elapsed_seconds": (
                round((ts - prev_ts).total_seconds(), 2) if ts and prev_ts else None
            ),
            "source": (t.metadata or {}).get("source"),
            "nodes": writes_by_cp.get(prev_id, []) if prev_id else [],
            "updated_channels": list((t.checkpoint or {}).get("updated_channels") or []),
        })
        prev_ts = ts or prev_ts
        prev_id = checkpoint_id

    return steps


def has_checkpoint(task_id: str) -> bool:
    """检查某分析运行是否存在断点（用于 resume 入口校验）

    checkpointer 不可用或无断点时返回 False，调用方应回退为全新执行。
    """
    cp = get_workflow_checkpointer()
    if cp is None or not task_id:
        return False
    try:
        config = build_thread_config(task_id)
        # get_tuple 返回最新 checkpoint；None 表示该 thread 无断点
        return cp.get_tuple(config) is not None
    except Exception as e:
        logger.warning(f"[checkpointer] 查询断点失败 task_id={task_id}: {e}")
        return False
