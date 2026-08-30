#!/usr/bin/env python3
"""v14.5.1 policy-v9 model-aware Ollama / Honcho timeout / pressure diagnostics."""
from pathlib import Path
import json, re, subprocess, sys, tempfile

ROOT=Path(__file__).resolve().parents[1]
cfg=(ROOT/'stack/configure-stack.sh').read_text(encoding='utf-8')
manage=(ROOT/'stack/manage.sh').read_text(encoding='utf-8')
audit=(ROOT/'stack/state-audit.py').read_text(encoding='utf-8')
boot=(ROOT/'linux/bootstrap.sh').read_text(encoding='utf-8')
assert (ROOT/'VERSION.txt').read_text(encoding='ascii').strip() in {'14.5.1','14.5.2'}

for marker in (
    'POLICY_VERSION=9', 'ollama_model_manifest_mib() {', 'resource_ollama_model_metrics() {',
    'OLLAMA_TEXT_ARTIFACT_MIB=%s', 'OLLAMA_EMBED_ARTIFACT_MIB=%s', 'OLLAMA_CONTEXT_LENGTH=%s',
    'OLLAMA_MODEL_FLOOR_MIB=%s', 'reconcile_model_aware_ollama_resources() {',
    'Managed Ollama model artifacts are now measurable', 'requested_ollama_floor',
):
    assert marker in cfg, marker
assert 'saved_version" == 9' in cfg
assert 'values.get("POLICY_VERSION") != "9"' in audit
assert './configure-stack.sh --refresh-resource-policy' in manage
assert './configure-stack.sh --refresh-resource-policy' in boot

# Execute the exact manifest parser against a synthetic Ollama manifest store.
m=re.search(r"ollama_model_manifest_mib\(\) \{.*?<<'PY_OLLAMA_MANIFEST_SIZE'\n(.*?)\nPY_OLLAMA_MANIFEST_SIZE",cfg,re.S)
assert m, 'manifest-size heredoc not found'
parser=m.group(1)
with tempfile.TemporaryDirectory(prefix='lv151-model-manifest-') as td:
    root=Path(td)/'manifests/registry.ollama.ai/library/qwen3.5'
    root.mkdir(parents=True)
    # ~3.40 GiB total artifact, representative of the audited 4B class.
    total=3_650_000_000
    (root/'4b').write_text(json.dumps({
        'config':{'size':1_000_000},
        'layers':[{'size':total-1_000_000}]
    }),encoding='utf-8')
    p=subprocess.run([sys.executable,'-',str(Path(td)/'manifests'),'qwen3.5:4b'],input=parser,text=True,capture_output=True,timeout=10)
    assert p.returncode==0,p.stderr
    mib=int(p.stdout.strip())
    assert 3400 <= mib <= 3600,mib
    # Policy-v9 CPU formula: artifact + >=1GiB transient + context/16, round 256 MiB.
    ctx=8192; transient=max(1024,mib//4); ctx_over=max(256,min(2048,(ctx+15)//16))
    floor=max(4608,((mib+transient+ctx_over+255)//256)*256)
    assert floor >= 5120,(mib,floor)

# The post-download reconciliation must happen before embedding verification can load a model.
pos_reconcile=cfg.index('reconcile_model_aware_ollama_resources || return 1')
pos_verify=cfg.index('verify_honcho_embedding_model "$(opt_text localEmbeddingModel)"')
assert pos_reconcile < pos_verify

# Honcho timeout is a supported root-level value and LatticeVale only updates values it owns.
for marker in ('choose_honcho_timeout() {','apply_honcho_timeout_policy() {','.latticevale-timeout-auto',"cfg['timeout']=recommended",'Preserving user-set Honcho request timeout'):
    assert marker in cfg,marker
m=re.search(r"python3 - \"\$path\" \"\$marker\" \"\$recommended\" <<'PY_HONCHO_TIMEOUT'\n(.*?)\nPY_HONCHO_TIMEOUT",cfg,re.S)
assert m,'Honcho timeout ownership heredoc not found'
timeout_code=m.group(1)
with tempfile.TemporaryDirectory(prefix='lv151-honcho-timeout-') as td:
    td=Path(td); hp=td/'honcho.json'; marker=td/'honcho.json.latticevale-timeout-auto'
    hp.write_text(json.dumps({'baseUrl':'http://honcho-api:8000','hosts':{'hermes':{'enabled':True}}}),encoding='utf-8')
    r=subprocess.run([sys.executable,'-',str(hp),str(marker),'180'],input=timeout_code,text=True,capture_output=True,timeout=10)
    assert r.returncode==0,r.stderr
    assert json.loads(hp.read_text())['timeout']==180
    assert marker.read_text().strip()=='180'
    # User edit breaks ownership; the next policy pass must preserve it and retire the marker.
    data=json.loads(hp.read_text()); data['timeout']=240; hp.write_text(json.dumps(data),encoding='utf-8')
    r=subprocess.run([sys.executable,'-',str(hp),str(marker),'150'],input=timeout_code,text=True,capture_output=True,timeout=10)
    assert r.returncode==0,r.stderr
    assert json.loads(hp.read_text())['timeout']==240
    assert not marker.exists()

# Profile reconciliation merges existing config instead of discarding root/user fields.
assert "try: cfg=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}" in cfg
assert "block.update({'enabled':True" in cfg

# Pressure reporting must use a short delta and distinguish historical counters.
for marker in ('show_memory_pressure_summary() {','sleep 2','dmax=$((now_max-','HISTORICAL no new max/OOM events in 2s','ACTIVE memory.max +','CRITICAL oom_kill +'):
    assert marker in manage,marker

print('v14.5.1 MODEL-AWARE OLLAMA / HONCHO / PRESSURE FIXTURES: PASS')
