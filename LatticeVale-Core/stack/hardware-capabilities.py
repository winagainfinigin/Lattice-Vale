#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from latticevale_arch import atomic_write_json, load_json, parse_compatibility, probe_hardware

def main()->int:
    p=argparse.ArgumentParser(description='Generate canonical LatticeVale hardware capability inventory.')
    p.add_argument('--stack',default='.')
    p.add_argument('--compat',default='compatibility.conf')
    p.add_argument('--windows-snapshot',default='data/latticevale/windows-hardware.json')
    p.add_argument('--output',default='data/latticevale/hardware-capabilities.json')
    p.add_argument('--json',action='store_true')
    a=p.parse_args(); root=Path(a.stack).resolve()
    compat=parse_compatibility(root/a.compat)
    windows=load_json(root/a.windows_snapshot,{})
    payload=probe_hardware(root,compat,windows)
    atomic_write_json(root/a.output,payload)
    if a.json: print(json.dumps(payload,indent=2,sort_keys=True))
    else: print(f"Hardware capabilities: fingerprint={payload['hardwareFingerprint']} Windows GPUs={len(payload['windows']['gpus'])} WSL RAM={payload['wsl']['memoryMiB']}MiB /dev/dxg={payload['wsl']['dxg']['present']} renderNodes={len(payload['wsl']['driRenderNodes'])}")
    return 0
if __name__=='__main__': raise SystemExit(main())
