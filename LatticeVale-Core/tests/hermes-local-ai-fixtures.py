#!/usr/bin/env python3
from pathlib import Path
import re, subprocess, tempfile, yaml
ROOT=Path(__file__).resolve().parents[1]
text=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
m=re.search(r"python3 - data/hermes/config.yaml \"\$local_model\" \"\$local_context\" \"\$\(local_text_openai_base_url\)\" <<'PY_LOCAL_HERMES'\n(.*?)\nPY_LOCAL_HERMES", text, re.S)
assert m, 'Hermes local AI config generator not found'
with tempfile.TemporaryDirectory() as td:
    root=Path(td); p=root/'data/hermes/config.yaml'; p.parent.mkdir(parents=True)
    p.write_text('terminal:\n  cwd: /workspace\nmodel:\n  default: old\n  provider: old-provider\nother:\n  keep: true\n')
    r=subprocess.run(['python3','-',str(p),'qwen3.5:4b','8192','http://ollama:11434/v1'],input=m.group(1),text=True,cwd=root,capture_output=True)
    assert r.returncode==0, r.stderr
    cfg=yaml.safe_load(p.read_text())
    assert cfg['model']=={'default':'qwen3.5:4b','provider':'custom','base_url':'http://ollama:11434/v1','context_length':8192}
    assert cfg['terminal']['cwd']=='/workspace' and cfg['other']['keep'] is True
print('HERMES LOCAL AI FIXTURES: PASS')
print('- selected local text backend model block is correct')
print('- unrelated Hermes configuration is preserved')

# Verifier must accept the memory-aware persisted context rather than requiring legacy 64K.
text=(ROOT/'stack/configure-stack.sh').read_text()
assert "int(m.get('context_length') or 0)==int(sys.argv[3])" in text
assert '>=64000' not in text
