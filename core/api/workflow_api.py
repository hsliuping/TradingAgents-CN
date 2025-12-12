"""
工作流 API

提供工作流的 CRUD 和执行接口
支持数据库存储和版本管理
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from pymongo import MongoClient
from pymongo.collection import Collection

from ..workflow import (
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowValidator,
)
from ..workflow.templates import DEFAULT_WORKFLOW, SIMPLE_WORKFLOW
from ..workflow.default_workflow_provider import get_default_workflow_provider

logger = logging.getLogger(__name__)


class WorkflowAPI:
    """
    工作流 API

    提供工作流的创建、读取、更新、删除和执行功能
    支持 MongoDB 数据库存储，文件系统作为备选方案
    """

    WORKFLOWS_DIR = "data/workflows"

    def __init__(self):
        self._engine = WorkflowEngine()
        self._validator = WorkflowValidator()
        self._db = None
        self._workflows_collection: Optional[Collection] = None
        self._history_collection: Optional[Collection] = None
        self._ensure_dir()
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库连接"""
        try:
            mongo_uri = os.getenv(
                "MONGODB_CONNECTION_STRING",
                "mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin"
            )
            db_name = os.getenv("MONGODB_DATABASE_NAME", "tradingagents")

            client = MongoClient(mongo_uri)
            self._db = client[db_name]
            self._workflows_collection = self._db.workflows
            self._history_collection = self._db.workflow_history

            # 创建索引
            self._workflows_collection.create_index("id", unique=True)
            self._workflows_collection.create_index("is_system")
            self._workflows_collection.create_index("created_by")
            self._history_collection.create_index("workflow_id")
            self._history_collection.create_index([("workflow_id", 1), ("version", -1)])

            logger.info("✅ WorkflowAPI 数据库连接成功")
        except Exception as e:
            logger.warning(f"⚠️ WorkflowAPI 数据库连接失败，将使用文件系统: {e}")
            self._db = None

    def _ensure_dir(self) -> None:
        """确保工作流目录存在（备选方案）"""
        Path(self.WORKFLOWS_DIR).mkdir(parents=True, exist_ok=True)

    def _get_path(self, workflow_id: str) -> Path:
        """获取工作流文件路径（备选方案）"""
        return Path(self.WORKFLOWS_DIR) / f"{workflow_id}.json"
    
    # ==================== CRUD 操作 ====================

    def create(self, data: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        创建新工作流

        Args:
            data: 工作流数据
            user_id: 创建者用户ID

        Returns:
            创建的工作流
        """
        # 生成 ID
        if "id" not in data or not data["id"]:
            data["id"] = str(uuid.uuid4())

        # 设置时间戳和版本
        now = datetime.now().isoformat()
        data["created_at"] = now
        data["updated_at"] = now
        data.setdefault("version", 1)
        data.setdefault("is_system", user_id is None)
        if user_id:
            data["created_by"] = user_id

        # 验证 (保存时使用宽松模式，允许空工作流)
        definition = WorkflowDefinition.from_dict(data)
        result = self._validator.validate_for_save(definition)

        if not result.is_valid:
            return {
                "success": False,
                "errors": [str(e) for e in result.errors],
            }

        workflow_dict = definition.to_dict()
        workflow_dict["version"] = data.get("version", 1)
        workflow_dict["is_system"] = data.get("is_system", False)
        if user_id:
            workflow_dict["created_by"] = user_id

        # 优先保存到数据库
        if self._workflows_collection is not None:
            try:
                # 检查是否已存在
                existing = self._workflows_collection.find_one({"id": definition.id})
                if existing:
                    return {"success": False, "error": "工作流ID已存在"}

                self._workflows_collection.insert_one(workflow_dict.copy())
                logger.info(f"✅ 工作流已保存到数据库: {definition.id}")

                # 记录历史
                self._record_history(definition.id, user_id, 1, workflow_dict, "create")

                return {"success": True, "workflow": workflow_dict}
            except Exception as e:
                logger.error(f"❌ 保存工作流到数据库失败: {e}")

        # 备选：保存到文件系统
        path = self._get_path(definition.id)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(definition.to_json())

        return {"success": True, "workflow": workflow_dict}

    def get(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """获取工作流"""
        # 优先从数据库获取
        if self._workflows_collection is not None:
            try:
                doc = self._workflows_collection.find_one({"id": workflow_id})
                if doc:
                    doc.pop("_id", None)
                    logger.debug(f"从数据库获取工作流: {workflow_id}")
                    return doc
            except Exception as e:
                logger.warning(f"从数据库获取工作流失败: {e}")

        # 备选：从文件系统获取
        path = self._get_path(workflow_id)
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                logger.debug(f"从文件系统获取工作流: {workflow_id}")
                return json.load(f)

        return None

    def update(self, workflow_id: str, data: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        """更新工作流"""
        existing = self.get(workflow_id)
        if existing is None:
            return {"success": False, "error": "工作流不存在"}

        # 合并数据
        data["id"] = workflow_id
        data["created_at"] = existing.get("created_at")
        data["updated_at"] = datetime.now().isoformat()

        # 版本号递增（支持字符串和整数格式）
        old_version = existing.get("version", 1)
        if isinstance(old_version, str):
            # 处理 "1.0.0" 格式的版本号
            try:
                parts = old_version.split(".")
                major = int(parts[0]) if len(parts) > 0 else 1
                minor = int(parts[1]) if len(parts) > 1 else 0
                patch = int(parts[2]) if len(parts) > 2 else 0
                data["version"] = f"{major}.{minor}.{patch + 1}"
            except (ValueError, IndexError):
                data["version"] = "1.0.1"
        else:
            data["version"] = old_version + 1

        data["is_system"] = existing.get("is_system", False)
        if existing.get("created_by"):
            data["created_by"] = existing.get("created_by")

        # 验证 (保存时使用宽松模式，允许空工作流)
        definition = WorkflowDefinition.from_dict(data)
        result = self._validator.validate_for_save(definition)

        if not result.is_valid:
            return {
                "success": False,
                "errors": [str(e) for e in result.errors],
            }

        workflow_dict = definition.to_dict()
        workflow_dict["version"] = data["version"]
        workflow_dict["is_system"] = data.get("is_system", False)
        if data.get("created_by"):
            workflow_dict["created_by"] = data["created_by"]

        # 优先更新数据库
        if self._workflows_collection is not None:
            try:
                result = self._workflows_collection.update_one(
                    {"id": workflow_id},
                    {"$set": workflow_dict}
                )
                if result.modified_count > 0 or result.matched_count > 0:
                    logger.info(f"✅ 工作流已更新到数据库: {workflow_id}, 版本: {data['version']}")

                    # 记录历史
                    self._record_history(workflow_id, user_id, data["version"], workflow_dict, "update")

                    return {"success": True, "workflow": workflow_dict}
                else:
                    # 数据库中不存在，尝试插入
                    self._workflows_collection.insert_one(workflow_dict.copy())
                    logger.info(f"✅ 工作流已插入到数据库: {workflow_id}")
                    self._record_history(workflow_id, user_id, data["version"], workflow_dict, "create")
                    return {"success": True, "workflow": workflow_dict}
            except Exception as e:
                logger.error(f"❌ 更新工作流到数据库失败: {e}")

        # 备选：保存到文件系统
        path = self._get_path(workflow_id)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(definition.to_json())

        return {"success": True, "workflow": workflow_dict}

    def delete(self, workflow_id: str) -> Dict[str, Any]:
        """删除工作流"""
        # 优先从数据库删除
        if self._workflows_collection is not None:
            try:
                result = self._workflows_collection.delete_one({"id": workflow_id})
                if result.deleted_count > 0:
                    logger.info(f"✅ 工作流已从数据库删除: {workflow_id}")
                    return {"success": True}
            except Exception as e:
                logger.error(f"❌ 从数据库删除工作流失败: {e}")

        # 备选：从文件系统删除
        path = self._get_path(workflow_id)
        if path.exists():
            path.unlink()
            return {"success": True}

        return {"success": False, "error": "工作流不存在"}

    def list_all(self) -> List[Dict[str, Any]]:
        """列出所有工作流"""
        workflows = []
        seen_ids = set()

        # 优先从数据库获取
        if self._workflows_collection is not None:
            try:
                for doc in self._workflows_collection.find():
                    doc.pop("_id", None)
                    workflows.append({
                        "id": doc.get("id"),
                        "name": doc.get("name"),
                        "description": doc.get("description"),
                        "version": doc.get("version", 1),
                        "tags": doc.get("tags", []),
                        "is_template": doc.get("is_template", False),
                        "is_system": doc.get("is_system", False),
                        "created_at": doc.get("created_at"),
                        "updated_at": doc.get("updated_at"),
                    })
                    seen_ids.add(doc.get("id"))
            except Exception as e:
                logger.warning(f"从数据库获取工作流列表失败: {e}")

        # 补充文件系统中的工作流（避免重复）
        for path in Path(self.WORKFLOWS_DIR).glob("*.json"):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    workflow_id = data.get("id")
                    if workflow_id and workflow_id not in seen_ids:
                        workflows.append({
                            "id": workflow_id,
                            "name": data.get("name"),
                            "description": data.get("description"),
                            "version": data.get("version", 1),
                            "tags": data.get("tags", []),
                            "is_template": data.get("is_template", False),
                            "is_system": data.get("is_system", False),
                            "created_at": data.get("created_at"),
                            "updated_at": data.get("updated_at"),
                        })
            except Exception:
                continue

        return workflows

    def _record_history(
        self,
        workflow_id: str,
        user_id: Optional[str],
        version: int,
        content: Dict[str, Any],
        change_type: str,
        change_description: Optional[str] = None
    ) -> None:
        """记录工作流历史"""
        if self._history_collection is None:
            return

        try:
            history_doc = {
                "workflow_id": workflow_id,
                "user_id": user_id,
                "version": version,
                "content": content,
                "change_type": change_type,
                "change_description": change_description,
                "created_at": datetime.now().isoformat()
            }
            self._history_collection.insert_one(history_doc)
            logger.debug(f"工作流历史已记录: {workflow_id} v{version}")
        except Exception as e:
            logger.error(f"❌ 记录工作流历史失败: {e}")

    def get_history(self, workflow_id: str) -> List[Dict[str, Any]]:
        """获取工作流历史"""
        if self._history_collection is None:
            return []

        try:
            histories = []
            for doc in self._history_collection.find(
                {"workflow_id": workflow_id}
            ).sort("version", -1):
                doc.pop("_id", None)
                histories.append(doc)
            return histories
        except Exception as e:
            logger.error(f"❌ 获取工作流历史失败: {e}")
            return []
    
    def get_templates(self) -> List[Dict[str, Any]]:
        """获取预定义模板"""
        return [
            DEFAULT_WORKFLOW.to_dict(),
            SIMPLE_WORKFLOW.to_dict(),
        ]
    
    # ==================== 执行操作 ====================
    
    def execute(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        legacy_config: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        执行工作流

        Args:
            workflow_id: 工作流 ID
            inputs: 输入参数
            legacy_config: 遗留智能体配置（LLM、模型等）
            progress_callback: 进度回调函数

        Returns:
            执行结果
        """
        # 尝试从数据库或文件加载工作流
        data = self.get(workflow_id)

        # 如果找不到，尝试从系统预置工作流加载
        if data is None:
            provider = get_default_workflow_provider()
            workflow = provider.get_system_workflow(workflow_id)
            if workflow:
                data = workflow.to_dict()

        if data is None:
            return {"success": False, "error": "工作流不存在"}

        try:
            definition = WorkflowDefinition.from_dict(data)

            # 准备输入参数
            prepared_inputs = self._prepare_inputs(inputs)

            logger.info(f"[工作流执行] 输入参数: ticker={prepared_inputs.get('ticker')}, trade_date={prepared_inputs.get('trade_date')}")

            # 创建带配置的引擎
            task_id = str(uuid.uuid4())
            engine = WorkflowEngine(legacy_config=legacy_config, task_id=task_id)
            engine.load(definition)
            result = engine.execute(prepared_inputs, progress_callback=progress_callback)

            return {
                "success": True,
                "result": result,
                "execution": engine.last_execution.model_dump() if engine.last_execution else None,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def _prepare_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        准备工作流输入参数

        处理字段映射、状态初始化等
        """
        prepared = dict(inputs)

        # 从输入中解析辩论轮数
        depth_mapping = {
            "快速": {"debate": 1, "risk": 1},
            "基础": {"debate": 1, "risk": 1},
            "标准": {"debate": 1, "risk": 2},
            "深度": {"debate": 2, "risk": 2},
            "全面": {"debate": 3, "risk": 3},
        }
        research_depth = prepared.get("research_depth", "标准")
        depth_config = depth_mapping.get(research_depth, depth_mapping["标准"])

        # 将辩论配置注入到输入中
        prepared["_max_debate_rounds"] = depth_config["debate"]
        prepared["_max_risk_rounds"] = depth_config["risk"]

        # 映射字段名以兼容原有智能体
        if "ticker" in prepared:
            prepared["company_of_interest"] = prepared["ticker"]
        if "analysis_date" in prepared and prepared["analysis_date"]:
            date_str = prepared["analysis_date"]
            if isinstance(date_str, str):
                if "T" in date_str:
                    date_str = date_str.split("T")[0]
                prepared["trade_date"] = date_str
            else:
                prepared["trade_date"] = str(date_str)[:10]
        else:
            prepared["trade_date"] = datetime.now().strftime("%Y-%m-%d")

        # 初始化原有智能体需要的状态字段
        prepared.setdefault("investment_debate_state", {
            "history": "", "bull_history": "", "bear_history": "",
            "current_response": "", "count": 0
        })
        prepared.setdefault("risk_debate_state", {
            "history": "", "risky_history": "", "safe_history": "",
            "neutral_history": "", "current_risky_response": "",
            "current_safe_response": "", "current_neutral_response": "",
            "latest_speaker": "", "count": 0
        })

        # 分析报告字段
        for field in ["market_report", "sentiment_report", "news_report", "fundamentals_report"]:
            prepared.setdefault(field, "")

        # 工具调用计数器
        for field in ["market_tool_call_count", "sentiment_tool_call_count",
                      "news_tool_call_count", "fundamentals_tool_call_count"]:
            prepared.setdefault(field, 0)

        # 分析师独立消息历史
        for field in ["_market_messages", "_social_messages",
                      "_news_messages", "_fundamentals_messages"]:
            prepared.setdefault(field, [])

        # 研究结果字段
        for field in ["bull_report", "bear_report", "investment_plan", "trader_investment_plan"]:
            prepared.setdefault(field, "")

        logger.info(f"[工作流执行] 分析深度: {research_depth}, 辩论轮数: {depth_config['debate']}, 风险轮数: {depth_config['risk']}")

        return prepared
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """验证工作流定义"""
        try:
            # 验证时如果没有 id，生成一个临时的
            if "id" not in data or not data["id"]:
                data["id"] = f"temp_{uuid.uuid4()}"
            definition = WorkflowDefinition.from_dict(data)
            result = self._validator.validate(definition)

            return {
                "is_valid": result.is_valid,
                "errors": [str(e) for e in result.errors],
                "warnings": [str(w) for w in result.warnings],
            }
        except Exception as e:
            return {"is_valid": False, "errors": [str(e)], "warnings": []}

