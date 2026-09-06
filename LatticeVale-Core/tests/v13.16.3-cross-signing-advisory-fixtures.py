#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
cfg=(root/'stack/configure-stack.sh').read_text(encoding='utf-8')
assert (root/'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}
cross=cfg[cfg.index('stage_matrix_cross_signing()'):cfg.index('verify_provider()')]
assert "Secure Matrix device cross-signing settings" in cfg
assert "Checking briefly for Hermes Matrix cross-signing confirmation (advisory only)." in cross
assert "WARNING: Hermes retained and loaded the Matrix recovery key" in cross
tail=cross[cross.index("Checking briefly for Hermes Matrix cross-signing confirmation (advisory only)."):]
assert "return 1" not in tail, 'missing confirmation log must not fail install'
assert "Waiting up to 120 seconds for Hermes to confirm Matrix cross-signing." not in cross
assert "docker logs --since 2m hermes-agent" in cross
assert "timeout --foreground --kill-after=5s 15s docker logs" in cross
print('v13.16.3 Matrix advisory cross-signing fixtures: PASS')
