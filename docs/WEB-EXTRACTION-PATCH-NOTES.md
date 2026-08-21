# v14.4.7 Web Extraction Patch Notes

## Problem

A v14.4.6 installation with SearXNG could perform Hermes `web_search`, but Hermes `web_extract` failed because the pinned Hermes SearXNG provider is intentionally search-only. Both default and installer-managed profiles could therefore discover URLs while being unable to read ordinary web pages unless the user independently configured another extraction provider.

## Design

v14.4.7 keeps the existing SearXNG + Valkey topology unchanged and adds a LatticeVale-owned Hermes web-provider plugin keyed `web/latticevale-web-extract` (manifest name `latticevale-web-extract`). It registers the provider name `latticevale-local` for extraction only.

When SearXNG is selected, LatticeVale sets `web.search_backend: searxng` as before. If `web.backend` is empty/SearXNG and `web.extract_backend` is empty/SearXNG/LatticeVale-local, it sets `web.extract_backend: latticevale-local`. An explicit Firecrawl, Tavily, Exa, Parallel, or custom shared/extract provider remains untouched.

The plugin is generated inside each applicable LatticeVale-managed Hermes home and enabled through that profile's normal `plugins.enabled` list. It uses the web-provider API already shipped in Hermes Agent v0.20.2 / v2026.8.16. No Hermes source tree is patched in place.

## Stability

The patch deliberately does **not** add self-hosted Firecrawl or another extraction service. No Compose service, image, database, queue, browser process, port, systemd unit, Windows task, WSL networking setting, CPU/RAM limit, model, package installation, or API credential is added. Existing SearXNG, QMD, Honcho, Matrix, Ollama, Kanban, Tailscale, Obsidian and resource-policy behavior is inherited.

The integrations checkpoint revision advances from 2 to 3. Resume / repair therefore reconciles the new managed-profile integration, but this does not advance `MANAGED_REPAIR_REFRESH_REVISION` and does not by itself force package/image/source refresh. Before that repair run, fully stop the selected LatticeVale WSL distro; if installed, **Shut Down LatticeVale** is the recommended method because it stops the managed stack and terminates only that distro.

## Network and content safety

`latticevale-local` is for ordinary public web documents, not arbitrary network retrieval. It:

- accepts only HTTP and HTTPS;
- rejects embedded URL credentials;
- resolves the destination and rejects any loopback/private/link-local/reserved/non-global address;
- revalidates every redirect destination;
- disables environment-proxy inheritance for its HTTP client;
- caps redirects at 5;
- caps each response body at 2,000,000 bytes;
- uses bounded connect/request timeouts;
- accepts text-oriented MIME types only;
- strips script/style/noscript/template/SVG/canvas content from HTML text extraction;
- caps returned text and reports per-URL errors without crashing the provider.

This is intentionally not an authenticated browser, JavaScript renderer, file downloader, or local-network client. Sites that require JavaScript, login state, anti-bot challenges, or a full browser can still require a separately configured browser/extraction provider.

## Search-result availability

The v14.4.7 extraction fix does not change how external search engines treat SearXNG traffic. SearXNG is hosted locally, but discovery still depends on upstream engines that can independently rate-limit, CAPTCHA, suspend, or refuse automated requests. Hermes can therefore receive a successful `web_search` response containing zero results even while the local SearXNG JSON API and provider wiring are healthy.

This is not, by itself, a LatticeVale repair condition. Retry later or broaden the query, inspect SearXNG's reported unresponsive engines when diagnosing repeated failures, and use `web_extract` directly when a trusted public URL is already known. Installation repair is appropriate when the local search/provider path itself is broken or the v14.4.7 extraction path cannot read ordinary known public pages.

## Upgrade behavior

- **Fresh install:** applicable managed profiles receive SearXNG search + LatticeVale local extraction.
- **v14.4.6 repair/resume:** integrations revision 3 applies the same pairing without a forced managed refresh.
- **Explicit extraction provider already configured:** preserved.
- **SearXNG deselected:** LatticeVale removes only its own SearXNG search selection and local extraction selection/plugin; unrelated web-provider configuration remains.

## Verification

Release regression coverage includes the v14.4.7 fixture, inherited fixtures, aggregate static audit, Python/shell syntax checks, mocked resume simulations, and complete source-manifest verification. Live target-system validation remains distinct from static fixture coverage; see `WINDOWS-INTEGRATION-TEST-MATRIX.md`.
