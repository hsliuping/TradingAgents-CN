import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.embedded_nanobot.utils.helpers import ensure_dir, safe_filename


@dataclass
class Session:
    key: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_consolidated: int = 0

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs,
        })
        self.updated_at = datetime.now()

    @staticmethod
    def _find_legal_start(messages: list[dict[str, Any]]) -> int:
        """找到消息列表中第一个合法的起始位置。

        处理两种非法情况：
        1. 孤儿 tool 响应（tool 消息对应的 tool_call_id 没有前置 assistant 声明）
        2. 孤儿 tool_calls（assistant 声明了 tool_calls 但后续缺失对应的 tool 响应）

        返回需要裁剪掉的前缀消息数量。
        """
        declared: set[str] = set()
        satisfied: set[str] = set()
        start = 0
        for index, msg in enumerate(messages):
            if msg.get("role") == "assistant":
                for tc in msg.get("tool_calls") or []:
                    if isinstance(tc, dict) and tc.get("id"):
                        declared.add(str(tc["id"]))
                # 该 assistant 消息之后的所有 tool 响应会逐步满足 declared
                satisfied.clear()
            elif msg.get("role") == "tool":
                tool_call_id = msg.get("tool_call_id")
                if tool_call_id:
                    tid = str(tool_call_id)
                    if tid not in declared:
                        # 孤儿 tool 响应：无法溯源的 tool 消息，跳过
                        start = index + 1
                        declared.clear()
                        satisfied.clear()
                    else:
                        satisfied.add(tid)
            # 如果某条 assistant 消息声明的 tool_calls 全被满足，degaard 可以重置
            if declared and declared == satisfied:
                declared.clear()
                satisfied.clear()
        # 循环结束后：如果 declared 中还有未满足的 tool_call_id，
        # 说明最后一条含 tool_calls 的 assistant 缺少对应的 tool 响应 → 孤儿 tool_calls
        if declared:
            # 倒找最后一条含未满足 tool_calls 的 assistant 消息
            for back_idx in range(len(messages) - 1, start - 1, -1):
                msg = messages[back_idx]
                if msg.get("role") == "assistant" and msg.get("tool_calls"):
                    unresolved_ids = {str(tc["id"]) for tc in msg["tool_calls"] if isinstance(tc, dict) and tc.get("id")}
                    if unresolved_ids & declared:
                        # 裁剪掉这条 assistant 及其之后的所有消息
                        return back_idx
        return start

    def get_history(self, max_messages: int = 500) -> list[dict[str, Any]]:
        unconsolidated = self.messages[self.last_consolidated:]
        sliced = unconsolidated if max_messages == 0 else unconsolidated[-max_messages:]
        for index, message in enumerate(sliced):
            if message.get("role") == "user":
                sliced = sliced[index:]
                break
        start = self._find_legal_start(sliced)
        if start:
            sliced = sliced[start:]
        out: list[dict[str, Any]] = []
        for message in sliced:
            entry: dict[str, Any] = {"role": message["role"], "content": message.get("content", "")}
            for key in ("tool_calls", "tool_call_id", "name"):
                if key in message:
                    entry[key] = message[key]
            out.append(entry)
        return out

    def clear(self) -> None:
        self.messages = []
        self.last_consolidated = 0
        self.updated_at = datetime.now()

    def retain_recent_legal_suffix(self, max_messages: int) -> None:
        if max_messages <= 0:
            self.clear()
            return
        if len(self.messages) <= max_messages:
            return

        start_index = max(0, len(self.messages) - max_messages)
        while start_index > 0 and self.messages[start_index].get("role") != "user":
            start_index -= 1

        retained = self.messages[start_index:]
        legal_start = self._find_legal_start(retained)
        if legal_start:
            retained = retained[legal_start:]

        dropped = len(self.messages) - len(retained)
        self.messages = retained
        self.last_consolidated = max(0, self.last_consolidated - dropped)
        self.updated_at = datetime.now()


class SessionManager:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.sessions_dir = ensure_dir(self.workspace / "nanobot_sessions")
        self._cache: dict[str, Session] = {}

    def _get_session_path(self, key: str) -> Path:
        return self.sessions_dir / f"{safe_filename(key.replace(':', '_'))}.jsonl"

    def get_or_create(self, key: str) -> Session:
        if key in self._cache:
            return self._cache[key]
        session = self._load(key) or Session(key=key)
        self._cache[key] = session
        return session

    def _load(self, key: str) -> Session | None:
        path = self._get_session_path(key)
        if not path.exists():
            return None
        try:
            messages: list[dict[str, Any]] = []
            metadata: dict[str, Any] = {}
            created_at = None
            last_consolidated = 0
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
                        last_consolidated = data.get("last_consolidated", 0)
                    else:
                        messages.append(data)
            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                metadata=metadata,
                last_consolidated=last_consolidated,
            )
        except Exception:
            return None

    def save(self, session: Session) -> None:
        path = self._get_session_path(session.key)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "_type": "metadata",
                "key": session.key,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "metadata": session.metadata,
                "last_consolidated": session.last_consolidated,
            }, ensure_ascii=False) + "\n")
            for msg in session.messages:
                handle.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self._cache[session.key] = session

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

    def list_sessions(self) -> list[dict[str, Any]]:
        sessions: list[dict[str, Any]] = []
        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                with open(path, encoding="utf-8") as handle:
                    first_line = handle.readline().strip()
                    if not first_line:
                        continue
                    data = json.loads(first_line)
                    if data.get("_type") == "metadata":
                        sessions.append({
                            "key": data.get("key") or path.stem.replace("_", ":", 1),
                            "created_at": data.get("created_at"),
                            "updated_at": data.get("updated_at"),
                            "path": str(path),
                        })
            except Exception:
                continue
        return sorted(sessions, key=lambda item: item.get("updated_at", ""), reverse=True)