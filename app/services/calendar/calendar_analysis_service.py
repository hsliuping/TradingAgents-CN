from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.core.database import get_mongo_db, get_redis_client
from app.models.calendar import CalendarAIResult, CalendarAnalysisInDB, CalendarAnalysisStatus
from app.services.calendar.calendar_queue_service import get_calendar_queue_service
from app.services.calendar.calendar_service import get_calendar_service
from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
from tradingagents.llm_adapters.openai_compatible_base import create_openai_compatible_llm


class CalendarAnalysisService:
    def __init__(self):
        self.redis = get_redis_client()
        self.queue = get_calendar_queue_service()
        self.calendar = get_calendar_service()

    async def enqueue_analysis(
        self,
        event_id: str,
        requested_by: str,
        model_name: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        db = get_mongo_db()
        if not force_refresh:
            existing = await db.calendar_ai_analyses.find_one(
                {"event_id": event_id, "status": CalendarAnalysisStatus.COMPLETED.value},
                sort=[("created_at", -1)],
                projection={"analysis_id": 1, "task_id": 1},
            )
            if existing:
                return {
                    "analysis_id": existing.get("analysis_id"),
                    "task_id": existing.get("task_id"),
                    "status": CalendarAnalysisStatus.COMPLETED.value,
                }

        task_id = await self.queue.enqueue(event_id=event_id, model_name=model_name, requested_by=requested_by)
        analysis_id = str(uuid.uuid4())

        now = datetime.utcnow()
        await db.calendar_ai_analyses.insert_one(
            CalendarAnalysisInDB(
                analysis_id=analysis_id,
                task_id=task_id,
                event_id=event_id,
                status=CalendarAnalysisStatus.QUEUED,
                model_provider=None,
                model_name=model_name,
                prompt_version="v1",
                input_snapshot={},
                result=None,
                error_message=None,
                created_at=now,
                updated_at=now,
            ).model_dump()
        )
        await self._set_progress(task_id, {"status": "queued", "progress": 0, "message": "已入队"})

        payload: Dict[str, Any] = {
            "task_id": task_id,
            "event_id": event_id,
            "model_name": model_name,
        }
        asyncio.create_task(self.run_task(payload))

        return {"analysis_id": analysis_id, "task_id": task_id, "status": CalendarAnalysisStatus.QUEUED.value}

    async def run_task(self, payload: Dict[str, Any]) -> None:
        task_id = str(payload.get("task_id") or "")
        event_id = str(payload.get("event_id") or "")
        model_name = payload.get("model_name")
        if not task_id or not event_id:
            return

        db = get_mongo_db()
        now = datetime.utcnow()
        await db.calendar_ai_analyses.update_one(
            {"task_id": task_id},
            {"$set": {"status": CalendarAnalysisStatus.RUNNING.value, "updated_at": now}},
        )
        await self._set_progress(task_id, {"status": "running", "progress": 5, "message": "开始分析"})

        try:
            event = await self.calendar.get_event(event_id)
            if not event:
                raise ValueError("event not found")

            snapshot = dict(event)
            await db.calendar_ai_analyses.update_one(
                {"task_id": task_id},
                {"$set": {"input_snapshot": snapshot, "updated_at": datetime.utcnow()}},
            )

            await self._set_progress(task_id, {"status": "running", "progress": 20, "message": "准备模型"})

            model = model_name or "deepseek-chat"
            provider_info = get_provider_and_url_by_model_sync(model)
            provider = provider_info.get("provider")
            api_key = provider_info.get("api_key")
            backend_url = provider_info.get("backend_url")

            llm = create_openai_compatible_llm(
                provider=provider,
                model=model,
                api_key=api_key,
                temperature=0.2,
                max_tokens=1800,
                base_url=backend_url,
            )

            await db.calendar_ai_analyses.update_one(
                {"task_id": task_id},
                {"$set": {"model_provider": provider, "model_name": model, "updated_at": datetime.utcnow()}},
            )

            await self._set_progress(task_id, {"status": "running", "progress": 45, "message": "调用大模型"})

            input_payload = {
                "event": {
                    "title": snapshot.get("title"),
                    "summary": snapshot.get("summary"),
                    "content": snapshot.get("content"),
                    "start_time": str(snapshot.get("start_time")),
                    "end_time": str(snapshot.get("end_time")) if snapshot.get("end_time") else None,
                    "date": str(snapshot.get("date")),
                    "timezone": snapshot.get("timezone"),
                    "region": snapshot.get("region"),
                    "category": snapshot.get("category"),
                    "importance": snapshot.get("importance"),
                    "tags": snapshot.get("tags"),
                },
                "output_schema": {
                    "event_summary": "string",
                    "themes": [{"theme": "string", "rationale": "string", "confidence": 0.0}],
                    "tradability": {
                        "score": 0,
                        "reason": "string",
                        "time_window": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "key_dates": []},
                    },
                    "concepts": [{"concept": "string", "why": "string", "risk": "string"}],
                    "related_stocks": [
                        {"market": "A股", "code": "000001", "name": "示例", "reason": "string", "confidence": 0.0}
                    ],
                    "risks": ["string"],
                    "validation_signals": ["string"],
                    "unknowns": ["string"],
                    "disclaimer": "string",
                },
            }
            input_json = json.dumps(input_payload, ensure_ascii=False)

            prompt = self._build_prompt()
            chain = prompt | llm
            result_msg = chain.invoke({"input_json": input_json})
            content = getattr(result_msg, "content", "") or ""

            await self._set_progress(task_id, {"status": "running", "progress": 75, "message": "解析结果"})

            parsed = self._extract_json(content)
            ai = CalendarAIResult(**parsed)

            now = datetime.utcnow()
            await db.calendar_ai_analyses.update_one(
                {"task_id": task_id},
                {"$set": {"status": CalendarAnalysisStatus.COMPLETED.value, "result": ai.model_dump(), "updated_at": now}},
            )
            await self._set_progress(task_id, {"status": "completed", "progress": 100, "message": "完成"})
            await self.queue.ack(task_id, True)
        except Exception as e:
            now = datetime.utcnow()
            await db.calendar_ai_analyses.update_one(
                {"task_id": task_id},
                {"$set": {"status": CalendarAnalysisStatus.FAILED.value, "error_message": str(e), "updated_at": now}},
            )
            await self._set_progress(task_id, {"status": "failed", "progress": 0, "message": str(e)})
            await self.queue.ack(task_id, False, error_message=str(e))

    async def get_analysis_by_task_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        db = get_mongo_db()
        doc = await db.calendar_ai_analyses.find_one({"task_id": task_id}, {"_id": 0})
        if not doc:
            return None
        return doc

    async def get_latest_analysis_for_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        db = get_mongo_db()
        doc = await db.calendar_ai_analyses.find_one(
            {"event_id": event_id, "status": CalendarAnalysisStatus.COMPLETED.value},
            {"_id": 0},
            sort=[("created_at", -1)],
        )
        return doc

    def _build_prompt(self) -> ChatPromptTemplate:
        system = (
            "你是一名A股题材与事件驱动研究员。"
            "你必须只基于给定事件信息做推演，禁止编造不存在的事实。"
            "输出必须是严格JSON，不要输出Markdown代码块，不要输出额外文本。"
            "related_stocks 必须包含 market/code/name/reason/confidence；不确定就留空，并在 unknowns 写明缺口。"
        )
        human = (
            "下面是一个投资日历事件的详细信息和期望的输出格式，均为JSON：\n"
            "{input_json}\n"
            "请严格按照上述 output_schema 的定义返回JSON，禁止输出额外文本。"
        )
        return ChatPromptTemplate.from_messages([("system", system), ("human", human)])

    def _extract_json(self, text: str) -> Dict[str, Any]:
        s = text.strip()
        if "```" in s:
            parts = s.split("```")
            if len(parts) >= 3:
                s = parts[1].strip()
                if s.startswith("json"):
                    s = s[4:].strip()
        if not s.startswith("{"):
            start = s.find("{")
            end = s.rfind("}")
            if start >= 0 and end >= 0 and end > start:
                s = s[start : end + 1]
        return json.loads(s)

    async def _set_progress(self, task_id: str, payload: Dict[str, Any]) -> None:
        key = f"cal:analysis:progress:{task_id}"
        await self.redis.set(key, json.dumps(payload, ensure_ascii=False), ex=3600)


_calendar_analysis_service: CalendarAnalysisService | None = None


def get_calendar_analysis_service() -> CalendarAnalysisService:
    global _calendar_analysis_service
    if _calendar_analysis_service is None:
        _calendar_analysis_service = CalendarAnalysisService()
    return _calendar_analysis_service
