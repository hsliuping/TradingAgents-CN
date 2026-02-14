"""
金融知识库管理 API

提供知识文档的 CRUD、语义搜索、批量初始化等接口。
底层使用 FinancialKnowledgeManager（Qdrant + Embedding）。
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_mongo_db

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


# ============================================================
# 请求 / 响应模型
# ============================================================


class KnowledgeDocRequest(BaseModel):
    """创建/更新知识文档请求"""
    id: str = Field(..., description="文档唯一标识，如 concept_sector_system")
    category: str = Field(..., description="分类: concept / tool_guide / methodology / pattern")
    title: str = Field(..., description="标题")
    content: str = Field(..., description="知识内容")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    priority: int = Field(default=5, ge=1, le=10, description="优先级 1-10，越小越高")


class KnowledgeDocResponse(BaseModel):
    """知识文档响应"""
    id: str
    category: str
    title: str
    content: str
    tags: List[str] = []
    priority: int = 5
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SearchRequest(BaseModel):
    """语义搜索请求"""
    query: str = Field(..., description="搜索文本")
    top_k: int = Field(default=3, ge=1, le=20, description="返回结果数量")
    category: Optional[str] = Field(default=None, description="可选分类筛选")


class SearchResultItem(BaseModel):
    """搜索结果条目"""
    doc_id: str
    title: str
    content: str
    category: str
    similarity: float
    tags: List[str] = []


class StatsResponse(BaseModel):
    """统计信息响应"""
    available: bool
    collection_name: str
    total_documents: int
    backend: str


class InitRequest(BaseModel):
    """初始化请求"""
    reset: bool = Field(default=False, description="是否清空后重灌")


# ============================================================
# 辅助函数
# ============================================================


def _get_km(db=None):
    """获取 FinancialKnowledgeManager 实例"""
    from core.knowledge import FinancialKnowledgeManager
    return FinancialKnowledgeManager(db=db)


# ============================================================
# API 路由
# ============================================================


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    """获取知识库统计信息"""
    km = _get_km(db=db)
    stats = km.get_stats()
    return StatsResponse(**stats)


@router.post("/search", response_model=List[SearchResultItem])
async def search_knowledge(
    req: SearchRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """语义搜索知识文档"""
    km = _get_km(db=db)
    if not km.available:
        raise HTTPException(status_code=503, detail="知识库不可用，请检查向量数据库和 Embedding 配置")

    snippets = km.search(query=req.query, top_k=req.top_k, category=req.category)
    return [
        SearchResultItem(
            doc_id=s.doc_id,
            title=s.title,
            content=s.content,
            category=s.category,
            similarity=round(s.similarity, 4),
            tags=s.tags,
        )
        for s in snippets
    ]


@router.post("/documents", response_model=Dict[str, Any])
async def add_document(
    req: KnowledgeDocRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """添加单条知识文档（幂等，相同 id 会覆盖）"""
    km = _get_km(db=db)
    if not km.available:
        raise HTTPException(status_code=503, detail="知识库不可用")

    from core.knowledge.financial_knowledge_manager import KnowledgeDocument
    doc = KnowledgeDocument(
        id=req.id,
        category=req.category,
        title=req.title,
        content=req.content,
        tags=req.tags,
        priority=req.priority,
    )
    ok = km.add_knowledge(doc)
    if not ok:
        raise HTTPException(status_code=500, detail="添加知识文档失败，请检查 Embedding 服务")
    return {"success": True, "id": req.id, "message": f"知识文档 '{req.title}' 已添加"}


@router.post("/documents/batch", response_model=Dict[str, Any])
async def add_documents_batch(
    docs: List[KnowledgeDocRequest],
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """批量添加知识文档"""
    km = _get_km(db=db)
    if not km.available:
        raise HTTPException(status_code=503, detail="知识库不可用")

    from core.knowledge.financial_knowledge_manager import KnowledgeDocument
    doc_objects = [
        KnowledgeDocument(
            id=d.id, category=d.category, title=d.title,
            content=d.content, tags=d.tags, priority=d.priority,
        )
        for d in docs
    ]
    success = km.add_knowledge_batch(doc_objects)
    return {
        "success": True,
        "total": len(docs),
        "added": success,
        "failed": len(docs) - success,
    }


@router.post("/init", response_model=Dict[str, Any])
async def init_knowledge_base(
    req: InitRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """
    使用内置知识数据初始化知识库。

    - reset=false: 增量模式（跳过已有）
    - reset=true: 清空后重灌
    """
    km = _get_km(db=db)
    if not km.available:
        raise HTTPException(status_code=503, detail="知识库不可用，请检查向量数据库和 Embedding 配置")

    if req.reset:
        km.clear_all()
        logger.info("🔄 [知识库API] 已清空知识库")

    from core.knowledge.knowledge_data import get_all_knowledge_documents
    from core.knowledge.financial_knowledge_manager import KnowledgeDocument

    all_docs_raw = get_all_knowledge_documents()
    docs = [KnowledgeDocument.from_dict(d) for d in all_docs_raw]
    success = km.add_knowledge_batch(docs)

    return {
        "success": True,
        "reset": req.reset,
        "total": len(docs),
        "added": success,
        "failed": len(docs) - success,
        "total_in_store": km.get_count(),
    }


@router.delete("/documents/{doc_id}", response_model=Dict[str, Any])
async def delete_document(
    doc_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """
    删除单条知识文档（通过 doc_id）。

    注意：当前 Qdrant 适配器不支持按 ID 删除单条文档，
    如需删除请使用 /init?reset=true 重新初始化。
    """
    # Qdrant 本地模式的 delete 需要知道 point UUID
    # 目前 VectorStoreInterface 没有 delete_by_id 方法
    # 提供一个占位接口，后续可扩展
    raise HTTPException(
        status_code=501,
        detail="单条删除暂未实现。请使用 POST /api/knowledge/init (reset=true) 重新初始化知识库。"
    )


@router.delete("/all", response_model=Dict[str, Any])
async def clear_all(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """清空所有知识文档"""
    km = _get_km(db=db)
    if not km.available:
        raise HTTPException(status_code=503, detail="知识库不可用")

    ok = km.clear_all()
    if not ok:
        raise HTTPException(status_code=500, detail="清空知识库失败")
    return {"success": True, "message": "知识库已清空", "total_in_store": km.get_count()}

