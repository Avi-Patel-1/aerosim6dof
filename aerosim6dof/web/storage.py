"""File-backed hosted storage helpers for the browser API."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORAGE_ROOT = ROOT / "outputs" / "web_runs"
STORAGE_ENV_VAR = "AEROSIM_STORAGE_DIR"
STORAGE_MANIFEST_NAME = ".aerosim_storage_manifest.json"
STORAGE_VERSION = 1
SAFE_NAMESPACES = frozenset({"runs", "drafts", "layouts", "reports", "gallery"})
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._~-]{0,127}$")
_MISSING = object()


class FileBackedStorage:
    """Small JSON storage layer rooted in a local or mounted directory."""

    def __init__(self, root: str | Path | None = None, *, env_backed: bool | None = None) -> None:
        if root is None:
            root = get_storage_root()
            env_backed = _env_storage_value() is not None if env_backed is None else env_backed
        self.root = Path(root).expanduser().resolve()
        self.env_backed = bool(env_backed)
        self.manifest_path = self.root / STORAGE_MANIFEST_NAME

    def namespace_path(self, namespace: str) -> Path:
        safe_namespace = self._validate_namespace(namespace)
        path = (self.root / safe_namespace).resolve()
        if not _is_within(path, self.root):
            raise ValueError(f"storage namespace escapes root: {namespace}")
        return path

    def json_path(self, namespace: str, item_id: str) -> Path:
        safe_id = self._validate_item_id(item_id)
        namespace_dir = self.namespace_path(namespace)
        path = (namespace_dir / f"{safe_id}.json").resolve()
        if not _is_within(path, namespace_dir):
            raise ValueError(f"storage id escapes namespace: {item_id}")
        return path

    def read_json(self, namespace: str, item_id: str, default: Any = _MISSING) -> Any:
        path = self.json_path(namespace, item_id)
        if not path.exists():
            if default is not _MISSING:
                return default
            raise FileNotFoundError(path)
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def write_json(self, namespace: str, item_id: str, data: Any) -> Path:
        self.ensure_manifest()
        path = self.json_path(namespace, item_id)
        _atomic_write_json(path, data)
        return path

    def list_json(self, namespace: str) -> list[str]:
        namespace_dir = self.namespace_path(namespace)
        if not namespace_dir.exists():
            return []
        return sorted(path.stem for path in namespace_dir.glob("*.json") if path.is_file())

    def delete_json(self, namespace: str, item_id: str) -> bool:
        path = self.json_path(namespace, item_id)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False

    def ensure_manifest(self) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        for namespace in SAFE_NAMESPACES:
            self.namespace_path(namespace).mkdir(parents=True, exist_ok=True)
        manifest = self._manifest_payload()
        if self.manifest_path.exists():
            try:
                existing = self._read_manifest()
                if (
                    existing.get("version") == STORAGE_VERSION
                    and existing.get("root") == manifest["root"]
                    and existing.get("env_backed") == manifest["env_backed"]
                    and existing.get("namespaces") == manifest["namespaces"]
                ):
                    return existing
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        _atomic_write_json(self.manifest_path, manifest)
        return manifest

    def status(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": False,
            "backend": "file",
            "root": str(self.root),
            "default_root": str(DEFAULT_STORAGE_ROOT),
            "env_var": STORAGE_ENV_VAR,
            "env_backed": self.env_backed,
            "persistent": self.env_backed,
            "version": STORAGE_VERSION,
            "namespaces": sorted(SAFE_NAMESPACES),
            "manifest_path": str(self.manifest_path),
            "manifest_exists": self.manifest_path.exists(),
            "writable": False,
            "error": None,
        }
        try:
            manifest = self.ensure_manifest()
            payload.update(
                ok=True,
                manifest_exists=True,
                writable=os.access(self.root, os.W_OK),
                manifest=manifest,
            )
        except OSError as exc:
            payload["error"] = str(exc)
        return payload

    def _manifest_payload(self) -> dict[str, Any]:
        return {
            "schema": "aerosim6dof.web.storage",
            "version": STORAGE_VERSION,
            "backend": "file",
            "created_at_utc": _utc_now(),
            "root": str(self.root),
            "env_var": STORAGE_ENV_VAR,
            "env_backed": self.env_backed,
            "persistent": self.env_backed,
            "namespaces": sorted(SAFE_NAMESPACES),
        }

    def _read_manifest(self) -> dict[str, Any]:
        with self.manifest_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("storage manifest must be a JSON object")
        return data

    @staticmethod
    def _validate_namespace(namespace: str) -> str:
        if namespace not in SAFE_NAMESPACES:
            allowed = ", ".join(sorted(SAFE_NAMESPACES))
            raise ValueError(f"unsupported storage namespace: {namespace}; expected one of {allowed}")
        return namespace

    @staticmethod
    def _validate_item_id(item_id: str) -> str:
        if not isinstance(item_id, str) or not _SAFE_ID_RE.fullmatch(item_id) or ".." in item_id:
            raise ValueError(f"unsafe storage id: {item_id!r}")
        return item_id


def get_storage_root() -> Path:
    value = _env_storage_value()
    if value is None:
        return DEFAULT_STORAGE_ROOT.resolve()
    return Path(value).expanduser().resolve()


def get_storage() -> FileBackedStorage:
    return FileBackedStorage(get_storage_root(), env_backed=_env_storage_value() is not None)


def storage_status() -> dict[str, Any]:
    return get_storage().status()


def _env_storage_value() -> str | None:
    value = os.environ.get(STORAGE_ENV_VAR)
    if value is None or not value.strip():
        return None
    return value


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp_path.open("x", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
