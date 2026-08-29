#!/usr/bin/env python3
"""Read-only typed view of an installed LatticeVale stack.

v14.5.0 intentionally does not make this model a write authority.  Existing files retain
ownership exactly as before:

* install-options.json: installer-selected policy/options
* .env / generated Compose/config files: installer-derived runtime configuration
* compose.override.yaml: user-owned override applied after generated policy
* .installer-state.json: advisory checkpoint/runtime history

This module reads those sources, validates enough structure for diagnostics/planning, and
never writes them back.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

_EPHEMERAL_OPTION_KEYS = {
    "installerVersion",
    "installerMode",
    "resetCheckpoints",
    "forceProviderSetup",
    "forceProfileSetup",
    "rebuildMatrixIdentity",
    "repairMaintenance",
    "forceManagedUpdate",
}


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    try:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.rstrip("\r")
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key:
                values[key] = value
    except Exception:
        return {}
    return values


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def options_hash(raw_options: Mapping[str, Any]) -> str:
    """Match configure-stack.sh OPTIONS_HASH without mutating the source mapping."""
    cleaned = dict(raw_options)
    for key in _EPHEMERAL_OPTION_KEYS:
        cleaned.pop(key, None)
    payload = json.dumps(
        {"options": cleaned}, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _bool(raw: Mapping[str, Any], key: str, default: bool = False) -> bool:
    value = raw.get(key, default)
    return value if isinstance(value, bool) else default


def _port(raw: Mapping[str, Any], key: str, default: int) -> int:
    value = raw.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if 1 <= parsed <= 65535 else default


def _text(raw: Mapping[str, Any], key: str, default: str = "") -> str:
    value = raw.get(key, default)
    return value.strip() if isinstance(value, str) else default


@dataclass(frozen=True)
class InstallOptions:
    schema: int | None
    installer_version: str
    installer_mode: str
    dashboard: bool
    multi_agent: bool
    kanban: bool
    matrix: bool
    tailscale: bool
    searxng: bool
    qmd: bool
    honcho: bool
    hermes_local_ai: bool
    ollama_backend: str
    container_resource_limits: bool
    obsidian: bool
    hermes_api_port: int
    dashboard_port: int
    matrix_port: int
    searxng_port: int
    honcho_port: int
    workers: tuple[str, ...] = ()
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "InstallOptions":
        schema_value = raw.get("schema")
        schema = schema_value if isinstance(schema_value, int) else None
        workers: list[str] = []
        for item in raw.get("workers", []) if isinstance(raw.get("workers"), list) else []:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                name = item["name"].strip()
                if name:
                    workers.append(name)
        backend = _text(raw, "ollamaBackend", "managed")
        if backend not in {"managed", "windows-native"}:
            backend = "managed"
        return cls(
            schema=schema,
            installer_version=_text(raw, "installerVersion"),
            installer_mode=_text(raw, "installerMode"),
            dashboard=_bool(raw, "dashboard"),
            multi_agent=_bool(raw, "multiAgent"),
            kanban=_bool(raw, "kanban"),
            matrix=_bool(raw, "matrix"),
            tailscale=_bool(raw, "tailscale"),
            searxng=_bool(raw, "searxng"),
            qmd=_bool(raw, "qmd"),
            honcho=_bool(raw, "honcho"),
            hermes_local_ai=_bool(raw, "hermesLocalAI"),
            ollama_backend=backend,
            container_resource_limits=_bool(raw, "containerResourceLimits"),
            obsidian=_bool(raw, "obsidian"),
            hermes_api_port=_port(raw, "hermesApiPort", 8642),
            dashboard_port=_port(raw, "dashboardLocalPort", 9119),
            matrix_port=_port(raw, "matrixLocalPort", 8008),
            searxng_port=_port(raw, "searxngLocalPort", 8888),
            honcho_port=_port(raw, "honchoLocalPort", 8000),
            workers=tuple(workers),
            raw=dict(raw),
        )

    @property
    def local_ai_enabled(self) -> bool:
        return self.honcho or self.hermes_local_ai

    def selected_components(self) -> tuple[str, ...]:
        selected = ["hermes"]
        for name, enabled in (
            ("dashboard", self.dashboard),
            ("kanban", self.kanban),
            ("matrix", self.matrix),
            ("searxng", self.searxng),
            ("qmd", self.qmd),
            ("honcho", self.honcho),
            ("ollama", self.local_ai_enabled),
            ("tailscale", self.tailscale),
            ("obsidian", self.obsidian),
        ):
            if enabled:
                selected.append(name)
        return tuple(selected)


@dataclass(frozen=True)
class CheckpointMetadata:
    name: str
    order: int
    revision: int
    description: str
    recovery: str


@dataclass(frozen=True)
class SourceInfo:
    path: str
    role: str
    exists: bool
    sha256: str | None = None
    note: str = ""


@dataclass(frozen=True)
class StackSnapshot:
    root: Path
    options: InstallOptions
    raw_options: Mapping[str, Any]
    installer_state: Mapping[str, Any]
    env: Mapping[str, str]
    checkpoints: tuple[CheckpointMetadata, ...]
    sources: tuple[SourceInfo, ...]
    warnings: tuple[str, ...]

    @classmethod
    def load(cls, root: Path | str) -> "StackSnapshot":
        root_path = Path(root).expanduser().resolve()
        warnings: list[str] = []
        raw_options = _read_json(root_path / "install-options.json", {})
        if not isinstance(raw_options, dict):
            warnings.append("install-options.json is missing, unreadable, or not a JSON object")
            raw_options = {}
        state = _read_json(root_path / ".installer-state.json", {})
        if not isinstance(state, dict):
            warnings.append(".installer-state.json is missing, unreadable, or not a JSON object")
            state = {}
        metadata_raw = _read_json(root_path / "checkpoint-metadata.json", {})
        checkpoint_rows: list[CheckpointMetadata] = []
        stages = metadata_raw.get("stages", {}) if isinstance(metadata_raw, dict) else {}
        if isinstance(stages, dict):
            for name, item in stages.items():
                if not isinstance(name, str) or not isinstance(item, dict):
                    continue
                revision = item.get("revision")
                order = item.get("order")
                if not isinstance(revision, int) or revision < 1:
                    continue
                if not isinstance(order, int):
                    order = 9999
                checkpoint_rows.append(
                    CheckpointMetadata(
                        name=name,
                        order=order,
                        revision=revision,
                        description=str(item.get("description") or name),
                        recovery=str(item.get("recovery") or "forward-fix"),
                    )
                )
        if not checkpoint_rows:
            warnings.append("checkpoint-metadata.json is missing/unreadable; revision-aware planning is unavailable")
        checkpoint_rows.sort(key=lambda row: (row.order, row.name))

        override = root_path / "compose.override.yaml"
        sources = (
            SourceInfo(
                "install-options.json",
                "installer-selected options (authoritative for installer choices)",
                (root_path / "install-options.json").is_file(),
                _sha256_file(root_path / "install-options.json"),
            ),
            SourceInfo(
                ".env",
                "installer-derived runtime environment (read-only to planner)",
                (root_path / ".env").is_file(),
                _sha256_file(root_path / ".env"),
            ),
            SourceInfo(
                "compose.override.yaml",
                "user-owned Compose override applied after generated policy",
                override.is_file(),
                _sha256_file(override),
                "opaque/user-owned: v14.5.0 does not parse, normalize, or rewrite this file",
            ),
            SourceInfo(
                ".installer-state.json",
                "advisory checkpoint/runtime history",
                (root_path / ".installer-state.json").is_file(),
                _sha256_file(root_path / ".installer-state.json"),
            ),
            SourceInfo(
                "checkpoint-metadata.json",
                "read-only metadata for the existing checkpoint revision gate",
                (root_path / "checkpoint-metadata.json").is_file(),
                _sha256_file(root_path / "checkpoint-metadata.json"),
            ),
        )
        return cls(
            root=root_path,
            options=InstallOptions.from_mapping(raw_options),
            raw_options=dict(raw_options),
            installer_state=dict(state),
            env=_read_env(root_path / ".env"),
            checkpoints=tuple(checkpoint_rows),
            sources=sources,
            warnings=tuple(warnings),
        )

    @property
    def computed_options_hash(self) -> str:
        return options_hash(self.raw_options)

    @property
    def user_override_present(self) -> bool:
        return (self.root / "compose.override.yaml").is_file()

    def checkpoint_state(self, name: str) -> Mapping[str, Any]:
        stages = self.installer_state.get("stages", {})
        if not isinstance(stages, dict):
            return {}
        item = stages.get(name, {})
        return item if isinstance(item, dict) else {}
