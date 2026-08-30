from pathlib import Path
import tempfile, subprocess, json, os
root=Path(__file__).resolve().parents[1]
assert (root/'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2'}
cfg=(root/'stack/configure-stack.sh').read_text(encoding='utf-8')
audit=(root/'stack/state-audit.py').read_text(encoding='utf-8')
readme=(root/'README.md').read_text(encoding='utf-8')

# Clean/repair integration must normalize both supported config forms and env-level s6 opt-in.
assert "cfg.pop('multiplex_profiles',None)" in cfg
assert "gateway['multiplex_profiles']=False" in cfg
assert 'remove_env_keys secrets/hermes-runtime.env GATEWAY_MULTIPLEX_PROFILES' in cfg
assert 'remove_env_keys \"$f\" GATEWAY_MULTIPLEX_PROFILES' in cfg
assert "gateway.get('multiplex_profiles') is not False" in cfg
assert "cfg.get('multiplex_profiles') is True" in cfg

# Clone sanitization must not inherit a multiplexer from the default profile.
clone=cfg[cfg.index("PY_PROFILE_SAFE_CLONE"):cfg.index("PY_PROFILE_SAFE_CLONE", cfg.index("PY_PROFILE_SAFE_CLONE")+1)]
assert "cfg.pop('multiplex_profiles',None)" in clone
assert "gateway['multiplex_profiles']=False" in clone
assert "not line.startswith('GATEWAY_MULTIPLEX_PROFILES=')" in clone

# Read-only audit must surface either YAML or runtime-env opt-in as a repair condition.
assert 'yaml_multiplex_enabled' in audit
assert 'GATEWAY_MULTIPLEX_PROFILES' in audit
assert 'env_override_locations' in audit
assert 'gatewayTopology' in audit
assert 'standalone per-profile gateway topology; multiplexing disabled' in audit

# Documentation makes the policy explicit rather than silently changing user topology.
assert 'one-process-per-profile' in readme.lower()
assert 'gateway.multiplex_profiles' in readme
assert 'v13.16.1' in (root.parent/'docs/CHANGELOG.md').read_text(encoding='utf-8')
print('v13.16.1 profile-gateway-isolation fixtures: PASS')
