"""Session store abstractions and implementations for named Codex threads."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SessionTurnRecord:
    """Summary metadata captured for one completed SDK operation.

    These records are appended to `SessionRecord.turns` as bounded history.
    """

    timestamp: float
    operation: str
    prompt_preview: str | None = None
    return_code: int | None = None
    turn_status: str | None = None
    duration_seconds: float | None = None
    message_preview: str | None = None


@dataclass(frozen=True)
class SessionRecord:
    """Persistent metadata and bounded history for one named session.

    This is the richer schema used by modern stores (schema v2), including
    counters and per-turn snapshots.
    """

    session_id: str
    session_name: str
    created_at: float
    updated_at: float
    last_turn_status: str | None = None
    turn_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    turns: tuple[SessionTurnRecord, ...] = field(default_factory=tuple)


class SessionStore(ABC):
    """Persistence interface for logical session-name to session-id mappings.

    Implement this interface to provide custom persistence backends.
    """

    @abstractmethod
    def get(self, name: str) -> str | None:
        """Return the stored Codex session id for `name`, if any."""
        raise NotImplementedError

    @abstractmethod
    def set(self, name: str, session_id: str) -> None:
        """Persist or overwrite the session id mapped to `name`."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, name: str) -> None:
        """Delete the mapping and metadata for `name` if present."""
        raise NotImplementedError

    @abstractmethod
    def all(self) -> dict[str, str]:
        """Return all known `name -> session_id` mappings."""
        raise NotImplementedError

    @abstractmethod
    def get_record(self, name: str) -> SessionRecord | None:
        """Return the full persisted record for `name`, if available."""
        raise NotImplementedError

    @abstractmethod
    def set_record(self, name: str, record: SessionRecord) -> None:
        """Persist the complete record for `name`."""
        raise NotImplementedError

    @abstractmethod
    def list_records(self) -> dict[str, SessionRecord]:
        """Return all named session records."""
        raise NotImplementedError


class InMemorySessionStore(SessionStore):
    """Thread-safe in-memory session store.

    Useful as the default store for single-process apps and tests.
    """

    def __init__(self, initial: dict[str, str] | None = None, max_turn_history: int = 20) -> None:
        """Initialize a store with optional seed mappings and history limit."""
        self._lock = threading.Lock()
        self.max_turn_history = max(1, max_turn_history)
        now = time.time()
        self._records: dict[str, SessionRecord] = {
            name: SessionRecord(
                session_id=session_id,
                session_name=name,
                created_at=now,
                updated_at=now,
            )
            for name, session_id in (initial or {}).items()
        }

    def get(self, name: str) -> str | None:
        """Look up a session id by logical name."""
        record = self.get_record(name)
        return record.session_id if record is not None else None

    def set(self, name: str, session_id: str) -> None:
        """Create or update a name-to-session mapping."""
        with self._lock:
            existing = self._records.get(name)
            now = time.time()
            if existing is None:
                self._records[name] = SessionRecord(
                    session_id=session_id,
                    session_name=name,
                    created_at=now,
                    updated_at=now,
                )
                return

            self._records[name] = SessionRecord(
                session_id=session_id,
                session_name=name,
                created_at=existing.created_at,
                updated_at=now,
                last_turn_status=existing.last_turn_status,
                turn_count=existing.turn_count,
                success_count=existing.success_count,
                failure_count=existing.failure_count,
                turns=existing.turns,
            )

    def delete(self, name: str) -> None:
        """Remove a stored session mapping and record."""
        with self._lock:
            self._records.pop(name, None)

    def all(self) -> dict[str, str]:
        """Return all mappings as a plain dictionary copy."""
        with self._lock:
            return {name: record.session_id for name, record in self._records.items()}

    def get_record(self, name: str) -> SessionRecord | None:
        """Return the complete session record for `name`."""
        with self._lock:
            return self._records.get(name)

    def set_record(self, name: str, record: SessionRecord) -> None:
        """Persist a record while enforcing bounded turn history."""
        with self._lock:
            turns = tuple(record.turns[-self.max_turn_history :])
            normalized = SessionRecord(
                session_id=record.session_id,
                session_name=name,
                created_at=record.created_at,
                updated_at=record.updated_at,
                last_turn_status=record.last_turn_status,
                turn_count=record.turn_count,
                success_count=record.success_count,
                failure_count=record.failure_count,
                turns=turns,
            )
            self._records[name] = normalized

    def list_records(self) -> dict[str, SessionRecord]:
        """Return a shallow copy of all in-memory records."""
        with self._lock:
            return dict(self._records)


