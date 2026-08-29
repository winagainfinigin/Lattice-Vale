#!/usr/bin/env python3
"""Read-only Hermes stack state audit.

The state file is advisory. Status is derived from the filesystem, selected options,
container state, and Hermes config whenever possible. No secrets are printed.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import shutil
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

STATES = {"NOT_INSTALLED", "PARTIAL", "CONFIGURED", "STOPPED", "STARTING", "RUNNING", "BROKEN", "OUTDATED", "DISABLED", "UNKNOWN"}
STARTUP_GRACE_SECONDS = 300

# The installer manages the rootful Engine in this distro. Auditing must never follow a
# caller's remote Docker context and report/mutate state from a different daemon.
for _name in ("DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH", "DOCKER_API_VERSION"):
    os.environ.pop(_name, None)
os.environ["DOCKER_HOST"] = "unix:///var/run/docker.sock"


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 8) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=timeout, check=False)
        return p.returncode, p.stdout.strip()
    except Exception:
        return 127, ""


def visible_cpu_count() -> int:
    """Return CPUs available to this WSL process, matching `nproc` semantics.

    os.cpu_count() can report the host/logical CPU total even when WSL or the process
    is constrained by processor allocation/affinity. The adaptive resource generator
    fingerprints `nproc`, so audit must compare against the same process-visible CPU
    set or it can falsely mark a freshly generated policy as stale.
    """
    try:
        affinity = os.sched_getaffinity(0)
        if affinity:
            return len(affinity)
    except (AttributeError, OSError):
        pass
    rc, out = run(["nproc"])
    if rc == 0 and out.isdigit() and int(out) > 0:
        return int(out)
    return os.cpu_count() or 0


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def env_keys(path: Path) -> set[str]:
    out: set[str] = set()
    if not path.is_file():
        return out
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                out.add(line.split("=", 1)[0].strip())
    except Exception:
        pass
    return out


def env_value(path: Path, key: str) -> str:
    """Read one dotenv value without exposing unrelated secrets."""
    if not path.is_file():
        return ""
    try:
        prefix = key + "="
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith(prefix):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def yaml_model_name(path: Path) -> str:
    if not path.is_file() or path.stat().st_size == 0:
        return ""
    try:
        import yaml  # type: ignore
        cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        model = cfg.get("model") or {}
        return str(model.get("default") or "").strip() if isinstance(model, dict) else ""
    except Exception:
        text = path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"(?ms)^model:\s*\n(?:^[ \t]+.*\n)*?^[ \t]+default:\s*['\"]?([^\s'\"#]+)", text)
        return m.group(1).strip() if m else ""


def yaml_model_default(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        import yaml  # type: ignore
        cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        model = cfg.get("model")
        return isinstance(model, dict) and isinstance(model.get("default"), str) and bool(model["default"].strip())
    except Exception:
        text = path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"(?ms)^model:\s*\n(?:^[ \t]+.*\n)*?^[ \t]+default:\s*['\"]?([^\s'\"#]+)", text)
        return bool(m and m.group(1).strip())

def yaml_multiplex_enabled(path: Path) -> bool:
    """True when either supported Hermes multiplex config form explicitly enables it."""
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        import yaml  # type: ignore
        cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(cfg, dict):
            return False
        if cfg.get("multiplex_profiles") is True:
            return True
        gateway = cfg.get("gateway") or {}
        return isinstance(gateway, dict) and gateway.get("multiplex_profiles") is True
    except Exception:
        text = path.read_text(encoding="utf-8", errors="replace")
        # Conservative fallback for malformed/unparseable YAML.
        if re.search(r"(?m)^multiplex_profiles:\s*(true|yes|on|1)\s*(?:#.*)?$", text, re.I):
            return True
        return bool(re.search(r"(?ms)^gateway:\s*\n(?:^[ \t]+.*\n)*?^[ \t]+multiplex_profiles:\s*(true|yes|on|1)\s*(?:#.*)?$", text, re.I))


def http_ok(url: str, headers: dict[str, str] | None = None, timeout: float = 3.0) -> bool:
    """True only for a successful application-level HTTP response."""
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= int(r.status) < 400
    except Exception:
        return False


def matrix_backend_reachable_from_hermes() -> bool:
    """Verify Docker DNS + Synapse API from the actual Hermes container network."""
    script = (
        "import http.client,socket; "
        "socket.getaddrinfo('synapse',8008); "
        "c=http.client.HTTPConnection('synapse',8008,timeout=5); "
        "c.request('GET','/_matrix/client/versions'); "
        "r=c.getresponse(); "
        "raise SystemExit(0 if 200 <= int(r.status) < 400 else 1)"
    )
    rc, _ = run(["docker", "exec", "hermes-agent", "python3", "-c", script], timeout=10)
    return rc == 0


def http_json(url: str, headers: dict[str, str] | None = None, timeout: float = 3.0) -> Any:
    """Return parsed JSON for a successful HTTP response, otherwise None."""
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if not (200 <= int(r.status) < 400):
                return None
            return json.loads(r.read().decode('utf-8'))
    except Exception:
        return None


def http_reachable(url: str, timeout: float = 3.0) -> bool:
    """True when an HTTP service answers, including expected auth failures such as 401."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 100 <= int(r.status) < 500
    except urllib.error.HTTPError as e:
        return 100 <= int(e.code) < 500
    except Exception:
        return False


def classify_service(enabled: bool, configured: bool, running: bool, broken: bool = False) -> str:
    if not enabled:
        return "DISABLED"
    if broken:
        return "BROKEN"
    if running:
        return "RUNNING"
    if configured:
        return "CONFIGURED"
    return "PARTIAL"


def container_state(name: str) -> dict[str, Any]:
    """Return enough Docker state to distinguish startup, clean stop, and real failure."""
    rc, out = run(["docker", "inspect", "-f", "{{json .State}}\n{{.HostConfig.RestartPolicy.Name}}", name])
    empty = {"exists": False, "running": False, "health": "", "age": None, "status": "", "exitCode": None, "oomKilled": False, "error": "", "restartPolicy": ""}
    if rc != 0 or not out:
        return empty
    parts = out.splitlines()
    try:
        state = json.loads(parts[0])
    except Exception:
        return {**empty, "exists": True}
    restart_policy = parts[1].strip().lower() if len(parts) > 1 else ""
    health = str(((state.get("Health") or {}).get("Status") or "")).strip().lower()
    running = bool(state.get("Running"))
    age = None
    started = str(state.get("StartedAt") or "").strip()
    if running and started:
        try:
            # Docker commonly emits RFC3339 with nanoseconds; datetime supports six-digit
            # microseconds, so trim the fractional part without changing the timezone.
            value = started
            m = re.match(r"^(.*?\.)(\d+)(Z|[+-]\d\d:\d\d)$", value)
            if m:
                value = m.group(1) + m.group(2)[:6].ljust(6, "0") + m.group(3)
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            dt = datetime.datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            age = max(0.0, (datetime.datetime.now(datetime.timezone.utc) - dt.astimezone(datetime.timezone.utc)).total_seconds())
        except Exception:
            age = None
    try:
        exit_code = int(state.get("ExitCode")) if state.get("ExitCode") is not None else None
    except Exception:
        exit_code = None
    return {
        "exists": True,
        "running": running,
        "health": health,
        "age": age,
        "status": str(state.get("Status") or "").strip().lower(),
        "exitCode": exit_code,
        "oomKilled": bool(state.get("OOMKilled")),
        "error": str(state.get("Error") or "").strip(),
        "restartPolicy": restart_policy,
    }


