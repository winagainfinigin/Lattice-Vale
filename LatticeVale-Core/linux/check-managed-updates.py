#!/usr/bin/env python3
"""Read-only remote software inventory for existing-stack Option 1.

The only intentional write is Ubuntu's downloaded APT package metadata. This
check never installs packages, pulls Docker images, updates Git, or changes
LatticeVale state. A failed remote check is UNKNOWN, not proof of currency.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import Request, urlopen

PACKAGES = (
    "ca-certificates", "curl", "git", "gnupg", "jq", "openssl", "procps",
    "python3", "python3-yaml", "sudo", "tzdata", "uidmap",
    "docker-ce", "docker-ce-cli", "containerd.io", "docker-buildx-plugin",
    "docker-compose-plugin",
)
IMAGES = (
    ("HERMES_IMAGE", "hermes", "nousresearch/hermes-agent:latest"),
    ("SYNAPSE_IMAGE", "matrix", "matrixdotorg/synapse:latest"),
    ("SEARXNG_IMAGE", "searxng", "searxng/searxng:latest"),
    ("POSTGRES_IMAGE", "matrix", "postgres:16-alpine"),
    ("PGVECTOR_IMAGE", "honcho", "pgvector/pgvector:pg15"),
    ("REDIS_IMAGE", "honcho", "redis:8-alpine"),
    ("VALKEY_IMAGE", "searxng", "valkey/valkey:8-alpine"),
    ("OLLAMA_IMAGE", "ollama", "ollama/ollama:latest"),
)
DIGEST = re.compile(r"^Digest:\s*(sha256:[0-9a-f]{64})\s*$", re.MULTILINE)
VERSION = re.compile(r"\b(\d+)\.(\d+)\.(\d+)\b")


def command(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


def load_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            result[key] = value.strip()
    return result


def latest_apt() -> tuple[list[str], list[str]]:
    updates: list[str] = []
    errors: list[str] = []
    # Updating indexes is not installing/upgrading software. It ensures the candidate
    # comparison is meaningful even when the previous refresh marker is recent.
    try:
        refresh = command(["apt-get", "-o", "Acquire::Retries=1", "-o", "Acquire::http::Timeout=20", "-o", "Acquire::https::Timeout=20", "update", "-qq"], 160)
        if refresh.returncode != 0 or "failed to fetch" in refresh.stderr.lower() or "some index files failed" in refresh.stderr.lower():
            errors.append("Ubuntu package index refresh was incomplete")
            return updates, errors
    except (OSError, subprocess.TimeoutExpired):
        errors.append("Ubuntu package index refresh was unavailable")
        return updates, errors
    for package in PACKAGES:
        try:
            p = command(["apt-cache", "policy", package], 10)
            installed = re.search(r"^\s*Installed:\s*(\S+)", p.stdout, re.MULTILINE)
            candidate = re.search(r"^\s*Candidate:\s*(\S+)", p.stdout, re.MULTILINE)
            if p.returncode or not installed or not candidate or candidate.group(1) == "(none)":
                errors.append(f"Cannot verify package candidate: {package}")
                continue
            current, proposed = installed.group(1), candidate.group(1)
            if current == "(none)":
                updates.append(f"Missing managed Ubuntu package: {package}")
            elif command(["dpkg", "--compare-versions", proposed, "gt", current], 5).returncode == 0:
                updates.append(f"Ubuntu package update: {package}")
        except (OSError, subprocess.TimeoutExpired):
            errors.append(f"Cannot compare package versions: {package}")
    return updates, errors


def owned(env: dict[str, str], key: str, desired: str) -> bool:
    current = env.get(key, "")
    previous_auto = env.get("LATTICEVALE_" + key + "_AUTO", "")
    return not current or current == desired or (bool(previous_auto) and current == previous_auto)


def selected(options: dict, service: str) -> bool:
    if service == "hermes":
        return True
    if service == "ollama":
        return options.get("ollamaBackend") != "windows-native" and bool(options.get("honcho") or options.get("hermesLocalAI"))
    return bool(options.get(service))


def image_updates(env: dict[str, str], options: dict) -> tuple[list[str], list[str]]:
    updates: list[str] = []
    errors: list[str] = []
    for key, feature, desired in IMAGES:
        if not selected(options, feature):
            continue
        # Never query or replace an explicitly user-owned image reference.
        if not owned(env, key, desired):
            continue
        current = env.get(key) or desired
        if current != desired:
            updates.append(f"Installer-owned image channel changed: {key}")
            continue
        try:
            local = command(["docker", "image", "inspect", current, "--format", "{{json .RepoDigests}}"], 20)
            if local.returncode:
                updates.append(f"Managed Docker image not installed: {key}")
                continue
            digests = json.loads(local.stdout)
            if not isinstance(digests, list) or not digests:
                errors.append(f"Cannot verify locally imported Docker image digest: {key}")
                continue
            registry = command(["docker", "buildx", "imagetools", "inspect", current], 30)
            match = DIGEST.search(registry.stdout)
            if registry.returncode or not match:
                errors.append(f"Cannot verify registry digest: {key}")
                continue
            remote = match.group(1)
            if not any(str(d).rsplit("@", 1)[-1] == remote for d in digests):
                updates.append(f"Newer managed Docker image digest: {key}")
        except (OSError, subprocess.TimeoutExpired, ValueError, TypeError):
            errors.append(f"Cannot compare image digests: {key}")
    return updates, errors


def optional_sources(stack: Path, env: dict[str, str], options: dict) -> tuple[list[str], list[str]]:
    updates: list[str] = []
    errors: list[str] = []
    if options.get("qmd") and owned(env, "QMD_VERSION", "latest"):
        try:
            local = command(["docker", "run", "--rm", "--network", "none", "--entrypoint", "qmd", "hermes-qmd:local", "--version"], 20)
            if local.returncode:
                updates.append("QMD image missing or its installed version is unreadable")
            else:
                match = VERSION.search(local.stdout + local.stderr)
                if not match:
                    errors.append("Cannot determine installed QMD version")
                else:
                    request = Request("https://registry.npmjs.org/@tobilu%2Fqmd/latest", headers={"User-Agent": "LatticeVale-update-check/14.6.7"})
                    with urlopen(request, timeout=15) as response:
                        release = json.load(response).get("version", "")
                    proposed = VERSION.search(release)
                    if not proposed:
                        errors.append("Cannot determine current QMD stable release")
                    elif tuple(map(int, proposed.groups())) > tuple(map(int, match.groups())):
                        updates.append("Newer QMD npm release")
        except (OSError, ValueError, TimeoutError, subprocess.TimeoutExpired):
            errors.append("Cannot compare QMD npm versions")
    if options.get("honcho"):
        repo = stack / "vendor" / "honcho"
        previous_auto = env.get("LATTICEVALE_HONCHO_SOURCE_AUTO", "")
        try:
            if not (repo / ".git").is_dir():
                updates.append("Managed Honcho source missing")
            else:
                head = command(["git", "-C", str(repo), "rev-parse", "HEAD"], 10)
                origin = command(["git", "-C", str(repo), "remote", "get-url", "origin"], 10)
                current = head.stdout.strip()
                official = origin.stdout.strip() in ("https://github.com/plastic-labs/honcho.git", "https://github.com/plastic-labs/honcho")
                installer_owned = official and (bool(previous_auto) and current == previous_auto or
                    not previous_auto and current in {"444897975c95393b0d48024470ece03c025d3aa4"})
                if head.returncode or origin.returncode:
                    errors.append("Cannot inspect Honcho checkout")
                elif installer_owned:
                    remote = command(["git", "ls-remote", "--tags", "https://github.com/plastic-labs/honcho.git"], 30)
                    # Annotated Git tags have a tag-object SHA distinct from
                    # the checked-out commit SHA. Prefer the peeled ^{} entry.
                    tags: dict[str, str] = {}
                    for line in remote.stdout.splitlines():
                        parts = line.split()
                        if len(parts) != 2 or not parts[1].startswith("refs/tags/"):
                            continue
                        name = parts[1][len("refs/tags/"):]
                        peeled = name.endswith("^{}")
                        tag = name[:-3] if peeled else name
                        if not re.fullmatch(r"v?\d+\.\d+\.\d+", tag):
                            continue
                        if peeled or tag not in tags:
                            tags[tag] = parts[0]
                    stable = [(tuple(map(int, VERSION.search(tag).groups())), sha) for tag, sha in tags.items()]
                    if remote.returncode or not stable:
                        errors.append("Cannot determine latest Honcho stable tag")
                    elif current != max(stable)[1]:
                        updates.append("Newer or different official Honcho stable source")
        except (OSError, subprocess.TimeoutExpired):
            errors.append("Cannot compare Honcho source")
    return updates, errors


def check(stack: Path) -> tuple[list[str], list[str]]:
    if not stack.is_dir() or stack.is_symlink():
        return [], ["Managed stack directory is absent or unsafe"]
    try:
        options = json.loads((stack / "install-options.json").read_text(encoding="utf-8"))
        env = load_env(stack / ".env")
        if not isinstance(options, dict):
            raise ValueError("invalid options")
    except (OSError, ValueError, TypeError):
        return [], ["Managed options or environment cannot be read"]
    updates, errors = latest_apt()
    for probe in (image_updates,):
        available, unknown = probe(env, options)
        updates.extend(available)
        errors.extend(unknown)
    available, unknown = optional_sources(stack, env, options)
    updates.extend(available)
    errors.extend(unknown)
    return updates, errors


def main() -> int:
    if len(sys.argv) != 2 or os.geteuid() != 0:
        print("Managed update check requires a stack path and root privileges", file=sys.stderr)
        return 2
    updates, unknown = check(Path(sys.argv[1]))
    for item in updates:
        print("UPDATE: " + item)
    for item in unknown:
        print("UNVERIFIED: " + item)
    verdict = "available" if updates else ("unknown" if unknown else "none")
    print("LATTICEVALE_MANAGED_UPDATE_STATUS=" + verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
