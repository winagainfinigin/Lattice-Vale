from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
STATE_AUDIT = ROOT / "stack" / "state-audit.py"
VERSION = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
assert VERSION == "14.4.6", VERSION

text = STATE_AUDIT.read_text(encoding="utf-8")
assert "def visible_cpu_count() -> int:" in text
assert "os.sched_getaffinity(0)" in text
assert "current_cpus = visible_cpu_count()" in text
assert "current_cpus = os.cpu_count()" not in text

spec = importlib.util.spec_from_file_location("latticevale_state_audit", STATE_AUDIT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Reproduce the real WSL failure: host exposes 8 logical CPUs to os.cpu_count(),
# while WSL/process affinity and nproc expose only the configured 4 CPUs.
orig_affinity = getattr(mod.os, "sched_getaffinity", None)
orig_cpu_count = mod.os.cpu_count
orig_run = mod.run
try:
    mod.os.sched_getaffinity = lambda _pid: {0, 1, 2, 3}
    mod.os.cpu_count = lambda: 8
    assert mod.visible_cpu_count() == 4

    # If affinity is unavailable, nproc remains the next source because the
    # generator/manager use nproc semantics too.
    def no_affinity(_pid):
        raise OSError("not available")
    mod.os.sched_getaffinity = no_affinity
    mod.run = lambda cmd, cwd=None, timeout=8: (0, "6") if cmd == ["nproc"] else (127, "")
    assert mod.visible_cpu_count() == 6

    # Last-resort fallback remains safe on platforms without affinity/nproc.
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
    mod.run = orig_run

print("v14.4.6 resource fingerprint audit fixtures: PASS")
