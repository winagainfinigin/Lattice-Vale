from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
version = (ROOT / "LatticeVale-Core" / "VERSION.txt").read_text(encoding="ascii").strip()
instructions = (ROOT / "docs" / "Instructions.txt").read_text(encoding="utf-8")
description = (ROOT / "docs" / "Installer Description.txt").read_text(encoding="utf-8")
changelog = (ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")

assert version in {"14.3.40", "14.3.41","14.3.42","14.3.43","14.4.0","14.4.1"}
assert instructions.startswith(f"LATTICEVALE v{version} — INSTRUCTIONS")
assert description.startswith(f"LATTICEVALE v{version} — INSTALLER DESCRIPTION")
assert "procedural operator guide" in instructions
assert "plain-language capability and configuration guide" in description
assert "EXISTING INSTALL — CHOOSE THE CORRECT MODE" in instructions
assert "SETTINGS THAT MAY STILL REQUIRE USER DECISIONS" in description
assert "AI PROVIDER AND MODEL SETTINGS" in description
assert "KANBAN AUTOMATION" in description
assert "TOOL PERMISSIONS AND APPROVALS" in description
assert "MATRIX / ELEMENT" in description
assert "TAILSCALE" in description
assert "OLLAMA / LOCAL MODEL SETTINGS" in description
assert "OBSIDIAN / QMD" in description
assert "HONCHO MEMORY" in description
assert "UPDATE POLICY" in description
assert "step-by-step install guide" in description
assert "## 14.3.40 - Documentation separation and post-install settings guide" in changelog
print("v14.3.40 documentation separation fixtures: PASS")
