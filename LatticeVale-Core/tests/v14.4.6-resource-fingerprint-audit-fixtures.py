from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
STATE_AUDIT = ROOT / "stack" / "state-audit.py"
ARCH = ROOT / "stack" / "latticevale_arch.py"
VERSION = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
assert VERSION in {"14.4.6","14.4.7","14.4.8","14.4.81","14.4.82","14.4.83","14.4.84","14.4.85","14.5.0","14.5.1","14.5.2","14.5.3","14.5.4","14.5.42","14.5.43","14.5.44",'14.5.45','14.5.46','14.5.47','14.6.0'}, VERSION

audit_text = STATE_AUDIT.read_text(encoding="utf-8")
arch_text = ARCH.read_text(encoding="utf-8")
if VERSION == "14.6.0":
    assert "def visible_cpu_count() -> int:" in arch_text
    assert "os.sched_getaffinity(0)" in arch_text
    assert "cpus = visible_cpu_count()" in arch_text
    assert "cpus = os.cpu_count()" not in arch_text
    assert "probe_hardware" in audit_text and "classify_backends" in audit_text
    assert "def visible_cpu_count() -> int:" not in audit_text
    module_path = ARCH
else:
    assert "def visible_cpu_count() -> int:" in audit_text
    assert "os.sched_getaffinity(0)" in audit_text
    assert "current_cpus = visible_cpu_count()" in audit_text
    assert "current_cpus = os.cpu_count()" not in audit_text
    module_path = STATE_AUDIT

spec = importlib.util.spec_from_file_location("latticevale_cpu_visibility", module_path)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Reproduce the real WSL failure: host exposes 8 logical CPUs to os.cpu_count(),
# while WSL/process affinity and nproc expose only the configured 4 CPUs.
orig_affinity = getattr(mod.os, "sched_getaffinity", None)
orig_cpu_count = mod.os.cpu_count
orig_run = getattr(mod, "run", None)
try:
    mod.os.sched_getaffinity = lambda _pid: {0, 1, 2, 3}
    mod.os.cpu_count = lambda: 8
    assert mod.visible_cpu_count() == 4

    # If affinity is unavailable, nproc remains the next source because the
    # generator/manager use nproc semantics too.
    def no_affinity(_pid):
        raise OSError("not available")
    mod.os.sched_getaffinity = no_affinity
    if VERSION == "14.6.0":
        orig_runner = mod.run_capture
        mod.run_capture = lambda cmd, timeout=8: (0, "6", "") if cmd == ["nproc"] else (127, "", "")
    else:
        orig_runner = mod.run
        mod.run = lambda cmd, cwd=None, timeout=8: (0, "6") if cmd == ["nproc"] else (127, "")
    assert mod.visible_cpu_count() == 6

    # Last-resort fallback remains safe on platforms without affinity/nproc.
    if VERSION == "14.6.0":
        mod.run_capture = lambda cmd, timeout=8: (127, "", "")
    else:
        mod.run = lambda cmd, cwd=None, timeout=8: (127, "")
    assert mod.visible_cpu_count() == 8
finally:
    if orig_affinity is not None:
        mod.os.sched_getaffinity = orig_affinity
    else:
        try:
            delattr(mod.os, "sched_getaffinity")
        except AttributeError:
            pass
    mod.os.cpu_count = orig_cpu_count
    if VERSION == "14.6.0":
        mod.run_capture = orig_runner
    else:
        mod.run = orig_run

print("v14.4.6 resource fingerprint audit fixtures: PASS")