def runtime_failed(state: dict[str, Any]) -> bool:
    """True only when Docker state contains evidence of a runtime failure, not a clean stop."""
    if not state.get("exists") or state.get("running"):
        return False
    if state.get("oomKilled") or state.get("error"):
        return True
    if state.get("status") in {"dead", "restarting"}:
        return True
    code = state.get("exitCode")
    # Compose uses restart: unless-stopped. Explicit `docker compose stop` may leave
    # a graceful SIGTERM/SIGKILL-derived 143/137 exit code even though the user
    # intentionally stopped the service. If Docker leaves such a container exited
    # under unless-stopped, do not diagnose corruption merely from that exit code.
    if state.get("status") == "exited" and state.get("restartPolicy") == "unless-stopped" and code in {0, 137, 143}:
        return False
    return isinstance(code, int) and code != 0


def runtime_stopped(state: dict[str, Any]) -> bool:
    return bool(state.get("exists") and not state.get("running") and not runtime_failed(state))


def runtime_probe_failed(state: dict[str, Any]) -> bool:
    """A live service probe failed and Docker state no longer explains it as normal startup/stop."""
    if runtime_failed(state) or not state.get("exists"):
        return True
    if state.get("running") and state.get("health") == "unhealthy":
        return True
    if state.get("running") and not is_settling(state):
        return True
    return False


def is_settling(state: dict[str, Any]) -> bool:
    if not state.get("running"):
        return False
    if state.get("health") == "starting":
        return True
    age = state.get("age")
    return isinstance(age, (int, float)) and age < STARTUP_GRACE_SECONDS


