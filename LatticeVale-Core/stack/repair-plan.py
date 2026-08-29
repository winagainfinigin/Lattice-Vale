#!/usr/bin/env python3
"""Read-only repair planner for LatticeVale v14.5.0.

The planner is deliberately advisory.  It never writes stack state and it does not replace
the proven configure-stack.sh reconciliation path.  Applying a repair still happens through
the Windows installer Resume / repair flow.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

sys.dont_write_bytecode = True

from latticevale_readonly import StackSnapshot

_BAD_AUDIT_STATES = {"BROKEN", "PARTIAL", "OUTDATED", "UNKNOWN", "NOT_INSTALLED"}


def _run_audit(root: Path, offline: bool) -> tuple[dict[str, Any], str | None]:
    command = [sys.executable, str(root / "state-audit.py"), "--stack", str(root), "--json"]
    if offline:
        command.append("--offline")
    try:
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=90 if not offline else 30,
            check=False,
        )
    except Exception as exc:
        return {}, f"state-audit.py could not run: {exc}"
    if proc.returncode not in (0, 1):
        detail = (proc.stderr or proc.stdout).strip()
        return {}, f"state-audit.py failed with exit {proc.returncode}: {detail[:300]}"
    try:
        payload = json.loads(proc.stdout)
        return payload if isinstance(payload, dict) else {}, None
    except Exception as exc:
        return {}, f"state-audit.py returned unreadable JSON: {exc}"


def _checkpoint_plan(snapshot: StackSnapshot) -> list[dict[str, Any]]:
    current_hash = snapshot.computed_options_hash
    actions: list[dict[str, Any]] = []
    for meta in snapshot.checkpoints:
        stored = snapshot.checkpoint_state(meta.name)
        status = str(stored.get("status") or "missing")
        stored_hash = str(stored.get("optionsHash") or "")
        try:
            stored_revision = int(stored.get("revision", 1))
        except (TypeError, ValueError):
            stored_revision = 1
        reasons: list[str] = []
        if status != "done":
            reasons.append(f"checkpoint status is {status!r}, not 'done'")
        if stored_hash and stored_hash != current_hash:
            reasons.append("checkpoint options hash differs from current installer-selected options")
        elif status == "done" and not stored_hash:
            reasons.append("completed checkpoint has no options hash")
        if stored_revision != meta.revision:
            reasons.append(f"checkpoint revision {stored_revision} != required revision {meta.revision}")
        if reasons:
            actions.append(
                {
                    "stage": meta.name,
                    "description": meta.description,
                    "action": "REPLAY_OR_VERIFY",
                    "recovery": meta.recovery,
                    "reasons": reasons,
                }
            )
    return actions


def _runtime_findings(audit: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    components = audit.get("components", {})
    if not isinstance(components, dict):
        return findings
    for name, item in components.items():
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "UNKNOWN")
        if status in _BAD_AUDIT_STATES:
            findings.append(
                {
                    "component": str(name),
                    "status": status,
                    "detail": str(item.get("detail") or ""),
                }
            )
    return findings


def build_plan(snapshot: StackSnapshot, audit: dict[str, Any], audit_error: str | None) -> dict[str, Any]:
    checkpoint_actions = _checkpoint_plan(snapshot)
    runtime_findings = _runtime_findings(audit)
    raw = snapshot.raw_options
    explicit_identity_rebuild = bool(raw.get("rebuildMatrixIdentity"))
    warnings = list(snapshot.warnings)
    if audit_error:
        warnings.append(audit_error)
    if snapshot.user_override_present:
        warnings.append(
            "compose.override.yaml is user-owned and remains opaque to this planner; it will not be normalized or rewritten"
        )
    if explicit_identity_rebuild:
        warnings.append(
            "install-options.json contains rebuildMatrixIdentity=true; applying Resume / repair may intentionally replace installer-owned Matrix identity state"
        )

    overall = str(audit.get("overall") or "UNKNOWN") if audit else "UNKNOWN"
    needs_repair = bool(checkpoint_actions or runtime_findings or overall == "NEEDS_REPAIR")
    return {
        "schema": 1,
        "mode": "read-only",
        "stackPath": str(snapshot.root),
        "installerVersion": snapshot.options.installer_version,
        "selectedComponents": list(snapshot.options.selected_components()),
        "workers": list(snapshot.options.workers),
        "sources": [
            {
                "path": source.path,
                "role": source.role,
                "exists": source.exists,
                "sha256": source.sha256,
                "note": source.note,
            }
            for source in snapshot.sources
        ],
        "auditOverall": overall,
        "checkpointActions": checkpoint_actions,
        "runtimeFindings": runtime_findings,
        "needsRepair": needs_repair,
        "explicitIdentityRebuildRequested": explicit_identity_rebuild,
        "destructiveOperations": (
            ["explicit installer-owned Matrix identity rebuild is requested by current options"]
            if explicit_identity_rebuild
            else []
        ),
        "warnings": warnings,
        "apply": {
            "supportedByPlanner": False,
            "instruction": "Rerun Install-LatticeVale.ps1 and choose Resume / repair to apply; the existing verifier/reconciliation engine remains authoritative.",
        },
    }


def _print_human(plan: dict[str, Any]) -> None:
    print("== LatticeVale read-only repair plan ==")
    print(f"Stack: {plan['stackPath']}")
    print(f"Installer metadata version: {plan.get('installerVersion') or 'unknown'}")
    print(f"Live audit: {plan.get('auditOverall') or 'UNKNOWN'}")
    print()
    print("Configuration sources:")
    for source in plan["sources"]:
        state = "present" if source["exists"] else "missing"
        print(f"  {source['path']:<26} {state:<8} {source['role']}")
        if source.get("note"):
            print(f"    - {source['note']}")

    actions = plan["checkpointActions"]
    print()
    print("Checkpoint/revision plan:")
    if not actions:
        print("  No stale/incomplete checkpoint revisions detected.")
    else:
        for item in actions:
            print(f"  {item['stage']:<30} {item['action']}")
            print(f"    - {item['description']}")
            for reason in item["reasons"]:
                print(f"    - {reason}")
            print(f"    - recovery policy: {item['recovery']}")

    findings = plan["runtimeFindings"]
    print()
    print("Live/runtime findings:")
    if not findings:
        print("  No BROKEN/PARTIAL/OUTDATED/UNKNOWN/NOT_INSTALLED component findings detected.")
    else:
        for item in findings:
            print(f"  {item['component']:<22} {item['status']}")
            if item["detail"]:
                print(f"    - {item['detail']}")

    print()
    destructive = plan["destructiveOperations"]
    if destructive:
        print("Potentially destructive operations explicitly requested by current installer options:")
        for item in destructive:
            print(f"  - {item}")
    else:
        print("Destructive operations requested by current options: NONE detected")

    if plan["warnings"]:
        print()
        print("Planner notes:")
        for warning in plan["warnings"]:
            print(f"  - {warning}")

    print()
    if plan["needsRepair"]:
        print("Plan result: REPAIR/VERIFICATION WORK DETECTED")
        print("Apply: rerun Install-LatticeVale.ps1 and choose Resume / repair.")
    else:
        print("Plan result: NO REPAIR WORK DETECTED")
    print("No changes were made.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only LatticeVale repair planner")
    parser.add_argument("--stack", default=".")
    parser.add_argument("--offline", action="store_true", help="Do not query Docker/HTTP runtime state")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    snapshot = StackSnapshot.load(args.stack)
    audit, audit_error = _run_audit(snapshot.root, args.offline)
    plan = build_plan(snapshot, audit, audit_error)
    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        _print_human(plan)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
