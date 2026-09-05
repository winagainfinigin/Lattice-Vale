from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
version = (ROOT / 'VERSION.txt').read_text(encoding='ascii').strip()
assert version in {'14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46','14.5.47','14.6.0'}, version

cs = (ROOT / 'stack/configure-stack.sh').read_text(encoding='utf-8')

# Native model discovery/pull stays API-based and requires no manual pre-download.
assert "base+'/api/tags'" in cs
assert "base+'/api/pull'" in cs
assert 'Selected models do not need to be pre-downloaded on Windows' in cs

# The native embedding capability check must not require the Compose network before
# infrastructure creates it. It uses the already-verified WSL relay endpoint directly.
start = cs.index('verify_honcho_embedding_model() {')
end = cs.index('\nread_yes_no() {', start)
block = cs[start:end]
assert 'if windows_native_ollama_enabled; then' in block
assert 'base="${base%/}/v1"' in block
assert "python3 - \"$model\" \"$base\" <<'PY_NATIVE_OLLAMA_EMBED_CHECK'" in block
native_start = block.index('if windows_native_ollama_enabled; then')
managed_start = block.index('  else\n    base="$(ollama_openai_base_url)"', native_start)
native_branch = block[native_start:managed_start]
assert '--network hermes-backend' not in native_branch
assert "base+'/embeddings'" in native_branch
assert "'dimensions':1536" in native_branch

# Managed Ollama still validates from the Honcho image on the real Compose backend.
managed_branch = block[managed_start:]
assert 'docker run --rm -i --network hermes-backend' in managed_branch
assert '--entrypoint /app/.venv/bin/python hermes-honcho:local' in managed_branch

print('v14.3.24 native Ollama model validation fixtures: PASS')
