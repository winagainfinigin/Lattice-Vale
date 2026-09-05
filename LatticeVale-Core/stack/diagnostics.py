#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from latticevale_arch import load_json,parse_compatibility,parse_env_state,schema_value,validate_runtime_policy_state

def main()->int:
    p=argparse.ArgumentParser(description='Read-only canonical LatticeVale diagnostics.')
    p.add_argument('--stack',default='.'); p.add_argument('--json',action='store_true'); a=p.parse_args(); root=Path(a.stack).resolve()
    files={
      'hardware':'data/latticevale/hardware-capabilities.json','backends':'data/latticevale/backend-capabilities.json','policy':'data/latticevale/runtime-policy.json','health':'data/latticevale/backend-health.json'}
    payload={'schema':1,'stack':str(root),'states':{},'issues':[]}
    for key,rel in files.items():
        value=load_json(root/rel,None); payload['states'][key]=value
        if not isinstance(value,dict): payload['issues'].append({'code':'GENERATED_STATE_MISSING','state':key,'path':rel})
    compat=parse_compatibility(root/'compatibility.conf')
    if (root/'.latticevale-resource-state').is_file():
        try: validate_runtime_policy_state(parse_env_state(root/'.latticevale-resource-state'),compat)
        except Exception as exc: payload['issues'].append({'code':'POLICY_VALIDATION_FAILED','detail':str(exc)})
    hw=payload['states'].get('hardware') or {}; be=payload['states'].get('backends') or {}
    summary={
      'windowsGpuCount':len(((hw.get('windows') or {}).get('gpus') or [])) if isinstance(hw,dict) else 0,
      'wslDxg':bool((((hw.get('wsl') or {}).get('dxg') or {}).get('present'))) if isinstance(hw,dict) else False,
      'wslRenderNodeCount':len(((hw.get('wsl') or {}).get('driRenderNodes') or [])) if isinstance(hw,dict) else 0,
      'selectedBackend':((be.get('selection') or {}).get('inferenceBackend')) if isinstance(be,dict) else None,
      'selectedTextBackend':((be.get('selection') or {}).get('textBackend')) if isinstance(be,dict) else None,
      'selectedOllamaAcceleration':((be.get('selection') or {}).get('ollamaAcceleration')) if isinstance(be,dict) else None,
    }
    payload['summary']=summary; payload['overall']='OK' if not payload['issues'] else 'NEEDS_ATTENTION'
    if a.json: print(json.dumps(payload,indent=2,sort_keys=True))
    else:
        print('== LatticeVale canonical diagnostics =='); print(f"Overall: {payload['overall']}")
        for k,v in summary.items(): print(f"{k}: {v}")
        for issue in payload['issues']: print(f"- {issue}")
    return 0 if not payload['issues'] else 1
if __name__=='__main__': raise SystemExit(main())
