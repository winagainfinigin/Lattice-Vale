#!/usr/bin/env python3
"""Read-only audit of LatticeVale's free/local operating path.

This checks the current installation configuration, not third-party future pricing.  Optional
external/proprietary integrations are reported separately and never reclassified as guaranteed
free merely because a vendor currently offers a free tier.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

from latticevale_readonly import StackSnapshot


def build_report(snapshot: StackSnapshot) -> dict:
    opts = snapshot.options
    external_optional: list[str] = []
    if opts.tailscale:
        external_optional.append("Tailscale Windows-host integration (optional third-party service; pricing/plan terms are external to LatticeVale)")
    if opts.obsidian:
        external_optional.append("Obsidian Windows-host integration (optional proprietary application integration)")
    if opts.hermes_local_ai and opts.ollama_backend == "windows-native":
        external_optional.append("Windows-native Ollama bridge (optional free/local host integration; not part of the WSL-only core runtime path)")

    # A free/local default Hermes model path is guaranteed by configuration only when the
    # installer-selected local Ollama provider is enabled.  Other Hermes provider choices are
    # user-owned and may be free or paid; this audit does not guess from credential names.
    local_default = opts.hermes_local_ai and opts.ollama_backend in {"managed", "windows-native"}
    wsl_native_default = opts.hermes_local_ai and opts.ollama_backend == "managed"
    honcho_local = (not opts.honcho) or opts.local_ai_enabled
    blockers: list[str] = []
    if not local_default:
        blockers.append(
            "Default Hermes provider is not installer-declared local Ollama; the user-selected provider may require an external account or paid API."
        )
    if not honcho_local:
        blockers.append("Honcho is selected without a local AI backend declaration.")

    return {
        "schema": 1,
        "mode": "read-only",
        "definition": "free-only means core operation can use local/self-hosted software without a required paid API, subscription, or proprietary hosted infrastructure",
        "currentConfigurationFreeOnly": not blockers,
        "localDefaultHermesAI": local_default,
        "wslNativeCoreAIPath": wsl_native_default,
        "ollamaBackend": opts.ollama_backend if opts.local_ai_enabled else "not-selected",
        "selectedComponents": list(opts.selected_components()),
        "optionalExternalIntegrations": external_optional,
        "blockers": blockers,
        "notes": [
            "This audit does not promise that a third-party free tier will remain free in the future.",
            "Optional paid/external providers do not violate the project invariant; they only make the current profile non-free-only if selected as its required provider.",
            "The managed Ollama backend is the WSL-native free/local baseline; Windows-native Ollama is reported as an optional host integration even though it can also be free/local.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the current LatticeVale free/local operating path")
    parser.add_argument("--stack", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report(StackSnapshot.load(Path(args.stack)))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("== LatticeVale free/local operation audit ==")
        print(report["definition"] + ".")
        print(f"Current configuration: {'FREE-ONLY CAPABLE' if report['currentConfigurationFreeOnly'] else 'USES/DEPENDS ON USER-SELECTED NONLOCAL PROVIDER PATH'}")
        print(f"Default Hermes local AI: {'yes' if report['localDefaultHermesAI'] else 'no/unknown'}")
        print(f"WSL-native core AI path: {'yes' if report['wslNativeCoreAIPath'] else 'no'}")
        print(f"Ollama backend: {report['ollamaBackend']}")
        if report["blockers"]:
            print("Current free-only blockers/unknowns:")
            for item in report["blockers"]:
                print(f"  - {item}")
        if report["optionalExternalIntegrations"]:
            print("Optional external/proprietary integrations (not core requirements):")
            for item in report["optionalExternalIntegrations"]:
                print(f"  - {item}")
        print("No changes were made.")
    return 0 if report["currentConfigurationFreeOnly"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
