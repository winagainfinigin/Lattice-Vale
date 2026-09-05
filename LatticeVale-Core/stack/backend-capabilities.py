#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from latticevale_arch import atomic_write_json,classify_backends,load_json,parse_compatibility,schema_value,validate_install_options

def main()->int:
    p=argparse.ArgumentParser(description='Classify LatticeVale inference backends from canonical hardware state.')
    p.add_argument('--stack',default='.')
    p.add_argument('--compat',default='compatibility.conf')
    p.add_argument('--hardware',default='data/latticevale/hardware-capabilities.json')
    p.add_argument('--options',default='install-options.json')
    p.add_argument('--output',default='data/latticevale/backend-capabilities.json')
    p.add_argument('--json',action='store_true')
    a=p.parse_args(); root=Path(a.stack).resolve(); compat=parse_compatibility(root/a.compat)
    hw=load_json(root/a.hardware,None); opts=load_json(root/a.options,None)
    if not isinstance(hw,dict): raise SystemExit('Canonical hardware capability state is missing or unreadable.')
    validate_install_options(opts,schema_value(compat,'install_options'))
    payload=classify_backends(hw,opts,root,compat); atomic_write_json(root/a.output,payload)
    if a.json: print(json.dumps(payload,indent=2,sort_keys=True))
    else:
        sel=payload['selection']; print(f"Backend capabilities: inference={sel['inferenceBackend']} text={sel['textBackend']} ollama={sel['ollamaAcceleration']} fallback={sel['fallbackBackend']} fingerprint={payload['backendFingerprint']}")
    return 0
if __name__=='__main__': raise SystemExit(main())
