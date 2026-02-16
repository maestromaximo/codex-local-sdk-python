from __future__ import annotations

import json
import os
import tempfile
import threading
from abc import ABC, abstractmethod


class SessionStore(ABC):
    """Abstraction for persisting logical session-name -> codex session-id mappings."""

    @abstractmethod
    def get(self, name: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def set(self, name: str, session_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, name: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def all(self) -> dict[str, str]:
        raise NotImplementedError


class InMemorySessionStore(SessionStore):
    """Thread-safe in-memory session store."""

    def __init__(self, initial: dict[str, str] | None = None) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, str] = dict(initial or {})

    def get(self, name: str) -> str | None:
        with self._lock:
            return self._data.get(name)

    def set(self, name: str, session_id: str) -> None:
        with self._lock:
            self._data[name] = session_id

    def delete(self, name: str) -> None:
        with self._lock:
            self._data.pop(name, None)

    def all(self) -> dict[str, str]:
        with self._lock:
            return dict(self._data)


class JsonFileSessionStore(SessionStore):
    """Thread-safe JSON-file-backed store for persistent local mappings."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self._lock = threading.Lock()

    def get(self, name: str) -> str | None:
        with self._lock:
            data = self._read_all()
            value = data.get(name)
            return value if isinstance(value, str) else None

    def set(self, name: str, session_id: str) -> None:
        with self._lock:
            data = self._read_all()
            data[name] = session_id
            self._write_all(data)

    def delete(self, name: str) -> None:
        with self._lock:
            data = self._read_all()
            data.pop(name, None)
            self._write_all(data)

    def all(self) -> dict[str, str]:
        with self._lock:
            data = self._read_all()
            return {k: v for k, v in data.items() if isinstance(v, str)}

    def _read_all(self) -> dict[str, str]:
        if not os.path.exists(self.file_path):
            return {}
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

        if not isinstance(raw, dict):
            return {}

        out: dict[str, str] = {}
        for key, value in raw.items():
            if isinstance(key, str) and isinstance(value, str):
                out[key] = value
        return out

    def _write_all(self, data: dict[str, str]) -> None:
        parent = os.path.dirname(self.file_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        fd, temp_path = tempfile.mkstemp(prefix=".session-store-", suffix=".json", dir=parent or None)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
                f.write("\n")
            os.replace(temp_path, self.file_path)
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
