#!/usr/bin/env python3
from pathlib import Path
import importlib.util
import tempfile

ROOT = Path(__file__).resolve().parents[1]
assert (ROOT / "VERSION.txt").read_text(encoding="ascii").strip() == "14.6.2"
compat = (ROOT / "compatibility.conf").read_text(encoding="utf-8")
assert "MANAGED_REPAIR_REFRESH_REVISION=5" in compat

compose = (ROOT / "stack/compose.yaml").read_text(encoding="utf-8")
assert "${HERMES_IMAGE:-nousresearch/hermes-agent:latest}" in compose
assert "${SYNAPSE_IMAGE:-matrixdotorg/synapse:latest}" in compose
assert "${SEARXNG_IMAGE:-searxng/searxng:latest}" in compose
assert "${OLLAMA_IMAGE:-ollama/ollama:latest}" in compose
assert "${QMD_VERSION:-latest}" in compose
assert "${POSTGRES_IMAGE:-postgres:16-alpine}" in compose
assert "${PGVECTOR_IMAGE:-pgvector/pgvector:pg15}" in compose
assert "${REDIS_IMAGE:-redis:8-alpine}" in compose
assert "${VALKEY_IMAGE:-valkey/valkey:8-alpine}" in compose

dockerfile = (ROOT / "stack/Dockerfile.qmd").read_text(encoding="utf-8")
assert "ARG QMD_VERSION=latest" in dockerfile
assert 'CMD ["qmd", "mcp", "--http", "--host", "0.0.0.0", "--port", "8181"]' in dockerfile
assert not (ROOT / "stack/patch-qmd-bind.py").exists()

upstream_path = ROOT / "stack/managed-upstreams.py"
spec = importlib.util.spec_from_file_location("managed_upstreams", upstream_path)
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert mod.CHANNELS["HERMES_IMAGE"]["desired"] == "nousresearch/hermes-agent:latest"
assert mod.CHANNELS["SYNAPSE_IMAGE"]["desired"] == "matrixdotorg/synapse:latest"
assert mod.CHANNELS["QMD_VERSION"]["desired"] == "latest"
assert mod.CHANNELS["POSTGRES_IMAGE"]["policy"] == "compatible-major-16"
assert mod.CHANNELS["PGVECTOR_IMAGE"]["policy"] == "compatible-major-15"
assert mod.CHANNELS["REDIS_IMAGE"]["policy"] == "compatible-major-8"
assert mod.CHANNELS["VALKEY_IMAGE"]["policy"] == "compatible-major-8"

# Ownership: installer-owned legacy refs advance; explicit custom refs survive.
legacy = ["HERMES_IMAGE=nousresearch/hermes-agent:v2026.8.16"]
legacy, decision = mod.reconcile_value(legacy, "HERMES_IMAGE", mod.CHANNELS["HERMES_IMAGE"], refresh=True, fresh=False)
assert "HERMES_IMAGE=nousresearch/hermes-agent:latest" in legacy
assert decision["installerOwned"] is True and decision["changed"] is True
custom = ["HERMES_IMAGE=example.invalid/custom-hermes:42"]
custom, decision = mod.reconcile_value(custom, "HERMES_IMAGE", mod.CHANNELS["HERMES_IMAGE"], refresh=True, fresh=False)
assert "HERMES_IMAGE=example.invalid/custom-hermes:42" in custom
assert decision["installerOwned"] is False and decision["changed"] is False

manage = (ROOT / "stack/manage.sh").read_text(encoding="utf-8")
configure = (ROOT / "stack/configure-stack.sh").read_text(encoding="utf-8")
installer = (ROOT / "Install-LatticeVale.ps1").read_text(encoding="utf-8")
assert "Force latest-supported upstream refresh" in manage
assert "managed-upstreams.py reconcile --stack . --refresh" in manage
assert "managed-upstreams.py record" in manage
assert "Latest-supported managed-upstream reconciliation failed before Docker mutation." in configure
assert "Option 6 pre-update safety backups" in installer
assert "force latest supported stable upstream channels/sources now" in installer
assert "stack\\managed-upstreams.py" in installer
assert "'compose.yaml','Dockerfile.qmd','configure-stack.sh','manage.sh','managed-upstreams.py','state-audit.py'" in installer
assert "versions/channels declared by this bundle" not in installer
assert "current managed package/image/source pins" not in installer
assert "managed-upstreams.json" in upstream_path.read_text(encoding="utf-8")

req = (ROOT / "stack/directml-requirements.txt").read_text(encoding="utf-8")
assert "torch-directml==0.2.5.dev240914" in req
assert "torch==2.4.1+cpu" in req
assert "torchvision==0.19.1+cpu" in req

print("V14.6.2 LATEST-SUPPORTED UPSTREAM FIXTURES: PASS")
