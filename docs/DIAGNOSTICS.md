# LatticeVale 14.6.0 Diagnostics

14.6.0 separates diagnostic evidence by layer so one failed GPU API is not reported as "no GPU" for every backend.

## Installer diagnostics

An existing managed installation exposes **Diagnostics / compatibility test** as a read-only installer option. Windows-side diagnostics report Windows/WSL/GPU prerequisite state without changing the stack.

Option 8 stages the **current bundle's** `state-audit.py`, canonical architecture library, `compatibility.conf`, and a freshly generated Windows hardware snapshot into a temporary WSL directory. This prevents a pre-14.6 installed stack from being mislabeled merely because its old on-disk copy does not yet contain the current validator. The temporary files are removed afterward and do not migrate or repair the stack.

GPU diagnostics report memory **source and confidence** separately from backend health. `DML_VRAM_CAPACITY_UNAVAILABLE` means the DirectML route reached bounded model admission without a trustworthy runtime/canonical capacity; it is not equivalent to `DML_DXG_MISSING` or a missing GPU driver. A report of zero **Linux-native Ollama** GPU adapters is likewise not evidence that DirectML is unavailable when `/dev/dxg` and the WSL DirectX bridge are healthy.

## WSL commands

From `~/hermes-stack`:

```bash
./manage.sh diagnose
./manage.sh diagnose-gpu
./manage.sh diagnose-backends
./manage.sh diagnose-policy
./directml-gateway.sh diagnose
```

The architecture diagnostics can run after their canonical files are staged even if final `.configured` state has not yet been reached, making them useful during repair.

## Canonical documents

- `hardware-capabilities.json`: Windows snapshot + live WSL device/runtime topology.
- `backend-capabilities.json`: structural candidate capabilities, selected adapter, configured policy backend, active runtime backend, and reason codes.
- `backend-health.json`: transient runtime proof/failure tied to hardware fingerprint and represented by a separate runtime-health fingerprint.
- `runtime-policy.json`: canonical validated resource policy.

Diagnostics are derived state and must not contain user secrets. Do not publish unrelated application logs, backups, API keys, Matrix secrets, prompts, or credentials when filing a bug.

## Confidence levels

LatticeVale distinguishes static/source checks, deterministic fixtures, WSL integration, Docker integration, GPU/backend integration, and complete live Windows installer qualification. A passing static/fixture suite is strong regression evidence but is not represented as proof that every physical GPU/driver combination has been exercised live.
