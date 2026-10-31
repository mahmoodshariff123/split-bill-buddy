"""Tiny JSON-file storage for groups (trips). Swap for a database later."""
import json
import threading
import uuid
from datetime import datetime, timezone

from . import config

_lock = threading.Lock()


def _file():
    return config.DATA_DIR / "groups.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def _load() -> dict:
    return json.loads(_file().read_text()) if _file().exists() else {}


def _save(groups: dict) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _file().with_suffix(".tmp")
    tmp.write_text(json.dumps(groups, indent=2))
    tmp.replace(_file())


def list_groups() -> list[dict]:
    with _lock:
        return sorted(_load().values(), key=lambda g: g["created_at"], reverse=True)


def get(group_id: str) -> dict | None:
    with _lock:
        return _load().get(group_id)


def save(group: dict) -> None:
    with _lock:
        groups = _load()
        groups[group["id"]] = group
        _save(groups)


def reset() -> None:
    with _lock:
        _save({})
