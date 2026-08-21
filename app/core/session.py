"""内存会话存储，用于多轮上诉与应答话术 opt-in 流程。

key 为 session_id（UUID），value 含 dialogue / verdict / appeals。
TTL 默认 1 小时。重启后丢失（v1 不持久化）。
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings


@dataclass
class Session:
    session_id: str
    dialogue: str
    verdict: str = ""
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)
    appeals: list[dict[str, Any]] = field(default_factory=list)
    reply_script_opted_in: bool = False


class SessionStore:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._store: dict[str, Session] = {}
        self._ttl = ttl_seconds
        self._cleaner_started = False

    def _maybe_start_cleaner(self) -> None:
        if not self._cleaner_started:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._cleaner_loop())
                self._cleaner_started = True
            except RuntimeError:
                pass

    async def _cleaner_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            now = time.time()
            expired = [sid for sid, s in self._store.items() if now - s.last_access > self._ttl]
            for sid in expired:
                self._store.pop(sid, None)

    def create(self, dialogue: str, verdict: str = "") -> Session:
        self._maybe_start_cleaner()
        sid = str(uuid.uuid4())
        s = Session(session_id=sid, dialogue=dialogue, verdict=verdict)
        self._store[sid] = s
        return s

    def get(self, session_id: str) -> Session | None:
        s = self._store.get(session_id)
        if s is None:
            return None
        s.last_access = time.time()
        return s

    def update_verdict(self, session_id: str, verdict: str) -> bool:
        s = self.get(session_id)
        if s is None:
            return False
        s.verdict = verdict
        return True

    def append_appeal(self, session_id: str, appeal_record: dict[str, Any]) -> bool:
        s = self.get(session_id)
        if s is None:
            return False
        s.appeals.append(appeal_record)
        return True

    def set_reply_script_opt_in(self, session_id: str, opted_in: bool = True) -> bool:
        s = self.get(session_id)
        if s is None:
            return False
        s.reply_script_opted_in = opted_in
        return True


_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        s = get_settings()
        _store = SessionStore(ttl_seconds=s.session_ttl_seconds)
    return _store
