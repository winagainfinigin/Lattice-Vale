# Native Windows Ollama integration

> **v14.4.81 WSL recovery note:** the bounded preflight recovery can change an explicitly mirrored host to NAT only after persistent `E_UNEXPECTED` and explicit user approval. If that occurs, later native-Windows-Ollama/Tailscale integration checks must rediscover and verify the recovered live topology; they must not assume the pre-recovery mirrored path remains valid. This does not change native Ollama ownership, model placement, or relay/firewall policy.

> **v14.4.8 non-impact note:** the inherited v14.4.7 web-extraction patch and v14.4.8 Hermes clean/repair reliability maintenance do not change native Windows Ollama discovery, relay/firewall topology, model placement, or WSL networking ownership. The local-browser and missing extraction-timeout defaults apply only to installer-managed Hermes web/browser configuration.

> **v14.3.41 host-safety update:** native Windows Ollama integration no longer offers or writes mirrored WSL networking as remediation. LatticeVale uses an already-working externally configured mirrored topology when available; otherwise it uses verified NAT/default/VirtioProxy-capable relays or the explicit firewall-scoped direct-Ollama fallback.


## v14.3.38 non-impact note

The v14.3.38 Kanban/skill-policy migration does **not** change native Windows Ollama discovery, relay topology, firewall scope, WSL networking ownership, or model-placement behavior. Its integrations-stage migration may rewrite managed Hermes policy/config fields, but it preserves the existing Ollama backend/network policy selected for the installation.

Native Windows Ollama is optional and advanced. It is useful when Ollama should own GPU/runtime/model storage on Windows while Hermes/Honcho remain in WSL/Docker, but it necessarily crosses Windows, WSL, Docker-network and firewall boundaries. The LatticeVale-managed WSL/Docker Ollama backend is the simpler baseline.

## Shared WSL networking policy with Tailscale

When native Windows Ollama and Windows-host Tailscale exposure are both selected, LatticeVale treats WSL networking mode as one shared policy rather than allowing each feature to change `.wslconfig` independently. `install-options.json` is the canonical saved policy. Diagnostic metadata mirrors the saved mode/owner so repair and status output can identify drift without creating another state store.

- **Preserve a verified NAT topology.** If native Windows Ollama already verifies through the installer-owned private/gateway relay, selecting Windows-host Tailscale does not trigger a `.wslconfig` edit or global WSL restart. The Windows relay discovers/refreshes the current WSL IPv4 target as needed.
- **LatticeVale does not select mirrored mode.** If the host/user already configured mirrored networking and the selected distro is healthy, LatticeVale may use that existing topology without rewriting `.wslconfig`. If the active default/NAT/VirtioProxy-capable path cannot verify native Ollama, use the scoped direct-Ollama compatibility path where appropriate or the managed WSL/Docker Ollama backend; normal installer flows do not change the global WSL networking architecture.
- The relay does not continuously wake WSL to inspect topology. A healthy cached target is reused; live mode/address discovery occurs after backend failure and only against an already-running distro unless explicit stack auto-start permits recovery.
- LatticeVale does not add a Tailscale container or a second tailnet node for this policy. Windows Tailscale Serve continues to proxy to installer-owned Windows loopback bridge ports.
- When an externally configured mirrored mode is already healthy, Tailscale-selected Dashboard/Matrix host ports may use WSL loopback. NAT/default compatibility paths use the broader WSL bind only where Windows must reach the distro by VM IPv4.
- If the user changes WSL networking mode outside LatticeVale after configuration, the relay/status path detects the mismatch, but a Windows **Resume / repair** run is the authority for reconciling saved policy and service bind configuration.

## Supported transport principles

- The selected WSL distro's real Ollama HTTP response is authoritative for reachability.
- NAT host addresses are discovered from the current WSL topology rather than hard-coded. Microsoft documents the default-route host-IP pattern for WSL NAT.
- An externally configured mirrored topology may use Windows localhost from WSL when it is already selected by the host/user and verifies successfully.
- A relay is bound only to the interface/address required for its role; LatticeVale does not intentionally expose its private relay on all LAN interfaces.
- Installer-owned Windows and Hyper-V firewall rules remain exact-address/port scoped for NAT/direct compatibility paths and are refreshed if selected distro/host addresses change. A healthy externally configured mirrored topology may avoid depending on a WSL DHCP address, but LatticeVale does not switch the host into that mode.
- The Windows relay first checks whether the distro is running; topology monitoring does not intentionally wake a stopped distro.

## Reliability controls

- WSL-local relay: watchdog supervisor; automatic child restart; target/listener re-discovery; health-triggered rebuild.
- If systemd is already active, bootstrap installs `latticevale-native-ollama-relay.service` with `Restart=on-failure`. LatticeVale does not enable systemd or modify `/etc/wsl.conf` for this feature.
- Non-systemd environments use the relay helper's internal watchdog.
- Windows relays refresh topology while running rather than relying only on Scheduled Task restart-on-process-exit.
- Relays cap active connections at 64 and use bounded upstream-connect/session or idle timeouts.
- Common failure/topology events are written to installer-owned relay logs.

## Security boundary

Ollama's local API does not gain custom LatticeVale authentication. LatticeVale therefore relies on minimal reachability: specific bind addresses, exact firewall source/destination/port rules, WSL-only/Docker-host-gateway placement, and fail-closed ownership checks. Do not broaden relay or Ollama listeners manually unless you understand the LAN exposure.

Windows relay firewall rules use `Profile Any` only together with exact WSL address and port constraints because virtual WSL/Hyper-V traffic can interact with host profile classification differently across machines. LatticeVale does not change global Windows or Hyper-V firewall defaults.

## AV/EDR note

The Windows relay helpers contain readable C# source and compile it in memory using PowerShell `Add-Type`. The installer also uses a small `Add-Type` P/Invoke helper to broadcast an environment change after an explicitly accepted Ollama bind change. No compiled relay executable is shipped or downloaded. In-memory compilation can still trigger AV/EDR heuristics, especially on managed endpoints. Do not disable organization security controls to force installation; use the managed WSL/Docker Ollama backend or obtain security approval.

## Upstream references

- Microsoft WSL networking: https://learn.microsoft.com/windows/wsl/networking
- Microsoft WSL systemd: https://learn.microsoft.com/windows/wsl/systemd
- Microsoft Hyper-V firewall: https://learn.microsoft.com/windows/security/operating-system-security/network-security/windows-firewall/hyper-v-firewall
- Ollama FAQ / Windows environment configuration: https://docs.ollama.com/faq
