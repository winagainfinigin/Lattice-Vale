# LatticeVale v14.7.0 hotfix — Ollama GPU verification

This hotfix does not change the release version, selected GPU backend, Docker
limits, WSL configuration, or normal model-retention settings.

- Ollama's `OLLAMA_KEEP_ALIVE=0s` is deliberate when DirectML reserves host
  memory. The prior GPU check ran a model and then inspected `ollama ps` after
  Ollama may already have unloaded it. The check now uses `ollama run --keepalive
  60s` for the one verification request and unloads that model afterward.
- Model startup failures and `ollama ps` failures are now visible rather than
  silently converted into generic unknown-offload failures. A different
  already-loaded model can no longer be mistaken for the selected model.
- Auto-selected Vulkan/ROCm/CUDA still falls back to CPU only when Ollama
  positively reports CPU execution. Unknown inference status fails closed; it
  does not justify GPU-sized memory assumptions.
- The prior installation audit also found a stale resource fingerprint,
  incomplete Vulkan overlay, a historical OOM event, and a DirectML gateway
  that was unreachable *before* the infrastructure repair completed. Those
  are separate runtime conditions, not proven causes of this failure. After
  installing the hotfix, use **Resume / repair** so the installer can finish
  the independent DirectML gateway checks and assess the runtime policy.
- The discrepancy between the questionnaire's initial no-render-node result
  and later Vulkan detection requires runtime evidence if offload still
  fails; this hotfix does not invent a GPU device or change driver settings.

Validation is source-level plus a deterministic, mocked seven-case regression
fixture. A live WSL/Docker/DirectML/GPU end-to-end test has not been performed
by the package author and must not be claimed as complete.

Repository source base: commit `714200ae6cecd3e8134174a3622946fdde54149a`.
