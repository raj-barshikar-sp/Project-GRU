"""File-backed workspace transcripts. ADK session state stays in memory."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CHATS_LIMIT = 40
_DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "output" / "chats"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _collection_id(value: Any) -> str:
    return str(value or "").strip()


def _is_protected(record: dict[str, Any]) -> bool:
    return bool(record.get("pinned")) or bool(_collection_id(record.get("collection_id")))


class ChatStore:
    def __init__(self, root: Path | None = None, *, limit: int = CHATS_LIMIT) -> None:
        self.root = Path(root) if root is not None else _DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        self.limit = limit

    def _path(self, chat_id: str) -> Path:
        return self.root / f"{chat_id}.json"

    def _read(self, chat_id: str) -> dict[str, Any] | None:
        path = self._path(chat_id)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, record: dict[str, Any]) -> None:
        path = self._path(str(record["id"]))
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        self._prune()

    def _prune(self) -> None:
        files = sorted(self.root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        for stale in files[self.limit :]:
            try:
                record = json.loads(stale.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                record = {}
            if _is_protected(record):
                continue
            stale.unlink(missing_ok=True)

    def _summary(self, record: dict[str, Any], *, path: Path) -> dict[str, Any]:
        turns = record.get("turns") or []
        last = turns[-1] if turns else {}
        pending = bool(turns) and last.get("reply") is None and last.get(
            "status"
        ) not in {"done", "error", "cancelled"}
        return {
            "id": record.get("id") or path.stem,
            "session_id": record.get("session_id") or "",
            "title": record.get("title") or "Chat",
            "created_at": record.get("created_at") or "",
            "updated_at": record.get("updated_at") or "",
            "task_id": record.get("task_id") or "",
            "filters": record.get("filters") or {},
            "pending": pending,
            "pinned": bool(record.get("pinned")),
            "pinned_at": record.get("pinned_at") or "",
            "collection_id": _collection_id(record.get("collection_id")),
        }

    def list_chats(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in self.root.glob("*.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            rows.append(self._summary(record, path=path))
        rows.sort(
            key=lambda item: item.get("updated_at") or item.get("created_at") or "",
            reverse=True,
        )
        rows.sort(key=lambda item: 0 if item.get("pinned") else 1)
        return rows

    def get(self, chat_id: str) -> dict[str, Any] | None:
        record = self._read(chat_id)
        if record is None:
            return None
        from ui.briefing import hydrate_reply

        turns = []
        for index, turn in enumerate(record.get("turns") or []):
            reply = turn.get("reply")
            if reply:
                turn = {**turn, "reply": hydrate_reply(reply)}
            turn_id = turn.get("id") or f"turn-{record.get('id')}-{index}"
            turns.append({**turn, "id": turn_id})
        return {**record, "turns": turns}

    def delete(self, chat_id: str) -> bool:
        path = self._path(chat_id)
        if not path.is_file():
            return False
        path.unlink()
        return True

    def append_user(
        self,
        *,
        chat_id: str,
        session_id: str,
        title: str,
        user: str,
        tags: list[dict[str, str]],
        filters: dict[str, list[str]],
        task_id: str = "",
        turn_id: str = "",
        collection_id: str = "",
        pinned: bool = False,
    ) -> dict[str, Any]:
        record = self._read(chat_id)
        now = _now()
        if record is None:
            record = {
                "id": chat_id,
                "session_id": session_id,
                "title": title or "Chat",
                "created_at": now,
                "updated_at": now,
                "task_id": task_id,
                "filters": filters,
                "pinned": bool(pinned),
                "pinned_at": _now() if pinned else "",
                "collection_id": _collection_id(collection_id),
                "turns": [],
            }
        else:
            record["session_id"] = session_id or record.get("session_id") or ""
            if task_id:
                record["task_id"] = task_id
            record["filters"] = filters
            record["updated_at"] = now
            record.setdefault("pinned", False)
            record.setdefault("pinned_at", "")
            record.setdefault("collection_id", "")
        turn = {
            "id": (turn_id or "").strip() or f"turn-{chat_id}-{len(record.get('turns') or [])}",
            "user": user,
            "tags": tags,
            "reply": None,
            "status": "pending",
            "status_label": "",
            "reasoning": "",
        }
        record.setdefault("turns", []).append(turn)
        self._write(record)
        return record

    def _turn(self, record: dict[str, Any], turn_id: str = "") -> dict[str, Any] | None:
        turns = record.get("turns") or []
        if not turns:
            return None
        if turn_id:
            for item in turns:
                if item.get("id") == turn_id:
                    return item
        for item in reversed(turns):
            if item.get("reply") is None and item.get("status") == "pending":
                return item
        return turns[-1]

    def patch_turn(self, chat_id: str, turn_id: str = "", **fields: Any) -> None:
        record = self._read(chat_id)
        if record is None:
            return
        turn = self._turn(record, turn_id)
        if turn is None:
            return
        for key, value in fields.items():
            if value is not None:
                turn[key] = value
        record["updated_at"] = _now()
        self._write(record)

    def finish_reply(
        self,
        chat_id: str,
        reply: dict[str, Any],
        turn_id: str = "",
        *,
        status: str = "",
    ) -> None:
        kind = (reply or {}).get("kind")
        resolved = status or ("error" if kind == "error" else "done")
        self.patch_turn(chat_id, turn_id, reply=reply, status=resolved)

    def patch_chat(self, chat_id: str, **fields: Any) -> dict[str, Any] | None:
        record = self._read(chat_id)
        if record is None:
            return None
        if "pinned" in fields:
            record["pinned"] = bool(fields["pinned"])
            record["pinned_at"] = _now() if record["pinned"] else ""
        if "collection_id" in fields:
            record["collection_id"] = _collection_id(fields["collection_id"])
        if "title" in fields:
            title = str(fields["title"] or "").strip()
            if title:
                record["title"] = title
        if "in_scope" in fields:
            record["in_scope"] = bool(fields["in_scope"])
        if "task_id" in fields and fields["task_id"]:
            record["task_id"] = str(fields["task_id"])
        record["updated_at"] = _now()
        self._write(record)
        return record

    def clear_collection(self, collection_id: str) -> None:
        wanted = _collection_id(collection_id)
        if not wanted:
            return
        for path in self.root.glob("*.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if _collection_id(record.get("collection_id")) != wanted:
                continue
            record["collection_id"] = ""
            record["updated_at"] = _now()
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