def classify_runtime(enabled: bool, configured: bool, running: bool, state: dict[str, Any], broken: bool = False) -> str:
    if not enabled:
        return "DISABLED"
    if running:
        return "RUNNING"
    if configured and is_settling(state):
        return "STARTING"
    if configured and runtime_stopped(state):
        return "STOPPED"
    if broken:
        return "BROKEN"
    if configured:
        return "CONFIGURED"
    return "PARTIAL"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--offline", action="store_true", help="Do not query Docker or HTTP endpoints")
    ap.add_argument("--strict", action="store_true", help="Exit nonzero if selected components are broken/partial")
    args = ap.parse_args()

    root = Path(args.stack).expanduser().resolve()
    opts = read_json(root / "install-options.json", {}) if root.exists() else {}
    state = read_json(root / ".installer-state.json", {}) if root.exists() else {}
    selected = lambda k: bool(opts.get(k, False))

    def option_port(key: str, default: int) -> int:
        try:
            value = int(opts.get(key, default))
            return value if 1 <= value <= 65535 else default
        except Exception:
            return default

    hermes_api_port = option_port("hermesApiPort", 8642)
    dashboard_port = option_port("dashboardLocalPort", 9119)
    matrix_port = option_port("matrixLocalPort", 8008)
    searxng_port = option_port("searxngLocalPort", 8888)
    honcho_port = option_port("honchoLocalPort", 8000)

    report: dict[str, Any] = {
        "schema": 1,
        "stackPath": str(root),
        "installerStateSchema": state.get("schema"),
        "installerVersion": state.get("installerVersion"),
        "currentStage": state.get("currentStage"),
        "lastRunStatus": state.get("status"),
        "components": {},
        "profiles": [],
        "legacyArtifacts": [],
        "notes": [],
        "windowsHints": state.get("windows", {}) if isinstance(state.get("windows"), dict) else {},
        "windowsFollowup": [],
    }
    c = report["components"]

    if not root.exists():
        c["stack"] = {"status": "NOT_INSTALLED", "detail": "~/hermes-stack does not exist"}
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print("Hermes stack: NOT_INSTALLED")
        return 1 if args.strict else 0

    options_schema = opts.get("schema") if isinstance(opts, dict) else None
    state_version = state.get("installerVersion") if isinstance(state, dict) else None
    options_version = opts.get("installerVersion") if isinstance(opts, dict) else None

    def version_tuple(value):
        if not isinstance(value, str):
            return ()
        text = value.strip().lower().lstrip("v")
        parts = text.split(".")
        out = []
        for part in parts[:3]:
            if not part.isdigit():
                break
            out.append(int(part))
        return tuple(out)

    # The Windows installer stages this audit before upgrading an existing stack. Do not
    # classify a healthy v14.4.x installation as BROKEN merely because v14.5 read-only
    # helper files have not been copied yet; require them once stack metadata is v14.5+.
    core_files = ["compose.yaml", "configure-stack.sh", "manage.sh", "install-options.json"]
    detected_version = state_version or options_version
    if version_tuple(detected_version) >= (14, 5):
        core_files.extend(["state-audit.py", "latticevale_readonly.py", "repair-plan.py", "audit-free.py", "checkpoint-metadata.json"])
    if selected("qmd"):
        core_files.extend(["Dockerfile.qmd", "patch-qmd-bind.py", "qmd-index-cycle.sh"])
    missing = [x for x in core_files if not (root / x).is_file()]
    legacy_schema = isinstance(options_schema, int) and options_schema < 13
    def version_major(value):
        if not isinstance(value, str):
            return None
        text=value.strip().lower()
        if text.startswith("v"):
            text=text[1:]
        head=text.split(".",1)[0]
        return int(head) if head.isdigit() else None
    state_major = version_major(state_version)
    legacy_state = state_major is not None and state_major < 13
    version_mismatch = bool(options_version and state_version and str(options_version) != str(state_version))
    if missing:
        stack_status, stack_detail = "BROKEN", "missing: " + ", ".join(missing)
    elif legacy_schema or legacy_state:
        stack_status, stack_detail = "OUTDATED", f"installer metadata predates v13 (options schema={options_schema!r}, state version={state_version!r})"
    elif version_mismatch:
        stack_status, stack_detail = "OUTDATED", f"installer options/state versions differ ({options_version!r} vs {state_version!r}); rerun Resume / repair"
    else:
        stack_status, stack_detail = "CONFIGURED", f"installer metadata consistent (version={state_version or options_version!r})"
    c["stack"] = {"status": stack_status, "detail": stack_detail}

    # The audit normally runs as the selected Ubuntu user. Verify the paths that the
    # installer and UID/GID-mapped containers are expected to modify. Container-owned
    # database/model trees are intentionally excluded.
    writable_dirs = [
        root, root / "data", root / "config", root / "config/searxng", root / "backups",
        root / "secrets", root / "logs", root / "vendor", root / "vault", root / "workspace",
        root / "data/hermes", root / "data/qmd", root / "data/qmd/config", root / "data/qmd/cache",
        root / "data/synapse", root / "data/searxng-valkey", root / "data/honcho-redis",
    ]
    writable_files = [
        root / "compose.yaml", root / "configure-stack.sh", root / "manage.sh", root / "state-audit.py",
        root / "latticevale_readonly.py", root / "repair-plan.py", root / "audit-free.py", root / "checkpoint-metadata.json",
        root / "install-options.json", root / ".env", root / ".installer-state.json",
    ]
    permission_failures: list[str] = []
    for path in writable_dirs:
        if path.exists() and (not path.is_dir() or not os.access(path, os.W_OK | os.X_OK)):
            permission_failures.append(str(path.relative_to(root)) if path != root else ".")
    for path in writable_files:
        if path.exists() and (not path.is_file() or not os.access(path, os.W_OK)):
            permission_failures.append(str(path.relative_to(root)))
    if permission_failures:
        c["permissions"] = {
            "status": "BROKEN",
            "detail": "selected Ubuntu user cannot write: " + ", ".join(permission_failures[:12]) + (" ..." if len(permission_failures) > 12 else ""),
        }
    else:
        c["permissions"] = {
            "status": "CONFIGURED",
            "detail": "installer/user-owned write paths are writable; database/Ollama container-owned paths excluded",
        }

    docker_cli = shutil.which("docker") is not None
    docker_available = False
    compose_valid = False
    container_rows: dict[str, str] = {}
    if docker_cli:
        rc, _ = run(["docker", "compose", "config", "--quiet"], root)
        compose_valid = rc == 0
    if not args.offline and docker_cli:
        rc, _ = run(["docker", "info"])
        docker_available = rc == 0
        if docker_available:
            rc, out = run(["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}"])
            if rc == 0:
                for line in out.splitlines():
                    if "|" in line:
                        n, st = line.split("|", 1)
                        container_rows[n.strip()] = st.strip()
    if not docker_cli:
        docker_status, docker_detail = "NOT_INSTALLED", "docker CLI not found"
    elif not compose_valid:
        docker_status, docker_detail = "BROKEN", "Docker CLI present; compose model invalid/unavailable"
    elif docker_available:
        docker_status, docker_detail = "RUNNING", "daemon reachable; compose valid"
    else:
        docker_status, docker_detail = "CONFIGURED", "Docker/Compose installed; daemon not currently reachable"
    c["docker"] = {"status": docker_status, "detail": docker_detail}

    # Repair should notice age-related storage pressure before pulls/builds fail. This
    # reports the Linux filesystem view; host-side PowerShell separately checks the
    # Windows partition that stores the WSL VHDX. Do not infer physical VHDX size here.
    try:
        usage = shutil.disk_usage(root)
        free_gib = usage.free / (1024 ** 3)
        total_gib = usage.total / (1024 ** 3)
        stack_gib = None
        rc, out = run(["du", "-skx", str(root)], timeout=20)
        if rc == 0 and out.split():
            try: stack_gib = int(out.split()[0]) / (1024 ** 2)
            except Exception: stack_gib = None
        if free_gib < 2:
            storage_status = "BROKEN"
        else:
            storage_status = "CONFIGURED"
        detail = f"WSL filesystem free={free_gib:.1f} GiB of {total_gib:.1f} GiB"
        if stack_gib is not None:
            detail += f"; Hermes stack={stack_gib:.1f} GiB"
        if free_gib < 5:
            detail += "; Resume / repair can reclaim only disposable cache and will preserve persistent application/user data"
        c["storage"] = {"status": storage_status, "detail": detail}
    except Exception as exc:
        c["storage"] = {"status": "UNKNOWN", "detail": f"storage audit unavailable: {exc}"}

    runtime_cache: dict[str, dict[str, Any]] = {}
    def runtime(name: str) -> dict[str, Any]:
        if not docker_available:
            return {"exists": False, "running": False, "health": "", "age": None, "status": "", "exitCode": None, "oomKilled": False, "error": "", "restartPolicy": ""}
        if name not in runtime_cache:
            runtime_cache[name] = container_state(name)
        return runtime_cache[name]

    model_ok = yaml_model_default(root / "data/hermes/config.yaml")
    hermes_running = False
    if docker_available:
        rc, _ = run(["docker", "exec", "-u", "hermes", "hermes-agent", "hermes", "--version"])
        hermes_running = rc == 0
    hermes_state = runtime("hermes-agent")
    hermes_broken = docker_available and model_ok and not hermes_running and not args.offline and runtime_probe_failed(hermes_state)
    hermes_status = classify_runtime(True, model_ok, hermes_running, hermes_state, hermes_broken)
    c["hermes"] = {"status": hermes_status, "detail": ("provider/model configured; container is still starting" if hermes_status == "STARTING" else ("provider/model configured; container is stopped" if hermes_status == "STOPPED" else ("provider/model configured" if model_ok else "provider/model not configured")))}

    runtime_keys = env_keys(root / "secrets/hermes-runtime.env")
    default_profile_keys = env_keys(root / "data/hermes/.env")
    api_cfg = {"API_SERVER_ENABLED", "API_SERVER_HOST", "API_SERVER_PORT", "API_SERVER_KEY"}.issubset(default_profile_keys)
    api_run = False if args.offline else http_ok(f"http://127.0.0.1:{hermes_api_port}/health")
    api_broken = docker_available and api_cfg and not api_run and not args.offline and runtime_probe_failed(hermes_state)
    api_status = classify_runtime(True, api_cfg, api_run, hermes_state, api_broken)
    c["api"] = {"status": api_status, "detail": f"authenticated Hermes API configured on localhost:{hermes_api_port}" + ("; container is still starting" if api_status == "STARTING" else ("; container is stopped" if api_status == "STOPPED" else "")) if api_cfg else "Hermes API configuration incomplete"}

    dash_keys = runtime_keys
    dash_cfg = {"HERMES_DASHBOARD_BASIC_AUTH_USERNAME", "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH"}.issubset(dash_keys)
    dash_run = False if args.offline else http_reachable(f"http://127.0.0.1:{dashboard_port}/")
    dash_broken = selected("dashboard") and docker_available and dash_cfg and not dash_run and not args.offline and runtime_probe_failed(hermes_state)
    dash_status = classify_runtime(selected("dashboard"), dash_cfg, dash_run, hermes_state, dash_broken)
    c["dashboard"] = {"status": dash_status, "detail": ("authenticated dashboard config present; Hermes container is still starting" if dash_status == "STARTING" else ("authenticated dashboard config present; Hermes container is stopped" if dash_status == "STOPPED" else "authenticated dashboard config present")) if dash_cfg else "dashboard credentials/config incomplete"}

    # Profiles are verified from actual directories/config, not checkpoint markers.
    for worker in opts.get("workers", []) if isinstance(opts.get("workers"), list) else []:
        name = str(worker.get("name", "")).strip()
        if not name:
            continue
        pdir = root / "data/hermes/profiles" / name
        exists = pdir.is_dir()
        configured = yaml_model_default(pdir / "config.yaml") if exists else False
        matrix_opts = worker.get("matrix") if isinstance(worker.get("matrix"), dict) else {}
        report["profiles"].append({
            "name": name,
            "status": "CONFIGURED" if configured else ("PARTIAL" if exists else "NOT_INSTALLED"),
            "model": yaml_model_name(pdir / "config.yaml") if configured else "",
            "matrixEnabled": bool(matrix_opts.get("enabled", False)),
        })
    c["profiles"] = {"status": "DISABLED" if not selected("multiAgent") else ("CONFIGURED" if all(p["status"] == "CONFIGURED" for p in report["profiles"]) else "PARTIAL"), "detail": f"{len(report['profiles'])} managed profile(s)"}

    # LatticeVale intentionally runs standalone per-profile gateways. Current upstream
    # multiplexing still has credential, Matrix-adapter, session/state, and s6
    # reconciliation defects, so an explicit opt-in is a repair condition.
    topology_paths = [("default", root / "data/hermes/config.yaml")]
    managed_names: set[str] = set()
    try:
        managed_names.update(x.strip() for x in (root / ".installer-managed-profiles").read_text(encoding="utf-8").splitlines() if x.strip())
    except Exception:
        pass
    managed_names.update(p["name"] for p in report["profiles"] if p.get("name"))
    topology_paths.extend((name, root / "data/hermes/profiles" / name / "config.yaml") for name in sorted(managed_names))
    multiplex_profiles = [name for name, path in topology_paths if yaml_multiplex_enabled(path)]
    env_override_locations: list[str] = []
    env_paths = [("container runtime", root / "secrets/hermes-runtime.env"), ("default", root / "data/hermes/.env")]
    env_paths.extend((name, root / "data/hermes/profiles" / name / ".env") for name in sorted(managed_names))
    for label, env_path in env_paths:
        try:
            if any(line.startswith("GATEWAY_MULTIPLEX_PROFILES=") for line in env_path.read_text(encoding="utf-8").splitlines()):
                env_override_locations.append(label)
        except Exception:
            pass
    if multiplex_profiles or env_override_locations:
        detail_bits=[]
        if multiplex_profiles: detail_bits.append("enabled in profile config: " + ", ".join(multiplex_profiles))
        if env_override_locations: detail_bits.append("GATEWAY_MULTIPLEX_PROFILES override present in: " + ", ".join(env_override_locations))
        c["gatewayTopology"] = {"status": "BROKEN", "detail": "; ".join(detail_bits) + "; Resume / repair will restore standalone per-profile gateways"}
    else:
        c["gatewayTopology"] = {"status": "CONFIGURED", "detail": "standalone per-profile gateway topology; multiplexing disabled"}

    matrix_cfg = (root / "data/synapse/homeserver.yaml").is_file() and (root / "secrets/matrix-bot.env").is_file()
    matrix_run = False if args.offline else http_ok(f"http://127.0.0.1:{matrix_port}/health")
    matrix_token_valid = False
    if selected("matrix") and matrix_run and (root / "secrets/matrix-bot.env").is_file() and not args.offline:
        token = ""
        try:
            for line in (root / "secrets/matrix-bot.env").read_text(encoding="utf-8").splitlines():
                if line.startswith("MATRIX_ACCESS_TOKEN="):
                    token = line.split("=", 1)[1].strip()
                    break
        except Exception:
            pass
        if token:
            expected_default_user = env_value(root / "secrets/matrix-bot.env", "MATRIX_USER_ID")
            whoami = http_json(f"http://127.0.0.1:{matrix_port}/_matrix/client/v3/account/whoami", {"Authorization": f"Bearer {token}"})
            matrix_token_valid = isinstance(whoami, dict) and bool(expected_default_user) and whoami.get("user_id") == expected_default_user
    matrix_state = runtime("hermes-synapse")
    matrix_db_state = runtime("hermes-synapse-db")
    matrix_internal_ready = False
    if selected("matrix") and docker_available and not args.offline and not runtime_stopped(hermes_state):
        matrix_internal_ready = matrix_backend_reachable_from_hermes()
    matrix_settling = is_settling(matrix_state) or is_settling(matrix_db_state) or is_settling(hermes_state)
    matrix_runtime_failed = runtime_probe_failed(matrix_state) or runtime_probe_failed(matrix_db_state)
    matrix_broken = selected("matrix") and docker_available and matrix_cfg and not args.offline and (
        ((not matrix_run or not matrix_token_valid) and matrix_runtime_failed) or
        (matrix_run and matrix_token_valid and not runtime_stopped(hermes_state) and not is_settling(hermes_state) and not matrix_internal_ready)
    )
    matrix_stopped = selected("matrix") and matrix_cfg and runtime_stopped(matrix_state) and runtime_stopped(matrix_db_state)
    if selected("matrix") and matrix_cfg and not (matrix_run and matrix_token_valid) and matrix_settling:
        matrix_status = "STARTING"
    elif matrix_stopped and not matrix_broken:
        matrix_status = "STOPPED"
    else:
        matrix_live_ok = matrix_run and matrix_token_valid and (runtime_stopped(hermes_state) or matrix_internal_ready)
        matrix_status = classify_service(selected("matrix"), matrix_cfg, matrix_live_ok, matrix_broken)
    matrix_detail = "homeserver + bot identity present"
    if matrix_status == "STARTING":
        matrix_detail += "; containers are still starting"
    elif matrix_status == "STOPPED":
        matrix_detail += "; containers are stopped"
    elif selected("matrix") and not args.offline and not runtime_stopped(hermes_state) and not matrix_internal_ready:
        matrix_detail += "; Synapse is not reachable from inside hermes-agent"
    c["matrix"] = {"status": matrix_status, "detail": matrix_detail if matrix_cfg else "Matrix bootstrap incomplete"}

    # Matrix-enabled secondary profiles are intentionally distinct from ordinary workers:
    # Kanban-only profiles are healthy while stopped, but a profile explicitly selected for
    # Matrix must have its own identity/room/model binding and a resident profile gateway.
    profile_matrix_rows: list[dict[str, Any]] = []
    for worker in opts.get("workers", []) if isinstance(opts.get("workers"), list) else []:
        if not isinstance(worker, dict):
            continue
        name = str(worker.get("name", "")).strip()
        matrix_opts = worker.get("matrix") if isinstance(worker.get("matrix"), dict) else {}
        if not name or not bool(matrix_opts.get("enabled", False)):
            continue
        localpart = str(matrix_opts.get("localpart") or name).strip()
        expected_user = f"@{localpart}:hermes.local"
        pdir = root / "data/hermes/profiles" / name
        secret = root / "secrets/matrix-profiles" / f"{name}.env"
        info = root / ".matrix-profiles" / f"{name}.info"
        penv = pdir / ".env"
        model = yaml_model_name(pdir / "config.yaml")
        info_model = env_value(info, "HERMES_MODEL")
        token = env_value(secret, "MATRIX_ACCESS_TOKEN")
        user_id = env_value(secret, "MATRIX_USER_ID")
        room_id = env_value(secret, "MATRIX_ALLOWED_ROOMS")
        provisioning_state = env_value(secret, "LATTICEVALE_PROVISIONING_STATE") or env_value(secret, "FOUNDRY_PROVISIONING_STATE")
        recovery_key = env_value(secret, "MATRIX_RECOVERY_KEY")
        runtime_recovery_key = env_value(penv, "MATRIX_RECOVERY_KEY")
        cross_signing_state = env_value(secret, "LATTICEVALE_CROSS_SIGNING_STATE")
        if not cross_signing_state:
            cross_signing_state = "complete" if recovery_key and runtime_recovery_key == recovery_key else "pending"
        default_token = env_value(root / "secrets/matrix-bot.env", "MATRIX_ACCESS_TOKEN")
        configured = bool(
            model and info_model == model and secret.is_file() and info.is_file() and penv.is_file() and token and
            (not default_token or token != default_token) and
            user_id == expected_user and room_id.startswith("!") and ":" in room_id and
            env_value(penv, "MATRIX_ACCESS_TOKEN") == token and
            env_value(penv, "MATRIX_USER_ID") == expected_user and
            env_value(penv, "MATRIX_ALLOWED_ROOMS") == room_id and
            env_value(penv, "MATRIX_HOME_ROOM") == room_id
        )
        live_identity = False
        gateway_running = False
        if configured and docker_available and not args.offline:
            whoami = http_json(
                f"http://127.0.0.1:{matrix_port}/_matrix/client/v3/account/whoami",
                {"Authorization": f"Bearer {token}"},
            )
            live_identity = isinstance(whoami, dict) and whoami.get("user_id") == expected_user
            if provisioning_state != "pending-manual":
                rc, gateway_out = run(["docker", "exec", "-u", "hermes", "hermes-agent", "hermes", "-p", name, "gateway", "status"], timeout=20)
                gateway_running = rc == 0 and "running" in gateway_out.lower()
        if not configured:
            status = "PARTIAL"
            detail = "profile model/Matrix identity-room binding is incomplete"
        elif provisioning_state == "pending-manual":
            if args.offline or not docker_available:
                status = "CONFIGURED"
                detail = f"{expected_user} -> {room_id}; model={model}; resources ready, Hermes activation incomplete; Resume / repair will retry; runtime not tested"
            elif live_identity:
                status = "CONFIGURED"
                detail = f"{expected_user} -> {room_id}; model={model}; resources ready, Hermes activation incomplete; Resume / repair will retry"
            elif matrix_status == "STOPPED":
                status = "STOPPED"
                detail = f"{expected_user} -> {room_id}; model={model}; resources preserved, Matrix is stopped"
            else:
                status = "BROKEN"
                detail = f"{expected_user} -> {room_id}; model={model}; incomplete activation token identity failed live verification"
        elif args.offline or not docker_available:
            status = "CONFIGURED"
            detail = f"{expected_user} -> {room_id}; model={model}; runtime not tested"
        elif live_identity and gateway_running and matrix_internal_ready and cross_signing_state == "pending":
            status = "CONFIGURED"
            detail = f"{expected_user} -> {room_id}; model={model}; independent gateway running; E2EE cross-signing persistence pending; Resume / repair will retry"
        elif live_identity and gateway_running and matrix_internal_ready:
            status = "RUNNING"
            detail = f"{expected_user} -> {room_id}; model={model}; independent gateway running; cross-signing persisted"
        elif matrix_status == "STARTING" or is_settling(hermes_state):
            status = "STARTING"
            detail = f"{expected_user} -> {room_id}; model={model}; Matrix/Hermes runtime is still starting"
        elif matrix_status == "STOPPED" or runtime_stopped(hermes_state):
            status = "STOPPED"
            detail = f"{expected_user} -> {room_id}; model={model}; stack/profile gateway stopped"
        else:
            status = "BROKEN"
            if gateway_running and not matrix_internal_ready:
                detail = f"{expected_user} -> {room_id}; model={model}; gateway process is running but Synapse is unreachable from inside hermes-agent"
            else:
                detail = f"{expected_user} -> {room_id}; model={model}; identity or independent gateway failed live verification"
        profile_matrix_rows.append({"name": name, "status": status, "detail": detail, "userId": expected_user, "roomId": room_id, "model": model, "crossSigningState": cross_signing_state})
    report["profileMatrix"] = profile_matrix_rows
    if not selected("matrix") or not profile_matrix_rows:
        c["profileMatrix"] = {"status": "DISABLED", "detail": "no secondary profile selected for Matrix"}
    elif any(x["status"] == "BROKEN" for x in profile_matrix_rows):
        c["profileMatrix"] = {"status": "BROKEN", "detail": "one or more Matrix-enabled profile gateways/identities failed live verification"}
    elif any(x["status"] == "PARTIAL" for x in profile_matrix_rows):
        c["profileMatrix"] = {"status": "PARTIAL", "detail": "one or more Matrix-enabled profiles are not fully provisioned"}
    elif any(x["status"] == "STARTING" for x in profile_matrix_rows):
        c["profileMatrix"] = {"status": "STARTING", "detail": "one or more Matrix-enabled profile gateways are still starting"}
    elif any(x["status"] == "STOPPED" for x in profile_matrix_rows):
        c["profileMatrix"] = {"status": "STOPPED", "detail": "Matrix-enabled profile configuration is preserved but its gateway is stopped"}
    elif all(x["status"] in {"RUNNING", "CONFIGURED"} for x in profile_matrix_rows):
        pending_count = sum("Hermes activation incomplete" in x.get("detail", "") for x in profile_matrix_rows)
        detail = f"{len(profile_matrix_rows)} independent profile Matrix identity/room binding(s)"
        if pending_count:
            detail += f"; {pending_count} profile(s) need automatic activation retry via Resume / repair"
        c["profileMatrix"] = {"status": "RUNNING" if any(x["status"] == "RUNNING" for x in profile_matrix_rows) else "CONFIGURED", "detail": detail}
    else:
        c["profileMatrix"] = {"status": "UNKNOWN", "detail": "profile Matrix state could not be classified"}

    local_ai = selected("honcho") or selected("hermesLocalAI")
    ollama_backend = str(opts.get("ollamaBackend", "managed")).strip().lower()
    if ollama_backend not in {"managed", "windows-native"}:
        ollama_backend = "managed"
    managed_ollama = local_ai and ollama_backend == "managed"
    native_ollama = local_ai and ollama_backend == "windows-native"
    native_ollama_port = int(opts.get("windowsOllamaBridgePort", 11435) or 11435)

    # v14.2 runtime policy is installer-owned configuration, but legacy installs that
    # predate these options remain valid until the user explicitly opts in. Verify the
    # generated overlay/acceleration handoff without exposing secrets.
    policy_issues: list[str] = []
    limits_selected = bool(opts.get("containerResourceLimits", False))
    overlay_path = root / "compose.latticevale.yaml"
    compose_selector = env_value(root / ".env", "COMPOSE_FILE")
    if limits_selected:
        if not overlay_path.is_file():
            policy_issues.append("adaptive resource limits selected but compose.latticevale.yaml is missing")
        else:
            try:
                overlay_text = overlay_path.read_text(encoding="utf-8", errors="replace")
                if "cpus:" not in overlay_text or "mem_limit:" not in overlay_text:
                    policy_issues.append("adaptive resource overlay is incomplete")
                if "MALLOC_ARENA_MAX:" not in overlay_text:
                    policy_issues.append("adaptive RAM-efficiency allocator tuning is missing")
                if selected("matrix") and "SYNAPSE_CACHE_FACTOR:" not in overlay_text:
                    policy_issues.append("adaptive Synapse cache tuning is missing")
                if (selected("matrix") or selected("honcho")) and "shared_buffers=" not in overlay_text:
                    policy_issues.append("adaptive PostgreSQL shared-buffer tuning is missing")
            except Exception:
                policy_issues.append("adaptive resource overlay is unreadable")
        if "compose.latticevale.yaml" not in compose_selector.split(":"):
            policy_issues.append("COMPOSE_FILE does not include the adaptive resource overlay")
        resource_state = root / ".latticevale-resource-state"
        if not resource_state.is_file():
            policy_issues.append("adaptive resource fingerprint is missing; start or repair LatticeVale to recalculate it")
        else:
            try:
                values = {}
                for line in resource_state.read_text(encoding="utf-8", errors="replace").splitlines():
                    if "=" in line:
                        k,v=line.split("=",1); values[k.strip()]=v.strip()
                current_cpus = visible_cpu_count()
                mem_kib = 0
                for line in Path("/proc/meminfo").read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("MemTotal:"):
                        mem_kib=int(line.split()[1]); break
                current_mem_mib=mem_kib//1024
                if values.get("POLICY_VERSION") != "4" or str(current_cpus) != values.get("CPUS") or str(current_mem_mib) != values.get("MEM_MIB"):
                    policy_issues.append("adaptive resource policy revision or WSL CPU/RAM allocation changed; next LatticeVale start or repair will recalculate the overlay")
            except Exception:
                policy_issues.append("adaptive resource fingerprint is unreadable")

    # Redis/Valkey background-save/fork operations require Linux memory overcommit.
    # LatticeVale owns a sysctl.d drop-in for this prerequisite when either managed
    # Redis/Valkey workload is selected; audit the effective kernel value read-only.
    redis_like_enabled = bool(isinstance(opts, dict) and (opts.get("searxng") is True or opts.get("honcho") is True))
    if redis_like_enabled:
        rc, out = run(["sysctl", "-n", "vm.overcommit_memory"])
        if rc != 0 or out.strip() != "1":
            policy_issues.append("vm.overcommit_memory is not 1; Resume / repair will restore the LatticeVale Redis/Valkey prerequisite")

    accel_managed = isinstance(opts, dict) and "ollamaAcceleration" in opts
    requested_accel = str(opts.get("ollamaAcceleration", "cpu")).strip().lower() if accel_managed else "legacy"
    resolved_accel = env_value(root / ".env", "LATTICEVALE_OLLAMA_ACCELERATION").lower()
    if managed_ollama and accel_managed:
        if resolved_accel not in {"cpu", "nvidia", "amd"}:
            policy_issues.append("managed Ollama acceleration has not been resolved")
        elif requested_accel in {"cpu", "nvidia", "amd"} and resolved_accel != requested_accel:
            policy_issues.append(f"requested Ollama acceleration {requested_accel} resolved unexpectedly as {resolved_accel}")
        image = env_value(root / ".env", "OLLAMA_IMAGE")
        auto_image = env_value(root / ".env", "LATTICEVALE_OLLAMA_IMAGE_AUTO")
        custom_ollama_image = bool(auto_image and image and image != auto_image)
        if resolved_accel == "amd" and not custom_ollama_image and not image.endswith("-rocm"):
            policy_issues.append("AMD/ROCm acceleration is selected but the installer-managed Ollama image is not a ROCm image")
        if resolved_accel in {"nvidia", "amd"}:
            if not overlay_path.is_file():
                policy_issues.append("GPU acceleration is selected but compose.latticevale.yaml is missing")
            elif "compose.latticevale.yaml" not in compose_selector.split(":"):
                policy_issues.append("GPU acceleration overlay is not included by COMPOSE_FILE")
            else:
                try:
                    gpu_overlay = overlay_path.read_text(encoding="utf-8", errors="replace")
                    if resolved_accel == "nvidia" and ("driver: nvidia" not in gpu_overlay or "capabilities: [gpu]" not in gpu_overlay):
                        policy_issues.append("NVIDIA acceleration overlay is incomplete")
                    if resolved_accel == "amd" and ("/dev/kfd:/dev/kfd" not in gpu_overlay or "/dev/dri:/dev/dri" not in gpu_overlay):
                        policy_issues.append("AMD/ROCm acceleration overlay is incomplete")
                except Exception:
                    policy_issues.append("GPU acceleration overlay is unreadable")

    if native_ollama:
        if resolved_accel not in {"windows-native", ""}:
            policy_issues.append(f"native Windows Ollama selected but persisted acceleration marker is {resolved_accel}")
        native_info_path = root / ".windows-native-info"
        if not native_info_path.is_file():
            policy_issues.append("native Windows Ollama selected but .windows-native-info is missing")
        else:
            native_info = {}
            try:
                for line in native_info_path.read_text(encoding="utf-8", errors="replace").splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1); native_info[k.strip()] = v.strip()
                transport = native_info.get("TRANSPORT", "windows-gateway-relay")
                if transport not in {"windows-gateway-relay", "wsl-localhost-relay", "wsl-host-relay"}:
                    policy_issues.append(f"native Windows Ollama relay transport is invalid: {transport}")
                if transport in {"wsl-localhost-relay", "wsl-host-relay"} and not (root / "native-ollama-relay.sh").is_file():
                    policy_issues.append("WSL-local native Ollama transport is selected but relay helper is missing")
                saved_network_mode = str(opts.get("wslNetworkingMode", "") or "").strip()
                saved_network_owner = str(opts.get("wslNetworkingModeOwner", "") or "").strip()
                info_network_mode = native_info.get("WSL_NETWORKING_MODE", "")
                info_network_owner = native_info.get("WSL_NETWORKING_MODE_OWNER", "")
                if info_network_mode and saved_network_mode and info_network_mode != saved_network_mode:
                    policy_issues.append("native Ollama networking metadata disagrees with install-options.json")
                if info_network_owner and saved_network_owner and info_network_owner != saved_network_owner:
                    policy_issues.append("native Ollama networking owner metadata disagrees with install-options.json")
                if saved_network_owner == "shared-native-ollama-tailscale" and saved_network_mode not in {"nat", "virtioproxy"}:
                    policy_issues.append("shared native-Ollama/Tailscale networking policy must record a verified non-mirrored topology")
                if saved_network_owner == "user-existing-mirrored" and saved_network_mode != "mirrored":
                    policy_issues.append("user-existing-mirrored networking metadata must record mirrored mode")
            except Exception:
                policy_issues.append("native Windows Ollama relay metadata is unreadable")

    if policy_issues:
        c["runtimePolicy"] = {"status": "PARTIAL", "detail": "; ".join(policy_issues)}
    else:
        details=[]
        details.append("adaptive CPU/RAM ceilings enabled" if limits_selected else "LatticeVale resource ceilings disabled")
        if managed_ollama:
            details.append(f"Ollama acceleration configuration={resolved_accel or requested_accel}")
            image = env_value(root / ".env", "OLLAMA_IMAGE")
            auto_image = env_value(root / ".env", "LATTICEVALE_OLLAMA_IMAGE_AUTO")
            if resolved_accel in {"nvidia", "amd"}:
                details.append("GPU container plumbing configured; model VRAM offload not independently measured")
            if auto_image and image and image != auto_image:
                details.append("custom Ollama image override preserved")
        elif native_ollama:
            details.append("Ollama backend=native Windows via installer-owned WSL-only relay; native runtime owns GPU/CPU policy")
        if not accel_managed and managed_ollama:
            details.append("legacy acceleration policy preserved")
        c["runtimePolicy"] = {"status": "CONFIGURED", "detail": "; ".join(details)}

    ollama_configured = bool(opts.get("localTextModel")) and ((root / "data/ollama").exists() if managed_ollama else (root / ".windows-native-info").is_file())
    ollama_running = False
    ollama_models_ok = False
    native_ollama_detail = ""
    if managed_ollama and docker_available and not args.offline:
        rc, health = run(["docker", "inspect", "-f", "{{.State.Health.Status}}", "hermes-ollama"])
        ollama_running = rc == 0 and health.strip() == "healthy"
        if ollama_running:
            rc, models = run(["docker", "compose", "exec", "-T", "ollama", "ollama", "list"], root, timeout=15)
            names = {line.split()[0] for line in models.splitlines()[1:] if line.split()} if rc == 0 else set()
            needed = {str(opts.get("localTextModel", "")).strip()}
            if selected("honcho"):
                needed.add(str(opts.get("localEmbeddingModel", "")).strip())
            needed.discard("")
            ollama_models_ok = bool(needed) and needed.issubset(names)
    elif native_ollama and not args.offline:
        native_host = env_value(root / ".env", "WINDOWS_HOST_IP")
        if native_host:
            base = f"http://{native_host}:{native_ollama_port}"
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(base + "/api/version", timeout=5) as resp:
                    version_payload = json.load(resp)
                ollama_running = True
                version = str(version_payload.get("version", "")).strip() if isinstance(version_payload, dict) else ""
                native_ollama_detail = f"native Windows Ollama {version}".strip()
                with opener.open(base + "/api/tags", timeout=8) as resp:
                    tags = json.load(resp)
                names = {str(x.get("name") or x.get("model") or "") for x in tags.get("models", []) if isinstance(x, dict)} if isinstance(tags, dict) else set()
                needed = {str(opts.get("localTextModel", "")).strip()}
                if selected("honcho"):
                    needed.add(str(opts.get("localEmbeddingModel", "")).strip())
                needed.discard("")
                def present(wanted: str) -> bool:
                    return wanted in names or (":" not in wanted and any(name.startswith(wanted + ":") for name in names))
                ollama_models_ok = bool(needed) and all(present(x) for x in needed)
            except Exception:
                ollama_running = False
        else:
            native_ollama_detail = "native relay host address unavailable from .env"
    ollama_state = runtime("hermes-ollama") if managed_ollama else {"exists": False, "running": False, "health": "", "status": "external", "exit_code": 0, "oom_killed": False, "error": "", "started_at": ""}
    if native_ollama:
        if not local_ai:
            ollama_status = "DISABLED"
        elif not ollama_configured:
            ollama_status = "PARTIAL"
        elif args.offline:
            ollama_status = "CONFIGURED"
        elif ollama_running and ollama_models_ok:
            ollama_status = "RUNNING"
        elif ollama_running:
            ollama_status = "PARTIAL"
        else:
            ollama_status = "BROKEN"
        detail = "native Windows Ollama via WSL-only relay; models remain in the Windows runtime"
        if native_ollama_detail:
            detail += f" ({native_ollama_detail})"
        if ollama_running and not ollama_models_ok:
            detail += "; one or more selected models are missing"
    else:
        ollama_broken = local_ai and docker_available and ollama_configured and not args.offline and not (ollama_running and ollama_models_ok) and runtime_probe_failed(ollama_state)
        ollama_status = classify_runtime(local_ai, ollama_configured, ollama_running and ollama_models_ok, ollama_state, ollama_broken)
        detail = (("local-only inference selected; container is still starting" if ollama_status == "STARTING" else ("local-only inference selected; container is stopped" if ollama_status == "STOPPED" else "local-only inference selected; cloud features disabled")) if local_ai else "not selected")
    c["ollama"] = {"status": ollama_status, "detail": detail}

    service_defs = [
        ("searxng", "searxng", "hermes-searxng", f"http://127.0.0.1:{searxng_port}/", root / "config/searxng/settings.yml"),
        # QMD deliberately has no host-published port in v13. Its audit probe must
        # run inside the container or a healthy QMD would be falsely reported BROKEN.
        ("qmd", "qmd", "hermes-qmd", None, root / "data/qmd"),
        ("honcho", "honcho", "hermes-honcho-api", f"http://127.0.0.1:{honcho_port}/health", root / "data/hermes/honcho.json"),
    ]
    for key, label, container, url, cfgpath in service_defs:
        enabled = selected(key)
        configured = cfgpath.exists()
        if key == "honcho":
            configured = configured and (root / "config/honcho/config.toml").is_file()
            try:
                hcfg = (root / "config/honcho/config.toml").read_text(encoding="utf-8")
                expected_ollama_base = (f'http://windows.host:{native_ollama_port}/v1' if native_ollama else 'http://ollama:11434/v1')
                configured = configured and f'base_url = "{expected_ollama_base}"' in hcfg
            except Exception:
                configured = False
        if args.offline:
            running = False
        elif key == "qmd":
            rc, _ = run(["docker", "exec", "hermes-qmd", "curl", "-fsS", "--max-time", "5", "http://127.0.0.1:8181/health"], timeout=8)
            running = rc == 0
        else:
            running = bool(url) and http_ok(url)
        state_now = runtime(container)
        dependency_settling = False
        if key == "searxng":
            dependency_settling = is_settling(runtime("hermes-searxng-valkey"))
        elif key == "honcho":
            dependency_settling = is_settling(runtime("hermes-honcho-db")) or is_settling(runtime("hermes-honcho-redis")) or (managed_ollama and is_settling(runtime("hermes-ollama")))
        settling = is_settling(state_now) or dependency_settling
        dependency_failed = False
        dependency_missing = False
        if key == "searxng":
            dep = runtime("hermes-searxng-valkey")
            dependency_failed = runtime_probe_failed(dep)
        elif key == "honcho":
            deps = [runtime("hermes-honcho-db"), runtime("hermes-honcho-redis")] + ([runtime("hermes-ollama")] if managed_ollama else [])
            dependency_failed = any(runtime_probe_failed(dep) for dep in deps)
        broken = enabled and docker_available and configured and not running and not args.offline and (
            runtime_probe_failed(state_now) or dependency_failed
        )
        stopped_states = [state_now]
        if key == "searxng":
            stopped_states.append(runtime("hermes-searxng-valkey"))
        elif key == "honcho":
            stopped_states.extend([runtime("hermes-honcho-db"), runtime("hermes-honcho-redis")] + ([runtime("hermes-ollama")] if managed_ollama else []))
        cleanly_stopped = enabled and configured and bool(stopped_states) and all(runtime_stopped(dep) for dep in stopped_states)
        if enabled and configured and not running and settling:
            status = "STARTING"
        elif cleanly_stopped and not broken:
            status = "STOPPED"
        else:
            status = classify_service(enabled, configured, running, broken)
        detail = f"{label} selected" if enabled else "not selected"
        if status == "STARTING":
            detail += "; container/dependencies are still starting"
        elif status == "STOPPED":
            detail += "; container/dependencies are stopped"
        if key == "honcho" and enabled:
            detail = ("fully local Honcho + pgvector/Redis; inference/embeddings routed to " + ("native Windows Ollama" if native_ollama else "local WSL/Docker Ollama")) + ("; containers are still starting" if status == "STARTING" else ("; containers are stopped" if status == "STOPPED" else ""))
        c[key] = {"status": status, "detail": detail}

    kanban_ok = False
    if selected("kanban") and hermes_running and not args.offline:
        rc, _ = run(["docker", "exec", "-u", "hermes", "hermes-agent", "hermes", "kanban", "list"])
        kanban_ok = rc == 0
    if not selected("kanban"):
        kanban_status = "DISABLED"
    elif kanban_ok:
        kanban_status = "RUNNING"
    elif hermes_status == "STARTING":
        kanban_status = "STARTING"
    elif hermes_status == "STOPPED":
        kanban_status = "STOPPED"
    elif docker_available and not args.offline and runtime_probe_failed(hermes_state):
        kanban_status = "BROKEN"
    elif (root / "data/hermes/config.yaml").is_file():
        kanban_status = "CONFIGURED"
    else:
        kanban_status = "PARTIAL"
    c["kanban"] = {"status": kanban_status, "detail": "not selected" if not selected("kanban") else ("shared board command available" if kanban_ok else "selected; runtime verification pending")}

    tailscale_meta = (root / ".tailscale-info").is_file()
    if not selected("tailscale"):
        tailscale_status = "DISABLED"
        tailscale_detail = "not selected"
    elif not tailscale_meta:
        tailscale_status = "PARTIAL"
        tailscale_detail = "Windows-side state must be verified by PowerShell"
    else:
        tailscale_status = "CONFIGURED"
        networking_mode = str(opts.get("wslNetworkingMode", "") or "").strip().lower()
        networking_owner = str(opts.get("wslNetworkingModeOwner", "") or "").strip()
        topology = f"; WSL networking={networking_mode or 'unknown'}"
        if networking_owner:
            topology += f" ({networking_owner})"
        tailscale_detail = "Windows-host Serve + loopback bridge metadata present" + topology
        degraded = []
        # install-options.json is the canonical shared networking policy.  A live mode
        # mismatch is actionable because the Windows relay can adapt its target, but the
        # saved policy should still be reconciled on the next Windows repair run.
        if not args.offline and networking_mode in {"nat", "mirrored", "virtioproxy", "none"}:
            wslinfo = shutil.which("wslinfo")
            if wslinfo:
                rc_mode, live_mode = run([wslinfo, "--networking-mode"], timeout=5)
                live_mode = live_mode.strip().lower() if rc_mode == 0 else ""
                if live_mode in {"nat", "mirrored", "virtioproxy", "none"} and live_mode != networking_mode:
                    degraded.append(f"live WSL networking mode is {live_mode}, saved shared policy is {networking_mode}; Windows relay will adapt but Windows repair should reconcile saved policy")
        if bool(opts.get("tailscaleDashboard")) and c.get("dashboard", {}).get("status") in {"BROKEN", "PARTIAL", "UNKNOWN", "NOT_INSTALLED"}:
            degraded.append("Dashboard dependency is not healthy")
        if bool(opts.get("tailscaleMatrix")) and c.get("matrix", {}).get("status") in {"BROKEN", "PARTIAL", "UNKNOWN", "NOT_INSTALLED"}:
            degraded.append("Matrix dependency is not healthy")
        if native_ollama and not args.offline and ollama_status in {"BROKEN", "PARTIAL", "UNKNOWN", "NOT_INSTALLED"}:
            degraded.append("native Ollama/model dependency is not healthy")
        if degraded:
            tailscale_status = "PARTIAL"
            tailscale_detail += "; remote stack degraded: " + "; ".join(degraded)
    c["tailscale"] = {"status": tailscale_status, "detail": tailscale_detail}

    # Legacy artifacts are reported, never deleted by this audit.
    for p in ["data/tailscale", "data/tailscale-matrix", ".provider-configured"]:
        if (root / p).exists():
            report["legacyArtifacts"].append(p)
    for old_container in ["hermes-tailscale", "hermes-tailscale-matrix"]:
        if old_container in container_rows:
            report["legacyArtifacts"].append(f"container:{old_container}")

    bad = []
    # Core stack/Docker/Hermes are mandatory even when an optional component is disabled.
    for name in ("stack", "permissions", "storage", "docker", "hermes", "api"):
        if c.get(name, {}).get("status") not in {"CONFIGURED", "STARTING", "STOPPED", "RUNNING"}:
            bad.append(name)
    for name, item in c.items():
        if name in {"stack", "permissions", "storage", "docker", "hermes", "api", "tailscale"}:
            continue
        if item["status"] in {"BROKEN", "PARTIAL", "UNKNOWN", "NOT_INSTALLED"}:
            bad.append(name)

    # Tailscale and Windows add-ons/autostart live on the Windows host. A WSL-side audit
    # cannot authoritatively verify or repair them, so they are warnings rather than Linux
    # stack repair blockers. The Windows installer remains the authority for these states.
    tailscale_item = c.get("tailscale", {})
    if tailscale_item.get("status") in {"BROKEN", "PARTIAL", "UNKNOWN", "NOT_INSTALLED"}:
        report["windowsFollowup"].append({
            "name": "tailscale",
            "status": tailscale_item.get("status", "UNKNOWN"),
            "detail": tailscale_item.get("detail", "Windows-side verification required"),
        })
    for name, item in report.get("windowsHints", {}).items():
        if name == "verifiedAt" or not isinstance(item, dict):
            continue
        if item.get("status") in {"BROKEN", "PARTIAL", "UNKNOWN", "NOT_INSTALLED"}:
            report["windowsFollowup"].append({
                "name": name,
                "status": item.get("status", "UNKNOWN"),
                "detail": item.get("detail", "Windows-side verification required"),
            })
    if selected("multiAgent"):
        for p in report["profiles"]:
            if p["status"] != "CONFIGURED":
                bad.append(f"profile:{p['name']}")
    starting = [name for name, item in c.items() if item.get("status") == "STARTING"]
    expected_states = [hermes_state]
    if selected("matrix"):
        expected_states.extend([matrix_state, matrix_db_state])
    if selected("searxng"):
        expected_states.extend([runtime("hermes-searxng"), runtime("hermes-searxng-valkey")])
    if selected("qmd"):
        expected_states.extend([runtime("hermes-qmd"), runtime("hermes-qmd-indexer")])
    if managed_ollama:
        expected_states.append(ollama_state)
    if selected("honcho"):
        expected_states.extend([
            runtime("hermes-honcho-db"), runtime("hermes-honcho-redis"),
            runtime("hermes-honcho-api"), runtime("hermes-honcho-deriver"),
        ])
    stack_stopped = bool(
        docker_available
        and expected_states
        and all(runtime_stopped(state_now) for state_now in expected_states)
    )
    # STOPPED is benign only when the whole selected runtime is stopped together.
    # If one selected service is stopped while others are running, that is a partial
    # runtime outage and must not be reported HEALTHY merely because STOPPED is a
    # recognized non-corruption state.
    partial_stopped = [name for name, item in c.items() if item.get("status") == "STOPPED"]
    if partial_stopped and not stack_stopped:
        for name in partial_stopped:
            if name not in bad:
                bad.append(name)
        report["notes"].append("One or more selected services are stopped while the rest of the stack is active; reconcile/start the stopped services.")
    if bad:
        report["overall"] = "NEEDS_REPAIR"
    elif starting:
        report["overall"] = "STARTING"
        report["notes"].append("Selected services are still within the normal startup grace period; wait and verify again before choosing repair.")
    elif stack_stopped:
        report["overall"] = "STOPPED"
        report["notes"].append("The managed stack is configured but intentionally/not-currently running. Start it before treating runtime checks as repair failures.")
    else:
        report["overall"] = "HEALTHY"
    report["resumeFrom"] = (state.get("currentStage") or bad[0]) if bad else None

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("== Existing installation audit ==")
        order = ["stack", "permissions", "storage", "docker", "runtimePolicy", "ollama", "hermes", "api", "dashboard", "profiles", "gatewayTopology", "matrix", "searxng", "qmd", "honcho", "kanban", "tailscale"]
        for name in order:
            item = c.get(name)
            if item:
                print(f"{name:<20} {item['status']}")
                if item.get("status") in {"BROKEN", "PARTIAL", "OUTDATED", "UNKNOWN", "NOT_INSTALLED", "STARTING", "STOPPED"} and item.get("detail"):
                    print(f"  - {item['detail']}")
        for p in report["profiles"]:
            suffix = f" model={p.get('model')}" if p.get("model") else ""
            suffix += " matrix=enabled" if p.get("matrixEnabled") else " matrix=disabled"
            print(f"profile:{p['name']:<12} {p['status']}{suffix}")
        for p in report.get("profileMatrix", []):
            print(f"matrix-profile:{p['name']:<5} {p['status']}")
            if p.get("detail"):
                print(f"  - {p['detail']}")
        if report["legacyArtifacts"]:
            print("Legacy artifacts: " + ", ".join(report["legacyArtifacts"]))
        if report.get("windowsHints"):
            print("Windows recovery hints (live Windows state is rechecked by the PowerShell installer):")
            for name, item in report["windowsHints"].items():
                if name == "verifiedAt" or not isinstance(item, dict):
                    continue
                print(f"  {name:<18} {item.get('status','UNKNOWN')}")
                if item.get("status") in {"BROKEN", "PARTIAL", "UNKNOWN", "NOT_INSTALLED"} and item.get("detail"):
                    print(f"    - {item.get('detail')}")
        if report.get("windowsFollowup"):
            print("Windows follow-up remains optional to Linux-stack health; rerun the PowerShell installer only if you want to repair those Windows integrations.")
        print(f"Overall: {report['overall']}")
        if report.get("overall") == "STOPPED":
            print("The stack is configured but stopped; use ./manage.sh start or Resume / repair to start/reconcile it without treating stop state as corruption.")
        if report.get("resumeFrom"):
            print(f"Suggested resume point: {report['resumeFrom']}")

    return 2 if args.strict and report["overall"] != "HEALTHY" else 0


if __name__ == "__main__":
    raise SystemExit(main())
