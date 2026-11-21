from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
kanban = (REPO / 'tools/hermes_kanban_export.py').read_text(encoding='utf-8')
structure = (REPO / 'tools/hermes_structure_audit.py').read_text(encoding='utf-8')

assert "parser.add_argument('--include-comments'" in kanban
assert "parser.add_argument('--include-worker-errors'" in kanban
assert "parser.add_argument('--include-paths'" in kanban
assert "INCLUDE_COMMENTS = os.environ.get('LV_KANBAN_INCLUDE_COMMENTS') == '1'" in kanban
assert "INCLUDE_RUN_ERRORS = os.environ.get('LV_KANBAN_INCLUDE_RUN_ERRORS') == '1'" in kanban
assert "INCLUDE_PATHS = os.environ.get('LV_KANBAN_INCLUDE_PATHS') == '1'" in kanban
assert 'sk-[A-Za-z0-9_-]{16,}' in kanban and 'PRIVATE KEY' in kanban
assert "mode=ro" in kanban and 'PRAGMA query_only=ON' in kanban
assert "parser.add_argument('--include-all-profiles'" in structure
assert "parser.add_argument('--include-paths'" in structure
assert 'if _args.include_all_profiles:' in structure
assert 'if not _args.include_paths:' in structure
assert "LV_AUDIT_INCLUDE_PATHS=" in structure
print('PASS opt-in redaction controls for supplied Hermes audit tools')