class JsonFileSessionStore(SessionStore):
    """Thread-safe and process-safe JSON-backed session store.

    This store:
    - supports legacy `{name: session_id}` migration,
    - writes schema-v2 records atomically,
    - uses lock files for cross-process safety.

    Example:
        store = JsonFileSessionStore(".codex/sessions.json")
        client = CodexLocalClient(session_store=store)
    """

    SCHEMA_VERSION = 2

    def __init__(self, file_path: str, max_turn_history: int = 20) -> None:
        """Initialize a JSON-backed store at `file_path`."""
        self.file_path = file_path
        self.max_turn_history = max(1, max_turn_history)
        self._thread_lock = threading.Lock()

    def get(self, name: str) -> str | None:
        """Look up a session id by logical name."""
        record = self.get_record(name)
        return record.session_id if record is not None else None

    def set(self, name: str, session_id: str) -> None:
        """Create or update a name-to-session mapping on disk."""
        with self._acquire_locks():
            records = self._load_records_locked()
            now = time.time()
            existing = records.get(name)
            if existing is None:
                records[name] = SessionRecord(
                    session_id=session_id,
                    session_name=name,
                    created_at=now,
                    updated_at=now,
                )
            else:
                records[name] = SessionRecord(
                    session_id=session_id,
                    session_name=name,
                    created_at=existing.created_at,
                    updated_at=now,
                    last_turn_status=existing.last_turn_status,
                    turn_count=existing.turn_count,
                    success_count=existing.success_count,
                    failure_count=existing.failure_count,
                    turns=existing.turns,
                )
            self._write_records_locked(records)

    def delete(self, name: str) -> None:
        """Remove a stored session mapping and record from disk."""
        with self._acquire_locks():
            records = self._load_records_locked()
            records.pop(name, None)
            self._write_records_locked(records)

    def all(self) -> dict[str, str]:
        """Return all mappings from the file-backed store."""
        with self._acquire_locks():
            records = self._load_records_locked()
            return {name: record.session_id for name, record in records.items()}

    def get_record(self, name: str) -> SessionRecord | None:
        """Return a full record by name from disk."""
        with self._acquire_locks():
            records = self._load_records_locked()
            return records.get(name)

    def set_record(self, name: str, record: SessionRecord) -> None:
        """Persist a complete record while enforcing bounded history."""
        with self._acquire_locks():
            records = self._load_records_locked()
            turns = tuple(record.turns[-self.max_turn_history :])
            normalized = SessionRecord(
                session_id=record.session_id,
                session_name=name,
                created_at=record.created_at,
                updated_at=record.updated_at,
                last_turn_status=record.last_turn_status,
                turn_count=record.turn_count,
                success_count=record.success_count,
                failure_count=record.failure_count,
                turns=turns,
            )
            records[name] = normalized
            self._write_records_locked(records)

    def list_records(self) -> dict[str, SessionRecord]:
        """Return all persisted records."""
        with self._acquire_locks():
            records = self._load_records_locked()
            return dict(records)

    @contextmanager
    def _acquire_locks(self):
        """Hold both thread and file locks for an atomic store operation."""
        with self._thread_lock:
            with self._file_lock():
                yield

    @contextmanager
    def _file_lock(self):
        """Acquire an inter-process lock file adjacent to the JSON store."""
        lock_path = f"{self.file_path}.lock"
        parent = os.path.dirname(lock_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        with open(lock_path, "a+b") as lock_file:
            if os.name == "nt":
                import msvcrt  # type: ignore

                lock_file.seek(0, os.SEEK_END)
                if lock_file.tell() == 0:
                    lock_file.write(b"\0")
                    lock_file.flush()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl  # type: ignore

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _load_records_locked(self) -> dict[str, SessionRecord]:
        """Load records and persist migrated schema if required."""
        records, migrated = self._read_records_locked()
        if migrated:
            self._write_records_locked(records)
        return records

    def _read_records_locked(self) -> tuple[dict[str, SessionRecord], bool]:
        """Read records from disk and detect whether migration is needed."""
        if not os.path.exists(self.file_path):
            return {}, False

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}, False

        if not isinstance(payload, dict):
            return {}, False

        # Schema v2 payload.
        if payload.get("schema_version") == self.SCHEMA_VERSION and isinstance(payload.get("records"), dict):
            raw_records = payload["records"]
            records: dict[str, SessionRecord] = {}
            for name, raw_record in raw_records.items():
                parsed = self._parse_record(name, raw_record)
                if parsed is not None:
                    records[name] = parsed
            return records, False

        # Legacy payload: {"name": "session_id"}.
        is_legacy = all(isinstance(k, str) and isinstance(v, str) for k, v in payload.items())
        if is_legacy:
            now = time.time()
            records = {
                name: SessionRecord(
                    session_id=session_id,
                    session_name=name,
                    created_at=now,
                    updated_at=now,
                )
                for name, session_id in payload.items()
            }
            return records, True

        return {}, False

    def _write_records_locked(self, records: dict[str, SessionRecord]) -> None:
        """Atomically write schema-v2 records to disk."""
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "records": {
                name: self._record_to_json(record)
                for name, record in records.items()
            },
        }

        parent = os.path.dirname(self.file_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        fd, temp_path = tempfile.mkstemp(prefix=".session-store-", suffix=".json", dir=parent or None)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
                f.write("\n")
            os.replace(temp_path, self.file_path)
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _parse_record(self, name: str, raw: object) -> SessionRecord | None:
        """Parse one persisted JSON object into a `SessionRecord`."""
        if not isinstance(raw, dict):
            return None

        session_id = raw.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            return None

        created_at = self._as_float(raw.get("created_at"), fallback=time.time())
        updated_at = self._as_float(raw.get("updated_at"), fallback=created_at)
        last_turn_status = raw.get("last_turn_status")
        if not isinstance(last_turn_status, str):
            last_turn_status = None

        turn_count = self._as_int(raw.get("turn_count"), fallback=0)
        success_count = self._as_int(raw.get("success_count"), fallback=0)
        failure_count = self._as_int(raw.get("failure_count"), fallback=0)

        turns: list[SessionTurnRecord] = []
        raw_turns = raw.get("turns")
        if isinstance(raw_turns, list):
            for raw_turn in raw_turns:
                parsed_turn = self._parse_turn(raw_turn)
                if parsed_turn is not None:
                    turns.append(parsed_turn)

        turns_tuple = tuple(turns[-self.max_turn_history :])
        return SessionRecord(
            session_id=session_id,
            session_name=name,
            created_at=created_at,
            updated_at=updated_at,
            last_turn_status=last_turn_status,
            turn_count=max(0, turn_count),
            success_count=max(0, success_count),
            failure_count=max(0, failure_count),
            turns=turns_tuple,
        )

    def _parse_turn(self, raw: object) -> SessionTurnRecord | None:
        """Parse one persisted turn entry into a `SessionTurnRecord`."""
        if not isinstance(raw, dict):
            return None

        operation = raw.get("operation")
        if not isinstance(operation, str) or not operation.strip():
            return None

        return SessionTurnRecord(
            timestamp=self._as_float(raw.get("timestamp"), fallback=time.time()),
            operation=operation,
            prompt_preview=self._as_optional_str(raw.get("prompt_preview")),
            return_code=self._as_optional_int(raw.get("return_code")),
            turn_status=self._as_optional_str(raw.get("turn_status")),
            duration_seconds=self._as_optional_float(raw.get("duration_seconds")),
            message_preview=self._as_optional_str(raw.get("message_preview")),
        )

    def _record_to_json(self, record: SessionRecord) -> dict:
        """Convert a `SessionRecord` into JSON-serializable schema-v2 data."""
        turns = [
            {
                "timestamp": turn.timestamp,
                "operation": turn.operation,
                "prompt_preview": turn.prompt_preview,
                "return_code": turn.return_code,
                "turn_status": turn.turn_status,
                "duration_seconds": turn.duration_seconds,
                "message_preview": turn.message_preview,
            }
            for turn in record.turns[-self.max_turn_history :]
        ]

        return {
            "session_id": record.session_id,
            "session_name": record.session_name,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "last_turn_status": record.last_turn_status,
            "turn_count": record.turn_count,
            "success_count": record.success_count,
            "failure_count": record.failure_count,
            "turns": turns,
        }

    @staticmethod
    def _as_float(value: object, fallback: float) -> float:
        """Coerce numeric values to `float` or return `fallback`."""
        if isinstance(value, (float, int)):
            return float(value)
        return fallback

    @staticmethod
    def _as_optional_float(value: object) -> float | None:
        """Coerce numeric values to `float` or return `None`."""
        if isinstance(value, (float, int)):
            return float(value)
        return None

    @staticmethod
    def _as_int(value: object, fallback: int) -> int:
        """Coerce integer values or return `fallback`."""
        if isinstance(value, int):
            return value
        return fallback

    @staticmethod
    def _as_optional_int(value: object) -> int | None:
        """Return integer values as-is, otherwise `None`."""
        if isinstance(value, int):
            return value
        return None

    @staticmethod
    def _as_optional_str(value: object) -> str | None:
        """Return string values as-is, otherwise `None`."""
        if isinstance(value, str):
            return value
        return None
