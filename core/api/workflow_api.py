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
from core.workflow.templates import (
    BLANK_WORKFLOW,
    TRADE_REVIEW_WORKFLOW_V2,
    POSITION_ANALYSIS_WORKFLOW_V2,
    V2_STOCK_ANALYSIS_WORKFLOW,
    V2_ETF_ANALYSIS_WORKFLOW,
)
from ..workflow.default_workflow_provider import get_default_workflow_provider

logger = logging.getLogger(__name__)


# ==================== 默认 input_config 生成 ====================

def _merge_input_config(
    existing: Dict[str, Any],
    defaults: Dict[str, Any],
) -> Dict[str, Any]:
    """
    合并补全 input_config：已有字段保留，缺少的字段从默认值补充。

    - existing: 数据库中已有的 input_config（可能只有部分字段）
    - defaults: 完整的默认 input_config（按 workflow_type 生成）
    - 返回：合并后的 input_config，已有字段不变，缺少的补上
    """
    if not existing or not existing.get("fields"):
        return defaults

    existing_field_names = {f["name"] for f in existing.get("fields", [])}
    merged_fields = list(existing.get("fields", []))

    for default_field in defaults.get("fields", []):
        if default_field["name"] not in existing_field_names:
            merged_fields.append(default_field)

    # 按 order 重新排序
    merged_fields.sort(key=lambda f: f.get("order", 999))
    return {"fields": merged_fields}


def _get_default_input_config(workflow_type: str) -> Dict[str, Any]:
    """
    根据 workflow_type 生成默认的 input_config，用于补充存量流程。

    新创建的流程应该由 AI 生成 input_config，这里只为没有 input_config 的
    存量流程提供兜底，确保前端能正常渲染执行表单。
    """
    if workflow_type == "general":
        return {
            "fields": [
                {
                    "name": "analysis_target",
                    "label": "分析目标",
                    "type": "textarea",
                    "required": True,
                    "default": None,
                    "description": "请输入分析目标，如：分析新能源行业趋势、对比000001和000002等",
                    "placeholder": "请输入分析目标",
                    "options": None,
                    "option_labels": None,
                    "min": None,
                    "max": None,
                    "group": "基本参数",
                    "order": 1,
                },
                {
                    "name": "quick_analysis_model",
                    "label": "快速分析模型",
                    "type": "select",
                    "required": False,
                    "default": None,
                    "description": "快速分析使用的 LLM 模型",
                    "placeholder": "选择模型",
                    "options": None, "option_labels": None, "min": None, "max": None,
                    "group": "模型配置", "order": 2,
                },
                {
                    "name": "deep_analysis_model",
                    "label": "深度分析模型",
                    "type": "select",
                    "required": False,
                    "default": None,
                    "description": "深度分析使用的 LLM 模型",
                    "placeholder": "选择模型",
                    "options": None, "option_labels": None, "min": None, "max": None,
                    "group": "模型配置", "order": 3,
                },
            ]
        }

    if workflow_type == "etf_analysis":
        return _build_stock_analysis_input_config(allow_etf=True)

    if workflow_type == "position_analysis":
        return {
            "fields": [
                {
                    "name": "portfolio_data",
                    "label": "持仓数据",
                    "type": "textarea",
                    "required": True,
                    "default": None,
                    "description": "请输入持仓数据（JSON 格式或文本描述）",
                    "placeholder": "持仓数据",
                    "options": None, "option_labels": None, "min": None, "max": None,
                    "group": "基本参数", "order": 1,
                },
                {
                    "name": "analysis_date",
                    "label": "分析日期",
                    "type": "date",
                    "required": False,
                    "default": None,
                    "description": "分析基准日期",
                    "placeholder": "", "options": None, "option_labels": None,
                    "min": None, "max": None, "group": "基本参数", "order": 2,
                },
                {
                    "name": "quick_analysis_model",
                    "label": "快速分析模型",
                    "type": "select",
                    "required": False,
                    "default": None,
                    "description": "快速分析使用的 LLM 模型",
                    "placeholder": "选择模型",
                    "options": None, "option_labels": None, "min": None, "max": None,
                    "group": "模型配置", "order": 3,
                },
                {
                    "name": "deep_analysis_model",
                    "label": "深度分析模型",
                    "type": "select",
                    "required": False,
                    "default": None,
                    "description": "深度分析使用的 LLM 模型",
                    "placeholder": "选择模型",
                    "options": None, "option_labels": None, "min": None, "max": None,
                    "group": "模型配置", "order": 4,
                },
            ]
        }

    if workflow_type == "trade_review":
        return {
            "fields": [
                {
                    "name": "trade_data",
                    "label": "交易记录",
                    "type": "textarea",
                    "required": True,
                    "default": None,
                    "description": "请输入要复盘的交易记录",
                    "placeholder": "交易记录",
                    "options": None, "option_labels": None, "min": None, "max": None,
                    "group": "基本参数", "order": 1,
                },
                {
                    "name": "analysis_date",
                    "label": "分析日期",
                    "type": "date",
                    "required": False,
                    "default": None,
                    "description": "复盘基准日期",
                    "placeholder": "", "options": None, "option_labels": None,
                    "min": None, "max": None, "group": "基本参数", "order": 2,
                },
                {
                    "name": "quick_analysis_model",
                    "label": "快速分析模型",
                    "type": "select",
                    "required": False,
                    "default": None,
                    "description": "快速分析使用的 LLM 模型",
                    "placeholder": "选择模型",
                    "options": None, "option_labels": None, "min": None, "max": None,
                    "group": "模型配置", "order": 3,
                },
                {
                    "name": "deep_analysis_model",
                    "label": "深度分析模型",
                    "type": "select",
                    "required": False,
                    "default": None,
                    "description": "深度分析使用的 LLM 模型",
                    "placeholder": "选择模型",
                    "options": None, "option_labels": None, "min": None, "max": None,
                    "group": "模型配置", "order": 4,
                },
            ]
        }

    # 默认：股票分析流程
    return _build_stock_analysis_input_config()


