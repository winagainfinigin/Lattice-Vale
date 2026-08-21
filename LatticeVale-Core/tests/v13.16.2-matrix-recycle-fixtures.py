from pathlib import Path
root=Path(__file__).resolve().parents[1]
cfg=(root/'stack/configure-stack.sh').read_text(encoding='utf-8')
assert (root/'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7'}
assert 'recycle_hermes_bounded()' in cfg
assert "docker stop --time 10 hermes-agent" in cfg
assert "docker rm -f hermes-agent" in cfg
assert "docker compose up -d --pull never --no-build --no-deps hermes" in cfg
assert "recycle_hermes_bounded 'Matrix recovery-key bootstrap'" in cfg
assert "recycle_hermes_bounded 'Matrix recovery-key activation'" in cfg
cross=cfg[cfg.index('stage_matrix_cross_signing()'):cfg.index('verify_provider()')]
assert 'docker compose restart hermes' not in cross
assert 'docker compose up -d hermes\n      timeout' not in cross
assert 'Waiting up to 60 seconds for Hermes to become command-ready.' in cfg
assert 'Refusing to recycle hermes-agent' in cfg
print('v13.16.2 Matrix bounded-recycle fixtures: PASS')
