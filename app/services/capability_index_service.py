import hashlib
import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.capability_index import (
    CapabilityDocument,
    CapabilityIndexSyncResult,
    CapabilitySearchHit,
)
from core.agents.config import AgentMaintenanceStatus, BUILTIN_AGENTS
from core.llm.embedding_manager import EmbeddingManager
from core.memory.memory_manager import VectorStoreManager
from core.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)

CAPABILITY_INDEX_COLLECTION = "capability_registry"
CAPABILITY_INDEX_STATE_COLLECTION = "capability_index_state"
CAPABILITY_INDEX_STATE_KEY = "default"
CAPABILITY_INDEX_TOP_K = 24


class CapabilityIndexService:
    """统一能力索引服务。"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db
        self._embedding_manager = EmbeddingManager(db=db)
        self._vector_store_manager = VectorStoreManager()
        self._collection = None
        self._cached_documents: Dict[str, CapabilityDocument] = {}

    async def ensure_index(self, force: bool = False) -> CapabilityIndexSyncResult:
        documents, fingerprint, document_hashes = await self._collect_source_documents()
        state = await self._load_state()
        current_fingerprint = str(state.get("fingerprint") or "") if state else ""
        collection_count = int(state.get("indexed_documents") or 0) if state else 0
        previous_hashes = state.get("document_hashes") or {} if state else {}

        if not force and current_fingerprint == fingerprint and collection_count > 0:
            self._cached_documents = {doc.capability_id: doc for doc in documents}
            logger.info(
                "[CapabilityIndex] 📦 索引已存在，指纹匹配，跳过构建"
                "（%d 个工具 / %d 个已索引 / 后端: %s）",
                len(documents), collection_count, self._vector_store_manager.backend,
            )
            return CapabilityIndexSyncResult(
                collection_name=CAPABILITY_INDEX_COLLECTION,
                fingerprint=fingerprint,
                total_documents=len(documents),
                indexed_documents=collection_count,
                skipped_documents=max(len(documents) - collection_count, 0),
                vector_backend=self._vector_store_manager.backend,
                sync_mode="no_change",
            )

        # 检查 embedding 模型是否可用
        config = self._embedding_manager.get_config()
        if not config.get("has_provider"):
            logger.warning(
                "[CapabilityIndex] ⚠️ 未配置 embedding 模型，跳过索引构建"
                "（%d 个工具将使用关键词匹配回退）",
                len(documents),
            )
            self._cached_documents = {doc.capability_id: doc for doc in documents}
            return CapabilityIndexSyncResult(
                collection_name=CAPABILITY_INDEX_COLLECTION,
                fingerprint=fingerprint,
                total_documents=len(documents),
                indexed_documents=0,
                skipped_documents=len(documents),
                vector_backend=self._vector_store_manager.backend,
                sync_mode="skipped_no_embedding",
            )

        if force or not previous_hashes:
            # 预检查：先测试第一个 embedding 调用是否成功
            # 如果 API Key 无效或网络不通，快速跳过避免长时间超时
            test_embedding, _ = self._embedding_manager.get_embedding("test")
            if test_embedding is None:
                logger.warning(
                    "[CapabilityIndex] ⚠️ Embedding API 不可用，跳过索引构建"
                    "（%d 个工具将使用关键词匹配回退）",
                    len(documents),
                )
                self._cached_documents = {doc.capability_id: doc for doc in documents}
                return CapabilityIndexSyncResult(
                    collection_name=CAPABILITY_INDEX_COLLECTION,
                    fingerprint=fingerprint,
                    total_documents=len(documents),
                    indexed_documents=0,
                    skipped_documents=len(documents),
                    vector_backend=self._vector_store_manager.backend,
                    sync_mode="skipped_embedding_unavailable",
                )
            logger.info(
                "[CapabilityIndex] 🔄 开始构建索引（%d 个工具，向量维度: %d）...",
                len(documents), self._embedding_manager.get_embedding_dimension(),
            )
            result = await asyncio.to_thread(self._rebuild_index, documents, fingerprint)
        else:
            logger.info(
                "[CapabilityIndex] 🔄 增量同步索引（%d 个工具，%d 个已有索引）...",
                len(documents), collection_count,
            )
            result = await asyncio.to_thread(
                self._sync_index_incrementally,
                documents=documents,
                fingerprint=fingerprint,
                document_hashes=document_hashes,
                previous_hashes=previous_hashes,
                expected_count=collection_count,
            )

        await self._save_state(result, document_hashes)
        self._cached_documents = {doc.capability_id: doc for doc in documents}
        logger.info(
            "[CapabilityIndex] ✅ 索引就绪: %d/%d 已索引，%d 跳过，模式: %s",
            result.indexed_documents, result.total_documents,
            result.skipped_documents, result.sync_mode,
        )
        return result

    async def search_capabilities(
        self,
        query: str,
        top_k: int = CAPABILITY_INDEX_TOP_K,
        bindable_only: bool = False,
        source_types: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
    ) -> List[CapabilitySearchHit]:
        await self.ensure_index()
        documents = list(self._cached_documents.values())
        if not documents:
            return []

        allowed_sources = set(source_types or [])
        allowed_categories = set(categories or [])
        filtered_documents = [
            doc for doc in documents
            if (not bindable_only or doc.bindable)
            and (not allowed_sources or doc.source_type in allowed_sources)
            and (not allowed_categories or doc.category in allowed_categories)
        ]
        if not filtered_documents:
            return []

        hits = self._vector_search(query, top_k=max(top_k * 4, top_k))
        search_method = "vector"
        if not hits:
            hits = self._lexical_search(query, filtered_documents, top_k=max(top_k * 4, top_k))
            search_method = "lexical"

        filtered: List[CapabilitySearchHit] = []
        allowed_ids = {doc.capability_id for doc in filtered_documents}
        for hit in hits:
            capability = hit.capability
            if capability.capability_id not in allowed_ids:
                continue
            filtered.append(hit)
            if len(filtered) >= top_k:
                break

        if len(filtered) < top_k and hits:
            lexical_hits = self._lexical_search(query, filtered_documents, top_k=max(top_k * 2, top_k))
            seen_ids = {hit.capability.capability_id for hit in filtered}
            for hit in lexical_hits:
                if hit.capability.capability_id in seen_ids:
                    continue
                filtered.append(hit)
                if len(filtered) >= top_k:
                    break
        logger.debug(
            "[CapabilityIndex] search method=%s query_len=%d results=%d top3=%s",
            search_method,
            len(query),
            len(filtered),
            [(h.capability.capability_id, round(float(h.score or 0), 3)) for h in filtered[:3]],
        )
        return filtered

    async def list_capabilities(self) -> List[CapabilityDocument]:
        await self.ensure_index()
        return list(self._cached_documents.values())

    async def rebuild_index(self) -> CapabilityIndexSyncResult:
        return await self.ensure_index(force=True)

    @staticmethod
    async def refresh_after_change(db) -> None:
        """工具变更（删除/新增/修改）后触发索引同步，清理幽灵工具。

        增量同步会自动检测并删除已不存在的工具向量。
        不抛异常，失败只记录日志——搜索时的 allowed_ids 过滤会兜底。
        """
        try:
            service = CapabilityIndexService(db)
            result = await service.ensure_index()
            logger.info(
                "[CapabilityIndex] 工具变更后同步完成: mode=%s, total=%d, indexed=%d",
                result.sync_mode, result.total_documents, result.indexed_documents,
            )
        except Exception as e:
            logger.warning(f"[CapabilityIndex] 工具变更后同步失败: {e}")

    async def get_index_state(self) -> Dict[str, Any]:
        state = await self._load_state()
        return state or {}

    async def _collect_source_documents(self) -> Tuple[List[CapabilityDocument], str, Dict[str, str]]:
        registry_docs = self._build_registry_documents()
        await self._merge_skills_documents(registry_docs)
        await self._merge_external_skills_documents(registry_docs)
        await self._merge_agents_documents(registry_docs)  # 🔥 v3.0: Agent 纳入统一能力索引（含DB自定义）

        documents = sorted(registry_docs.values(), key=lambda item: (item.source_type, item.capability_id))
        payload = [
            {
                "capability_id": doc.capability_id,
                "registry_tool_id": doc.registry_tool_id,
                "source_type": doc.source_type,
                "status": doc.status,
                "bindable": doc.bindable,
                "fc_enabled": doc.fc_enabled,
                "category": doc.category,
                "name": doc.name,
                "description": doc.description,
                "when_to_use": doc.when_to_use,
                "when_not_to_use": doc.when_not_to_use,
                "returns": doc.returns,
                "related_tools": doc.related_tools,
                "coverage_terms": doc.coverage_terms,
                "retrieval_text": doc.retrieval_text,
                "data_source": doc.data_source,
                "capability_tags": doc.capability_tags,
                "tool_role_hint": doc.tool_role_hint,
                "output_shape": doc.output_shape,
                "preferred_for": doc.preferred_for,
                "not_replacement_for": doc.not_replacement_for,
            }
            for doc in documents
        ]
        fingerprint = hashlib.sha1(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        document_hashes = {
            doc.capability_id: hashlib.sha1(
                json.dumps(doc.model_dump(mode="json"), ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            for doc in documents
        }
        return documents, fingerprint, document_hashes

    def _build_registry_documents(self) -> Dict[str, CapabilityDocument]:
        registry = get_tool_registry()
        documents: Dict[str, CapabilityDocument] = {}
        for tool in registry.list_all():
            tool_id = str(tool.id or "").strip()
            if not tool_id:
                continue
            source_type = "mcp_tool" if str(tool.category) == "mcp" else "builtin_tool"
            coverage_terms = self._extract_coverage_terms(self._build_searchable_text(
                tool_id,
                str(tool.name or ""),
                str(tool.description or ""),
                str(tool.when_to_use or ""),
                str(tool.when_not_to_use or ""),
                str(tool.returns or ""),
                str(tool.data_source or ""),
                " ".join(tool.related_tools or []),
            ))
            doc = CapabilityDocument(
                capability_id=tool_id,
                registry_tool_id=tool_id,
                source_type=source_type,
                status="active",
                bindable=True,
                fc_enabled=bool(tool.fc_enabled),
                category=str(tool.category or ""),
                name=str(tool.name or tool_id),
                label=f"{tool_id} | {tool.name}",
                description=str(tool.description or ""),
                when_to_use=str(tool.when_to_use or ""),
                when_not_to_use=str(tool.when_not_to_use or ""),
                returns=str(tool.returns or ""),
                related_tools=[str(item) for item in (tool.related_tools or []) if str(item).strip()],
                coverage_terms=coverage_terms,
                retrieval_text=self._build_retrieval_text(
                    tool_id=tool_id,
                    name=str(tool.name or tool_id),
                    source_type=source_type,
                    category=str(tool.category or ""),
                    description=str(tool.description or ""),
                    when_to_use=str(tool.when_to_use or ""),
                    when_not_to_use=str(tool.when_not_to_use or ""),
                    returns=str(tool.returns or ""),
                    related_tools=[str(item) for item in (tool.related_tools or []) if str(item).strip()],
                    data_source=str(tool.data_source or ""),
                    coverage_terms=coverage_terms,
                    capability_tags=[str(item) for item in (tool.capability_tags or []) if str(item).strip()],
                    tool_role_hint=str(tool.tool_role_hint or ""),
                    output_shape=str(tool.output_shape or ""),
                    preferred_for=[str(item) for item in (tool.preferred_for or []) if str(item).strip()],
                    not_replacement_for=[str(item) for item in (tool.not_replacement_for or []) if str(item).strip()],
                ),
                data_source=str(tool.data_source or ""),
                capability_tags=[str(item) for item in (tool.capability_tags or []) if str(item).strip()],
                tool_role_hint=str(tool.tool_role_hint or ""),
                output_shape=str(tool.output_shape or ""),
                preferred_for=[str(item) for item in (tool.preferred_for or []) if str(item).strip()],
                not_replacement_for=[str(item) for item in (tool.not_replacement_for or []) if str(item).strip()],
                metadata={
                    "is_online": bool(tool.is_online),
                    "timeout_tier": str(tool.timeout_tier or ""),
                    "parameters": [p.model_dump(mode="json") for p in (tool.parameters or [])],
                },
            )
            documents[tool_id] = doc
        return documents

    async def _merge_skills_documents(self, documents: Dict[str, CapabilityDocument]) -> None:
        cursor = self._db.skills.find({"enabled": True})
        async for doc in cursor:
            skill_name = str(doc.get("name") or "").strip()
            if not skill_name:
                continue
            tool_id = skill_name.replace("-", "_")
            description = str(doc.get("description") or "").strip()
            implementation = doc.get("implementation")
            parameters = doc.get("parameters") or []
            bindable = bool(implementation and parameters and tool_id in documents)

            base = documents.get(tool_id)
            merged = self._merge_capability_document(
                base=base,
                capability_id=tool_id,
                registry_tool_id=tool_id if tool_id in documents else None,
                source_type="skill",
                status="active",
                bindable=bindable,
                fc_enabled=bool(base.fc_enabled) if base else True,
                category=str(doc.get("category") or getattr(base, "category", "utility") or "utility"),
                name=skill_name,
                label=(base.label if base else f"{tool_id} | {skill_name}"),
                description=description or (base.description if base else ""),
                when_to_use=str(doc.get("when_to_use") or getattr(base, "when_to_use", "") or ""),
                when_not_to_use=str(doc.get("when_not_to_use") or getattr(base, "when_not_to_use", "") or ""),
                returns=str(doc.get("returns") or getattr(base, "returns", "") or ""),
                related_tools=list(getattr(base, "related_tools", []) or []),
                data_source=str(doc.get("data_source") or getattr(base, "data_source", "") or ""),
                capability_tags=list(getattr(base, "capability_tags", []) or []),
                tool_role_hint=str(getattr(base, "tool_role_hint", "") or ""),
                output_shape=str(getattr(base, "output_shape", "") or ""),
                preferred_for=list(getattr(base, "preferred_for", []) or []),
                not_replacement_for=list(getattr(base, "not_replacement_for", []) or []),
                metadata={
                    **(base.metadata if base else {}),
                    "skill_type": doc.get("skill_type"),
                    "source_url": doc.get("source_url"),
                },
            )
            documents[tool_id] = merged

    async def _merge_external_skills_documents(self, documents: Dict[str, CapabilityDocument]) -> None:
        cursor = self._db.external_skills.find({"status": {"$in": ["active", "draft"]}})
        async for doc in cursor:
            tool_id = str(doc.get("tool_id") or "").strip()
            if not tool_id:
                continue
            status = str(doc.get("status") or "draft")
            display_name = str(doc.get("display_name") or tool_id).strip()
            description = str(doc.get("description") or "").strip()
            base = documents.get(tool_id)
            bindable = status == "active" and tool_id in documents
            metadata = dict(doc.get("metadata") or {})
            capability_tags = self._dedupe([
                *list(getattr(base, "capability_tags", []) or []),
                *[str(item) for item in (doc.get("capability_tags") or metadata.get("capability_tags") or []) if str(item).strip()],
            ])
            tool_role_hint = str(doc.get("tool_role_hint") or metadata.get("tool_role_hint") or getattr(base, "tool_role_hint", "") or "").strip()
            output_shape = str(doc.get("output_shape") or metadata.get("output_shape") or getattr(base, "output_shape", "") or "").strip()
            preferred_for = self._dedupe([
                *list(getattr(base, "preferred_for", []) or []),
                *[str(item) for item in (doc.get("preferred_for") or metadata.get("preferred_for") or []) if str(item).strip()],
            ])
            not_replacement_for = self._dedupe([
                *list(getattr(base, "not_replacement_for", []) or []),
                *[str(item) for item in (doc.get("not_replacement_for") or metadata.get("not_replacement_for") or []) if str(item).strip()],
            ])
            merged = self._merge_capability_document(
                base=base,
                capability_id=tool_id,
                registry_tool_id=tool_id if tool_id in documents else None,
                source_type="external_skill",
                status=status,
                bindable=bindable,
                fc_enabled=bool(base.fc_enabled) if base else True,
                category=str(doc.get("category") or getattr(base, "category", "external") or "external"),
                name=display_name,
                label=(base.label if base else f"{tool_id} | {display_name}"),
                description=description or (base.description if base else ""),
                when_to_use=str(doc.get("when_to_use") or getattr(base, "when_to_use", "") or ""),
                when_not_to_use=str(doc.get("when_not_to_use") or getattr(base, "when_not_to_use", "") or ""),
                returns=str(doc.get("returns") or getattr(base, "returns", "") or ""),
                related_tools=list(getattr(base, "related_tools", []) or []),
                data_source=str(doc.get("data_source") or getattr(base, "data_source", "") or ""),
                capability_tags=capability_tags,
                tool_role_hint=tool_role_hint,
                output_shape=output_shape,
                preferred_for=preferred_for,
                not_replacement_for=not_replacement_for,
                metadata={
                    **(base.metadata if base else {}),
                    "session_id": doc.get("session_id"),
                    "source": doc.get("source"),
                },
            )
            documents[tool_id] = merged

    async def _merge_agents_documents(self, documents: Dict[str, CapabilityDocument]) -> None:
        """
        将 BUILTIN_AGENTS + MongoDB 自定义 Agent 合并到能力索引

        每个 Agent 作为一个独立的能力项，source_type="agent"。
        内置只收录 MAINTAINED 状态的，DB 只收录 enabled=True 的。
        """
        before_count = len(documents)
        # ── 1. 内置 Agent ──
        builtin_added = 0
        for agent_id, meta in BUILTIN_AGENTS.items():
            status = meta.maintenance_status
            if status not in (AgentMaintenanceStatus.MAINTAINED,):
                logger.debug(
                    "[CapabilityIndex] 跳过 Agent: %s (status=%s)",
                    agent_id, status.value if hasattr(status, 'value') else status,
                )
                continue
            self._add_agent_document(
                documents, agent_id,
                name=meta.name,
                description=meta.description or "",
                category=meta.category.value if hasattr(meta.category, 'value') else str(meta.category),
                default_tools=list(meta.default_tools) if meta.default_tools else [],
                inputs=[i.name for i in meta.inputs] if meta.inputs else [],
                outputs=[o.name for o in meta.outputs] if meta.outputs else [],
                output_field=meta.output_field or "",
                source="builtin",
            )
            builtin_added += 1

        logger.info(
            "[CapabilityIndex] 📥 Agent 文档: 内置 %d 个, 合并前总文档 %d, 合并后 %d",
            builtin_added, before_count, len(documents),
        )

        # ── 2. MongoDB 自定义 Agent ──
        if self._db is not None:
            try:
                builtin_ids = {agent_id for agent_id, _ in BUILTIN_AGENTS.items()}
                cursor = self._db.agent_configs.find({"enabled": True})
                async for doc in cursor:
                    aid = doc.get("agent_id", "").strip()
                    if not aid or aid in builtin_ids:
                        continue
                    self._add_agent_document(
                        documents, aid,
                        name=doc.get("name", aid),
                        description=doc.get("description", ""),
                        category=doc.get("category", "custom"),
                        default_tools=doc.get("default_tools", []) or [],
                        inputs=doc.get("inputs", []) or [],
                        outputs=doc.get("outputs", []) or [],
                        output_field=doc.get("output_field", doc.get("report_label", "")) or "",
                        source="database",
                    )
                    logger.info(
                        f"📥 [CapabilityIndex] 已索引自定义 Agent: {aid} ({doc.get('name', '')})"
                    )
            except Exception as e:
                logger.warning(f"从 MongoDB 加载自定义 Agent 到索引失败: {e}")

    def _add_agent_document(
        self, documents: Dict[str, CapabilityDocument],
        agent_id: str, name: str, description: str, category: str,
        default_tools: list, inputs: list, outputs: list,
        output_field: str, source: str,
    ) -> None:
        """为单个 Agent 构建 CapabilityDocument 并加入索引"""
        safe_inputs = self._safe_list_to_str(inputs)
        safe_outputs = self._safe_list_to_str(outputs)
        safe_tools = self._safe_list_to_str(default_tools)

        when_to_use_parts = []
        if safe_inputs:
            when_to_use_parts.append(f"需要的输入: {', '.join(safe_inputs)}")
        if safe_outputs:
            when_to_use_parts.append(f"产生的输出: {', '.join(safe_outputs)}")
        if safe_tools:
            when_to_use_parts.append(f"默认工具: {', '.join(safe_tools)}")
        if output_field:
            when_to_use_parts.append(f"产出字段: {output_field}")

        documents[agent_id] = self._merge_capability_document(
            base=None,
            capability_id=agent_id,
            registry_tool_id=None,
            source_type="agent",
            status="active",
            bindable=True,
            fc_enabled=False,
            category=category,
            name=name,
            label=f"{agent_id} | {name}",
            description=description,
            when_to_use="; ".join(when_to_use_parts) if when_to_use_parts else "",
            when_not_to_use="",
            returns="报告文本",
            related_tools=list(safe_tools),
            data_source=source,
            capability_tags=list(safe_tools),
            tool_role_hint="agent",
            output_shape="report",
            preferred_for=[],
            not_replacement_for=[],
            metadata={
                "agent_id": agent_id,
                "source": source,
                "output_field": output_field,
                "default_tools": list(safe_tools),
                "has_inputs": len(safe_inputs) > 0,
                "has_outputs": len(safe_outputs) > 0,
            },
        )

    @staticmethod
    def _safe_list_to_str(items: list) -> List[str]:
        """将列表安全转为字符串列表，处理 dict 元素和非 list 输入"""
        if not items:
            return []
        if not isinstance(items, list):
            return [str(items)]
        result = []
        for item in items:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                # 尝试取常用字段名，取不到则 str()
                for key in ("field", "name", "desc", "key", "label"):
                    if key in item:
                        result.append(str(item[key]))
                        break
                else:
                    result.append(str(item))
            else:
                result.append(str(item))
        return result

    def _merge_capability_document(
        self,
        base: Optional[CapabilityDocument],
        capability_id: str,
        registry_tool_id: Optional[str],
        source_type: str,
        status: str,
        bindable: bool,
        fc_enabled: bool,
        category: str,
        name: str,
        label: str,
        description: str,
        when_to_use: str,
        when_not_to_use: str,
        returns: str,
        related_tools: List[str],
        data_source: str,
        metadata: Dict[str, Any],
        capability_tags: Optional[List[str]] = None,
        tool_role_hint: str = "",
        output_shape: str = "",
        preferred_for: Optional[List[str]] = None,
        not_replacement_for: Optional[List[str]] = None,
    ) -> CapabilityDocument:
        searchable = self._build_searchable_text(
            capability_id,
            name,
            description,
            when_to_use,
            when_not_to_use,
            returns,
            data_source,
            " ".join(related_tools),
        )
        coverage_terms = self._extract_coverage_terms(searchable)
        return CapabilityDocument(
            capability_id=capability_id,
            registry_tool_id=registry_tool_id,
            source_type=source_type,
            status=status,
            bindable=bindable,
            fc_enabled=fc_enabled,
            category=category,
            name=name,
            label=label,
            description=description,
            when_to_use=when_to_use,
            when_not_to_use=when_not_to_use,
            returns=returns,
            related_tools=related_tools,
            coverage_terms=coverage_terms,
            retrieval_text=self._build_retrieval_text(
                tool_id=capability_id,
                name=name,
                source_type=source_type,
                category=category,
                description=description,
                when_to_use=when_to_use,
                when_not_to_use=when_not_to_use,
                returns=returns,
                related_tools=related_tools,
                data_source=data_source,
                coverage_terms=coverage_terms,
                capability_tags=capability_tags or [],
                tool_role_hint=tool_role_hint,
                output_shape=output_shape,
                preferred_for=preferred_for or [],
                not_replacement_for=not_replacement_for or [],
            ),
            data_source=data_source,
            capability_tags=self._dedupe([str(item) for item in (capability_tags or []) if str(item).strip()]),
            tool_role_hint=str(tool_role_hint or ""),
            output_shape=str(output_shape or ""),
            preferred_for=self._dedupe([str(item) for item in (preferred_for or []) if str(item).strip()]),
            not_replacement_for=self._dedupe([str(item) for item in (not_replacement_for or []) if str(item).strip()]),
            metadata=metadata,
        )

    def _build_retrieval_text(
        self,
        tool_id: str,
        name: str,
        source_type: str,
        category: str,
        description: str,
        when_to_use: str,
        when_not_to_use: str,
        returns: str,
        related_tools: List[str],
        data_source: str,
        coverage_terms: List[str],
        capability_tags: Optional[List[str]] = None,
        tool_role_hint: str = "",
        output_shape: str = "",
        preferred_for: Optional[List[str]] = None,
        not_replacement_for: Optional[List[str]] = None,
    ) -> str:
        parts = [
            f"tool_id: {tool_id}",
            f"name: {name}",
            f"source_type: {source_type}",
            f"category: {category}",
            f"description: {description}",
            f"when_to_use: {when_to_use}",
            f"when_not_to_use: {when_not_to_use}",
            f"returns: {returns}",
            f"related_tools: {' '.join(related_tools)}",
            f"data_source: {data_source}",
            f"coverage_terms: {' '.join(coverage_terms)}",
            f"capability_tags: {' '.join(capability_tags or [])}",
            f"tool_role_hint: {tool_role_hint}",
            f"output_shape: {output_shape}",
            f"preferred_for: {' '.join(preferred_for or [])}",
            f"not_replacement_for: {' '.join(not_replacement_for or [])}",
        ]
        return "\n".join(part for part in parts if part.strip())

    def _build_searchable_text(self, *parts: str) -> str:
        return " ".join(str(part or "").strip() for part in parts if str(part or "").strip()).lower()

    def _extract_coverage_terms(self, text: str) -> List[str]:
        import re

        searchable = str(text or "").lower()
        patterns = [
            # ── 估值类 ──
            (r"(?<![a-z0-9])(valuation|valuations)(?![a-z0-9])", "valuation"),
            (r"(?<![a-z0-9])dcf(?![a-z0-9])", "dcf"),
            (r"(?<![a-z0-9])pe(?![a-z0-9])|市盈率|pe_ttm|p/e", "pe"),
            (r"(?<![a-z0-9])pb(?![a-z0-9])|市净率|pb_mrq", "pb"),
            (r"(?<![a-z0-9])peg(?![a-z0-9])", "peg"),
            (r"(?<![a-z0-9])ps(?![a-z0-9])", "ps"),
            (r"ev/?ebitda", "ev_ebitda"),
            (r"可比公司|同业对比|peer comparison|peer", "peer_comparison"),
            (r"估值|估价|定价|目标价|价格区间|估值区间|相对估值", "valuation_cn"),
            (r"增长|growth|营收同比|净利润同比|cagr", "growth"),
            (r"现金流|cashflow|fcf|ocf|经营现金流|自由现金流", "cashflow"),
            (r"roe|roa|roic|毛利率|净利率|利润率|盈利稳定性|资本效率|piotroski|altman|beneish", "quality"),
            (r"历史|多年|年报序列|时间序列|trend|series", "historical_series"),
            (r"分位|percentile|估值分位", "percentile"),
            (r"ma20|rsi14|rsi|kdj|macd|技术指标|technical", "technical"),
            # ── 资产质量 / 基本面风险 ──
            (r"应收账款|receivables|(?<![a-z0-9])dso(?![a-z0-9])|账龄|坏账|bad_debt|回款|收款", "asset_quality_receivables"),
            (r"存货|inventory|(?<![a-z0-9])dio(?![a-z0-9])|存货周转|跌价", "asset_quality_inventory"),
            (r"资产质量|asset_quality|资产减值", "asset_quality"),
            (r"偿债|solvency|debt_to_equity|资产负债率|利息覆盖|利息保障|debt_structure|有息负债", "solvency"),
            (r"流动性|liquidity|current_ratio|quick_ratio|流动比率|速动比率|短期偿债", "liquidity"),
            (r"商誉|goodwill|减值测试|impairment", "goodwill"),
            (r"破产|bankruptcy|ohlson|z_score|zscore|altman|beneish|mscore|oscore|欺诈|fraud|财务造假|财务舞弊|风险|risk_adjusted|risk_profile|risk_event|risk_flag", "risk"),
            # ── 资本成本 / 风险度量 / 投资组合 / 归因分析 / 统计分析 ──
            (r"wacc|capm|cost_of_equity|cost_of_debt|折现率|资本成本|加权平均资本成本", "cost_of_capital"),
            (r"(?<![a-z0-9])beta(?![a-z0-9])|(?<![a-z0-9])alpha(?![a-z0-9])|sharpe|sortino|treynor|calmar|jensen|information_ratio|(?<![a-z0-9])var(?![a-z0-9])|cvar|volatility|波动率|最大回撤|max_drawdown|downside|风险调整", "risk_metrics"),
            (r"portfolio|组合|efficient_frontier|monte_carlo|蒙特卡洛|马科维茨|markowitz|optimal_weight|最优权重|scenario_analysis|情景分析", "portfolio"),
            (r"attribution|归因|brinson|factor_attribution|sector_attribution", "attribution"),
            (r"correlation|cointegration|协整|regression|回归|normality|正态|stationarity|平稳|(?<![a-z0-9])adf(?![a-z0-9])|garch|ewma|统计|statistical", "statistics"),
            # ── 筛选 / 宏观 / 股息 / 筹码 / 量价 ──
            (r"screen|筛选|filter|过滤|选股", "screening"),
            (r"macro|宏观|economic_cycle|经济周期|monetary|货币环境|美林时钟|yield_curve|收益率曲线|景气|recession|衰退|recovery|复苏|overheating|过热|stagflation|滞胀", "macro"),
            (r"dividend|股息|分红|送股|红利|股利|送转|每股分红", "dividend"),
            (r"chip|筹码|获利比例|平均成本|集中度", "chip_distribution"),
            (r"vwap|obv|turnover|换手率|成交量|量价|volume_profile|成交额|主力净流入|资金流|capital_flow|fund_flow", "volume_analysis"),
            # ── 技术分析扩展 ──
            (r"pivot|支撑|阻力|压力位|fibonacci|斐波那契|枢轴点|颈线|趋势线", "support_resistance"),
            (r"candlestick|k线|k 线|chart_pattern|形态|头肩|双顶|双底|三角形|旗形|楔形|缺口|十字星|锤头", "chart_pattern"),
            # ── 债券 / 期权 / 事件研究 ──
            (r"bond|债券|久期|duration|凸性|convexity|credit_spread|信用利差|国债|企业债|可转债", "bond"),
            (r"option|期权|black_scholes|greeks|希腊字母|delta|gamma|theta|vega|rho|implied_volatility|隐含波动率|行权价|strike", "option"),
            (r"event_study|事件研究|事件日|事件驱动|event_driven|公告事件|监管事件|event_timeline", "event_study"),
            # ── 财务报表 / ETF / 内部人 / 市场宽度 / 证券主数据 ──
            (r"income_analysis|利润表|营收|主营业务|main_business|收入结构|费用分析", "income_statement"),
            (r"financial_statement|财务报表|balance_sheet|资产负债表|financial_statements|fundamentals_unified|财务数据", "financial_statements"),
            (r"(?<![a-z0-9])etf(?![a-z0-9])|基金基本面", "etf_fundamentals"),
            (r"insider|内部人|内部人士|insider_sentiment|insider_transaction", "insider"),
            (r"market_breadth|市场宽度|market_overview|市场概览|market_environment|市场环境|market_cycle|市场周期|涨跌家数|breadth|index_data|指数数据|sector_data|板块数据|sector_analysis|板块分析", "market_breadth"),
            (r"security_master|证券主数据|上市状态|stock_master|证券信息|交易所|市值", "security_master"),
        ]
        matched: List[str] = []
        for pattern, normalized in patterns:
            if re.search(pattern, searchable):
                matched.append(normalized)
        return self._dedupe(matched)

    def _rebuild_index(
        self,
        documents: List[CapabilityDocument],
        fingerprint: str,
    ) -> CapabilityIndexSyncResult:
        try:
            self._vector_store_manager.delete_collection(CAPABILITY_INDEX_COLLECTION)
        except Exception:
            pass

        self._collection = self._vector_store_manager.get_or_create_collection(
            CAPABILITY_INDEX_COLLECTION,
            vector_size=self._embedding_manager.get_embedding_dimension(),
        )

        indexed = 0
        skipped = 0
        total = len(documents)
        batch_size = max(1, total // 10)  # 每 10% 输出一次进度
        consecutive_failures = 0  # 🔥 连续失败计数器，超过阈值则跳过剩余文档
        max_consecutive_failures = 5
        for idx, document in enumerate(documents):
            embedding, provider = self._embedding_manager.get_embedding(document.retrieval_text)
            if embedding is None:
                skipped += 1
                consecutive_failures += 1
                # 🔥 连续失败超过阈值，跳过剩余文档避免长时间阻塞
                if consecutive_failures >= max_consecutive_failures:
                    remaining = total - idx - 1
                    logger.warning(
                        "[CapabilityIndex] ⚠️ 连续 %d 次失败，跳过剩余 %d 个文档（Embedding API 不可用）",
                        consecutive_failures, remaining,
                    )
                    skipped += remaining
                    break
                continue
            consecutive_failures = 0  # 成功则重置
            metadata = document.model_dump(mode="json")
            metadata["embedding_provider"] = provider
            self._collection.add(
                documents=[document.retrieval_text],
                embeddings=[embedding],
                metadatas=[metadata],
                ids=[str(uuid.uuid5(uuid.NAMESPACE_DNS, document.capability_id))],
            )
            indexed += 1
            if indexed % batch_size == 0 or idx == total - 1:
                logger.info(
                    "[CapabilityIndex] 构建中... %d/%d (%d 跳过)",
                    indexed, total, skipped,
                )

        return CapabilityIndexSyncResult(
            collection_name=CAPABILITY_INDEX_COLLECTION,
            fingerprint=fingerprint,
            total_documents=len(documents),
            indexed_documents=indexed,
            skipped_documents=skipped,
            vector_backend=self._vector_store_manager.backend,
            sync_mode="full_rebuild",
        )

    def _sync_index_incrementally(
        self,
        documents: List[CapabilityDocument],
        fingerprint: str,
        document_hashes: Dict[str, str],
        previous_hashes: Dict[str, str],
        expected_count: int,
    ) -> CapabilityIndexSyncResult:
        self._collection = self._vector_store_manager.get_or_create_collection(
            CAPABILITY_INDEX_COLLECTION,
            vector_size=self._embedding_manager.get_embedding_dimension(),
        )

        current_count = self._collection.count()
        if expected_count > 0 and current_count == 0 and documents:
            logger.warning(
                "[CapabilityIndex] 检测到状态存在但向量集合为空，回退为全量重建: expected=%s actual=%s",
                expected_count,
                current_count,
            )
            return self._rebuild_index(documents, fingerprint)

        docs_by_id = {doc.capability_id: doc for doc in documents}
        deleted_ids = sorted(set(previous_hashes.keys()) - set(document_hashes.keys()))
        changed_ids = sorted(
            capability_id
            for capability_id, doc_hash in document_hashes.items()
            if previous_hashes.get(capability_id) != doc_hash
        )

        deleted_count = 0
        if deleted_ids:
            point_ids = [self._build_point_id(capability_id) for capability_id in deleted_ids]
            if not self._collection.delete_ids(point_ids):
                logger.warning("[CapabilityIndex] 增量删除失败，回退为全量重建")
                return self._rebuild_index(documents, fingerprint)
            deleted_count = len(deleted_ids)

        upserted = 0
        skipped = 0
        consecutive_failures = 0  # 🔥 连续失败计数器
        max_consecutive_failures = 5
        if changed_ids:
            upsert_documents: List[str] = []
            upsert_embeddings: List[List[float]] = []
            upsert_metadatas: List[Dict[str, Any]] = []
            upsert_ids: List[str] = []

            for capability_id in changed_ids:
                document = docs_by_id[capability_id]
                embedding, provider = self._embedding_manager.get_embedding(document.retrieval_text)
                if embedding is None:
                    skipped += 1
                    consecutive_failures += 1
                    # 🔥 连续失败超过阈值，跳过剩余变更文档
                    if consecutive_failures >= max_consecutive_failures:
                        remaining = len(changed_ids) - len(upsert_ids) - skipped
                        logger.warning(
                            "[CapabilityIndex] ⚠️ 增量同步连续 %d 次失败，跳过剩余 %d 个文档",
                            consecutive_failures, remaining,
                        )
                        skipped += remaining
                        break
                    continue
                consecutive_failures = 0  # 成功则重置
                metadata = document.model_dump(mode="json")
                metadata["embedding_provider"] = provider
                upsert_documents.append(document.retrieval_text)
                upsert_embeddings.append(embedding)
                upsert_metadatas.append(metadata)
                upsert_ids.append(self._build_point_id(document.capability_id))

            if upsert_ids and not self._collection.add(
                documents=upsert_documents,
                embeddings=upsert_embeddings,
                metadatas=upsert_metadatas,
                ids=upsert_ids,
            ):
                logger.warning("[CapabilityIndex] 增量 upsert 失败，回退为全量重建")
                return self._rebuild_index(documents, fingerprint)
            upserted = len(upsert_ids)

        indexed_documents = self._collection.count()
        return CapabilityIndexSyncResult(
            collection_name=CAPABILITY_INDEX_COLLECTION,
            fingerprint=fingerprint,
            total_documents=len(documents),
            indexed_documents=indexed_documents,
            skipped_documents=skipped,
            vector_backend=self._vector_store_manager.backend,
            sync_mode="incremental_sync",
        )

    def _build_point_id(self, capability_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, capability_id))

    def _vector_search(self, query: str, top_k: int) -> List[CapabilitySearchHit]:
        if not query.strip():
            return []
        try:
            if self._collection is None:
                self._collection = self._vector_store_manager.get_or_create_collection(
                    CAPABILITY_INDEX_COLLECTION,
                    vector_size=self._embedding_manager.get_embedding_dimension(),
                )
            query_embedding, _provider = self._embedding_manager.get_embedding(query)
            if query_embedding is None:
                return []
            result = self._collection.query(query_embeddings=[query_embedding], n_results=top_k)
            hits: List[CapabilitySearchHit] = []
            documents = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]
            for _doc_text, metadata, distance in zip(documents, metadatas, distances):
                capability = CapabilityDocument.model_validate(metadata)
                hits.append(CapabilitySearchHit(capability=capability, score=round(1.0 - float(distance), 4)))
            return hits
        except Exception as exc:
            logger.warning("[CapabilityIndex] 向量检索失败，回退词法检索: %s", exc)
            return []

    def _lexical_search(
        self,
        query: str,
        documents: Iterable[CapabilityDocument],
        top_k: int,
    ) -> List[CapabilitySearchHit]:
        tokens = [token for token in self._tokenize(query) if token]
        scored: List[CapabilitySearchHit] = []
        for doc in documents:
            haystack = self._build_searchable_text(
                doc.capability_id,
                doc.name,
                doc.description,
                doc.when_to_use,
                doc.returns,
                " ".join(doc.coverage_terms),
                " ".join(doc.capability_tags),
                " ".join(doc.preferred_for),
            )
            score = 0.0
            for token in tokens:
                if token in haystack:
                    score += 1.0
            if score > 0:
                scored.append(CapabilitySearchHit(capability=doc, score=score / max(len(tokens), 1)))
        scored.sort(key=lambda item: (-item.score, item.capability.label))
        return scored[:top_k]

    def _tokenize(self, text: str) -> List[str]:
        import re

        pieces = re.split(r"[^0-9A-Za-z\u4e00-\u9fff_]+", str(text or "").lower())
        return [piece for piece in pieces if piece and len(piece) > 1]

    def _dedupe(self, items: List[str]) -> List[str]:
        seen = set()
        results = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            results.append(item)
        return results

    async def _load_state(self) -> Optional[Dict[str, Any]]:
        return await self._db[CAPABILITY_INDEX_STATE_COLLECTION].find_one({"_id": CAPABILITY_INDEX_STATE_KEY})

    async def _save_state(self, result: CapabilityIndexSyncResult, document_hashes: Dict[str, str]) -> None:
        payload = result.model_dump(mode="json")
        payload["_id"] = CAPABILITY_INDEX_STATE_KEY
        payload["document_hashes"] = document_hashes
        await self._db[CAPABILITY_INDEX_STATE_COLLECTION].update_one(
            {"_id": CAPABILITY_INDEX_STATE_KEY},
            {"$set": payload},
            upsert=True,
        )
