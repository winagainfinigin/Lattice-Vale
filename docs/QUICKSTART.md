# LatticeVale 14.6.0 Quickstart

LatticeVale installs into an **existing supported Ubuntu WSL2 distribution**. It does not create, import, convert, unregister, update, or repair WSL distributions, and it does not install or replace Windows display drivers.

## 1. Before running the installer

- Use a supported Windows/WSL configuration and a supported Ubuntu release listed by `LatticeVale-Core/compatibility.conf`.
- Make sure the chosen Ubuntu distribution launches normally.
- Keep sufficient free space on the Windows partition that stores the WSL distribution.
- For GPU acceleration, install/maintain the appropriate Windows/vendor driver outside LatticeVale. GPU acceleration is optional; qualified systems may run the local inference path on CPU.

## 2. Start LatticeVale

From PowerShell in the extracted release root:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\installer\Install-LatticeVale.ps1
```

Choose an existing supported Ubuntu WSL2 distribution and Linux user. Review the configuration summary before confirming installation.

## 3. Existing installation

For an existing installer-managed LatticeVale stack, use the **full current release** and choose **Option 1 — Resume / repair installation**. Do not layer the repository patch ZIP over `~/hermes-stack`; the installer owns migration, backup, permissions, generated state, and checkpoint reconciliation.

## 4. GPU/backend behavior

14.6.0 separates durable user preference from derived capability state. The installer records Windows hardware into a derived snapshot, WSL probes its own live devices, and the canonical backend engine classifies DirectML, CUDA, ROCm, Vulkan, native-Windows Ollama, and CPU independently. A missing Linux-native GPU does not automatically invalidate WSL-host DirectML. DirectML memory admission uses runtime capacity when available, otherwise bounded canonical Windows adapter evidence; unknown capacity fails safely to fallback rather than loading an unbounded model.

See [GPU-BACKENDS.md](GPU-BACKENDS.md) for the capability model and [RESOURCE-POLICY.md](RESOURCE-POLICY.md) for memory admission.

## 5. Verify

After installation or repair:

```bash
cd ~/hermes-stack
./manage.sh status
./manage.sh verify
./manage.sh diagnose
```

The installer also exposes a read-only **Diagnostics / compatibility test** for existing managed installations.

## 6. If something fails

Use Option 1 again after addressing the reported prerequisite or invariant. LatticeVale repair is resumable and preservation-first. Do not delete the WSL distribution or persistent stack data as a first troubleshooting step.

See [REPAIR.md](REPAIR.md), [DIAGNOSTICS.md](DIAGNOSTICS.md), and [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
