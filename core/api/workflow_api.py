"""
工作流 API

提供工作流的 CRUD 和执行接口
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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
    """
    
    WORKFLOWS_DIR = "data/workflows"
    
    def __init__(self):
        self._engine = WorkflowEngine()
        self._validator = WorkflowValidator()
        self._ensure_dir()
    
    def _ensure_dir(self) -> None:
        """确保工作流目录存在"""
        Path(self.WORKFLOWS_DIR).mkdir(parents=True, exist_ok=True)
    
    def _get_path(self, workflow_id: str) -> Path:
        """获取工作流文件路径"""
        return Path(self.WORKFLOWS_DIR) / f"{workflow_id}.json"
    
    # ==================== CRUD 操作 ====================
    
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建新工作流
        
        Args:
            data: 工作流数据
            
        Returns:
            创建的工作流
        """
        # 生成 ID
        if "id" not in data or not data["id"]:
            data["id"] = str(uuid.uuid4())
        
        # 设置时间戳
        now = datetime.now().isoformat()
        data["created_at"] = now
        data["updated_at"] = now
        
        # 验证 (保存时使用宽松模式，允许空工作流)
        definition = WorkflowDefinition.from_dict(data)
        result = self._validator.validate_for_save(definition)

        if not result.is_valid:
            return {
                "success": False,
                "errors": [str(e) for e in result.errors],
            }

        # 保存
        path = self._get_path(definition.id)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(definition.to_json())
        
        return {
            "success": True,
            "workflow": definition.to_dict(),
        }
    
    def get(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """获取工作流"""
        path = self._get_path(workflow_id)
        
        if not path.exists():
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def update(self, workflow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """更新工作流"""
        existing = self.get(workflow_id)
        if existing is None:
            return {"success": False, "error": "工作流不存在"}
        
        # 合并数据
        data["id"] = workflow_id
        data["created_at"] = existing.get("created_at")
        data["updated_at"] = datetime.now().isoformat()
        
        # 验证 (保存时使用宽松模式，允许空工作流)
        definition = WorkflowDefinition.from_dict(data)
        result = self._validator.validate_for_save(definition)

        if not result.is_valid:
            return {
                "success": False,
                "errors": [str(e) for e in result.errors],
            }

        # 保存
        path = self._get_path(workflow_id)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(definition.to_json())

        return {"success": True, "workflow": definition.to_dict()}
    
    def delete(self, workflow_id: str) -> Dict[str, Any]:
        """删除工作流"""
        path = self._get_path(workflow_id)
        
        if not path.exists():
            return {"success": False, "error": "工作流不存在"}
        
        path.unlink()
        return {"success": True}
    
    def list_all(self) -> List[Dict[str, Any]]:
        """列出所有工作流"""
        workflows = []
        
        for path in Path(self.WORKFLOWS_DIR).glob("*.json"):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 只返回摘要信息
                    workflows.append({
                        "id": data.get("id"),
                        "name": data.get("name"),
                        "description": data.get("description"),
                        "version": data.get("version"),
                        "tags": data.get("tags", []),
                        "is_template": data.get("is_template", False),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                    })
            except Exception:
                continue
        
        return workflows
    
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

