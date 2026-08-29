#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RELEASE=ROOT.parent
ps=(ROOT/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
boot=(ROOT/'linux/bootstrap.sh').read_text(encoding='utf-8')
manage=(ROOT/'stack/manage.sh').read_text(encoding='utf-8')
conf=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
readme=(RELEASE/'docs/README.md').read_text(encoding='utf-8')
security=(RELEASE/'docs/SECURITY.md').read_text(encoding='utf-8')
assert (ROOT/'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0'}
assert 'schema = 19' in ps
assert "questionnaireMode = $questionnaireMode" in ps
if (ROOT/'VERSION.txt').read_text().strip() in {'14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0'}:
    assert 'Choose setup questionnaire:' not in ps
    assert 'Quick setup — recommended defaults' not in ps
    assert "questionnaireMode = 'explicit'" in ps
    assert "if ($questionnaireMode -in @('custom','explicit'))" in ps
else:
    assert 'Choose setup questionnaire:' in ps
    assert 'Quick setup — recommended defaults' in ps and 'Custom setup — review every optional service' in ps
    assert "if ($questionnaireMode -eq 'quick')" in ps
    assert "Dashboard=on, SearXNG=on, Matrix=off" in ps
assert "containerResourceLimits = $containerResourceLimits" in ps
assert "ollamaAcceleration = $ollamaAcceleration" in ps
assert 'schema must be an integer from 1 through 19' in conf
assert ('questionnaireMode must be quick or custom' in conf) or ('questionnaireMode must be quick, custom, or explicit' in conf)
# NVIDIA toolkit must never be silently downgraded by this release.
assert '--allow-downgrades' not in boot
assert 'dpkg --compare-versions' in boot
assert 'preserving it and verifying the runtime instead of downgrading' in boot
assert 'will not downgrade the newer packages automatically' in boot
# Offline pin visibility: status/verify may show age but must not network-check freshness.
assert "LATTICEVALE_PIN_DATE='2026-08-17'" in manage
assert 'Configured image pins' in manage and 'no network check' in manage
assert 'Note: pin age is visibility only' in manage
for image in ('nousresearch/hermes-agent:v2026.8.16','matrixdotorg/synapse:v1.158.0','searxng/searxng:2026.8.17-374939b88','ollama/ollama:0.32.14'):
    assert image in manage
# GPU fit is advisory and actual loaded-model processor evidence comes from ollama ps.
assert '--query-gpu=memory.total' in manage
assert 'mem_info_vram_total' in manage
assert 'VRAM warning:' in manage
assert 'rough fit signal only' in manage
assert 'ollama ps' in manage
assert 'Loaded-model offload:' in manage
assert 'quantization, context length, KV cache' in manage
assert 'LatticeVale hardware/resource summary:' in conf
# Backup warning: informative only; no new encryption dependency/tooling.
assert 'this backup may contain API keys, Matrix credentials' in manage
assert 'consider encrypting it before copying it' in manage
assert 'age-encryption.org' not in manage and 'gpg --encrypt' not in manage
# User-facing docs describe all additions and retain jq as a real prerequisite rather than weakening production for sandbox tests.
assert (('Quick setup' in readme and 'Custom setup' in readme) or ('explicit' in readme.lower() and 'fresh install' in readme.lower()))
assert 'pin age' in readme.lower()
assert 'VRAM' in readme and 'ollama ps' in readme
assert 'backup' in security.lower() and 'encrypt' in security.lower()
assert 'jq' in (ROOT/'linux/bootstrap.sh').read_text(encoding='utf-8')
print('v14.3.0 usability/safety fixtures: PASS')
