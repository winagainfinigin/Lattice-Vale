# LatticeVale 14.6.1 Troubleshooting

## Tailscale remote access reports PARTIAL or FAIL

`PASS` now means a second Tailscale device opened the installer-created HTTPS challenge in the current run. `PARTIAL` means the Windows relay/Serve/client-path checks passed but the second-device proof was not completed. `FAIL` means a prerequisite or classified remote test failed.

For `DNS` failure or an Android client that says **DNS unavailable**, verify the Tailscale Admin Console DNS configuration, MagicDNS/HTTPS availability, and the phone's **Use Tailscale DNS settings** state. LatticeVale can validate and normalize the Windows client, but it cannot silently rewrite tailnet-wide DNS policy. For `TRANSPORT`, `TLS`, or `SERVE`, keep the generated remote-access log and rerun Resume / repair after correcting the reported layer.

The focused Windows log is written under `%LOCALAPPDATA%\LatticeVale\logs\remote-access-*.log` (with a temporary-directory fallback if needed).


## Matrix works in a browser over Tailscale but a client cannot sign in

For a Tailscale-exposed Matrix install, test the public `/_matrix/client/versions` endpoint and `/.well-known/matrix/client`. v14.6.1 requires the well-known response to advertise the exact Tailscale HTTPS base URL and requires the login endpoint to expose a flow before the installer keeps its Matrix Serve mapping. Resume / repair with the full v14.6.1 release to reconcile an older false-positive mapping.

If those checks pass but a client still rejects the homeserver, capture the client-visible error plus the public `/_matrix/client/v3/login` response. v14.6.1 deliberately does not change the authentication backend, `server_name`, or existing Matrix IDs; troubleshoot authentication separately from the Tailscale transport/discovery path.


## DirectML fail-closed and high-CPU checks

If DirectML was configured with no Ollama text fallback, a DirectML worker/model failure is expected to leave local text inference unavailable rather than silently switch to Ollama. Resume / repair removes any legacy forced-fallback marker under this policy. For unexpected CPU saturation, inspect `resource-policy-report.txt`: policy v13 records system headroom, DirectML reserve, Docker envelope, aggregate Docker allocation, and per-service quotas. The aggregate Docker allocation must be at or below the Docker envelope.

## Repair fails after generating configuration

Use the reported stage and reason code. Do not immediately recreate the distro. Run the read-only diagnostics and rerun Option 1 after correcting the prerequisite. Current generated options/policy must validate through the canonical architecture layer before downstream service work continues.

## Windows sees a GPU but WSL reports no Linux GPU adapters

That is not enough evidence to declare all GPU acceleration broken. Check each route separately:

- DirectML: `/dev/dxg`, projected D3D12/DXCore libraries, DirectML runtime/tensor probe;
- CUDA: WSL NVIDIA runtime/device visibility;
- ROCm: `/dev/kfd` and DRM topology;
- Vulkan: DRM render device plus runtime execution proof.

CPU fallback remains valid when no GPU backend is usable.

## DirectML tensor probe passes but the model self-test has no HTTP response

A passing tensor probe proves the WSL DirectX bridge, `torch_directml` import, selected adapter, and a simple device operation. It does **not** prove that every Transformers model/operator used during generation is supported. Current v14.6.1 retains the v14.6.0 protection for the pinned Qwen2/Qwen2.5 path from known DirectML causal-mask `masked_fill`/in-place-mask failures and fixes the fail-closed helper used when Ollama text fallback is disabled.

On Resume / repair, LatticeVale rebuilds/revalidates its isolated DirectML environment and retries the model self-test. If the HTTP request still terminates, the self-test now prints the bounded curl error and the last 120 lines of `logs/directml-gateway.log` before applying the configured fallback policy. With fallback `none`, this remains a hard fail-closed result; with a configured Ollama text fallback, LatticeVale may activate the bounded fallback marker and continue. Do not interpret a successful standalone system-Python tensor test as proof that the managed model-generation path is healthy.

## DirectML gateway uses Ollama fallback because memory capacity is unavailable

If the gateway reports `DML_VRAM_CAPACITY_UNAVAILABLE`, do not install arbitrary WSL GPU packages or disable the safety check. Current 14.6.1 first tries the DirectML runtime's own capacity API, then the canonical PNP-correlated Windows memory inventory. Discrete dedicated memory and UMA/shared memory are handled differently. If neither produces a trustworthy bounded admission ceiling, DirectML intentionally falls back rather than loading an unbounded model.

Run Option 8 or `./directml-gateway.sh diagnose` and inspect the selected adapter, declared memory source/confidence, `/dev/dxg`, D3D12/DXCore bridge libraries, and tensor result. Windows/WSL projection or vendor-driver failure is a host prerequisite problem; successful projection with missing/mis-correlated canonical memory is a LatticeVale diagnostic/admission problem.

A DirectML runtime fallback is transient health state. It should not by itself make `runtime-policy.json` stale when the policy topology and host reserve remain conservative; Resume / repair may retry DirectML after a material hardware/driver/WSL fingerprint change.

## DirectML chose the wrong GPU

Run `./directml-gateway.sh diagnose` and `./manage.sh diagnose-backends`. Explicit adapter identity is applied before DirectML import and verified again in runtime. If the explicitly saved adapter no longer exists, LatticeVale preserves the saved intent but does not silently redirect it to an unrelated device.

## Resource policy says stale

Run `./manage.sh diagnose-policy`. Hardware/backend fingerprint changes intentionally invalidate dependent derived policy. Option 1 regenerates it using the canonical budget API.

## Patch ZIP versus full release

The repository patch ZIP contains only changed/new repository files relative to the declared parent release. It is not a live-stack overlay. Existing installations should always be updated/repaired through the full release installer.