def _build_stock_analysis_input_config(allow_etf: bool = False) -> Dict[str, Any]:
    """构建股票分析（或ETF分析）的默认 input_config"""
    ticker_label = "股票代码" if not allow_etf else "ETF代码"
    ticker_placeholder = "如: 600519.SH" if not allow_etf else "如: 510300.SH"
    ticker_desc = "要分析的股票代码" if not allow_etf else "要分析的ETF代码"

    return {
        "fields": [
            {
                "name": "ticker",
                "label": ticker_label,
                "type": "string",
                "required": True,
                "default": None,
                "description": ticker_desc,
                "placeholder": ticker_placeholder,
                "options": None, "option_labels": None, "min": None, "max": None,
                "group": "基本参数", "order": 1,
            },
            {
                "name": "analysis_date",
                "label": "分析日期",
                "type": "date",
                "required": False,
                "default": None,
                "description": "分析基准日期",
                "placeholder": "", "options": None, "option_labels": None,
                "min": None, "max": None, "group": "基本参数", "order": 2,
            },
            {
                "name": "research_depth",
                "label": "分析深度",
                "type": "select",
                "required": False,
                "default": "标准",
                "description": "分析深度等级",
                "placeholder": "",
                "options": ["快速", "基础", "标准", "深度", "全面"],
                "option_labels": ["快速 (2-4分钟)", "基础 (4-6分钟)", "标准 (6-10分钟)", "深度 (10-15分钟)", "全面 (15-25分钟)"],
                "min": None, "max": None, "group": "基本参数", "order": 3,
            },
            {
                "name": "selected_analysts",
                "label": "分析师团队",
                "type": "multiselect",
                "required": False,
                "default": ["index_analyst", "sector_analyst", "market", "fundamentals", "news", "social"],
                "description": "选择参与分析的分析师（不选则使用全部）",
                "placeholder": "选择分析师",
                "options": ["index_analyst", "sector_analyst", "market", "fundamentals", "news", "social"],
                "option_labels": ["大盘分析师", "行业分析师", "市场分析师", "基本面分析师", "新闻分析师", "社交媒体分析师"],
                "min": None, "max": None, "group": "基本参数", "order": 4,
            },
            {
                "name": "quick_analysis_model",
                "label": "快速分析模型",
                "type": "select",
                "required": False,
                "default": None,
                "description": "快速分析使用的 LLM 模型",
                "placeholder": "选择模型",
                "options": None, "option_labels": None, "min": None, "max": None,
                "group": "模型配置", "order": 4,
            },
            {
                "name": "deep_analysis_model",
                "label": "深度分析模型",
                "type": "select",
                "required": False,
                "default": None,
                "description": "深度分析使用的 LLM 模型",
                "placeholder": "选择模型",
                "options": None, "option_labels": None, "min": None, "max": None,
                "group": "模型配置", "order": 5,
            },
            {
                "name": "lookback_days",
                "label": "回看天数",
                "type": "number",
                "required": False,
                "default": 365,
                "description": "历史数据回看天数",
                "placeholder": "",
                "options": None, "option_labels": None,
                "min": 1, "max": 365, "group": "高级参数", "order": 6,
            },
            {
                "name": "max_debate_rounds",
                "label": "辩论轮数",
                "type": "number",
                "required": False,
                "default": 2,
                "description": "积极/谨慎情景研究的最大轮数",
                "placeholder": "",
                "options": None, "option_labels": None,
                "min": 1, "max": 10, "group": "高级参数", "order": 7,
            },
        ]
    }


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
            self._workflows_collection = self._db.workflows
            self._history_collection = self._db.workflow_history

            # 创建索引
            self._workflows_collection.create_index("id", unique=True)
            self._workflows_collection.create_index("is_system")
            self._workflows_collection.create_index("created_by")
            self._workflows_collection.create_index("is_default")
            self._workflows_collection.create_index("workflow_type")
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

    def _log_workflow_source(
        self,
        workflow_id: str,
        source: str,
        data: Dict[str, Any],
        source_path: Optional[str] = None,
    ) -> None:
        """记录工作流来源和关键边，便于排查实际加载的是哪份定义。"""
        edges = data.get("edges") or []
        edge_list = [f"{edge.get('id')}:{edge.get('source')}->{edge.get('target')}" for edge in edges]
        critical_edge_ids = {"e_to_risk_debate", "e_risk_judge", "e_trader", "e_end"}
        critical_edges = {
            edge.get("id"): (edge.get("source"), edge.get("target"))
            for edge in edges
            if edge.get("id") in critical_edge_ids
        }
        logger.info(f"📋 [WorkflowAPI] 工作流来源: {workflow_id} <- {source}")
        if source_path:
            logger.info(f"📋 [WorkflowAPI] 来源路径: {source_path}")
        logger.info(f"📋 [WorkflowAPI] 边列表: {edge_list}")
        if critical_edges:
            logger.info(f"📋 [WorkflowAPI] 关键边: {critical_edges}")
    
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
        workflow_dict["is_default"] = bool(data.get("is_default", False))
        workflow_dict["workflow_type"] = data.get("workflow_type") or get_default_workflow_provider().infer_workflow_type(workflow_dict)
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
        provider = get_default_workflow_provider()
        system_workflow = provider.get_system_workflow(workflow_id)
        if system_workflow is not None:
            data = system_workflow.to_dict()
            # 🆕 合并补全 input_config：已有字段保留，缺少的从默认值补充
            if not data.get("input_config"):
                data["input_config"] = {}
            wf_type = provider.infer_workflow_type(system_workflow, workflow_id)
            data["input_config"] = _merge_input_config(data["input_config"], _get_default_input_config(wf_type))
            logger.info(f"📋 [WorkflowAPI] 使用系统预置工作流: {workflow_id}")
            self._log_workflow_source(workflow_id, "system_preset", data)
            return data

        # 优先从数据库获取
        if self._workflows_collection is not None:
            try:
                doc = self._workflows_collection.find_one({"id": workflow_id})
                if doc:
                    doc.pop("_id", None)
                    # 🔥 转换 datetime 对象为字符串（Pydantic 验证需要字符串类型）
                    if "created_at" in doc and isinstance(doc["created_at"], datetime):
                        doc["created_at"] = doc["created_at"].isoformat()
                    if "updated_at" in doc and isinstance(doc["updated_at"], datetime):
                        doc["updated_at"] = doc["updated_at"].isoformat()
                    # 🆕 确保 workflow_type 字段存在（用于前端判断工作流类型）
                    if not doc.get("workflow_type"):
                        doc["workflow_type"] = provider.infer_workflow_type(doc, workflow_id)
                    # 🆕 合并补全 input_config：已有字段保留，缺少的从默认值补充
                    wf_type = doc.get("workflow_type", "stock_analysis")
                    doc["input_config"] = _merge_input_config(
                        doc.get("input_config") or {},
                        _get_default_input_config(wf_type),
                    )
                    logger.info(f"📋 [WorkflowAPI] 从数据库获取工作流: {workflow_id} (type={doc.get('workflow_type')})")
                    self._log_workflow_source(workflow_id, "database", doc)
                    return doc
            except Exception as e:
                logger.warning(f"从数据库获取工作流失败: {e}")

        # 备选：从文件系统获取
        path = self._get_path(workflow_id)
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"📋 [WorkflowAPI] 从文件系统获取工作流: {workflow_id}")
                self._log_workflow_source(workflow_id, "filesystem", data, str(path))
                return data

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
        workflow_dict["is_default"] = bool(data.get("is_default", existing.get("is_default", False)))
        workflow_dict["workflow_type"] = data.get("workflow_type") or existing.get("workflow_type") or get_default_workflow_provider().infer_workflow_type(workflow_dict)
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
                        "is_default": doc.get("is_default", False),
                        "workflow_type": doc.get("workflow_type") or get_default_workflow_provider().infer_workflow_type(doc),
                        "created_at": doc.get("created_at"),
                        "updated_at": doc.get("updated_at"),
                        "nodes": doc.get("nodes", []),
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
                            "is_default": data.get("is_default", False),
                            "workflow_type": data.get("workflow_type") or get_default_workflow_provider().infer_workflow_type(data),
                            "created_at": data.get("created_at"),
                            "updated_at": data.get("updated_at"),
                            "nodes": data.get("nodes", []),
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
        provider = get_default_workflow_provider()
        try:
            provider.ensure_system_workflows_exist()
        except Exception as e:
            logger.warning(f"确保系统工作流存在失败（忽略）: {e}")

        return [
            BLANK_WORKFLOW.to_dict(),
            TRADE_REVIEW_WORKFLOW_V2.to_dict(),
            POSITION_ANALYSIS_WORKFLOW_V2.to_dict(),
            V2_STOCK_ANALYSIS_WORKFLOW.to_dict(),
            V2_ETF_ANALYSIS_WORKFLOW.to_dict(),
        ]
    
    # ==================== 执行操作 ====================
    
    def execute(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        legacy_config: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行工作流

        Args:
            workflow_id: 工作流 ID
            inputs: 输入参数
            legacy_config: 遗留智能体配置（LLM、模型等）
            progress_callback: 进度回调函数
            task_id: 任务 ID（任务中心的 task_id，用于执行轨迹关联。不传则随机生成）

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
                self._log_workflow_source(workflow_id, "system_preset", data)

        if data is None:
            return {"success": False, "error": "工作流不存在"}

        try:
            definition = WorkflowDefinition.from_dict(data)
            logger.info(f"📋 [WorkflowAPI] 执行工作流定义: {definition.id} - {definition.name}")

            # 准备输入参数
            prepared_inputs = self._prepare_inputs(inputs)

            logger.info(f"[工作流执行] 输入参数: ticker={prepared_inputs.get('ticker')}, trade_date={prepared_inputs.get('trade_date')}")

            # 创建带配置的引擎（优先用传入的 task_id，用于执行轨迹关联）
            task_id = task_id or str(uuid.uuid4())
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

    def _prepare_system_variables(
        self,
        stock_code: str,
        analysis_date: str
    ) -> Dict[str, Any]:
        """
        准备系统变量（在工作流开始时统一获取）

        优先从数据库获取，速度快且不受 API 限流影响

        Args:
            stock_code: 股票代码
            analysis_date: 分析日期（字符串或 datetime 对象）

        Returns:
            系统变量字典
        """
        system_vars = {}

        try:
            from tradingagents.utils.stock_utils import StockUtils
            from app.core.database import get_mongo_db_sync  # 使用同步版本

            # 确保 analysis_date 是纯日期字符串 (YYYY-MM-DD)
            if isinstance(analysis_date, datetime):
                analysis_date = analysis_date.strftime('%Y-%m-%d')
            elif isinstance(analysis_date, str):
                # 处理可能包含时间的字符串，如 "2026-01-14T00:00:00" 或 "2026-01-14 00:00:00"
                if 'T' in analysis_date:
                    analysis_date = analysis_date.split('T')[0]
                elif ' ' in analysis_date:
                    analysis_date = analysis_date.split()[0]

            market_info = StockUtils.get_market_info(stock_code)
            is_china = market_info.get('is_china', False)
            effective_data_date = analysis_date
            stable_data_note = ""

            if is_china:
                try:
                    from core.tools.trade_date_policy import apply_stable_data_cutoff, build_stable_data_cutoff_note

                    effective_data_date = apply_stable_data_cutoff(analysis_date)
                    stable_data_note = build_stable_data_cutoff_note(
                        analysis_date,
                        effective_data_date,
                        subject="A股日频稳定数据",
                    )
                except Exception as e:
                    logger.warning(f"⚠️ 计算稳定数据日期失败，回退到分析日期: {e}")

            system_vars["effective_data_date"] = effective_data_date
            system_vars["stable_data_note"] = stable_data_note

            # 1. 从数据库获取股票基础信息（公司名称、行业）
            company_name = stock_code
            industry = "未知"

            if is_china:
                try:
                    db = get_mongo_db_sync()  # 使用同步版本

                    # 优先从 stock_basic_info 获取
                    stock_info = db.stock_basic_info.find_one(
                        {"$or": [{"code": stock_code}, {"symbol": stock_code}]},
                        {"_id": 0, "name": 1, "industry": 1}
                    )

                    if stock_info:
                        company_name = stock_info.get("name", stock_code)
                        industry = stock_info.get("industry", "未知")
                        logger.info(f"📊 [系统变量-数据库] 公司名称: {company_name}, 行业: {industry}")
                    else:
                        logger.warning(f"⚠️ 数据库中未找到股票 {stock_code} 的基础信息")
                except Exception as e:
                    logger.warning(f"⚠️ 从数据库获取股票基础信息失败: {e}")

            system_vars["company_name"] = company_name
            system_vars["industry"] = industry

            # 2. 从数据库获取当前价格
            current_price = "未知"
            current_price_context_date = ""

            if is_china:
                try:
                    db = get_mongo_db_sync()  # 使用同步版本
                    logger.info(f"🔍 [价格查询] 开始查询股票 {stock_code} 的价格...")

                    # 优先从 market_quotes 获取不晚于稳定日期的价格，避免把汇总口径拉回分析日当天。
                    logger.info(f"🔍 [价格查询] 步骤1: 从 market_quotes 查询稳定日期价格...")
                    quote = None
                    date_candidates = [effective_data_date]
                    compact_effective_date = effective_data_date.replace('-', '')
                    if compact_effective_date != effective_data_date:
                        date_candidates.append(compact_effective_date)

                    for date_candidate in date_candidates:
                        quote = db.market_quotes.find_one(
                            {
                                "$or": [{"code": stock_code}, {"symbol": stock_code}],
                                "trade_date": {"$lte": date_candidate},
                            },
                            {"_id": 0, "close": 1, "trade_date": 1},
                            sort=[("trade_date", -1)]
                        )
                        if quote:
                            break

                    logger.info(f"🔍 [价格查询] market_quotes 查询结果: {quote}")

                    if quote and quote.get("close"):
                        current_price = str(quote["close"])
                        current_price_context_date = str(quote.get("trade_date") or "")
                        logger.info(f"✅ [系统变量-数据库] 当前价格: ¥{current_price} (日期: {quote.get('trade_date', 'N/A')})")
                    else:
                        logger.warning(
                            f"⚠️ 数据库中未找到股票 {stock_code} 在稳定日期 {effective_data_date} 及之前的价格信息"
                        )
                except Exception as e:
                    logger.warning(f"⚠️ 从数据库获取当前价格失败: {e}")
                    import traceback
                    traceback.print_exc()

            system_vars["current_price"] = current_price
            system_vars["current_price_context_date"] = current_price_context_date

            # 3. 市场信息
            market_name = "A股" if is_china else "港股" if market_info.get('is_hk') else "美股"
            system_vars["market_name"] = market_name

            # 4. 货币信息
            if is_china:
                system_vars["currency_name"] = "人民币"
                system_vars["currency_symbol"] = "¥"
            elif market_info.get('is_hk'):
                system_vars["currency_name"] = "港币"
                system_vars["currency_symbol"] = "HK$"
            else:
                system_vars["currency_name"] = "美元"
                system_vars["currency_symbol"] = "$"

            # 5. 日期信息
            from datetime import timedelta
            system_vars["current_date"] = analysis_date
            start_date = (datetime.strptime(analysis_date, '%Y-%m-%d') - timedelta(days=365)).strftime('%Y-%m-%d')
            system_vars["start_date"] = start_date

            # 6. 🆕 行业/个股分析维度注入
            try:
                from app.services.analysis_profile_service import AnalysisProfileService

                # 查询行业分析维度
                if industry and industry != "未知":
                    industry_dims = AnalysisProfileService.get_industry_dimensions_sync(industry)
                    system_vars.update(industry_dims)

                # 查询个股分析维度（覆盖行业维度）
                stock_dims = AnalysisProfileService.get_stock_dimensions_sync(stock_code)
                system_vars.update(stock_dims)
            except Exception as e:
                logger.warning(f"⚠️ 获取分析维度失败（不影响主流程）: {e}")

            logger.info(f"✅ [系统变量] 准备完成: {list(system_vars.keys())}")
            logger.info(f"   - company_name: {company_name}")
            logger.info(f"   - industry: {industry}")
            logger.info(f"   - current_price: {current_price}")
            logger.info(f"   - effective_data_date: {effective_data_date}")
            logger.info(f"   - market_name: {market_name}")
            if system_vars.get("industry_dimensions"):
                logger.info(f"   - 🏭 已注入行业分析维度")
            if system_vars.get("stock_dimensions"):
                logger.info(f"   - 📊 已注入个股分析维度")

        except Exception as e:
            logger.error(f"❌ 准备系统变量失败: {e}")
            import traceback
            traceback.print_exc()

        return system_vars

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

        # A9-P1: 风险自我辩论开关（单节点替代风险三角多轮辩论，仅深度/全面档）
        # 优先级：环境变量 RISK_SELF_DEBATE（on/off，一键回退）> 输入显式覆盖 > 档位默认
        _self_debate_mode = str(os.environ.get("RISK_SELF_DEBATE", "auto")).strip().lower()
        if _self_debate_mode in ("on", "1", "true"):
            prepared["_risk_self_debate"] = True
        elif _self_debate_mode in ("off", "0", "false"):
            prepared["_risk_self_debate"] = False
        elif "risk_self_debate" in prepared:
            # 允许调用方按任务显式覆盖（truthy 判定）
            prepared["_risk_self_debate"] = bool(prepared.get("risk_self_debate"))
        else:
            # 默认：仅深度/全面档启用，其余档位走原风险三角路径
            prepared["_risk_self_debate"] = research_depth in ("深度", "全面")
        logger.info(
            f"[A9-P1] 风险自我辩论开关: {prepared['_risk_self_debate']} "
            f"(mode={_self_debate_mode}, depth={research_depth})"
        )

        # A3: 投资辩论并行开局开关（第一轮乐观/审慎研究员并行出简报，替代串行接力）
        # 优先级：环境变量 RESEARCH_PARALLEL_OPENING（on/off，一键回退）> 输入显式覆盖 > 默认启用
        _parallel_opening_mode = str(
            os.environ.get("RESEARCH_PARALLEL_OPENING", "auto")
        ).strip().lower()
        if _parallel_opening_mode in ("on", "1", "true"):
            prepared["_parallel_opening"] = True
        elif _parallel_opening_mode in ("off", "0", "false"):
            prepared["_parallel_opening"] = False
        elif "parallel_opening" in prepared:
            # 允许调用方按任务显式覆盖（truthy 判定）
            prepared["_parallel_opening"] = bool(prepared.get("parallel_opening"))
        else:
            # 默认全档位启用：并行开局只是把第一轮串行接力改为并行，
            # 辩论语义不变（各自基于同一份分析师材料独立出初始简报）
            prepared["_parallel_opening"] = True
        logger.info(
            f"[A3] 投资辩论并行开局开关: {prepared['_parallel_opening']} "
            f"(mode={_parallel_opening_mode})"
        )

        # 映射字段名以兼容原有智能体
        if "ticker" in prepared:
            prepared["company_of_interest"] = prepared["ticker"]
        if "analysis_date" in prepared and prepared["analysis_date"]:
            date_str = prepared["analysis_date"]
            if isinstance(date_str, str):
                # 处理可能包含时间的字符串
                if "T" in date_str:
                    date_str = date_str.split("T")[0]
                elif " " in date_str:
                    date_str = date_str.split()[0]
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

        # 🆕 准备系统变量（公司名称、行业、当前价格等）
        ticker = prepared.get("ticker")
        analysis_date = prepared.get("analysis_date") or prepared.get("trade_date")

        if ticker and analysis_date:
            system_vars = self._prepare_system_variables(ticker, analysis_date)
            prepared.update(system_vars)

        return prepared
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """验证工作流定义"""
        try:
            # 验证时如果没有 id，生成一个临时的
            if "id" not in data or not data["id"]:
                data["id"] = f"temp_{uuid.uuid4()}"
            # 🔥 转换 datetime 对象为字符串（Pydantic 验证需要字符串类型）
            if "created_at" in data and isinstance(data["created_at"], datetime):
                data["created_at"] = data["created_at"].isoformat()
            if "updated_at" in data and isinstance(data["updated_at"], datetime):
                data["updated_at"] = data["updated_at"].isoformat()
            definition = WorkflowDefinition.from_dict(data)
            result = self._validator.validate(definition)

            return {
                "is_valid": result.is_valid,
                "errors": [str(e) for e in result.errors],
                "warnings": [str(w) for w in result.warnings],
            }
        except Exception as e:
            return {"is_valid": False, "errors": [str(e)], "warnings": []}

