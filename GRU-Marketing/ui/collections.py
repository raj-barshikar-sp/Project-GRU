"""Named folders that group chats in the workspace sidebar."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "output" / "collections"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CollectionStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else _DEFAULT_ROOT

    def _path(self, collection_id: str) -> Path:
        return self.root / f"{collection_id}.json"

    def _read(self, collection_id: str) -> dict[str, Any] | None:
        path = self._path(collection_id)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, record: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(str(record["id"]))
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    def _row(self, record: dict[str, Any], *, path: Path) -> dict[str, Any]:
        return {
            "id": record.get("id") or path.stem,
            "name": (record.get("name") or "Collection").strip() or "Collection",
            "created_at": record.get("created_at") or "",
            "updated_at": record.get("updated_at") or "",
        }

    def list_collections(self) -> list[dict[str, Any]]:
        if not self.root.is_dir():
            return []
        rows: list[dict[str, Any]] = []
        for path in self.root.glob("*.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            rows.append(self._row(record, path=path))
        rows.sort(
            key=lambda item: item.get("updated_at") or item.get("created_at") or "",
            reverse=True,
        )
        return rows

    def get(self, collection_id: str) -> dict[str, Any] | None:
        record = self._read(collection_id)
        if record is None:
            return None
        return self._row(record, path=self._path(collection_id))

    def create(self, name: str) -> dict[str, Any]:
        now = _now()
        record = {
            "id": str(uuid.uuid4()),
            "name": name.strip() or "Collection",
            "created_at": now,
            "updated_at": now,
        }
        self._write(record)
        return self._row(record, path=self._path(record["id"]))

    def rename(self, collection_id: str, name: str) -> dict[str, Any] | None:
        record = self._read(collection_id)
        if record is None:
            return None
        record["name"] = name.strip() or record.get("name") or "Collection"
        record["updated_at"] = _now()
        self._write(record)
        return self._row(record, path=self._path(collection_id))

    def delete(self, collection_id: str) -> bool:
        path = self._path(collection_id)
        if not path.is_file():
            return False
        path.unlink()
        return True
