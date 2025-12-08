"""
工作流 API

提供工作流的 CRUD 和执行接口
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..workflow import (
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowValidator,
)
from ..workflow.templates import DEFAULT_WORKFLOW, SIMPLE_WORKFLOW

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
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行工作流

        Args:
            workflow_id: 工作流 ID
            inputs: 输入参数

        Returns:
            执行结果
        """
        data = self.get(workflow_id)
        if data is None:
            return {"success": False, "error": "工作流不存在"}

        try:
            definition = WorkflowDefinition.from_dict(data)

            # 从输入中解析辩论轮数
            depth_mapping = {
                "快速": {"debate": 1, "risk": 1},
                "基础": {"debate": 1, "risk": 1},
                "标准": {"debate": 1, "risk": 2},
                "深度": {"debate": 2, "risk": 2},
                "全面": {"debate": 3, "risk": 3},
            }
            research_depth = inputs.get("research_depth", "标准")
            depth_config = depth_mapping.get(research_depth, depth_mapping["标准"])

            # 将辩论配置注入到输入中
            inputs["_max_debate_rounds"] = depth_config["debate"]
            inputs["_max_risk_rounds"] = depth_config["risk"]

            logger.info(f"[工作流执行] 分析深度: {research_depth}, 辩论轮数: {depth_config['debate']}, 风险轮数: {depth_config['risk']}")
            logger.info(f"[工作流执行] 输入参数: {inputs}")

            self._engine.load(definition)
            result = self._engine.execute(inputs)

            return {
                "success": True,
                "result": result,
                "execution": self._engine.last_execution.model_dump() if self._engine.last_execution else None,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
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

