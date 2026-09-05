#!/usr/bin/env python3
"""Canonical LatticeVale 14.6 architecture primitives.

This module owns schemas, durable-options validation, hardware/backend state
fingerprints, backend classification, host-memory budgeting, generated-state
validation, and atomic state writes.  PowerShell/Bash entry points should call
this module instead of reimplementing these invariants.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable

sys.dont_write_bytecode = True

ARCHITECTURE_VERSION = "14.6"
REASON = {
    "OK": "OK",
    "CPU_ALWAYS_AVAILABLE": "CPU_ALWAYS_AVAILABLE",
    "DML_DXG_MISSING": "DML_DXG_MISSING",
    "DML_WINDOWS_BUILD_UNSUPPORTED": "DML_WINDOWS_BUILD_UNSUPPORTED",
    "DML_WINDOWS_BUILD_UNKNOWN": "DML_WINDOWS_BUILD_UNKNOWN",
    "DML_BRIDGE_LIB_MISSING": "DML_BRIDGE_LIB_MISSING",
    "DML_RUNTIME_UNVERIFIED": "DML_RUNTIME_UNVERIFIED",
    "DML_RUNTIME_VERIFIED": "DML_RUNTIME_VERIFIED",
    "DML_VRAM_CAPACITY_UNAVAILABLE": "DML_VRAM_CAPACITY_UNAVAILABLE",
    "CUDA_DEVICE_MISSING": "CUDA_DEVICE_MISSING",
    "CUDA_RUNTIME_UNAVAILABLE": "CUDA_RUNTIME_UNAVAILABLE",
    "CUDA_RUNTIME_VISIBLE": "CUDA_RUNTIME_VISIBLE",
    "ROCM_DEVICE_MISSING": "ROCM_DEVICE_MISSING",
    "ROCM_ARCH_UNSUPPORTED": "ROCM_ARCH_UNSUPPORTED",
    "ROCM_RUNTIME_VISIBLE": "ROCM_RUNTIME_VISIBLE",
    "VULKAN_RENDER_NODE_MISSING": "VULKAN_RENDER_NODE_MISSING",
    "VULKAN_RUNTIME_PROBE_FAILED": "VULKAN_RUNTIME_PROBE_FAILED",
    "VULKAN_RUNTIME_VISIBLE": "VULKAN_RUNTIME_VISIBLE",
    "WINDOWS_NATIVE_UNAVAILABLE": "WINDOWS_NATIVE_UNAVAILABLE",
    "WINDOWS_NATIVE_VERIFIED": "WINDOWS_NATIVE_VERIFIED",
    "BACKEND_EXPLICIT_UNAVAILABLE": "BACKEND_EXPLICIT_UNAVAILABLE",
    "POLICY_BUDGET_MISMATCH": "POLICY_BUDGET_MISMATCH",
    "POLICY_FINGERPRINT_MISMATCH": "POLICY_FINGERPRINT_MISMATCH",
    "SCHEMA_FUTURE_VERSION": "SCHEMA_FUTURE_VERSION",
    "GENERATED_STATE_INVALID": "GENERATED_STATE_INVALID",
}


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True, ensure_ascii=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def parse_compatibility(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        out[key] = value
    return out


def load_compat(path: Path) -> dict[str, str]:
    """Backward-compatible name for the canonical compatibility.conf parser."""
    return parse_compatibility(path)


def schema_value(compat: dict[str, str], name: str) -> int:
    mapping = {
        "install_options": "INSTALL_OPTIONS_SCHEMA",
        "hardware_capabilities": "HARDWARE_CAPABILITIES_SCHEMA",
        "backend_capabilities": "BACKEND_CAPABILITIES_SCHEMA",
        "backend_health": "BACKEND_HEALTH_SCHEMA",
        "runtime_policy": "RUNTIME_POLICY_SCHEMA",
        "diagnostics": "DIAGNOSTICS_SCHEMA",
    }
    key = mapping[name]
    if key not in compat:
        raise ValueError(f"Missing {key} in compatibility.conf")
    raw = compat[key]
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid {mapping[name]} in compatibility.conf") from exc
    if value < 1 or value > 1_000_000:
        raise ValueError(f"Invalid {mapping[name]} in compatibility.conf")
    return value


def _bool(d: dict[str, Any], key: str) -> None:
    if key in d and not isinstance(d[key], bool):
        raise ValueError(f"{key} must be true or false")


def validate_install_options(data: Any, current_schema: int) -> dict[str, Any]:
    """Validate the persisted durable configuration.

    The schema ceiling is supplied by compatibility.conf; no consumer should own
    an independent maximum.
    """
    if not isinstance(data, dict):
        raise ValueError("top level must be an object")
    bool_keys = (
        "dashboard", "multiAgent", "kanban", "matrix", "tailscale", "installWindowsTailscale",
        "tailscaleDashboard", "tailscaleMatrix", "searxng", "qmd", "honcho", "hermesLocalAI",
        "obsidian", "unattendedUpdates", "autoStart", "windowsShortcuts", "keepWslServicesRunning",
        "containerResourceLimits", "resetCheckpoints", "forceProviderSetup", "forceProfileSetup",
        "rebuildMatrixIdentity", "repairMaintenance", "forceManagedUpdate", "universalRepairMigration",
    )
    for key in bool_keys:
        _bool(data, key)
    schema = data.get("schema", current_schema)
    if isinstance(schema, bool) or not isinstance(schema, int) or not 1 <= schema <= current_schema:
        if isinstance(schema, int) and schema > current_schema:
            raise ValueError(f"{REASON['SCHEMA_FUTURE_VERSION']}: schema {schema} is newer than supported schema {current_schema}")
        raise ValueError(f"schema must be an integer from 1 through {current_schema}")
    origin = data.get("repairOriginSchema", 0)
    if isinstance(origin, bool) or not isinstance(origin, int) or not 0 <= origin <= current_schema:
        if isinstance(origin, int) and origin > current_schema:
            raise ValueError(f"{REASON['SCHEMA_FUTURE_VERSION']}: repairOriginSchema {origin} is newer than supported schema {current_schema}")
        raise ValueError(f"repairOriginSchema must be an integer from 0 through {current_schema}")

    workers = data.get("workers", [])
    if not isinstance(workers, list):
        raise ValueError("workers must be an array")
    if len(workers) > 8:
        raise ValueError("at most 8 additional profiles are supported")
    seen: set[str] = set()
    name_re = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
    for i, worker in enumerate(workers, 1):
        if not isinstance(worker, dict):
            raise ValueError(f"worker {i} must be an object")
        name = worker.get("name")
        if not isinstance(name, str) or name == "default" or not name_re.fullmatch(name) or name in seen:
            raise ValueError(f"worker {i} has an unsafe, reserved, or duplicate name")
        seen.add(name)
        if "description" in worker and not isinstance(worker["description"], str):
            raise ValueError(f"worker {name} description must be text")
        if "clone" in worker and not isinstance(worker["clone"], bool):
            raise ValueError(f"worker {name} clone must be true or false")
        if "modelMode" in worker and worker["modelMode"] not in ("clone-default", "profile-selected"):
            raise ValueError(f"worker {name} modelMode is invalid")
        mx = worker.get("matrix")
        if mx is not None:
            if not isinstance(mx, dict):
                raise ValueError(f"worker {name} matrix must be an object")
            if "enabled" in mx and not isinstance(mx["enabled"], bool):
                raise ValueError(f"worker {name} matrix.enabled must be true or false")
            if mx.get("enabled") is True and name == "hermes":
                raise ValueError("a secondary Matrix-enabled profile cannot be named hermes")
            localpart = mx.get("localpart", name)
            if not isinstance(localpart, str) or localpart != name:
                raise ValueError(f"worker {name} Matrix localpart must match the profile name")
            mode = mx.get("roomMode", "create")
            if mode not in ("create", "existing"):
                raise ValueError(f"worker {name} matrix.roomMode must be create or existing")
            room_name = mx.get("roomName", f"LatticeVale {name}")
            if not isinstance(room_name, str) or not room_name.strip() or len(room_name) > 120 or "\n" in room_name or "\r" in room_name:
                raise ValueError(f"worker {name} Matrix room name is invalid")
            room_id = mx.get("roomId", "")
            if not isinstance(room_id, str):
                raise ValueError(f"worker {name} matrix.roomId must be text")
            if mode == "existing" and mx.get("enabled") and not re.fullmatch(r"![^:\s]+:[^\s]+", room_id):
                raise ValueError(f"worker {name} existing Matrix room ID is invalid")

    text_backend = data.get("localTextBackend", "ollama")
    if text_backend not in ("ollama", "directml"):
        raise ValueError("localTextBackend must be ollama or directml")
    directml_model = data.get("directmlTextModel", "Qwen/Qwen2.5-1.5B-Instruct")
    if not isinstance(directml_model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}/[A-Za-z0-9][A-Za-z0-9._-]{0,127}", directml_model):
        raise ValueError("directmlTextModel must be a safe Hugging Face owner/model repository ID")
    backend = data.get("ollamaBackend", "managed")
    if backend not in ("managed", "windows-native"):
        raise ValueError("ollamaBackend must be managed or windows-native")
    accel = data.get("ollamaAcceleration")
    if accel is not None and accel not in ("auto", "cpu", "nvidia", "amd", "vulkan"):
        raise ValueError("ollamaAcceleration must be auto, cpu, nvidia, amd, or vulkan")
    model_re = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
    for key in ("localTextModel", "localEmbeddingModel"):
        value = data.get(key)
        if value is not None and (not isinstance(value, str) or not model_re.fullmatch(value)):
            raise ValueError(f"{key} is not a safe Ollama model/tag")
    for key in (
        "hermesApiPort", "dashboardLocalPort", "matrixLocalPort", "searxngLocalPort", "honchoLocalPort",
        "tailscaleDashboardPort", "tailscaleMatrixPort", "dashboardBridgePort", "matrixBridgePort",
        "windowsOllamaBridgePort", "windowsOllamaTargetPort", "directmlPort",
    ):
        if key in data and (isinstance(data[key], bool) or not isinstance(data[key], int) or not 1 <= data[key] <= 65535):
            raise ValueError(f"{key} must be an integer TCP port from 1 to 65535")
    text_keys = (
        "timezone", "installerVersion", "installerMode", "repairOriginVersion", "questionnaireMode",
        "obsidianVaultWindowsPath", "obsidianVaultWslPath", "windowsOllamaBridgeTaskName",
        "windowsOllamaTransport", "windowsOllamaTargetAddress", "windowsOllamaHostAddress",
        "directmlAdapterName", "directmlGpuVendor", "gpuPreferenceMode", "gpuPreferenceName",
        "gpuPreferenceVendor", "gpuPreferenceId", "gpuPreferencePnpDeviceId", "inferenceBackendPreference",
    )
    for key in text_keys:
        if key in data and not isinstance(data[key], str):
            raise ValueError(f"{key} must be text")
    if data.get("directmlGpuVendor", "") not in ("", "amd", "nvidia", "intel", "qualcomm", "other"):
        raise ValueError("directmlGpuVendor must be amd, nvidia, intel, qualcomm, other, or empty")
    if data.get("gpuPreferenceVendor", "") not in ("", "amd", "nvidia", "intel", "qualcomm", "other"):
        raise ValueError("gpuPreferenceVendor must be amd, nvidia, intel, qualcomm, other, or empty")
    for key in ("directmlAdapterName", "gpuPreferenceName"):
        value = data.get(key, "")
        if isinstance(value, str) and ("\n" in value or "\r" in value or len(value) > 160):
            raise ValueError(f"{key} is too long or contains a newline")
    for key in ("gpuPreferenceId", "gpuPreferencePnpDeviceId"):
        value = data.get(key, "")
        if isinstance(value, str) and ("\n" in value or "\r" in value or len(value) > 256):
            raise ValueError(f"{key} is too long or contains a newline")
    if "directmlVramMiB" in data and (isinstance(data["directmlVramMiB"], bool) or not isinstance(data["directmlVramMiB"], int) or not 0 <= data["directmlVramMiB"] <= 1048576):
        raise ValueError("directmlVramMiB must be an integer from 0 through 1048576 MiB")
    if data.get("questionnaireMode") is not None and data.get("questionnaireMode") not in ("quick", "custom", "explicit"):
        raise ValueError("questionnaireMode must be quick, custom, or explicit")
    if data.get("gpuPreferenceMode") not in (None, "", "auto", "explicit"):
        raise ValueError("gpuPreferenceMode must be auto or explicit")
    if data.get("inferenceBackendPreference") not in (None, "", "auto", "directml", "cuda", "rocm", "vulkan", "cpu", "windows-native"):
        raise ValueError("inferenceBackendPreference is invalid")
    if backend == "windows-native":
        transport = data.get("windowsOllamaTransport", "windows-gateway-relay")
        if transport not in ("windows-gateway-relay", "wsl-localhost-relay", "wsl-host-relay"):
            raise ValueError("windowsOllamaTransport is invalid")
        target = str(data.get("windowsOllamaTargetAddress", "127.0.0.1")).strip().lower()
        if target == "localhost":
            target = "127.0.0.1"
        try:
            target_ip = ipaddress.ip_address(target)
        except ValueError as exc:
            raise ValueError("windowsOllamaTargetAddress must be IPv4 loopback") from exc
        if target_ip.version != 4 or not target_ip.is_loopback:
            raise ValueError("windowsOllamaTargetAddress must remain on IPv4 loopback")
        host_address = str(data.get("windowsOllamaHostAddress", "")).strip()
        if transport in ("windows-gateway-relay", "wsl-host-relay"):
            try:
                host_ip = ipaddress.ip_address(host_address)
            except ValueError as exc:
                raise ValueError("windowsOllamaHostAddress must be a non-loopback IPv4 address") from exc
            if host_ip.version != 4 or host_ip.is_loopback or host_ip.is_link_local:
                raise ValueError("windowsOllamaHostAddress must be a non-loopback, non-link-local IPv4 address")
    for key in ("kanbanMaxInProgress", "kanbanMaxInProgressPerProfile"):
        if key in data and (isinstance(data[key], bool) or not isinstance(data[key], int) or not 1 <= data[key] <= 8):
            raise ValueError(f"{key} must be an integer from 1 to 8")
    if data.get("obsidian"):
        wp = data.get("obsidianVaultWindowsPath", "")
        lp = data.get("obsidianVaultWslPath", "")
        if not isinstance(wp, str) or not re.fullmatch(r"[A-Za-z]:\\[^\r\n]+", wp):
            raise ValueError("obsidianVaultWindowsPath must be a Windows-local drive path")
        if not isinstance(lp, str) or not lp.startswith("/") or lp == "/" or "\n" in lp or "\r" in lp or "/.." in lp:
            raise ValueError("obsidianVaultWslPath must be an absolute WSL path to a mounted local Windows drive")
    return data


def run_capture(args: list[str], timeout: int = 8) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as exc:
        return 127, "", str(exc)


def _mem_total_mib() -> int:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 0


def visible_cpu_count() -> int:
    """Return CPUs visible to this WSL/process resource envelope.

    Affinity is authoritative when available; `nproc` is the portable WSL fallback.
    Host logical-CPU count is only the last resort so canonical hardware/resource
    policy never assumes CPUs that the selected distro/process cannot schedule.
    """
    try:
        affinity = os.sched_getaffinity(0)
        if affinity:
            return len(affinity)
    except (AttributeError, OSError):
        pass
    code, out, _err = run_capture(["nproc"], 4)
    raw = out.strip()
    if code == 0 and raw.isdigit() and int(raw) > 0:
        return int(raw)
    return os.cpu_count() or 0


def _device(path: str) -> dict[str, Any]:
    p = Path(path)
    result: dict[str, Any] = {"path": path, "present": p.exists()}
    if p.exists():
        try:
            st = p.stat()
            result.update({"mode": oct(st.st_mode & 0o777), "uid": st.st_uid, "gid": st.st_gid})
        except OSError:
            pass
    return result


PCI_VENDOR_NAMES = {
    "0x1002": "amd",
    "0x10de": "nvidia",
    "0x8086": "intel",
    "0x17cb": "qualcomm",
}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""


def _drm_adapters() -> list[dict[str, Any]]:
    adapters: list[dict[str, Any]] = []
    root = Path("/sys/class/drm")
    if not root.is_dir():
        return adapters
    for render in sorted(root.glob("renderD*"), key=lambda p: p.name):
        dev = render / "device"
        if not dev.exists():
            continue
        vendor_id = _read_text(dev / "vendor").lower()
        device_id = _read_text(dev / "device").lower()
        subsystem_vendor = _read_text(dev / "subsystem_vendor").lower()
        subsystem_device = _read_text(dev / "subsystem_device").lower()
        driver = ""
        try:
            driver = (dev / "driver").resolve().name
        except Exception:
            pass
        pci_address = ""
        try:
            pci_address = dev.resolve().name
        except Exception:
            pass
        vram_mib = 0
        for candidate in (dev / "mem_info_vram_total", dev / "mem_info_vis_vram_total"):
            raw = _read_text(candidate)
            if raw.isdigit():
                vram_mib = max(vram_mib, int(raw) // (1024 * 1024))
        material = {
            "renderNode": f"/dev/dri/{render.name}",
            "vendorId": vendor_id,
            "deviceId": device_id,
            "pciAddress": pci_address,
            "driver": driver,
        }
        adapters.append({
            "id": "wsl-gpu-" + fingerprint(material)[:16],
            "renderNode": f"/dev/dri/{render.name}",
            "vendor": PCI_VENDOR_NAMES.get(vendor_id, "unknown"),
            "vendorId": vendor_id,
            "deviceId": device_id,
            "subsystemVendorId": subsystem_vendor,
            "subsystemDeviceId": subsystem_device,
            "pciAddress": pci_address,
            "driver": driver,
            "vramMiB": vram_mib,
        })
    return adapters


def _nvidia_smi_path() -> str | None:
    found = shutil.which("nvidia-smi")
    if found:
        return found
    projected = Path("/usr/lib/wsl/lib/nvidia-smi")
    return str(projected) if projected.is_file() and os.access(projected, os.X_OK) else None


def _nonnegative_int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except Exception:
        return max(0, int(default))


def _windows_gpu_normalize(item: dict[str, Any]) -> dict[str, Any]:
    name = str(item.get("name") or item.get("Name") or "").strip()
    vendor = str(item.get("vendor") or item.get("Vendor") or "").strip().lower()
    pnp = str(item.get("pnpDeviceId") or item.get("PnpDeviceId") or "").strip()
    dedicated = _nonnegative_int(item.get("dedicatedMemoryMiB", item.get("DedicatedMemoryMiB", item.get("vramMiB", item.get("VramMiB", 0)))))
    shared = _nonnegative_int(item.get("sharedMemoryMiB", item.get("SharedMemoryMiB", 0)))
    display = _nonnegative_int(item.get("displayMemoryMiB", item.get("DisplayMemoryMiB", 0)))
    memory_source = str(item.get("memorySource") or item.get("MemorySource") or ("legacy-vram" if dedicated else "unknown"))
    memory_confidence = str(item.get("memoryConfidence") or item.get("MemoryConfidence") or ("legacy" if dedicated else "unknown"))
    memory_lower_bound = bool(item.get("memoryIsLowerBound", item.get("MemoryIsLowerBound", False)))
    memory_model = str(item.get("memoryModel") or item.get("MemoryModel") or ("dedicated" if dedicated >= 1024 else ("shared-or-uma" if shared >= 1024 else ("dedicated-low" if dedicated else "unknown"))))
    supplied_id = str(item.get("stableId") or item.get("id") or "").strip().lower()
    material = ("pnp|" + pnp.casefold()) if pnp else ("fallback|" + vendor.casefold() + "|" + name.casefold())
    stable_id = supplied_id if re.fullmatch(r"gpu-[0-9a-f]{16,64}", supplied_id) else "gpu-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return {
        "id": stable_id,
        "name": name,
        "vendor": vendor,
        "pnpDeviceId": pnp,
        # vramMiB remains a compatibility alias for dedicated/lower-bound memory.
        "vramMiB": dedicated,
        "dedicatedMemoryMiB": dedicated,
        "sharedMemoryMiB": shared,
        "displayMemoryMiB": display,
        "memorySource": memory_source,
        "memoryConfidence": memory_confidence,
        "memoryIsLowerBound": memory_lower_bound,
        "memoryModel": memory_model,
        "driverVersion": str(item.get("driverVersion") or item.get("DriverVersion") or ""),
        "driverDate": str(item.get("driverDate") or item.get("DriverDate") or ""),
    }


def probe_hardware(stack: Path, compat: dict[str, str], windows_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    windows_snapshot = windows_snapshot if isinstance(windows_snapshot, dict) else {}
    cpus = visible_cpu_count()
    mem_mib = _mem_total_mib()
    dxg = _device("/dev/dxg")
    drm_adapters = _drm_adapters()
    dri_render = [str(item.get("renderNode") or "") for item in drm_adapters if item.get("renderNode")]
    # Preserve the topology signal even when sysfs identity is unavailable (some WSL/kernel combinations).
    if not dri_render and Path("/dev/dri").exists():
        dri_render = sorted(str(p) for p in Path("/dev/dri").glob("renderD*") if p.exists())
    kfd = _device("/dev/kfd")
    bridge: dict[str, dict[str, Any]] = {}
    for name in ("libd3d12.so", "libd3d12core.so", "libdxcore.so"):
        p = Path("/usr/lib/wsl/lib") / name
        bridge[name] = {"path": str(p), "present": p.is_file()}

    smi = _nvidia_smi_path()
    smi_code, smi_out, smi_err = (127, "", "")
    nvidia_rows: list[dict[str, Any]] = []
    if smi:
        smi_code, smi_out, smi_err = run_capture(
            [smi, "--query-gpu=name,memory.total,driver_version,uuid,pci.bus_id", "--format=csv,noheader,nounits"],
            8,
        )
        if smi_code == 0:
            for raw in smi_out.splitlines():
                parts = [x.strip() for x in raw.split(",")]
                if len(parts) >= 5:
                    try:
                        memory = int(float(parts[1]))
                    except ValueError:
                        memory = 0
                    material = {"uuid": parts[3], "pciBusId": parts[4], "name": parts[0]}
                    nvidia_rows.append({
                        "id": "wsl-nvidia-" + fingerprint(material)[:16],
                        "name": parts[0],
                        "vramMiB": memory,
                        "driverVersion": parts[2],
                        "uuid": parts[3],
                        "pciBusId": parts[4],
                    })

    vulkan_code: int | None = None
    vulkan_devices: list[str] = []
    vulkan_error = ""
    if shutil.which("vulkaninfo"):
        vulkan_code, vulkan_out, vulkan_error = run_capture(["vulkaninfo", "--summary"], 10)
        if vulkan_code == 0:
            vulkan_devices = [m.group(1).strip() for m in re.finditer(r"deviceName\s*=\s*(.+)", vulkan_out)]

    windows_gpus = [_windows_gpu_normalize(x) for x in (windows_snapshot.get("gpus") or []) if isinstance(x, dict)]
    try:
        windows_build = int(windows_snapshot.get("windowsBuild") or 0)
    except Exception:
        windows_build = 0
    try:
        min_windows_build = int(compat.get("MIN_WINDOWS_BUILD", "19041"))
    except ValueError:
        min_windows_build = 19041
    try:
        dml_min_build = int(compat.get("DIRECTML_MIN_WINDOWS_BUILD", "22000"))
    except ValueError:
        dml_min_build = 22000
    supported_arches = tuple(x for x in compat.get("SUPPORTED_WSL_ARCHITECTURES", "x86_64").split() if x)
    arch = platform.machine()
    observed_core_violations: list[str] = []
    if windows_build and windows_build < min_windows_build:
        observed_core_violations.append(f"Windows build {windows_build} is below required {min_windows_build}")
    if supported_arches and arch not in supported_arches:
        observed_core_violations.append(f"WSL architecture {arch} is not in supported set {', '.join(supported_arches)}")
    if cpus < 1:
        observed_core_violations.append("WSL exposes no CPU")
    if mem_mib < 512:
        observed_core_violations.append("WSL exposes less than 512 MiB RAM")

    native_ollama = windows_snapshot.get("nativeOllama") if isinstance(windows_snapshot.get("nativeOllama"), dict) else {}
    payload: dict[str, Any] = {
        "schema": schema_value(compat, "hardware_capabilities"),
        "architectureVersion": ARCHITECTURE_VERSION,
        "generatedAt": utc_now(),
        "provenance": {
            "source": "live-wsl-plus-installer-windows-snapshot",
            "windowsSnapshotPresent": bool(windows_snapshot),
            "stackPath": str(stack),
        },
        "windows": {
            "build": windows_build,
            "version": windows_snapshot.get("windowsVersion", ""),
            "architecture": windows_snapshot.get("architecture", ""),
            "physicalMemoryMiB": windows_snapshot.get("physicalMemoryMiB", 0),
            "gpus": windows_gpus,
            "nativeOllama": native_ollama,
        },
        "wsl": {
            "distro": os.environ.get("WSL_DISTRO_NAME", ""),
            "kernel": platform.release(),
            "architecture": arch,
            "cpuCount": cpus,
            "memoryMiB": mem_mib,
            "dxg": dxg,
            "directxBridgeLibraries": bridge,
            "driRenderNodes": dri_render,
            "drmAdapters": drm_adapters,
            "kfd": kfd,
            "nvidiaSmi": {
                "toolPath": smi or "",
                "available": smi_code == 0,
                "exitCode": smi_code,
                "error": smi_err.strip()[:500] if smi_code != 0 else "",
                "gpus": nvidia_rows,
            },
            "vulkan": {
                "toolPresent": bool(shutil.which("vulkaninfo")),
                "probeSucceeded": vulkan_code == 0 if vulkan_code is not None else False,
                "exitCode": vulkan_code,
                "error": vulkan_error.strip()[:500] if vulkan_code not in (None, 0) else "",
                "devices": vulkan_devices,
            },
        },
        "qualification": {
            "observedCorePrerequisitesSatisfied": not observed_core_violations,
            "observedViolations": observed_core_violations,
            "windowsBuildKnown": bool(windows_build),
            "minimumWindowsBuild": min_windows_build,
            "supportedWslArchitectures": list(supported_arches),
        },
        "directmlPrerequisites": {
            "minimumWindowsBuild": dml_min_build,
            "windowsBuildKnown": bool(windows_build),
            "windowsBuildSupported": (windows_build >= dml_min_build) if windows_build else None,
            "dxgPresent": bool(dxg.get("present")),
            "bridgeLibrariesReady": all(bool((bridge.get(name) or {}).get("present")) for name in ("libd3d12.so", "libd3d12core.so", "libdxcore.so")),
        },
    }
    payload["hardwareFingerprint"] = fingerprint({
        "windows": payload["windows"],
        "wsl": payload["wsl"],
        "qualification": payload["qualification"],
        "directmlPrerequisites": payload["directmlPrerequisites"],
    })
    return payload


def _health_record(stack: Path, backend: str) -> dict[str, Any]:
    state = load_json(stack / "data" / "latticevale" / "backend-health.json", {})
    if not isinstance(state, dict):
        return {}
    record = (state.get("backends") or {}).get(backend, {})
    return record if isinstance(record, dict) else {}


def _capability_usable(capability: dict[str, Any]) -> bool:
    return bool(capability.get("available")) and capability.get("status") != "temporarily-failed"


def _select_windows_adapter(hardware: dict[str, Any], options: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    gpus = [x for x in ((hardware.get("windows") or {}).get("gpus") or []) if isinstance(x, dict)]
    mode = str(options.get("gpuPreferenceMode") or "auto")
    wanted_id = str(options.get("gpuPreferenceId") or "").strip()
    wanted_pnp = str(options.get("gpuPreferencePnpDeviceId") or "").strip()
    wanted_name = str(options.get("gpuPreferenceName") or options.get("directmlAdapterName") or "").strip()
    wanted_vendor = str(options.get("gpuPreferenceVendor") or options.get("directmlGpuVendor") or "").strip().lower()
    if mode == "explicit":
        if wanted_id:
            exact_id = [g for g in gpus if str(g.get("id") or "") == wanted_id]
            if len(exact_id) == 1:
                return exact_id[0], "GPU_EXPLICIT_STABLE_ID_MATCH"
        if wanted_pnp:
            exact_pnp = [g for g in gpus if str(g.get("pnpDeviceId") or "").casefold() == wanted_pnp.casefold()]
            if len(exact_pnp) == 1:
                return exact_pnp[0], "GPU_EXPLICIT_PNP_MATCH"
        if wanted_name:
            exact = [g for g in gpus if str(g.get("name") or "").casefold() == wanted_name.casefold()]
            if wanted_vendor:
                exact = [g for g in exact if str(g.get("vendor") or "").lower() == wanted_vendor]
            if len(exact) == 1:
                return exact[0], "GPU_EXPLICIT_NAME_MATCH"
            contains = [g for g in gpus if wanted_name.casefold() in str(g.get("name") or "").casefold()]
            if wanted_vendor:
                contains = [g for g in contains if str(g.get("vendor") or "").lower() == wanted_vendor]
            if len(contains) == 1:
                return contains[0], "GPU_EXPLICIT_SUBSTRING_MATCH"
        return None, "GPU_EXPLICIT_ADAPTER_NOT_FOUND"
    candidates = gpus
    if wanted_vendor:
        vendor_matches = [g for g in candidates if str(g.get("vendor") or "").lower() == wanted_vendor]
        if vendor_matches:
            candidates = vendor_matches
    if not candidates:
        return None, "GPU_WINDOWS_INVENTORY_EMPTY"
    candidates = sorted(candidates, key=lambda g: (-int(g.get("vramMiB") or 0), str(g.get("id") or "")))
    return candidates[0], "GPU_AUTO_SELECTED"


def _directml_admission_capacity(adapter: dict[str, Any] | None, hardware: dict[str, Any]) -> dict[str, Any]:
    """Return a bounded DirectML model-admission capacity for the selected adapter.

    Runtime torch-directml memory reporting remains preferred by the gateway. This
    value is the installer/capability fallback when that API is absent or unusable.
    Discrete adapters use Windows-reported dedicated memory (or a conservative WMI
    lower bound). UMA/integrated adapters may use only a bounded share of Windows-
    reported shared memory, additionally capped by the RAM currently visible to WSL.
    No GPU model name, vendor, or known-machine RAM size participates in the formula.
    """
    if not isinstance(adapter, dict):
        return {"capacityMiB": 0, "source": "unavailable", "confidence": "none", "memoryKind": "unknown", "isLowerBound": False}
    dedicated = _nonnegative_int(adapter.get("dedicatedMemoryMiB", adapter.get("vramMiB", 0)))
    shared = _nonnegative_int(adapter.get("sharedMemoryMiB", 0))
    source = str(adapter.get("memorySource") or "unknown")
    confidence = str(adapter.get("memoryConfidence") or "unknown")
    lower_bound = bool(adapter.get("memoryIsLowerBound", False))
    memory_model = str(adapter.get("memoryModel") or "").strip().lower()
    wsl_mem = _nonnegative_int(((hardware.get("wsl") or {}).get("memoryMiB", 0)))
    # UMA/integrated adapters can report a small fixed dedicated aperture even
    # though DirectML legitimately allocates from shared system memory. Do not
    # misclassify that aperture as the whole model-admission ceiling.
    prefer_shared = memory_model in {"shared-or-uma", "uma", "integrated", "shared"}
    if not prefer_shared and dedicated >= 256:
        return {
            "capacityMiB": dedicated,
            "source": source if source != "unknown" else "windows-dedicated-memory",
            "confidence": confidence if confidence != "unknown" else "medium",
            "memoryKind": "dedicated-lower-bound" if lower_bound else "dedicated",
            "isLowerBound": lower_bound,
        }
    if shared >= 512 and wsl_mem >= 1024:
        # UMA/shared-memory admission is intentionally conservative: bound the
        # Windows-reported shared-memory ceiling by 30% of WSL-visible RAM, then the
        # gateway applies its additional DirectML percentage limit. This is adaptive
        # to arbitrary WSL allocations and cannot claim more memory than either side
        # reports available.
        adaptive_cap = max(512, (wsl_mem * 30) // 100)
        capacity = min(shared, adaptive_cap)
        capacity = (capacity // 64) * 64
        if capacity >= 512:
            return {
                "capacityMiB": capacity,
                "source": "windows-shared-memory-bounded",
                "confidence": "medium",
                "memoryKind": "shared-uma",
                "isLowerBound": False,
                "windowsSharedMemoryMiB": shared,
                "wslMemoryMiB": wsl_mem,
            }
    if dedicated >= 256:
        return {
            "capacityMiB": dedicated,
            "source": source if source != "unknown" else "windows-dedicated-memory",
            "confidence": confidence if confidence != "unknown" else "medium",
            "memoryKind": "dedicated-lower-bound" if lower_bound else "dedicated",
            "isLowerBound": lower_bound,
        }
    return {"capacityMiB": 0, "source": "unavailable", "confidence": "none", "memoryKind": "unknown", "isLowerBound": False}


def classify_backends(hardware: dict[str, Any], options: dict[str, Any], stack: Path, compat: dict[str, str]) -> dict[str, Any]:
    wsl = hardware.get("wsl") or {}
    windows = hardware.get("windows") or {}
    bridge = wsl.get("directxBridgeLibraries") or {}
    dxg_ok = bool((wsl.get("dxg") or {}).get("present"))
    libs_ok = all(bool((bridge.get(name) or {}).get("present")) for name in ("libd3d12.so", "libd3d12core.so", "libdxcore.so"))
    try:
        windows_build = int(windows.get("build") or 0)
    except Exception:
        windows_build = 0
    try:
        dml_min_build = int(compat.get("DIRECTML_MIN_WINDOWS_BUILD", "22000"))
    except ValueError:
        dml_min_build = 22000
    dml_windows_ok = windows_build >= dml_min_build if windows_build else True

    nvidia = wsl.get("nvidiaSmi") or {}
    nvidia_ok = bool(nvidia.get("available")) and bool(nvidia.get("gpus") or [])
    arch = str(wsl.get("architecture") or platform.machine())
    drm_adapters = [x for x in (wsl.get("drmAdapters") or []) if isinstance(x, dict)]
    render_nodes = list(wsl.get("driRenderNodes") or [])
    amd_drm = [x for x in drm_adapters if str(x.get("vendor") or "") == "amd"]
    rocm_topology = bool((wsl.get("kfd") or {}).get("present")) and bool(render_nodes)
    rocm_ok = rocm_topology and arch == "x86_64" and (bool(amd_drm) or not drm_adapters)
    vulkan_topology = bool(render_nodes)
    native = windows.get("nativeOllama") if isinstance(windows.get("nativeOllama"), dict) else {}
    native_ready = bool(native.get("apiReady"))

    if not dml_windows_ok:
        dml_structural_status, dml_reason, dml_available = "unsupported", REASON["DML_WINDOWS_BUILD_UNSUPPORTED"], False
    elif not dxg_ok:
        dml_structural_status, dml_reason, dml_available = "unsupported", REASON["DML_DXG_MISSING"], False
    elif not libs_ok:
        dml_structural_status, dml_reason, dml_available = "unsupported", REASON["DML_BRIDGE_LIB_MISSING"], False
    else:
        dml_structural_status, dml_reason, dml_available = "available-unverified", REASON["DML_RUNTIME_UNVERIFIED"], True

    if rocm_topology and arch != "x86_64":
        rocm_reason = REASON["ROCM_ARCH_UNSUPPORTED"]
    else:
        rocm_reason = REASON["ROCM_RUNTIME_VISIBLE"] if rocm_ok else REASON["ROCM_DEVICE_MISSING"]

    vulkan_probe = wsl.get("vulkan") or {}
    caps: dict[str, dict[str, Any]] = {
        "directml": {
            "structuralStatus": dml_structural_status,
            "structuralReasonCode": dml_reason,
            "status": dml_structural_status,
            "reasonCode": dml_reason,
            "available": dml_available,
            "topology": {"dxg": dxg_ok, "bridgeLibraries": libs_ok, "windowsBuild": windows_build, "minimumWindowsBuild": dml_min_build},
        },
        "cuda": {
            "structuralStatus": "available-unverified" if nvidia_ok else "unsupported",
            "structuralReasonCode": REASON["CUDA_RUNTIME_VISIBLE"] if nvidia_ok else REASON["CUDA_DEVICE_MISSING"],
            "status": "available-unverified" if nvidia_ok else "unsupported",
            "reasonCode": REASON["CUDA_RUNTIME_VISIBLE"] if nvidia_ok else REASON["CUDA_DEVICE_MISSING"],
            "available": nvidia_ok,
            "topology": {"nvidiaSmi": bool(nvidia.get("available")), "gpuCount": len(nvidia.get("gpus") or [])},
        },
        "rocm": {
            "structuralStatus": "available-unverified" if rocm_ok else "unsupported",
            "structuralReasonCode": rocm_reason,
            "status": "available-unverified" if rocm_ok else "unsupported",
            "reasonCode": rocm_reason,
            "available": rocm_ok,
            "topology": {"kfd": bool((wsl.get("kfd") or {}).get("present")), "renderNodeCount": len(render_nodes), "amdDrmAdapterCount": len(amd_drm), "architecture": arch},
        },
        "vulkan": {
            "structuralStatus": "available-unverified" if vulkan_topology else "unsupported",
            "structuralReasonCode": REASON["VULKAN_RUNTIME_VISIBLE"] if vulkan_topology else REASON["VULKAN_RENDER_NODE_MISSING"],
            "status": "available-unverified" if vulkan_topology else "unsupported",
            "reasonCode": REASON["VULKAN_RUNTIME_VISIBLE"] if vulkan_topology else REASON["VULKAN_RENDER_NODE_MISSING"],
            "available": vulkan_topology,
            "experimental": False,
            "topology": {"renderNodeCount": len(render_nodes), "drmAdapters": drm_adapters},
            "probe": {"toolPresent": bool(vulkan_probe.get("toolPresent")), "succeeded": bool(vulkan_probe.get("probeSucceeded")), "devices": list(vulkan_probe.get("devices") or [])},
        },
        "windows-native": {
            "structuralStatus": "verified-working" if native_ready else "unsupported",
            "structuralReasonCode": REASON["WINDOWS_NATIVE_VERIFIED"] if native_ready else REASON["WINDOWS_NATIVE_UNAVAILABLE"],
            "status": "verified-working" if native_ready else "unsupported",
            "reasonCode": REASON["WINDOWS_NATIVE_VERIFIED"] if native_ready else REASON["WINDOWS_NATIVE_UNAVAILABLE"],
            "available": native_ready,
            "details": native,
        },
        "cpu": {
            "structuralStatus": "verified-working",
            "structuralReasonCode": REASON["CPU_ALWAYS_AVAILABLE"],
            "status": "verified-working",
            "reasonCode": REASON["CPU_ALWAYS_AVAILABLE"],
            "available": True,
        },
    }

    # Runtime health is transient evidence. It may change the currently active
    # fallback but must not mutate the policy topology for a DirectML gateway that
    # remains configured and safely proxies to Ollama. CUDA/ROCm/Vulkan auto-mode
    # can still re-budget explicitly when their runtime verification falls to CPU.
    runtime_health_material: dict[str, Any] = {}
    for backend in ("directml", "cuda", "rocm", "vulkan", "windows-native"):
        health = _health_record(stack, backend)
        if health and health.get("hardwareFingerprint") == hardware.get("hardwareFingerprint"):
            runtime_health_material[backend] = {
                "result": health.get("result"),
                "reasonCode": health.get("reasonCode"),
                "hardwareFingerprint": health.get("hardwareFingerprint"),
            }
            result = health.get("result")
            if result == "verified-working":
                caps[backend]["status"] = "verified-working"
                caps[backend]["reasonCode"] = health.get("reasonCode") or REASON["OK"]
                caps[backend]["available"] = True
            elif result == "failed":
                if caps[backend].get("available"):
                    caps[backend]["status"] = "temporarily-failed"
                caps[backend]["reasonCode"] = health.get("reasonCode") or f"{backend.upper().replace('-', '_')}_RUNTIME_FAILED"
            caps[backend]["runtimeHealth"] = health

    selected_adapter, adapter_reason = _select_windows_adapter(hardware, options)
    selected_admission = _directml_admission_capacity(selected_adapter, hardware)
    if isinstance(selected_adapter, dict):
        selected_adapter = dict(selected_adapter)
        selected_adapter["directmlAdmission"] = selected_admission
    if options.get("gpuPreferenceMode") == "explicit" and selected_adapter is None:
        caps["directml"]["selectionBlocked"] = True
        caps["directml"]["selectionReasonCode"] = adapter_reason
    caps["directml"]["admission"] = selected_admission

    requested_text = str(options.get("localTextBackend") or "ollama")
    requested_ollama = str(options.get("ollamaAcceleration") or "auto")
    explicit_backend = str(options.get("inferenceBackendPreference") or "auto") or "auto"
    windows_native_selected = options.get("ollamaBackend") == "windows-native"

    directml_structurally_usable = bool(caps["directml"].get("available")) and not caps["directml"].get("selectionBlocked")
    directml_runtime_usable = _capability_usable(caps["directml"]) and not caps["directml"].get("selectionBlocked")
    # Policy topology follows durable intent + structural capability. A transient
    # DirectML execution failure is handled inside the gateway by Ollama fallback;
    # retaining the DirectML host reserve makes a later health retry safe.
    text_backend = "directml" if requested_text == "directml" and directml_structurally_usable else "ollama"
    active_text_backend = "directml" if text_backend == "directml" and directml_runtime_usable else "ollama"

    def auto_ollama() -> tuple[str, str]:
        if windows_native_selected and _capability_usable(caps["windows-native"]):
            return "windows-native", "windows-native"
        if _capability_usable(caps["cuda"]):
            return "nvidia", "cuda"
        if _capability_usable(caps["rocm"]):
            return "amd", "rocm"
        if _capability_usable(caps["vulkan"]):
            return "vulkan", "vulkan"
        return "cpu", "cpu"

    if windows_native_selected:
        if _capability_usable(caps["windows-native"]):
            ollama_accel, auto_backend = "windows-native", "windows-native"
        else:
            ollama_accel, auto_backend = "cpu", "cpu"
    elif requested_ollama != "auto":
        requested_map = {"nvidia": "cuda", "amd": "rocm", "vulkan": "vulkan", "cpu": "cpu"}
        wanted = requested_map.get(requested_ollama, "cpu")
        if wanted == "cpu" or _capability_usable(caps[wanted]):
            ollama_accel, auto_backend = requested_ollama, wanted
        else:
            ollama_accel, auto_backend = auto_ollama()
    else:
        ollama_accel, auto_backend = auto_ollama()

    explicit_usable = True
    if explicit_backend in caps:
        # DirectML policy selection is structural; its gateway owns safe runtime
        # fallback. Other accelerators must be runtime-usable because they change
        # the managed Ollama resource envelope directly.
        if explicit_backend == "directml":
            explicit_usable = directml_structurally_usable
        else:
            explicit_usable = _capability_usable(caps[explicit_backend])
    elif explicit_backend != "auto":
        explicit_usable = False

    policy_selected = "directml" if text_backend == "directml" else auto_backend
    active_selected = "directml" if active_text_backend == "directml" else auto_backend
    if explicit_backend != "auto" and explicit_usable:
        selected = explicit_backend
        selection_reason = "BACKEND_EXPLICIT_AVAILABLE"
        if explicit_backend == "directml":
            active_selected = "directml" if directml_runtime_usable else auto_backend
        else:
            active_selected = explicit_backend
    elif explicit_backend != "auto":
        selected = policy_selected
        selection_reason = "BACKEND_EXPLICIT_UNAVAILABLE_SAFE_FALLBACK"
    else:
        selected = policy_selected
        selection_reason = "BACKEND_AUTO_SELECTED"

    gpu_available = any(bool(caps[name].get("available")) for name in ("directml", "cuda", "rocm", "vulkan", "windows-native"))
    qualification_observed = hardware.get("qualification") if isinstance(hardware.get("qualification"), dict) else {}
    core_ok = bool(qualification_observed.get("observedCorePrerequisitesSatisfied", True))
    qualification = {
        "runtimeClass": "gpu-acceleration-available" if gpu_available else "cpu-fallback",
        "qualifiedForCoreStack": core_ok,
        "reasonCode": ("QUALIFIED_GPU_OR_CPU_FALLBACK" if gpu_available else "QUALIFIED_CPU_FALLBACK") if core_ok else "CORE_PREREQUISITE_VIOLATION",
        "observedViolations": list(qualification_observed.get("observedViolations") or []),
        "note": "Core qualification is based only on observed installer prerequisites; acceleration capability is independent and may safely fall back to CPU.",
    }

    fallback_chain: list[str] = []
    for candidate in ("directml", "cuda", "rocm", "vulkan", "windows-native", "cpu"):
        if candidate == selected:
            continue
        if _capability_usable(caps[candidate]):
            fallback_chain.append(candidate)
    if "cpu" not in fallback_chain and selected != "cpu":
        fallback_chain.append("cpu")

    selection = {
        "requestedTextBackend": requested_text,
        "requestedOllamaAcceleration": requested_ollama,
        "requestedInferenceBackend": explicit_backend,
        # Policy/resource fields: stable across transient DirectML fallback.
        "textBackend": text_backend,
        "ollamaAcceleration": ollama_accel,
        "inferenceBackend": selected,
        "selectionReasonCode": selection_reason,
        "fallbackBackend": fallback_chain[0] if fallback_chain else "none",
        "fallbackChain": fallback_chain,
        # Runtime observation fields are intentionally excluded from backendFingerprint.
        "activeTextBackend": active_text_backend,
        "activeInferenceBackend": active_selected,
        "runtimeFallbackActive": bool(text_backend == "directml" and active_text_backend != "directml"),
    }

    payload = {
        "schema": schema_value(compat, "backend_capabilities"),
        "architectureVersion": ARCHITECTURE_VERSION,
        "generatedAt": utc_now(),
        "hardwareFingerprint": hardware.get("hardwareFingerprint", ""),
        "capabilities": caps,
        "adapterSelection": {
            "mode": str(options.get("gpuPreferenceMode") or "auto"),
            "requestedId": str(options.get("gpuPreferenceId") or ""),
            "requestedPnpDeviceId": str(options.get("gpuPreferencePnpDeviceId") or ""),
            "requestedName": str(options.get("gpuPreferenceName") or options.get("directmlAdapterName") or ""),
            "requestedVendor": str(options.get("gpuPreferenceVendor") or options.get("directmlGpuVendor") or ""),
            "selected": selected_adapter,
            "reasonCode": adapter_reason,
        },
        "selection": selection,
        "qualification": qualification,
    }

    # The policy fingerprint deliberately excludes transient backend-health records,
    # timestamps, diagnostic detail, and active DirectML fallback state. It changes
    # only when hardware topology, durable selection, or a resource-relevant Ollama
    # acceleration decision changes.
    policy_caps: dict[str, Any] = {}
    for name, cap in caps.items():
        policy_caps[name] = {
            "structuralStatus": cap.get("structuralStatus"),
            "structuralReasonCode": cap.get("structuralReasonCode"),
            "available": bool(cap.get("available")),
            "topology": cap.get("topology", {}),
            "experimental": bool(cap.get("experimental", False)),
            "selectionBlocked": bool(cap.get("selectionBlocked", False)),
            "selectionReasonCode": cap.get("selectionReasonCode", ""),
        }
    policy_selection = {k: selection.get(k) for k in (
        "requestedTextBackend", "requestedOllamaAcceleration", "requestedInferenceBackend",
        "textBackend", "ollamaAcceleration", "inferenceBackend", "selectionReasonCode",
    )}
    payload["backendFingerprint"] = fingerprint({
        "hardwareFingerprint": payload["hardwareFingerprint"],
        "capabilities": policy_caps,
        "adapterSelection": payload["adapterSelection"],
        "selection": policy_selection,
        "qualification": qualification,
    })
    payload["runtimeHealthFingerprint"] = fingerprint(runtime_health_material)
    return payload


def _round_up(value: float | int, quantum: int) -> int:
    if quantum <= 0:
        raise ValueError("quantum must be positive")
    n = int(value)
    return ((n + quantum - 1) // quantum) * quantum


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    if maximum < minimum:
        maximum = minimum
    return max(minimum, min(maximum, int(value)))


def _round_step(value: float | int, step: int = 64) -> int:
    if step < 1:
        raise ValueError("rounding step must be positive")
    return int((float(value) + (step / 2.0)) // step) * step


def host_memory_budget(mem_mib: int, accel: str, managed_ollama: bool, directml_selected: bool) -> dict[str, int]:
    """Derive host/container memory from live WSL RAM and selected execution paths.

    This intentionally has no machine-size table.  Safety floors/caps protect tiny
    and very large allocations, while the actual reserve scales continuously with
    the RAM WSL exposes.  DirectML receives an additional WSL-host reserve because
    its Python process lives outside Docker; CUDA/ROCm/Vulkan/CPU Ollama memory is
    already accounted for inside the container budget.
    """
    if mem_mib < 512:
        raise ValueError("WSL memory must be at least 512 MiB")
    if accel not in ("cpu", "vulkan", "nvidia", "amd"):
        raise ValueError("unsupported managed Ollama acceleration")

    # Keep ordinary WSL host headroom proportional to the actual allocation.  A
    # small fixed floor protects systemd/Docker/WSL services; the cap prevents a
    # large workstation from wasting an unbounded amount of RAM outside containers.
    base_ratio = 0.12 if managed_ollama else 0.15
    base_cap = max(384, min(6144, mem_mib - 384))
    reserve = _clamp_int(_round_step(mem_mib * base_ratio), 768, base_cap)

    directml = 0
    if directml_selected:
        # DirectML is a WSL-host workload. Scale its reserve continuously with WSL
        # RAM instead of matching any known topology.  The floor is a runtime safety
        # minimum, while the cap keeps large hosts from over-reserving indefinitely.
        directml_cap = max(384, min(8192, mem_mib - 384))
        dml_floor = min(2048, directml_cap)
        directml = _clamp_int(_round_step(mem_mib * 0.22), dml_floor, directml_cap)
        reserve = max(reserve, directml)

    budget = mem_mib - reserve
    if budget < 384:
        raise ValueError("too little memory remains for a safe LatticeVale container budget")
    return {"reserveMiB": reserve, "directmlHostReserveMiB": directml, "containerBudgetMiB": budget}


def ram_profile(mem_mib: int) -> str:
    if mem_mib <= 0:
        raise ValueError("memory must be positive")
    # Descriptive label only; no resource calculation branches on this value.
    gib = mem_mib / 1024.0
    return "compact" if gib < 10.0 else ("balanced" if gib < 24.0 else "large")


def cpu_profile(cpus: int) -> str:
    if cpus < 1:
        raise ValueError("CPU count must be at least 1")
    # Descriptive label only; quotas are calculated directly from the live count.
    return "compact" if cpus < 6 else ("balanced" if cpus < 12 else "high")


def _context_from_capacity(capacity_mib: int, *, gpu: bool) -> int:
    """Map continuously-derived capacity to a supported power-of-two context."""
    if capacity_mib < 0:
        raise ValueError("capacity cannot be negative")
    allowed = (4096, 8192, 16384, 32768, 65536)
    if gpu:
        raw = max(4096, int(max(0, capacity_mib - 2048) * 1.5))
    else:
        raw = max(4096, int(max(0, capacity_mib - 4096) * 2.0))
    chosen = allowed[0]
    for value in allowed:
        if value <= raw:
            chosen = value
        else:
            break
    return chosen


def ram_context_recommendation(mem_mib: int) -> int:
    if mem_mib <= 0:
        raise ValueError("memory must be positive")
    return _context_from_capacity(mem_mib, gpu=False)


def gpu_context_recommendation(usable_mib: int) -> int:
    return _context_from_capacity(usable_mib, gpu=True)


def directml_context_recommendation(mem_mib: int, adapter_vram_mib: int = 0) -> int:
    if mem_mib <= 0 or adapter_vram_mib < 0:
        raise ValueError("invalid DirectML context inputs")
    host_ctx = ram_context_recommendation(mem_mib)
    if adapter_vram_mib > 0:
        host_ctx = min(host_ctx, gpu_context_recommendation(adapter_vram_mib))
    # The current gateway intentionally caps model context at 32k even when the
    # host could sustain more; this is a model/runtime safety ceiling, not a host
    # topology preset.
    return min(32768, host_ctx)


def ollama_model_floor(
    mem_mib: int,
    artifact_mib: int,
    context_tokens: int,
    accel: str,
    hybrid_directml: bool,
    usable_gpu_max_mib: int = 0,
    usable_gpu_total_mib: int = 0,
) -> int:
    """Adaptive host-memory floor for managed Ollama.

    The calculation uses the measured model artifact when available.  Before a
    model is downloaded it derives a provisional allowance from current WSL RAM
    and context instead of selecting a fixed compact/balanced topology floor.
    """
    if mem_mib < 512:
        raise ValueError("WSL memory must be at least 512 MiB")
    if artifact_mib < 0 or context_tokens < 1024:
        raise ValueError("invalid model/context metrics")
    if accel not in ("cpu", "vulkan", "nvidia", "amd"):
        raise ValueError("unsupported managed Ollama acceleration")
    gpu_backed = accel in ("nvidia", "amd")

    runtime_ratio = 0.055 if hybrid_directml else 0.075
    runtime_base = _round_up(_clamp_int(mem_mib * runtime_ratio, 640 if hybrid_directml else 896, 3072), 64)
    context_divisor = 48 if hybrid_directml else (32 if gpu_backed else 20)
    context_overhead = _round_up(_clamp_int(context_tokens / context_divisor, 128, 2048), 64)

    if artifact_mib > 0:
        if gpu_backed:
            usable_total = max(0, usable_gpu_total_mib)
            if artifact_mib <= usable_total:
                host_model = max(128, int(artifact_mib * 0.10))
            else:
                host_model = max(0, artifact_mib - usable_total) + max(128, int(artifact_mib * 0.10))
            transient = max(256, int(artifact_mib * (0.10 if hybrid_directml else 0.14)))
        else:
            # CPU and experimental Vulkan are budgeted conservatively in host RAM
            # until runtime offload evidence proves otherwise.
            host_model = artifact_mib
            transient = max(384, int(artifact_mib * (0.12 if hybrid_directml else 0.20)))
    else:
        # Provisional model allowance scales with live WSL RAM.  This is replaced by
        # measured artifact sizing after download/reconciliation.
        ratio = 0.08 if hybrid_directml else (0.07 if gpu_backed else 0.13)
        provisional_cap = 2048 if hybrid_directml else (2048 if gpu_backed else 4096)
        host_model = _round_up(_clamp_int(mem_mib * ratio, 512 if hybrid_directml else 768, provisional_cap), 64)
        transient = max(256, host_model // 5)

    floor = runtime_base + context_overhead + host_model + transient
    floor = _round_up(floor, 256)
    # The floor may not consume nearly the entire VM before other services are even
    # considered.  service_memory_plan performs the final selected-service admission.
    return min(floor, max(1536, mem_mib - 768))


def hermes_floor_mib(matrix_gateways: int, kanban_concurrency: int) -> int:
    if matrix_gateways < 0:
        raise ValueError("Matrix gateway count cannot be negative")
    if not 1 <= kanban_concurrency <= 8:
        raise ValueError("Kanban concurrency must be between 1 and 8")
    # This is workload-topology adaptive rather than host-size specific: persistent
    # gateways and concurrent workers add bounded memory pressure to Hermes itself.
    extra_gateways = max(0, matrix_gateways - 1)
    extra_kanban = max(0, kanban_concurrency - 3)
    return min(4096, 1024 + extra_gateways * 192 + extra_kanban * 96)


def gpu_coordination(accel: str, count: int, min_mib: int, max_mib: int, directml_vendor: str, directml_selected: bool) -> dict[str, Any]:
    if accel not in ("nvidia", "amd"):
        return {"ollamaGpuOverheadMiB": 0, "directmlVramLimitPct": 75, "sharedVendor": False}
    if not directml_selected or directml_vendor != accel or count <= 0 or min_mib <= 0 or max_mib <= 0:
        return {"ollamaGpuOverheadMiB": 0, "directmlVramLimitPct": 75, "sharedVendor": False}
    # Coordinate two runtimes sharing the same vendor from measured VRAM, never a
    # hard-coded adapter size.  Heterogeneous sets use the smallest adapter as the
    # safety envelope and never pretend unlike VRAM pools are aggregate memory.
    similarity = min_mib / max_mib
    target_fraction = 0.50 if similarity >= 0.75 else max(0.25, min(0.50, similarity * 0.60))
    overhead = _round_step(max_mib * target_fraction, 256)
    overhead = min(overhead, _round_step(min_mib * 0.75, 256))
    overhead = max(256, overhead)
    directml_pct = _clamp_int(round((overhead / max_mib) * 100), 5, 50)
    return {"ollamaGpuOverheadMiB": overhead, "directmlVramLimitPct": directml_pct, "sharedVendor": True}


SERVICE_ORDER = (
    "hermes", "synapse-db", "synapse", "searxng-valkey", "searxng", "qmd", "qmd-indexer",
    "ollama", "honcho-db", "honcho-redis", "honcho-api", "honcho-deriver",
)


def _service_specs(
    budget_mib: int,
    *,
    matrix: bool,
    searxng: bool,
    qmd: bool,
    ollama: bool,
    honcho: bool,
    hermes_floor: int,
    ollama_floor: int,
) -> list[tuple[str, int, int, int]]:
    """Return adaptive workload minima/weights/caps for the current service set."""
    base: list[tuple[str, int, int, int]] = [("hermes", 8, hermes_floor, 12288)]
    if matrix:
        base += [("synapse-db", 2, 160, 4096), ("synapse", 2, 192, 4096)]
    if searxng:
        base += [("searxng-valkey", 1, 64, 2048), ("searxng", 2, 192, 3072)]
    if qmd:
        base += [("qmd", 2, 192, 4096), ("qmd-indexer", 2, 192, 4096)]
    if honcho:
        base += [
            ("honcho-db", 2, 192, 4096), ("honcho-redis", 1, 64, 2048),
            ("honcho-api", 4, 384, 6144), ("honcho-deriver", 3, 256, 6144),
        ]
    if ollama:
        base += [("ollama", 12, max(1536, ollama_floor), 98304)]

    min_total = sum(item[2] for item in base)
    extra = max(0, budget_mib - min_total)
    total_weight = max(1, sum(item[1] for item in base))
    specs: list[tuple[str, int, int, int]] = []
    for name, weight, minimum, absolute_max in base:
        # Each cap expands with the current free container envelope and workload
        # weight. Absolute maxima are safety rails only, never host-size profiles.
        adaptive_extra = _round_step(extra * (weight / total_weight) * 1.35, 16)
        cap = min(absolute_max, max(minimum, minimum + adaptive_extra))
        specs.append((name, weight, minimum, cap))
    return specs


def service_memory_plan(
    budget_mib: int,
    *,
    matrix: bool,
    searxng: bool,
    qmd: bool,
    ollama: bool,
    honcho: bool,
    hermes_floor: int,
    ollama_floor: int,
) -> dict[str, int]:
    """Water-fill enabled services from live budget with no RAM-size profiles."""
    if budget_mib < 384:
        raise ValueError("container budget is too small")
    if not 1024 <= hermes_floor <= 4096:
        raise ValueError("Invalid adaptive Hermes topology floor")
    specs = _service_specs(
        budget_mib, matrix=matrix, searxng=searxng, qmd=qmd, ollama=ollama,
        honcho=honcho, hermes_floor=hermes_floor, ollama_floor=ollama_floor,
    )
    mins = {n: m for n, _w, m, _c in specs}
    caps = {n: c for n, _w, _m, c in specs}
    weights = {n: w for n, w, _m, _c in specs}
    alloc = dict(mins)
    min_total = sum(mins.values())
    if min_total > budget_mib:
        enabled = ", ".join(n for n, _w, _m, _c in specs)
        raise ValueError(
            f"Adaptive resource policy cannot safely fit selected services: budget={budget_mib}MiB, "
            f"minimum={min_total}MiB, services={enabled}"
        )

    remaining = budget_mib - min_total
    while remaining >= 16:
        open_names = [n for n in alloc if alloc[n] + 16 <= caps[n]]
        if not open_names:
            break
        total_w = sum(weights[n] for n in open_names)
        snapshot = remaining
        progressed = False
        for name in sorted(open_names, key=lambda x: (-weights[x], x)):
            if remaining < 16:
                break
            share = max(16, int((snapshot * weights[name] / total_w) // 16) * 16)
            add = min(share, caps[name] - alloc[name], remaining)
            add = (add // 16) * 16
            if add >= 16:
                alloc[name] += add
                remaining -= add
                progressed = True
        if not progressed:
            break
    return {name: alloc[name] for name in SERVICE_ORDER if name in alloc}


def cpu_quota_plan(cpus: int, matrix_gateways: int, kanban_concurrency: int, accel: str) -> dict[str, int]:
    if cpus < 1:
        raise ValueError("CPU count must be at least one")
    if accel not in ("cpu", "vulkan", "nvidia", "amd"):
        raise ValueError("unsupported acceleration for CPU quota planning")
    # Quotas are adaptive milli-CPU ceilings.  They scale continuously from the
    # process-visible CPU count and workload pressure rather than whole-core tiers.
    capacity = cpus * 1000
    pressure = max(0, matrix_gateways - 1) * 0.055 + max(0, kanban_concurrency - 1) * 0.025
    hermes_ratio = min(1.0, 0.62 + pressure)
    ollama_ratio = 0.95 if accel in ("cpu", "vulkan") else 0.55
    medium_ratio = min(0.68, 0.38 + 0.025 * max(0, cpus - 1))
    light_ratio = min(0.36, 0.18 + 0.012 * max(0, cpus - 1))

    def quota(ratio: float, minimum: int = 250) -> int:
        raw = max(minimum, int(round(capacity * ratio)))
        return min(capacity, max(minimum, _round_step(raw, 50)))

    return {
        "hermes": quota(hermes_ratio, 500),
        "synapse-db": quota(medium_ratio), "synapse": quota(medium_ratio),
        "searxng-valkey": quota(light_ratio), "searxng": quota(medium_ratio),
        "qmd": quota(medium_ratio), "qmd-indexer": quota(medium_ratio),
        "ollama": quota(ollama_ratio, 500),
        "honcho-db": quota(medium_ratio), "honcho-redis": quota(light_ratio),
        "honcho-api": quota(medium_ratio), "honcho-deriver": quota(medium_ratio),
    }


def directml_cpu_thread_plan(cpus: int) -> int:
    if cpus < 1:
        raise ValueError("CPU count must be at least one")
    # DirectML inference is GPU-led but tokenization/model orchestration still needs
    # host CPU. Scale with visible CPUs while leaving capacity for Docker services.
    return _clamp_int(_round_step(cpus * 0.35, 1), 1, min(12, cpus))


def directml_generation_limit(context_tokens: int) -> int:
    if context_tokens < 1024:
        raise ValueError("DirectML context must be at least 1024 tokens")
    # Output allowance grows with the selected context while remaining bounded so a
    # single request cannot monopolize the WSL-host gateway indefinitely.
    return _clamp_int(_round_step(context_tokens / 16.0, 64), 256, 2048)


def ollama_runtime_settings(mem_mib: int, cpus: int, accel: str, directml_selected: bool) -> dict[str, Any]:
    if mem_mib < 512 or cpus < 1:
        raise ValueError("invalid WSL resource envelope")
    if accel not in ("cpu", "vulkan", "nvidia", "amd"):
        raise ValueError("unsupported Ollama acceleration")
    # Concurrency derives from both CPU and RAM. GPU-backed paths need less host CPU
    # per request, but RAM still constrains request/model bookkeeping.
    cpu_slots = max(1, int(cpus * (0.25 if accel in ("nvidia", "amd") else 0.18)))
    memory_slots = max(1, mem_mib // (6144 if accel in ("nvidia", "amd") else 8192))
    parallel = _clamp_int(min(cpu_slots, memory_slots), 1, 4)
    # Multiple loaded models are useful only when the VM has ample headroom and
    # DirectML is not simultaneously reserving host memory for a primary model.
    model_slots = max(1, mem_mib // 16384)
    max_loaded = 1 if directml_selected else _clamp_int(min(model_slots, max(1, cpus // 6)), 1, 3)
    keep_seconds = 0 if directml_selected else _clamp_int(mem_mib / 512.0, 15, 300)
    return {"maxLoadedModels": max_loaded, "parallel": parallel, "keepAlive": f"{keep_seconds}s"}


def runtime_tuning(mem_mib: int, cpus: int = 1, synapse_mib: int = 0, database_mib: int = 0) -> dict[str, Any]:
    """Derive allocator/database/cache tuning from live resources and allocations."""
    if mem_mib <= 0:
        raise ValueError("memory must be positive")
    if cpus < 1:
        raise ValueError("CPU count must be at least one")
    # Arena count follows both CPU parallelism and memory-per-CPU, with conservative
    # bounds to avoid allocator fragmentation on either tiny or very large hosts.
    memory_per_cpu = mem_mib / cpus
    arena_target = round(cpus * min(1.0, max(0.25, memory_per_cpu / 8192.0)))
    malloc_arenas = _clamp_int(arena_target, 2, 8)

    synapse_basis = synapse_mib if synapse_mib > 0 else max(192, int(mem_mib * 0.04))
    cache_factor = 0.20 + 0.30 * min(1.0, synapse_basis / 2048.0)
    cache_factor_text = f"{cache_factor:.2f}"

    db_basis = database_mib if database_mib > 0 else max(160, int(mem_mib * 0.03))
    shared_mib = _clamp_int(_round_step(db_basis * 0.20, 16), 32, min(512, max(32, db_basis // 2)))
    return {
        "mallocArenaMax": malloc_arenas,
        "synapseCacheFactor": cache_factor_text,
        "postgresSharedBuffers": f"{shared_mib}MB",
    }

def _state_service_limits(state: dict[str, str]) -> tuple[dict[str, int], dict[str, int]]:
    mem: dict[str, int] = {}
    cpu: dict[str, int] = {}
    for name in SERVICE_ORDER:
        key = name.upper().replace("-", "_")
        mk = f"LIMIT_{key}_MIB"
        ck = f"CPU_{key}_MILLI"
        if mk in state:
            mem[name] = _int_state(state, mk, 0)
        if ck in state:
            cpu[name] = _int_state(state, ck, 0)
    return mem, cpu


def parse_env_state(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            result[key] = value
    return result


def _int_state(state: dict[str, str], key: str, minimum: int = 0) -> int:
    try:
        value = int(state.get(key, ""))
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{key} must be >= {minimum}")
    return value


def validate_runtime_policy_state(
    state: dict[str, str],
    compat: dict[str, str],
    options: dict[str, Any] | None = None,
    hardware: dict[str, Any] | None = None,
    backends: dict[str, Any] | None = None,
) -> dict[str, Any]:
    version = _int_state(state, "POLICY_VERSION", 1)
    current = schema_value(compat, "runtime_policy")
    if version != current:
        raise ValueError(f"runtime policy schema {version} != required {current}")
    mem = _int_state(state, "MEM_MIB", 512)
    cpus = _int_state(state, "CPUS", 1) if "CPUS" in state else 1
    accel = state.get("OLLAMA_ACCELERATION", "cpu")
    managed = state.get("MANAGED_OLLAMA_SELECTED", "false") == "true" if "MANAGED_OLLAMA_SELECTED" in state else True
    directml = state.get("DIRECTML_SELECTED", "false") == "true"
    expected = host_memory_budget(mem, accel, managed, directml)
    actual = {
        "reserveMiB": _int_state(state, "RESERVE_MIB", 0),
        "directmlHostReserveMiB": _int_state(state, "DIRECTML_HOST_RESERVE_MIB", 0),
        "containerBudgetMiB": _int_state(state, "BUDGET_MIB", 0),
    }
    if expected != actual:
        raise ValueError(f"{REASON['POLICY_BUDGET_MISMATCH']}: expected {expected}, found {actual}")

    if state.get("RESOURCE_POLICY_MODE", "adaptive") != "adaptive":
        raise ValueError("RESOURCE_POLICY_MODE must be adaptive")

    if "RAM_PROFILE" in state and state.get("RAM_PROFILE") != ram_profile(mem):
        raise ValueError(f"RAM_PROFILE mismatch: expected {ram_profile(mem)}, found {state.get('RAM_PROFILE')}")
    if "CPU_PROFILE" in state and state.get("CPU_PROFILE") != cpu_profile(cpus):
        raise ValueError(f"CPU_PROFILE mismatch: expected {cpu_profile(cpus)}, found {state.get('CPU_PROFILE')}")
    matrix_gateways = _int_state(state, "MATRIX_PROFILE_GATEWAYS", 0) if "MATRIX_PROFILE_GATEWAYS" in state else 0
    kanban = _int_state(state, "KANBAN_CONCURRENCY", 1) if "KANBAN_CONCURRENCY" in state else 1
    if "HERMES_MIN_MIB" in state:
        expected_hermes = hermes_floor_mib(matrix_gateways, kanban)
        if _int_state(state, "HERMES_MIN_MIB", 0) != expected_hermes:
            raise ValueError(f"HERMES_MIN_MIB mismatch: expected {expected_hermes}, found {state.get('HERMES_MIN_MIB')}")

    service_mem, service_cpu = _state_service_limits(state)
    expected_cpu = cpu_quota_plan(cpus, matrix_gateways, kanban, accel)
    for name, actual_cpu in service_cpu.items():
        if expected_cpu.get(name) != actual_cpu:
            raise ValueError(f"CPU quota mismatch for {name}: expected {expected_cpu.get(name)}, found {actual_cpu}")

    if options is not None and service_mem:
        ollama_floor = _int_state(state, "OLLAMA_MODEL_FLOOR_MIB", 0)
        expected_mem = service_memory_plan(
            actual["containerBudgetMiB"],
            matrix=bool(options.get("matrix")),
            searxng=bool(options.get("searxng")),
            qmd=bool(options.get("qmd")),
            ollama=managed,
            honcho=bool(options.get("honcho")),
            hermes_floor=_int_state(state, "HERMES_MIN_MIB", 1024),
            ollama_floor=ollama_floor,
        )
        if service_mem != expected_mem:
            raise ValueError(f"service memory plan mismatch: expected {expected_mem}, found {service_mem}")

    synapse_mib = service_mem.get("synapse", 0)
    db_candidates = [service_mem.get("synapse-db", 0), service_mem.get("honcho-db", 0)]
    db_candidates = [value for value in db_candidates if value > 0]
    database_mib = min(db_candidates) if db_candidates else 0
    tuning = runtime_tuning(mem, cpus, synapse_mib, database_mib)
    if "MALLOC_ARENA_MAX" in state and _int_state(state, "MALLOC_ARENA_MAX", 1) != tuning["mallocArenaMax"]:
        raise ValueError("MALLOC_ARENA_MAX does not match canonical tuning")
    if "SYNAPSE_CACHE_FACTOR" in state and state.get("SYNAPSE_CACHE_FACTOR") != tuning["synapseCacheFactor"]:
        raise ValueError("SYNAPSE_CACHE_FACTOR does not match canonical tuning")
    if "POSTGRES_SHARED_BUFFERS" in state and state.get("POSTGRES_SHARED_BUFFERS") != tuning["postgresSharedBuffers"]:
        raise ValueError("POSTGRES_SHARED_BUFFERS does not match canonical tuning")

    ollama_runtime = ollama_runtime_settings(mem, cpus, accel, directml)
    if "OLLAMA_MAX_LOADED_MODELS" in state and _int_state(state, "OLLAMA_MAX_LOADED_MODELS", 1) != ollama_runtime["maxLoadedModels"]:
        raise ValueError("OLLAMA_MAX_LOADED_MODELS does not match canonical adaptive runtime settings")
    if "OLLAMA_NUM_PARALLEL" in state and _int_state(state, "OLLAMA_NUM_PARALLEL", 1) != ollama_runtime["parallel"]:
        raise ValueError("OLLAMA_NUM_PARALLEL does not match canonical adaptive runtime settings")
    if "OLLAMA_KEEP_ALIVE" in state and state.get("OLLAMA_KEEP_ALIVE") != ollama_runtime["keepAlive"]:
        raise ValueError("OLLAMA_KEEP_ALIVE does not match canonical adaptive runtime settings")

    if directml:
        # Derived GPU memory comes from the canonical selected-adapter capability,
        # never from a machine-specific constant. directmlVramMiB is retained only
        # as a migration fallback for older 14.5.x options when derived state is not
        # yet available.
        vram_mib = 0
        vram_source = "legacy-install-options"
        vram_confidence = "legacy"
        if isinstance(backends, dict):
            selected = ((backends.get("adapterSelection") or {}).get("selected") or {})
            admission = selected.get("directmlAdmission") if isinstance(selected, dict) else None
            if isinstance(admission, dict):
                vram_mib = _nonnegative_int(admission.get("capacityMiB", 0))
                vram_source = str(admission.get("source") or "unavailable")
                vram_confidence = str(admission.get("confidence") or "none")
        if vram_mib <= 0 and options is not None:
            vram_mib = _nonnegative_int(options.get("directmlVramMiB", 0))
        dml_context = directml_context_recommendation(mem, vram_mib)
        dml_threads = directml_cpu_thread_plan(cpus)
        dml_generation = directml_generation_limit(dml_context)
        if "DIRECTML_ADMISSION_MIB" in state and _int_state(state, "DIRECTML_ADMISSION_MIB", 0) != vram_mib:
            raise ValueError("DIRECTML_ADMISSION_MIB does not match canonical selected-adapter capacity")
        if "DIRECTML_ADMISSION_SOURCE" in state and state.get("DIRECTML_ADMISSION_SOURCE") != vram_source:
            raise ValueError("DIRECTML_ADMISSION_SOURCE does not match canonical selected-adapter provenance")
        if "DIRECTML_ADMISSION_CONFIDENCE" in state and state.get("DIRECTML_ADMISSION_CONFIDENCE") != vram_confidence:
            raise ValueError("DIRECTML_ADMISSION_CONFIDENCE does not match canonical selected-adapter provenance")
    else:
        dml_context = dml_threads = dml_generation = 0
        vram_mib = 0
        vram_source = "unavailable"
        vram_confidence = "none"
    if "DIRECTML_CONTEXT_LENGTH" in state and _int_state(state, "DIRECTML_CONTEXT_LENGTH", 0) != dml_context:
        raise ValueError("DIRECTML_CONTEXT_LENGTH does not match canonical adaptive context")
    if "DIRECTML_CPU_THREADS" in state and _int_state(state, "DIRECTML_CPU_THREADS", 0) != dml_threads:
        raise ValueError("DIRECTML_CPU_THREADS does not match canonical adaptive CPU plan")
    if "DIRECTML_MAX_NEW_TOKENS" in state and _int_state(state, "DIRECTML_MAX_NEW_TOKENS", 0) != dml_generation:
        raise ValueError("DIRECTML_MAX_NEW_TOKENS does not match canonical adaptive generation limit")

    if all(k in state for k in ("GPU_COUNT", "GPU_MIN_MIB", "GPU_MAX_MIB", "DIRECTML_GPU_VENDOR", "OLLAMA_GPU_OVERHEAD_MIB", "DIRECTML_VRAM_LIMIT_PCT", "GPU_SHARED_WITH_DIRECTML")):
        coordination = gpu_coordination(
            accel,
            _int_state(state, "GPU_COUNT", 0),
            _int_state(state, "GPU_MIN_MIB", 0),
            _int_state(state, "GPU_MAX_MIB", 0),
            state.get("DIRECTML_GPU_VENDOR", ""),
            directml,
        )
        coord_actual = {
            "ollamaGpuOverheadMiB": _int_state(state, "OLLAMA_GPU_OVERHEAD_MIB", 0),
            "directmlVramLimitPct": _int_state(state, "DIRECTML_VRAM_LIMIT_PCT", 0),
            "sharedVendor": state.get("GPU_SHARED_WITH_DIRECTML", "false") == "true",
        }
        if coordination != coord_actual:
            raise ValueError(f"GPU coordination mismatch: expected {coordination}, found {coord_actual}")

    policy_fp = state.get("POLICY_FINGERPRINT", "")
    material = "\n".join(f"{k}={v}" for k, v in sorted(state.items()) if k != "POLICY_FINGERPRINT") + "\n"
    actual_fp = hashlib.sha256(material.encode("utf-8")).hexdigest()
    if not policy_fp or policy_fp != actual_fp:
        raise ValueError(f"{REASON['POLICY_FINGERPRINT_MISMATCH']}: expected persisted fingerprint {policy_fp or '<missing>'}, computed {actual_fp}")
    return {
        "schema": current,
        "memory": actual,
        "cpuCount": cpus,
        "cpuProfile": cpu_profile(cpus),
        "ramProfile": ram_profile(mem),
        "services": service_mem,
        "cpuQuotasMilli": {name: service_cpu[name] for name in SERVICE_ORDER if name in service_cpu},
        "tuning": tuning,
        "ollamaRuntime": ollama_runtime,
        "directmlRuntime": {"contextLength": dml_context, "cpuThreads": dml_threads, "maxNewTokens": dml_generation, "admissionMiB": vram_mib, "admissionSource": vram_source, "admissionConfidence": vram_confidence},
        "policyFingerprint": policy_fp,
    }


def build_runtime_policy_document(state: dict[str, str], hardware: dict[str, Any], backends: dict[str, Any], compat: dict[str, str], options: dict[str, Any]) -> dict[str, Any]:
    validation = validate_runtime_policy_state(state, compat, options, hardware, backends)
    gpu = {
        "count": int(state.get("GPU_COUNT", "0") or 0),
        "minMiB": int(state.get("GPU_MIN_MIB", "0") or 0),
        "maxMiB": int(state.get("GPU_MAX_MIB", "0") or 0),
        "aggregateMiB": int(state.get("GPU_TOTAL_MIB", "0") or 0),
        "heterogeneous": state.get("GPU_HETEROGENEOUS", "false") == "true",
        "ollamaOverheadMiBPerGpu": int(state.get("OLLAMA_GPU_OVERHEAD_MIB", "0") or 0),
        "directmlVramLimitPct": int(state.get("DIRECTML_VRAM_LIMIT_PCT", "75") or 75),
        "directmlAdmissionMiB": int(state.get("DIRECTML_ADMISSION_MIB", "0") or 0),
        "directmlAdmissionSource": state.get("DIRECTML_ADMISSION_SOURCE", "unavailable"),
        "directmlAdmissionConfidence": state.get("DIRECTML_ADMISSION_CONFIDENCE", "none"),
        "sharedWithDirectml": state.get("GPU_SHARED_WITH_DIRECTML", "false") == "true",
    }
    models = {
        "ollamaTextArtifactMiB": int(state.get("OLLAMA_TEXT_ARTIFACT_MIB", "0") or 0),
        "ollamaEmbeddingArtifactMiB": int(state.get("OLLAMA_EMBED_ARTIFACT_MIB", "0") or 0),
        "ollamaContextLength": int(state.get("OLLAMA_CONTEXT_LENGTH", "0") or 0),
        "ollamaModelFloorMiB": int(state.get("OLLAMA_MODEL_FLOOR_MIB", "0") or 0),
        "ollamaMaxLoadedModels": int(state.get("OLLAMA_MAX_LOADED_MODELS", "1") or 1),
        "ollamaParallel": int(state.get("OLLAMA_NUM_PARALLEL", "1") or 1),
        "ollamaKeepAlive": state.get("OLLAMA_KEEP_ALIVE", ""),
        "directmlContextLength": int(state.get("DIRECTML_CONTEXT_LENGTH", "0") or 0),
        "directmlCpuThreads": int(state.get("DIRECTML_CPU_THREADS", "0") or 0),
        "directmlMaxNewTokens": int(state.get("DIRECTML_MAX_NEW_TOKENS", "0") or 0),
    }
    backend_selection = (backends.get("selection") or {}) if isinstance(backends.get("selection"), dict) else {}
    policy_selection_keys = (
        "requestedTextBackend", "requestedOllamaAcceleration", "requestedInferenceBackend",
        "textBackend", "ollamaAcceleration", "inferenceBackend", "selectionReasonCode",
        "fallbackBackend", "fallbackChain",
    )
    policy_selection = {key: backend_selection.get(key) for key in policy_selection_keys if key in backend_selection}
    payload: dict[str, Any] = {
        "schema": schema_value(compat, "runtime_policy"),
        "architectureVersion": ARCHITECTURE_VERSION,
        "generatedAt": utc_now(),
        "provenance": {
            "hardwareFingerprint": hardware.get("hardwareFingerprint", ""),
            "backendFingerprint": backends.get("backendFingerprint", ""),
            "sourceOptionsFingerprint": fingerprint(options),
        },
        # Retain top-level compatibility fields for older state-audit/repair readers.
        "hardwareFingerprint": hardware.get("hardwareFingerprint", ""),
        "backendFingerprint": backends.get("backendFingerprint", ""),
        "sourceOptionsFingerprint": fingerprint(options),
        "policyFingerprint": validation["policyFingerprint"],
        # runtime-policy.json captures resource-relevant selection only. Transient
        # active fallback/health lives in backend-capabilities.json and must not make
        # an otherwise safe policy stale after a DirectML fallback response.
        "selection": policy_selection,
        "host": {
            "wslMemoryMiB": int(state.get("MEM_MIB", "0") or 0),
            "wslCpuCount": validation["cpuCount"],
            "ramProfile": validation["ramProfile"],
            "cpuProfile": validation["cpuProfile"],
            **validation["memory"],
        },
        "gpu": gpu,
        "models": models,
        "services": {
            name: {"memoryLimitMiB": mib, "cpuLimitMilli": validation["cpuQuotasMilli"].get(name, 0)}
            for name, mib in validation["services"].items()
        },
        "tuning": validation["tuning"],
        "state": dict(sorted(state.items())),
    }
    payload["documentFingerprint"] = fingerprint({k: v for k, v in payload.items() if k not in ("generatedAt", "documentFingerprint")})
    return payload


def validate_runtime_policy_document(document: Any, state: dict[str, str], hardware: dict[str, Any], backends: dict[str, Any], compat: dict[str, str], options: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError("runtime-policy.json is missing or unreadable")
    if document.get("schema") != schema_value(compat, "runtime_policy"):
        raise ValueError("runtime-policy.json schema does not match compatibility.conf")
    expected = build_runtime_policy_document(state, hardware, backends, compat, options)
    if document.get("policyFingerprint") != expected.get("policyFingerprint"):
        raise ValueError("runtime-policy.json policy fingerprint does not match canonical resource state")
    if document.get("hardwareFingerprint") != expected.get("hardwareFingerprint"):
        raise ValueError("runtime-policy.json hardware fingerprint is stale")
    if document.get("backendFingerprint") != expected.get("backendFingerprint"):
        raise ValueError("runtime-policy.json backend fingerprint is stale")
    if document.get("sourceOptionsFingerprint") != expected.get("sourceOptionsFingerprint"):
        raise ValueError("runtime-policy.json source options fingerprint is stale")
    if document.get("documentFingerprint") != expected.get("documentFingerprint"):
        raise ValueError("runtime-policy.json canonical document fingerprint mismatch")
    return expected


def write_backend_health(stack: Path, compat: dict[str, str], backend: str, result: str, reason_code: str, hardware_fingerprint: str, detail: str = "") -> dict[str, Any]:
    path = stack / "data" / "latticevale" / "backend-health.json"
    current = load_json(path, {})
    if not isinstance(current, dict) or current.get("schema") != schema_value(compat, "backend_health"):
        current = {"schema": schema_value(compat, "backend_health"), "architectureVersion": ARCHITECTURE_VERSION, "backends": {}}
    current.setdefault("backends", {})[backend] = {
        "result": result,
        "reasonCode": reason_code,
        "detail": detail,
        "hardwareFingerprint": hardware_fingerprint,
        "checkedAt": utc_now(),
    }
    current["healthFingerprint"] = fingerprint(current.get("backends", {}))
    atomic_write_json(path, current)
    return current


def command_validate_options(args: argparse.Namespace) -> int:
    compat = parse_compatibility(Path(args.compat))
    schema = schema_value(compat, "install_options")
    data = load_json(Path(args.path), None)
    try:
        validate_install_options(data, schema)
    except Exception as exc:
        print(f"Invalid install-options.json: {exc}", file=sys.stderr)
        return 1
    print(f"Persisted installer options validated (schema <= {schema}).")
    return 0


def command_host_budget(args: argparse.Namespace) -> int:
    try:
        result = host_memory_budget(args.mem_mib, args.accel, args.managed_ollama == "true", args.directml == "true")
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"{result['reserveMiB']}:{result['directmlHostReserveMiB']}:{result['containerBudgetMiB']}")
    return 0


def command_record_health(args: argparse.Namespace) -> int:
    compat = parse_compatibility(Path(args.compat))
    hardware = load_json(Path(args.hardware), {})
    hwfp = str(hardware.get("hardwareFingerprint") or "") if isinstance(hardware, dict) else ""
    if not re.fullmatch(r"[0-9a-f]{64}", hwfp):
        print("Canonical hardware fingerprint is unavailable; refusing to persist backend health.", file=sys.stderr)
        return 1
    write_backend_health(Path(args.stack), compat, args.backend, args.result, args.reason_code, hwfp, args.detail)
    return 0

def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("validate-options")
    p.add_argument("path")
    p.add_argument("--compat", required=True)
    p.set_defaults(func=command_validate_options)
    p = sub.add_parser("host-budget")
    p.add_argument("mem_mib", type=int)
    p.add_argument("accel")
    p.add_argument("managed_ollama", choices=("true", "false"))
    p.add_argument("directml", choices=("true", "false"))
    p.set_defaults(func=command_host_budget)
    p = sub.add_parser("record-health")
    p.add_argument("backend", choices=("directml", "cuda", "rocm", "vulkan", "cpu"))
    p.add_argument("result", choices=("verified-working", "failed"))
    p.add_argument("reason_code")
    p.add_argument("--detail", default="")
    p.add_argument("--stack", default=".")
    p.add_argument("--compat", default="compatibility.conf")
    p.add_argument("--hardware", default="data/latticevale/hardware-capabilities.json")
    p.set_defaults(func=command_record_health)
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
