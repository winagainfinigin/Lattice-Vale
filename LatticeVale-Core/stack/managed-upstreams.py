#!/usr/bin/env python3
"""LatticeVale latest-supported managed-upstream policy.

This helper owns only non-secret software/source references and exact resolved
artifact metadata. It never reads or writes provider credentials or application
persistent state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from datetime import datetime, timezone

OFFICIAL_HONCHO_ORIGINS = {
    "https://github.com/plastic-labs/honcho.git",
    "https://github.com/plastic-labs/honcho",
}
LEGACY_HONCHO_COMMITS = {"444897975c95393b0d48024470ece03c025d3aa4"}

# Floating stable channels for application components. Stateful databases stay on
# the current tested major line so an ordinary software refresh cannot perform an
# implicit on-disk major migration.
CHANNELS = {
    "HERMES_IMAGE": {
        "marker": "LATTICEVALE_HERMES_IMAGE_AUTO",
        "desired": "nousresearch/hermes-agent:latest",
        "legacy": {"nousresearch/hermes-agent:v2026.8.16"},
        "label": "Hermes Agent",
        "policy": "stable-latest",
    },
    "SYNAPSE_IMAGE": {
        "marker": "LATTICEVALE_SYNAPSE_IMAGE_AUTO",
        "desired": "matrixdotorg/synapse:latest",
        "legacy": {"matrixdotorg/synapse:v1.158.0"},
        "label": "Matrix Synapse",
        "policy": "stable-latest",
    },
    "SEARXNG_IMAGE": {
        "marker": "LATTICEVALE_SEARXNG_IMAGE_AUTO",
        "desired": "searxng/searxng:latest",
        "legacy": {"searxng/searxng:2026.8.17-374939b88", "searxng/searxng:latest", "searxng/searxng"},
        "label": "SearXNG",
        "policy": "stable-latest",
    },
    "QMD_VERSION": {
        "marker": "LATTICEVALE_QMD_VERSION_AUTO",
        "desired": "latest",
        "legacy": {"2.5.3", "latest"},
        "label": "QMD",
        "policy": "npm-latest",
    },
    "POSTGRES_IMAGE": {
        "marker": "LATTICEVALE_POSTGRES_IMAGE_AUTO",
        "desired": "postgres:16-alpine",
        "legacy": {"postgres:16-alpine"},
        "label": "Synapse PostgreSQL",
        "policy": "compatible-major-16",
    },
    "PGVECTOR_IMAGE": {
        "marker": "LATTICEVALE_PGVECTOR_IMAGE_AUTO",
        "desired": "pgvector/pgvector:pg15",
        "legacy": {"pgvector/pgvector:pg15"},
        "label": "Honcho pgvector/PostgreSQL",
        "policy": "compatible-major-15",
    },
    "REDIS_IMAGE": {
        "marker": "LATTICEVALE_REDIS_IMAGE_AUTO",
        "desired": "redis:8-alpine",
        "legacy": {"redis:8-alpine"},
        "label": "Honcho Redis",
        "policy": "compatible-major-8",
    },
    "VALKEY_IMAGE": {
        "marker": "LATTICEVALE_VALKEY_IMAGE_AUTO",
        "desired": "valkey/valkey:8-alpine",
        "legacy": {"valkey/valkey:8-alpine"},
        "label": "SearXNG Valkey",
        "policy": "compatible-major-8",
    },
}


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 120, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=check)


def env_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def get_env(lines: list[str], key: str) -> str:
    prefix = key + "="
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix):]
    return ""


def set_env(lines: list[str], key: str, value: str) -> list[str]:
    prefix = key + "="
    out: list[str] = []
    wrote = False
    for line in lines:
        if line.startswith(prefix):
            if not wrote:
                out.append(prefix + value)
                wrote = True
            continue
        out.append(line)
    if not wrote:
        out.append(prefix + value)
    return out


def atomic_write(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".tmp.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def reconcile_value(lines: list[str], key: str, spec: dict[str, object], *, refresh: bool, fresh: bool) -> tuple[list[str], dict[str, object]]:
    marker = str(spec["marker"])
    desired = str(spec["desired"])
    legacy = set(spec["legacy"])
    current = get_env(lines, key)
    prior_auto = get_env(lines, marker)
    installer_owned = (not current) or (bool(prior_auto) and current == prior_auto) or (not prior_auto and current in legacy) or current == desired
    changed = False

    if fresh or not current:
        current = desired
        lines = set_env(lines, key, current)
        lines = set_env(lines, marker, current)
        installer_owned = True
        changed = True
    elif refresh and installer_owned:
        if current != desired:
            changed = True
        current = desired
        lines = set_env(lines, key, current)
        lines = set_env(lines, marker, current)
    elif installer_owned:
        # Preserve the current automatic value between refresh windows while keeping
        # ownership provable for the next due refresh.
        lines = set_env(lines, marker, current)
    elif not prior_auto:
        # Record the comparison point without claiming ownership of the custom value.
        lines = set_env(lines, marker, desired)

    return lines, {
        "key": key,
        "label": spec["label"],
        "policy": spec["policy"],
        "value": current,
        "desired": desired,
        "installerOwned": installer_owned,
        "changed": changed,
    }


def stable_tag_key(tag: str) -> tuple[int, int, int]:
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", tag)
    if not m:
        raise ValueError(tag)
    return tuple(int(x) for x in m.groups())


def latest_honcho_stable_tag(origin: str) -> str:
    cp = run(["git", "ls-remote", "--tags", "--refs", origin], timeout=90)
    tags: list[str] = []
    for raw in cp.stdout.splitlines():
        parts = raw.split()
        if len(parts) != 2 or not parts[1].startswith("refs/tags/"):
            continue
        tag = parts[1][len("refs/tags/"):]
        try:
            stable_tag_key(tag)
        except ValueError:
            continue
        tags.append(tag)
    if not tags:
        raise RuntimeError("Honcho has no stable semantic-version tag reachable from its official origin")
    return max(tags, key=stable_tag_key)


def reconcile_honcho(stack: Path, lines: list[str], *, refresh: bool, fresh: bool) -> tuple[list[str], dict[str, object]]:
    options_path = stack / "install-options.json"
    try:
        opts = json.loads(options_path.read_text(encoding="utf-8"))
    except Exception:
        opts = {}
    if not bool(opts.get("honcho", False)):
        return lines, {"selected": False}

    repo = stack / "vendor" / "honcho"
    prior_auto = get_env(lines, "LATTICEVALE_HONCHO_SOURCE_AUTO")
    prior_tag = get_env(lines, "LATTICEVALE_HONCHO_TAG_AUTO")
    current_commit = ""
    origin = "https://github.com/plastic-labs/honcho.git"
    if (repo / ".git").is_dir():
        try:
            current_commit = run(["git", "-C", str(repo), "rev-parse", "HEAD"], timeout=20).stdout.strip()
            origin = run(["git", "-C", str(repo), "remote", "get-url", "origin"], timeout=20).stdout.strip()
        except Exception as exc:
            raise RuntimeError(f"Existing Honcho checkout is invalid: {exc}") from exc

    official = origin in OFFICIAL_HONCHO_ORIGINS
    installer_owned = (not current_commit) or (official and bool(prior_auto) and current_commit == prior_auto) or (official and not prior_auto and current_commit in LEGACY_HONCHO_COMMITS)
    changed = False
    resolved_tag = prior_tag

    if fresh or not current_commit or (refresh and installer_owned):
        if not official and current_commit:
            return lines, {
                "selected": True,
                "installerOwned": False,
                "changed": False,
                "commit": current_commit,
                "tag": prior_tag or None,
                "origin": origin,
                "policy": "user-override",
            }
        resolved_tag = latest_honcho_stable_tag("https://github.com/plastic-labs/honcho.git")
        repo.parent.mkdir(parents=True, exist_ok=True)
        if not (repo / ".git").is_dir():
            if repo.exists():
                raise RuntimeError("Honcho source path exists but is not a Git checkout; refusing to overwrite it")
            repo.mkdir(parents=True)
            run(["git", "-C", str(repo), "init", "-q"], timeout=20)
            run(["git", "-C", str(repo), "remote", "add", "origin", "https://github.com/plastic-labs/honcho.git"], timeout=20)
        run(["git", "-C", str(repo), "fetch", "--force", "--depth", "1", "origin", f"refs/tags/{resolved_tag}:refs/tags/{resolved_tag}"], timeout=900)
        run(["git", "-C", str(repo), "checkout", "--force", "--detach", resolved_tag], timeout=60)
        new_commit = run(["git", "-C", str(repo), "rev-parse", "HEAD"], timeout=20).stdout.strip()
        changed = new_commit != current_commit
        current_commit = new_commit
        installer_owned = True
        lines = set_env(lines, "LATTICEVALE_HONCHO_SOURCE_AUTO", current_commit)
        lines = set_env(lines, "LATTICEVALE_HONCHO_TAG_AUTO", resolved_tag)
    elif installer_owned:
        lines = set_env(lines, "LATTICEVALE_HONCHO_SOURCE_AUTO", current_commit)
        if prior_tag:
            lines = set_env(lines, "LATTICEVALE_HONCHO_TAG_AUTO", prior_tag)

    return lines, {
        "selected": True,
        "installerOwned": installer_owned,
        "changed": changed,
        "commit": current_commit or None,
        "tag": resolved_tag or None,
        "origin": origin,
        "policy": "latest-stable-semver-tag" if installer_owned else "user-override",
    }


def desired_ollama(acceleration: str) -> dict[str, object]:
    desired = "ollama/ollama:rocm" if acceleration == "amd" else "ollama/ollama:latest"
    legacy = {"ollama/ollama:0.32.14", "ollama/ollama:0.32.14-rocm", "ollama/ollama:latest", "ollama/ollama:rocm"}
    return {
        "marker": "LATTICEVALE_OLLAMA_IMAGE_AUTO",
        "desired": desired,
        "legacy": legacy,
        "label": "Ollama",
        "policy": "stable-rocm" if acceleration == "amd" else "stable-latest",
    }


def cmd_reconcile(args: argparse.Namespace) -> int:
    stack = Path(args.stack).resolve()
    env_path = stack / ".env"
    lines = env_lines(env_path)
    if not lines:
        raise SystemExit(f"Managed upstream reconciliation requires an existing .env: {env_path}")

    decisions: list[dict[str, object]] = []
    for key, spec in CHANNELS.items():
        lines, decision = reconcile_value(lines, key, spec, refresh=args.refresh, fresh=args.fresh)
        decisions.append(decision)

    ollama_spec = desired_ollama(args.ollama_acceleration)
    lines, ollama_decision = reconcile_value(lines, "OLLAMA_IMAGE", ollama_spec, refresh=args.refresh, fresh=args.fresh)
    decisions.append(ollama_decision)

    lines, honcho = reconcile_honcho(stack, lines, refresh=args.refresh, fresh=args.fresh)
    atomic_write(env_path, "\n".join(lines) + "\n", 0o600)

    print("Latest-supported managed-upstream policy:")
    for d in decisions:
        state = "managed" if d["installerOwned"] else "custom-preserved"
        suffix = "; advanced" if d["changed"] else ""
        print(f"  {d['label']}: {d['value']} ({d['policy']}; {state}{suffix})")
    if honcho.get("selected"):
        state = "managed" if honcho.get("installerOwned") else "custom-preserved"
        print(f"  Honcho: {honcho.get('tag') or honcho.get('commit') or 'unknown'} ({honcho.get('policy')}; {state})")
    return 0


def inspect_image(ref: str) -> dict[str, object] | None:
    if not ref:
        return None
    try:
        cp = run(["docker", "image", "inspect", ref], timeout=30)
        data = json.loads(cp.stdout)
        if not isinstance(data, list) or not data:
            return None
        obj = data[0]
        return {
            "declaredRef": ref,
            "imageId": obj.get("Id"),
            "repoDigests": obj.get("RepoDigests") or [],
            "created": obj.get("Created"),
        }
    except Exception:
        return {"declaredRef": ref, "unavailable": True}


def git_value(repo: Path, args: list[str]) -> str | None:
    try:
        value = run(["git", "-C", str(repo), *args], timeout=20).stdout.strip()
        return value or None
    except Exception:
        return None


def cmd_record(args: argparse.Namespace) -> int:
    stack = Path(args.stack).resolve()
    lines = env_lines(stack / ".env")
    image_keys = ["HERMES_IMAGE", "SYNAPSE_IMAGE", "SEARXNG_IMAGE", "OLLAMA_IMAGE", "POSTGRES_IMAGE", "PGVECTOR_IMAGE", "REDIS_IMAGE", "VALKEY_IMAGE"]
    images = {key: inspect_image(get_env(lines, key)) for key in image_keys if get_env(lines, key)}
    images["QMD_LOCAL_IMAGE"] = inspect_image("hermes-qmd:local")
    images["HONCHO_LOCAL_IMAGE"] = inspect_image("hermes-honcho:local")

    honcho_repo = stack / "vendor" / "honcho"
    honcho = {
        "commit": git_value(honcho_repo, ["rev-parse", "HEAD"]),
        "tag": git_value(honcho_repo, ["describe", "--tags", "--exact-match", "HEAD"]),
        "origin": git_value(honcho_repo, ["remote", "get-url", "origin"]),
    }
    req = stack / "directml-requirements.txt"
    directml_hash = hashlib.sha256(req.read_bytes()).hexdigest() if req.is_file() else None
    payload = {
        "schema": 1,
        "installerVersion": args.installer_version,
        "resolvedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "policy": "latest-supported-upstream",
        "channels": {key: get_env(lines, key) for key in [*image_keys, "QMD_VERSION"] if get_env(lines, key)},
        "images": images,
        "honcho": honcho,
        "directml": {
            "policy": "LatticeVale compatibility envelope",
            "requirementsSha256": directml_hash,
        },
    }
    out = stack / "data" / "latticevale" / "managed-upstreams.json"
    atomic_write(out, json.dumps(payload, indent=2, sort_keys=True) + "\n", 0o600)
    print(f"Recorded exact managed-upstream resolution state: {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("reconcile")
    p.add_argument("--stack", default=".")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--fresh", action="store_true")
    p.add_argument("--ollama-acceleration", choices=["cpu", "nvidia", "amd", "vulkan", "windows-native"], default="cpu")
    p.set_defaults(func=cmd_reconcile)
    p = sub.add_parser("record")
    p.add_argument("--stack", default=".")
    p.add_argument("--installer-version", required=True)
    p.set_defaults(func=cmd_record)
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
