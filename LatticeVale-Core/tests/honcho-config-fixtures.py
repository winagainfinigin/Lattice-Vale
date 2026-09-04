#!/usr/bin/env python3
from pathlib import Path
import re, subprocess, tempfile, tomllib

ROOT=Path(__file__).resolve().parents[1]
text=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
m=re.search(r"python3 - \"\$local_text_model\" \"\$local_embedding_model\" \"\$\(ollama_openai_base_url\)\" \"\$\(local_text_openai_base_url\)\" <<'PY_HONCHO_LOCAL'\n(.*?)\nPY_HONCHO_LOCAL", text, re.S)
assert m, 'Honcho local config generator heredoc not found'
code=m.group(1)
with tempfile.TemporaryDirectory() as td:
    root=Path(td); (root/'config/honcho').mkdir(parents=True)
    r=subprocess.run(['python3','-','qwen3.5:4b','qwen3-embedding:4b','http://ollama:11434/v1','http://directml.host:11436/v1'],input=code,text=True,cwd=root,capture_output=True)
    assert r.returncode==0, r.stderr
    cfg=tomllib.loads((root/'config/honcho/config.toml').read_text())
    assert cfg['auth']['USE_AUTH'] is False
    assert cfg['telemetry']['ENABLED'] is False
    assert cfg['cache']['ENABLED'] is True
    emb=cfg['embedding']
    assert emb['VECTOR_DIMENSIONS']==1536
    assert emb['model_config']['model']=='qwen3-embedding:4b'
    assert emb['model_config']['dimensions_mode']=='always'
    assert emb['model_config']['overrides']['base_url']=='http://ollama:11434/v1'
    paths=[
      cfg['deriver']['model_config'],
      *[cfg['dialectic']['levels'][x]['model_config'] for x in ('minimal','low','medium','high','max')],
      cfg['summary']['model_config'], cfg['dream']['deduction_model_config'], cfg['dream']['induction_model_config']]
    assert len(paths)==9
    for item in paths:
        assert item['transport']=='openai'
        assert item['model']=='qwen3.5:4b'
        assert item['overrides']['base_url']=='http://directml.host:11436/v1'
        assert item['overrides']['api_key_env']=='LLM_OPENAI_API_KEY'
print('HONCHO LOCAL CONFIG FIXTURES: PASS')
print('- generated TOML parses')
print('- Honcho LLM paths can use the selected text gateway while embeddings remain on Ollama')
print('- 1536-dimensional local embedding request is explicit')
