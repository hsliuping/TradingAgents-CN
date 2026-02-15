"""
报告模板服务

提供报告模板的 CRUD 操作和工作流报告生成功能。
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.models.report_template import (
    ReportTemplate, 
    ReportTemplateCreate, 
    ReportTemplateUpdate,
    ReportTemplateResponse
)

logger = logging.getLogger(__name__)


class ReportTemplateService:
    """报告模板服务"""
    
    def __init__(self, db):
        """
        初始化服务
        
        Args:
            db: MongoDB 数据库连接
        """
        self.db = db
        self.collection = db.report_templates
    
    async def create_template(
        self, 
        data: ReportTemplateCreate,
        user_id: Optional[str] = None
    ) -> ReportTemplateResponse:
        """创建报告模板"""
        # 检查 template_id 是否已存在
        existing = await self.collection.find_one({"template_id": data.template_id})
        if existing:
            raise ValueError(f"模板ID '{data.template_id}' 已存在")
        
        # 检查 workflow_id 是否已有模板
        existing_workflow = await self.collection.find_one({
            "workflow_id": data.workflow_id,
            "status": "active"
        })
        if existing_workflow:
            logger.warning(
                f"⚠️ 工作流 {data.workflow_id} 已有活动模板 {existing_workflow.get('template_id')}，"
                f"将被新模板 {data.template_id} 替代"
            )
            # 将旧模板设为 inactive
            await self.collection.update_one(
                {"_id": existing_workflow["_id"]},
                {"$set": {"status": "inactive", "updated_at": datetime.utcnow()}}
            )
        
        # 创建文档
        doc = {
            "template_id": data.template_id,
            "name": data.name,
            "description": data.description,
            "workflow_id": data.workflow_id,
            "output_schema": [f.dict() for f in data.output_schema],
            "generator_prompt": data.generator_prompt,
            "summary_fields": data.summary_fields,
            "display_config": data.display_config,
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "created_by": user_id
        }
        
        result = await self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        
        logger.info(f"✅ 创建报告模板: {data.template_id} (workflow_id={data.workflow_id})")
        
        return self._to_response(doc)
    
    async def get_template(self, template_id: str) -> Optional[ReportTemplateResponse]:
        """获取报告模板"""
        doc = await self.collection.find_one({"template_id": template_id})
        return self._to_response(doc) if doc else None
    
    async def get_template_by_workflow(
        self, 
        workflow_id: str
    ) -> Optional[ReportTemplateResponse]:
        """根据工作流ID获取报告模板"""
        doc = await self.collection.find_one({
            "workflow_id": workflow_id,
            "status": "active"
        })
        return self._to_response(doc) if doc else None
    
    async def list_templates(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
    ) -> List[ReportTemplateResponse]:
        """列出报告模板"""
        query = {}
        if workflow_id:
            query["workflow_id"] = workflow_id
        if status:
            query["status"] = status
        
        cursor = self.collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
        docs = await cursor.to_list(length=limit)
        
        return [self._to_response(doc) for doc in docs]
    
    async def update_template(
        self,
        template_id: str,
        data: ReportTemplateUpdate
    ) -> Optional[ReportTemplateResponse]:
        """更新报告模板"""
        update_data = {"updated_at": datetime.utcnow()}
        
        if data.name is not None:
            update_data["name"] = data.name
        if data.description is not None:
            update_data["description"] = data.description
        if data.output_schema is not None:
            update_data["output_schema"] = [f.dict() for f in data.output_schema]
        if data.generator_prompt is not None:
            update_data["generator_prompt"] = data.generator_prompt
        if data.summary_fields is not None:
            update_data["summary_fields"] = data.summary_fields
        if data.display_config is not None:
            update_data["display_config"] = data.display_config
        if data.status is not None:
            update_data["status"] = data.status
        
        result = await self.collection.find_one_and_update(
            {"template_id": template_id},
            {"$set": update_data},
            return_document=True
        )
        
        if result:
            logger.info(f"✅ 更新报告模板: {template_id}")
        
        return self._to_response(result) if result else None
    
    async def delete_template(self, template_id: str) -> bool:
        """删除报告模板"""
        result = await self.collection.delete_one({"template_id": template_id})
        if result.deleted_count > 0:
            logger.info(f"✅ 删除报告模板: {template_id}")
            return True
        return False
    
    def _to_response(self, doc: Dict[str, Any]) -> ReportTemplateResponse:
        """转换为响应模型"""
        return ReportTemplateResponse(
            id=str(doc["_id"]),
            template_id=doc["template_id"],
            name=doc["name"],
            description=doc.get("description", ""),
            workflow_id=doc["workflow_id"],
            output_schema=doc.get("output_schema", []),
            generator_prompt=doc.get("generator_prompt", ""),
            summary_fields=doc.get("summary_fields", []),
            display_config=doc.get("display_config", {}),
            status=doc.get("status", "active"),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
            created_by=doc.get("created_by")
        )

