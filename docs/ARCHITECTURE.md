# LatticeVale 14.6.0 Architecture

## Principle

**Detect once, classify once, calculate once, validate once.** Downstream components consume canonical derived state instead of independently recreating hardware/backend/resource assumptions.

```text
Windows host snapshot + live WSL probes
                  |
                  v
      hardware-capabilities.json
                  |
                  v
       Backend Capability Engine
      /      |       |       \\
 DirectML   CUDA    ROCm    Vulkan -- CPU/native-Windows fallback
                  |
                  v
       backend-capabilities.json
                  |
                  v
      Canonical Resource Policy
                  |
                  v
          runtime-policy.json
                  |
     +------------+-------------------------------+
     |            |             |                 |
 DirectML       Ollama        Hermes/Honcho    Compose/service limits
                  |
                  v
        Canonical validation/audit
                  |
                  v
       Repair planner / diagnostics
```

## Ownership

- `install-options.json`: durable user intent and component choices.
- `latticevale_arch.py`: canonical schemas, hardware/backend classification, stable fingerprints, resource-policy invariants, atomic JSON writes, backend-health state.
- `hardware-capabilities.py`: live hardware document generator.
- `backend-capabilities.py`: capability/selection document generator.
- `runtime-policy.py`: canonical resource-policy document write/verify CLI.
- `diagnostics.py`: read-only architecture summary.
- `state-audit.py`: independent invariant/state verification that consumes canonical documents rather than duplicating formulas.
- `repair-plan.py`: dependency-aware repair recommendation.

## Provenance

Generated architecture documents include schema, architecture version, generation time, source/hardware/policy fingerprints as appropriate. Atomic replacement is used for canonical JSON documents so interrupted generation does not expose a half-written active file.

## Compatibility

14.6.0 migrates recognized managed 14.x installations through Resume / repair. Durable historical option names remain understood for migration. Future schemas fail closed. User/application data, persistent identities, and explicit overrides remain preservation-first.
