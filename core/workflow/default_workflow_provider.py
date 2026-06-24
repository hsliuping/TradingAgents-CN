"""
默认工作流提供者

管理系统默认工作流和活动工作流的加载
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from .models import WorkflowDefinition
from .templates import v2_stock_analysis_workflow as v2_stock_analysis_workflow_module
from .templates.default_workflow import DEFAULT_WORKFLOW
from .templates.simple_workflow import SIMPLE_WORKFLOW
from .templates.trade_review_workflow import TRADE_REVIEW_WORKFLOW
from .templates.trade_review_workflow_v2 import TRADE_REVIEW_WORKFLOW_V2
from .templates.position_analysis_workflow import POSITION_ANALYSIS_WORKFLOW
from .templates.position_analysis_workflow_v2 import POSITION_ANALYSIS_WORKFLOW_V2
from .templates.v2_stock_analysis_workflow import V2_STOCK_ANALYSIS_WORKFLOW
from .templates.v2_etf_analysis_workflow import V2_ETF_ANALYSIS_WORKFLOW

logger = logging.getLogger(__name__)

# 系统默认工作流 ID
SYSTEM_DEFAULT_WORKFLOW_ID = "default_analysis"
SYSTEM_SIMPLE_WORKFLOW_ID = "simple_analysis"
SYSTEM_TRADE_REVIEW_WORKFLOW_ID = "trade_review"
SYSTEM_POSITION_ANALYSIS_WORKFLOW_ID = "position_analysis"
SYSTEM_TRADE_REVIEW_WORKFLOW_V2_ID = "trade_review_v2"
SYSTEM_POSITION_ANALYSIS_WORKFLOW_V2_ID = "position_analysis_v2"
SYSTEM_V2_STOCK_ANALYSIS_WORKFLOW_ID = "v2_stock_analysis"
SYSTEM_V2_ETF_ANALYSIS_WORKFLOW_ID = "v2_etf_analysis"


class DefaultWorkflowProvider:
    """
    默认工作流提供者

    职责：
    1. 提供系统预置的默认工作流
    2. 确保默认工作流存在于数据库
    3. 获取当前活动工作流
    """

    # 系统预置工作流
    SYSTEM_WORKFLOWS = {
        SYSTEM_DEFAULT_WORKFLOW_ID: DEFAULT_WORKFLOW,
        SYSTEM_SIMPLE_WORKFLOW_ID: SIMPLE_WORKFLOW,
        SYSTEM_TRADE_REVIEW_WORKFLOW_ID: TRADE_REVIEW_WORKFLOW,
        SYSTEM_POSITION_ANALYSIS_WORKFLOW_ID: POSITION_ANALYSIS_WORKFLOW,
        SYSTEM_TRADE_REVIEW_WORKFLOW_V2_ID: TRADE_REVIEW_WORKFLOW_V2,
        SYSTEM_POSITION_ANALYSIS_WORKFLOW_V2_ID: POSITION_ANALYSIS_WORKFLOW_V2,
        SYSTEM_V2_STOCK_ANALYSIS_WORKFLOW_ID: V2_STOCK_ANALYSIS_WORKFLOW,
        SYSTEM_V2_ETF_ANALYSIS_WORKFLOW_ID: V2_ETF_ANALYSIS_WORKFLOW,
    }

    def __init__(self):
        self._db = None
        self._active_workflow_id: Optional[str] = None

    def _get_db(self):
        """获取数据库连接（懒加载）"""
        if self._db is None:
            try:
                import os
                from pymongo import MongoClient

                # 优先使用环境变量中的连接字符串
                # ⚠️ 安全警告：不再使用硬编码凭证作为默认值
                mongo_uri = os.getenv("MONGODB_CONNECTION_STRING")
                
                if not mongo_uri:
                    raise ValueError(
                        "必须设置环境变量 MONGODB_CONNECTION_STRING。"
                        "示例: mongodb://user:password@host:port/database?authSource=admin"
                    )
                
                db_name = os.getenv("MONGODB_DATABASE_NAME", "tradingagents")

                client = MongoClient(mongo_uri)
                self._db = client[db_name]
                logger.info(f"✅ DefaultWorkflowProvider 数据库连接成功: {db_name}")
            except Exception as e:
                logger.warning(f"无法连接数据库: {e}")
                self._db = None
        return self._db

    def get_default_workflow(self) -> WorkflowDefinition:
        """获取系统默认工作流"""
        return DEFAULT_WORKFLOW

    def get_simple_workflow(self) -> WorkflowDefinition:
        """获取简单工作流"""
        return SIMPLE_WORKFLOW

    def get_system_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """获取系统预置工作流"""
        return self.SYSTEM_WORKFLOWS.get(workflow_id)

    def _build_system_workflow_doc(
        self,
        workflow: WorkflowDefinition,
        created_at: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """构造用于持久化的系统工作流文档。"""
        timestamp = datetime.utcnow().isoformat()
        doc = workflow.to_dict()
        doc["created_at"] = self._stringify_timestamp(created_at) or timestamp
        doc["updated_at"] = timestamp
        doc["created_by"] = "system"
        doc["is_system"] = True
        return doc

    def _normalize_workflow_doc_for_compare(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """移除运行时字段，便于比较代码定义和数据库副本是否一致。"""
        normalized = dict(doc)
        for key in ("_id", "created_at", "updated_at"):
            normalized.pop(key, None)
        return normalized

    def _stringify_timestamp(self, value: Optional[Any]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    def _log_workflow_diagnostics(
        self,
        workflow: WorkflowDefinition,
        source: str,
        source_path: Optional[str] = None,
    ) -> None:
        """记录工作流来源和关键边，便于排查是否加载到预期版本。"""
        nodes = [node.id for node in workflow.nodes]
        edges = [f"{edge.id}:{edge.source}->{edge.target}" for edge in workflow.edges]
        logger.info(f"📋 [工作流加载] 来源: {source}")
        if source_path:
            logger.info(f"📋 [工作流加载] 来源文件: {source_path}")
        logger.info(f"📋 [工作流加载] 节点列表: {nodes}")
        logger.info(f"📋 [工作流加载] 边列表: {edges}")

        critical_edge_ids = ("e_to_risk_debate", "e_risk_judge", "e_trader", "e_end")
        critical_edges = {
            edge.id: (edge.source, edge.target)
            for edge in workflow.edges
            if edge.id in critical_edge_ids
        }
        if critical_edges:
            logger.info(f"📋 [工作流加载] 关键边: {critical_edges}")

    def is_system_workflow(self, workflow_id: str) -> bool:
        """检查是否为系统预置工作流"""
        return workflow_id in self.SYSTEM_WORKFLOWS

    def get_active_workflow_id(self) -> str:
        """
        获取当前活动工作流 ID

        优先级：
        1. config/settings.json 中的 default_workflow_id（前端设置）
        2. 数据库中的 system_configs.active_workflow_id
        3. 系统默认工作流
        """
        if self._active_workflow_id:
            return self._active_workflow_id

        # 🆕 优先从 config/settings.json 读取（前端"设为默认"功能）
        try:
            import json
            from pathlib import Path

            config_path = Path("config/settings.json")
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if config.get("default_workflow_id"):
                        self._active_workflow_id = config["default_workflow_id"]
                        logger.info(f"从配置文件获取活动工作流: {self._active_workflow_id} ({config.get('default_workflow_name', '')})")
                        return self._active_workflow_id
        except Exception as e:
            logger.warning(f"从配置文件获取活动工作流失败: {e}")

        # 从数据库获取
        db = self._get_db()
        if db is not None:
            try:
                config = db.system_configs.find_one(
                    {"is_active": True},
                    sort=[("version", -1)]
                )
                if config and config.get("active_workflow_id"):
                    self._active_workflow_id = config["active_workflow_id"]
                    logger.info(f"从数据库获取活动工作流: {self._active_workflow_id}")
                    return self._active_workflow_id
            except Exception as e:
                logger.warning(f"从数据库获取活动工作流失败: {e}")

        # 默认使用系统默认工作流
        self._active_workflow_id = SYSTEM_DEFAULT_WORKFLOW_ID
        logger.info(f"使用系统默认工作流: {self._active_workflow_id}")
        return self._active_workflow_id

    def set_active_workflow_id(self, workflow_id: str, workflow_name: str = "") -> bool:
        """设置活动工作流 ID"""
        success = True

        # 🆕 同时更新配置文件（与前端"设为默认"功能保持一致）
        try:
            import json
            from pathlib import Path

            config_path = Path("config/settings.json")
            config = {}
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)

            config["default_workflow_id"] = workflow_id
            if workflow_name:
                config["default_workflow_name"] = workflow_name

            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            logger.info(f"已更新配置文件: {workflow_id} ({workflow_name})")
        except Exception as e:
            logger.warning(f"更新配置文件失败: {e}")
            success = False

        # 更新数据库
        db = self._get_db()
        if db is not None:
            try:
                db.system_configs.update_one(
                    {"is_active": True},
                    {
                        "$set": {
                            "active_workflow_id": workflow_id,
                            "updated_at": datetime.utcnow()
                        }
                    },
                    upsert=True
                )
                logger.info(f"已更新数据库: {workflow_id}")
            except Exception as e:
                logger.warning(f"更新数据库失败: {e}")
                success = False
        else:
            logger.warning("无法更新数据库: 连接失败")

        if success:
            self._active_workflow_id = workflow_id
            logger.info(f"已设置活动工作流: {workflow_id}")

        return success

    def load_workflow(self, workflow_id: Optional[str] = None) -> WorkflowDefinition:
        """
        加载工作流

        Args:
            workflow_id: 工作流 ID，None 则加载活动工作流

        Returns:
            WorkflowDefinition
        """
        import json
        from pathlib import Path

        # 如果未指定，使用活动工作流
        if workflow_id is None:
            workflow_id = self.get_active_workflow_id()

        logger.info(f"📋 [工作流加载] 开始加载工作流: {workflow_id}")

        # 检查是否为系统预置工作流
        if self.is_system_workflow(workflow_id):
            workflow = self.SYSTEM_WORKFLOWS[workflow_id]
            logger.info(f"✅ [工作流加载] 使用系统预置工作流: {workflow_id} - {workflow.name}")
            source_path = None
            if workflow_id == SYSTEM_V2_STOCK_ANALYSIS_WORKFLOW_ID:
                source_path = getattr(v2_stock_analysis_workflow_module, "__file__", None)
            self._log_workflow_diagnostics(workflow, "system_preset", source_path)
            return workflow

        # 1. 优先从数据库加载
        db = self._get_db()
        if db is not None:
            try:
                doc = db.workflows.find_one({"id": workflow_id})
                if doc:
                    # 移除 MongoDB 的 _id 字段
                    doc.pop("_id", None)
                    # 🔥 转换 datetime 对象为字符串（Pydantic 验证需要字符串类型）
                    if "created_at" in doc and isinstance(doc["created_at"], datetime):
                        doc["created_at"] = doc["created_at"].isoformat()
                    if "updated_at" in doc and isinstance(doc["updated_at"], datetime):
                        doc["updated_at"] = doc["updated_at"].isoformat()
                    workflow = WorkflowDefinition.from_dict(doc)

                    # 统计分析师节点
                    analyst_nodes = [n for n in workflow.nodes if n.type == "analyst"]
                    analyst_ids = [n.agent_id for n in analyst_nodes]

                    logger.info(f"✅ [工作流加载] 从数据库加载: {workflow_id}")
                    logger.info(f"   名称: {workflow.name}")
                    logger.info(f"   版本: {doc.get('version', 1)}")
                    logger.info(f"   分析师数量: {len(analyst_nodes)}")
                    logger.info(f"   分析师列表: {analyst_ids}")
                    self._log_workflow_diagnostics(workflow, "database")

                    return workflow
                else:
                    logger.debug(f"[工作流加载] 数据库中未找到工作流: {workflow_id}")
            except Exception as e:
                logger.error(f"❌ [工作流加载] 从数据库加载失败: {e}")

        # 2. 尝试从文件系统加载
        workflows_dir = Path("data/workflows")
        file_path = workflows_dir / f"{workflow_id}.json"

        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                workflow = WorkflowDefinition.from_dict(data)

                # 统计分析师节点
                analyst_nodes = [n for n in workflow.nodes if n.type == "analyst"]
                analyst_ids = [n.agent_id for n in analyst_nodes]

                logger.info(f"✅ [工作流加载] 从文件系统加载: {workflow_id}")
                logger.info(f"   名称: {workflow.name}")
                logger.info(f"   分析师数量: {len(analyst_nodes)}")
                logger.info(f"   分析师列表: {analyst_ids}")
                self._log_workflow_diagnostics(workflow, f"filesystem:{file_path}")

                return workflow
            except Exception as e:
                logger.error(f"❌ [工作流加载] 从文件系统加载失败: {e}")

        # 3. 回退到默认工作流
        logger.warning(f"⚠️ [工作流加载] 工作流 {workflow_id} 不存在，使用系统默认工作流")
        default_workflow = DEFAULT_WORKFLOW
        analyst_nodes = [n for n in default_workflow.nodes if n.type == "analyst"]
        analyst_ids = [n.agent_id for n in analyst_nodes]
        logger.info(f"   默认工作流: {default_workflow.name}")
        logger.info(f"   分析师数量: {len(analyst_nodes)}")
        logger.info(f"   分析师列表: {analyst_ids}")
        self._log_workflow_diagnostics(default_workflow, "fallback_default")

        return default_workflow

    def ensure_system_workflows_exist(self) -> Dict[str, bool]:
        """
        确保系统预置工作流在数据库中与代码定义保持一致

        Returns:
            Dict[workflow_id, changed]: 是否新建或更新
        """
        results = {}
        db = self._get_db()

        if db is None:
            logger.warning("无法确保系统工作流存在: 数据库连接失败")
            return {wf_id: False for wf_id in self.SYSTEM_WORKFLOWS}

        for wf_id, workflow in self.SYSTEM_WORKFLOWS.items():
            try:
                existing = db.workflows.find_one({"id": wf_id})
                desired_doc = self._build_system_workflow_doc(
                    workflow,
                    existing.get("created_at") if existing else None,
                )

                if existing and self._normalize_workflow_doc_for_compare(existing) == self._normalize_workflow_doc_for_compare(desired_doc):
                    results[wf_id] = False
                    logger.debug(f"系统工作流已是最新版本: {wf_id}")
                    continue

                update_doc = dict(desired_doc)
                created_at = update_doc.pop("created_at")
                db.workflows.update_one(
                    {"id": wf_id},
                    {
                        "$set": update_doc,
                        "$setOnInsert": {"created_at": created_at},
                    },
                    upsert=True,
                )
                results[wf_id] = True
                logger.info(f"已同步系统工作流: {wf_id}")
            except Exception as e:
                logger.error(f"确保系统工作流存在失败 {wf_id}: {e}")
                results[wf_id] = False

        return results


# 单例实例
_default_provider: Optional[DefaultWorkflowProvider] = None


def get_default_workflow_provider() -> DefaultWorkflowProvider:
    """获取默认工作流提供者单例"""
    global _default_provider
    if _default_provider is None:
        _default_provider = DefaultWorkflowProvider()
    return _default_provider
