#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
from latticevale_arch import (
    atomic_write_json, build_runtime_policy_document, cpu_profile, cpu_quota_plan, directml_context_recommendation, directml_cpu_thread_plan, directml_generation_limit,
    gpu_context_recommendation, gpu_coordination, hermes_floor_mib, host_memory_budget, ollama_model_floor,
    load_json, ollama_runtime_settings, parse_compatibility, parse_env_state, ram_context_recommendation,
    ram_profile, runtime_tuning, schema_value, service_memory_plan,
    validate_install_options, validate_runtime_policy_document, validate_runtime_policy_state,
)

def tf(value:str)->bool:
    if value not in ('true','false'): raise argparse.ArgumentTypeError('must be true or false')
    return value=='true'

def main()->int:
    p=argparse.ArgumentParser(description='Canonical LatticeVale runtime resource-policy interface.')
    sub=p.add_subparsers(dest='cmd',required=True)
    q=sub.add_parser('host-budget'); q.add_argument('mem_mib',type=int); q.add_argument('accel'); q.add_argument('managed',type=tf); q.add_argument('directml',type=tf)
    q=sub.add_parser('profile'); q.add_argument('kind',choices=('ram','cpu')); q.add_argument('value',type=int)
    q=sub.add_parser('context'); q.add_argument('kind',choices=('ram','gpu')); q.add_argument('mib',type=int)
    q=sub.add_parser('directml-context'); q.add_argument('mem_mib',type=int); q.add_argument('adapter_vram_mib',type=int,nargs='?',default=0)
    q=sub.add_parser('directml-cpu'); q.add_argument('cpus',type=int)
    q=sub.add_parser('directml-generation'); q.add_argument('context_tokens',type=int)
    q=sub.add_parser('ollama-runtime'); q.add_argument('mem_mib',type=int); q.add_argument('cpus',type=int); q.add_argument('accel'); q.add_argument('directml',type=tf)
    q=sub.add_parser('hermes-floor'); q.add_argument('matrix_gateways',type=int); q.add_argument('kanban_concurrency',type=int)
    q=sub.add_parser('ollama-floor'); q.add_argument('mem_mib',type=int); q.add_argument('artifact_mib',type=int); q.add_argument('context_tokens',type=int); q.add_argument('accel'); q.add_argument('hybrid',type=tf); q.add_argument('usable_gpu_max_mib',type=int,nargs='?',default=0); q.add_argument('usable_gpu_total_mib',type=int,nargs='?',default=0)
    q=sub.add_parser('gpu-coordination'); q.add_argument('accel'); q.add_argument('count',type=int); q.add_argument('min_mib',type=int); q.add_argument('max_mib',type=int); q.add_argument('directml_vendor'); q.add_argument('directml_selected',type=tf)
    q=sub.add_parser('cpu-plan'); q.add_argument('cpus',type=int); q.add_argument('matrix_gateways',type=int); q.add_argument('kanban_concurrency',type=int); q.add_argument('accel')
    q=sub.add_parser('tuning'); q.add_argument('mem_mib',type=int); q.add_argument('cpus',type=int); q.add_argument('synapse_mib',type=int); q.add_argument('database_mib',type=int)
    q=sub.add_parser('service-plan'); q.add_argument('budget_mib',type=int); q.add_argument('matrix',type=tf); q.add_argument('searxng',type=tf); q.add_argument('qmd',type=tf); q.add_argument('ollama',type=tf); q.add_argument('honcho',type=tf); q.add_argument('hermes_floor',type=int); q.add_argument('ollama_floor',type=int)
    for name in ('write','verify'):
        q=sub.add_parser(name); q.add_argument('--stack',default='.'); q.add_argument('--compat',default='compatibility.conf'); q.add_argument('--state',default='.latticevale-resource-state'); q.add_argument('--output',default='data/latticevale/runtime-policy.json')
    a=p.parse_args()
    try:
        if a.cmd=='host-budget':
            r=host_memory_budget(a.mem_mib,a.accel,a.managed,a.directml); print(f"{r['reserveMiB']}:{r['directmlHostReserveMiB']}:{r['containerBudgetMiB']}"); return 0
        if a.cmd=='profile':
            print(ram_profile(a.value) if a.kind=='ram' else cpu_profile(a.value)); return 0
        if a.cmd=='context':
            print(ram_context_recommendation(a.mib) if a.kind=='ram' else gpu_context_recommendation(a.mib)); return 0
        if a.cmd=='directml-context':
            print(directml_context_recommendation(a.mem_mib,a.adapter_vram_mib)); return 0
        if a.cmd=='directml-cpu':
            print(directml_cpu_thread_plan(a.cpus)); return 0
        if a.cmd=='directml-generation':
            print(directml_generation_limit(a.context_tokens)); return 0
        if a.cmd=='ollama-runtime':
            r=ollama_runtime_settings(a.mem_mib,a.cpus,a.accel,a.directml); print(f"{r['maxLoadedModels']}:{r['parallel']}:{r['keepAlive']}"); return 0
        if a.cmd=='hermes-floor':
            print(hermes_floor_mib(a.matrix_gateways,a.kanban_concurrency)); return 0
        if a.cmd=='ollama-floor':
            print(ollama_model_floor(a.mem_mib,a.artifact_mib,a.context_tokens,a.accel,a.hybrid,a.usable_gpu_max_mib,a.usable_gpu_total_mib)); return 0
        if a.cmd=='gpu-coordination':
            r=gpu_coordination(a.accel,a.count,a.min_mib,a.max_mib,a.directml_vendor,a.directml_selected); print(f"{r['ollamaGpuOverheadMiB']}:{r['directmlVramLimitPct']}:{str(r['sharedVendor']).lower()}"); return 0
        if a.cmd=='cpu-plan':
            r=cpu_quota_plan(a.cpus,a.matrix_gateways,a.kanban_concurrency,a.accel)
            for k,v in r.items(): print(f'{k}={v}')
            return 0
        if a.cmd=='tuning':
            r=runtime_tuning(a.mem_mib,a.cpus,a.synapse_mib,a.database_mib); print(f"{r['mallocArenaMax']}:{r['synapseCacheFactor']}:{r['postgresSharedBuffers']}"); return 0
        if a.cmd=='service-plan':
            r=service_memory_plan(a.budget_mib,matrix=a.matrix,searxng=a.searxng,qmd=a.qmd,ollama=a.ollama,honcho=a.honcho,hermes_floor=a.hermes_floor,ollama_floor=a.ollama_floor)
            for k,v in r.items(): print(f'{k}={v}')
            return 0
    except ValueError as exc:
        print(str(exc),file=sys.stderr); return 3

    root=Path(a.stack).resolve(); compat=parse_compatibility(root/a.compat); state=parse_env_state(root/a.state)
    hardware=load_json(root/'data/latticevale/hardware-capabilities.json',{})
    backends=load_json(root/'data/latticevale/backend-capabilities.json',{})
    opts=load_json(root/'install-options.json',{}); validate_install_options(opts,schema_value(compat,'install_options'))
    if a.cmd=='verify':
        existing=load_json(root/a.output,None)
        try: validate_runtime_policy_document(existing,state,hardware,backends,compat,opts)
        except ValueError as exc: raise SystemExit(str(exc))
        print(f"Runtime policy verified: schema={existing['schema']} fingerprint={existing['policyFingerprint']}"); return 0
    # Validate the legacy env-state representation before building the structured canonical document.
    validate_runtime_policy_state(state,compat,opts,hardware,backends)
    payload=build_runtime_policy_document(state,hardware,backends,compat,opts); atomic_write_json(root/a.output,payload)
    # Self-consistency invariant: the artifact just generated must be accepted by the canonical consumer.
    validate_runtime_policy_document(load_json(root/a.output,None),state,hardware,backends,compat,opts)
    print(f"Runtime policy written: schema={payload['schema']} fingerprint={payload['policyFingerprint']}"); return 0
if __name__=='__main__': raise SystemExit(main())
