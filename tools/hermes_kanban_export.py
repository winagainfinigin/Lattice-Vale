#!/usr/bin/env python3
"""Read-only, timeout-bounded export of the verified LatticeVale/Hermes Kanban DB.

Run from the WSL shell (not inside the container). The Dockerized Python reads
/opt/data/kanban.db, and the WSL-side script writes the Windows Desktop report.
"""
import os
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Established from Hermes-Structure-Audit-20261121-035822.txt.
DESKTOP = Path(os.environ.get("HERMES_REPORT_DESKTOP", "/mnt/c/Users/Brian/Desktop"))
DEFAULT_OUTPUT = DESKTOP / "Hermes-Kanban-All-Cards.txt"
TIMEOUT_SECONDS = 60

CONTAINER_SCRIPT = r'''
import sqlite3
import sys
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

DB = Path('/opt/data/kanban.db')
INCLUDE_COMMENTS = os.environ.get('LV_KANBAN_INCLUDE_COMMENTS') == '1'
INCLUDE_RUN_ERRORS = os.environ.get('LV_KANBAN_INCLUDE_RUN_ERRORS') == '1'
INCLUDE_PATHS = os.environ.get('LV_KANBAN_INCLUDE_PATHS') == '1'
SECRET_PATTERNS = [
    re.compile(r'(?i)\b(bearer\s+)[A-Za-z0-9._~+/-]+=*'),
    re.compile(r'(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)(\s*[:=]\s*)[^\s,;]+'),
    re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{16,})\b'),
    re.compile(r'\b(?:sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16})\b'),
    re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b'),
    re.compile(r'(?i)(https?://)[^/@\s:]+:[^/@\s]+@'),
    re.compile(r'(?is)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
]

def safe_text(value):
    text = str(value if value not in (None, '') else '(none)')
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda m: (m.group(1) + '[REDACTED]') if m.lastindex and m.lastindex >= 1 and m.group(1).lower().startswith('bearer') else '[REDACTED]', text)
    return text

print(f'[Docker] Reading {DB} ...', file=sys.stderr, flush=True)
if not DB.is_file():
    raise SystemExit(f'ERROR: Database missing: {DB}')

con = sqlite3.connect(DB.as_uri() + '?mode=ro', uri=True, timeout=1)
con.row_factory = sqlite3.Row
con.execute('PRAGMA busy_timeout=1000')
con.execute('PRAGMA query_only=ON')
con.execute('BEGIN')  # One consistent WAL snapshot; does not block normal writers.

names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
required = {'tasks', 'task_runs', 'task_comments', 'task_links', 'task_attachments'}
if missing := (required - names):
    raise SystemExit('ERROR: Required Kanban tables missing: ' + ', '.join(sorted(missing)))

tasks = [dict(r) for r in con.execute('SELECT * FROM tasks ORDER BY created_at, id')]
runs = defaultdict(list)
comments = defaultdict(list)
parents = defaultdict(list)
children = defaultdict(list)
attachments = defaultdict(list)
for r in con.execute('SELECT * FROM task_runs ORDER BY started_at, id'):
    d = dict(r)
    runs[d['task_id']].append(d)
for r in con.execute('SELECT * FROM task_comments ORDER BY created_at, id'):
    d = dict(r)
    comments[d['task_id']].append(d)
for r in con.execute('SELECT parent_id, child_id FROM task_links'):
    parents[r['child_id']].append(r['parent_id'])
    children[r['parent_id']].append(r['child_id'])
for r in con.execute('SELECT * FROM task_attachments ORDER BY created_at, id'):
    d = dict(r)
    attachments[d['task_id']].append(d)
con.rollback()  # End the read transaction; no changes made.
con.close()

if not tasks:
    raise SystemExit('ERROR: Kanban database has zero cards; refusing empty report.')

statuses = Counter(t.get('status') or '<null>' for t in tasks)
print(f'[Docker] Loaded {len(tasks)} cards, {sum(map(len,runs.values()))} runs, '
      f'{sum(map(len,comments.values()))} comments, '
      f'{sum(map(len,attachments.values()))} attachments.', file=sys.stderr, flush=True)

print('HERMES KANBAN — ALL CARDS AND RECORDED SUMMARIES')
print('Generated UTC:', datetime.now(timezone.utc).isoformat())
print('Source: Docker container hermes-agent, database /opt/data/kanban.db')
print('Cards:', len(tasks))
print('Status breakdown:')
for status, count in sorted(statuses.items()):
    print(f'  {safe_text(status)}: {count}')
print('NOTE: Includes current card state plus all persisted historical worker attempts.')
print('NOTE: Attachment contents are not embedded; attachment paths and comments are omitted unless explicitly requested.')

# Unfinished first, done last, with stable order by status and creation.
tasks.sort(key=lambda t: (t.get('status') == 'done', str(t.get('status') or ''),
                          t.get('created_at') or 0, t['id']))

def print_detail(label, value):
    print(f'\n{label}:')
    print(safe_text(value))

for idx, t in enumerate(tasks, 1):
    tid = t['id']
    if idx == 1 or idx % 25 == 0 or idx == len(tasks):
        print(f'[Docker] Writing card {idx}/{len(tasks)}', file=sys.stderr, flush=True)
    print('\n' + '=' * 90)
    print(f"CARD {idx}/{len(tasks)} | {safe_text(str(t.get('status') or '<null>').upper())} | {tid}")
    print('=' * 90)
    for col in ('title', 'assignee', 'priority', 'created_at', 'started_at', 'completed_at',
                'consecutive_failures', 'block_kind', 'block_recurrences'):
        print(f'{col}: {safe_text(t.get(col))}')
    print('last_failure_error:', safe_text(t.get('last_failure_error')) if INCLUDE_RUN_ERRORS else '(omitted; pass --include-worker-errors to include)')
    print('workspace_path:', safe_text(t.get('workspace_path')) if INCLUDE_PATHS else '(redacted; pass --include-paths to include)')
    print('parent cards (depends on):', ', '.join(parents[tid]) or '(none)')
    print('child cards (dependents):', ', '.join(children[tid]) or '(none)')
    print_detail('CARD DESCRIPTION', t.get('body'))
    print_detail('CARD RESULT', t.get('result'))
    print(f'\nWORKER RUN HISTORY ({len(runs[tid])}):')
    if not runs[tid]:
        print('(no worker runs recorded)')
    for r in runs[tid]:
        print('\n  ' + '-' * 65)
        for key in ('id', 'profile', 'status', 'outcome', 'started_at', 'ended_at'):
            print(f'  {key}: {r.get(key)}')
        print('  SUMMARY:')
        print(safe_text(r.get('summary')))
        print('  ERROR:')
        print(safe_text(r.get('error')) if INCLUDE_RUN_ERRORS else '(omitted; pass --include-worker-errors to include)')
    print(f'\nCOMMENTS ({len(comments[tid])}; bodies {"included" if INCLUDE_COMMENTS else "omitted"}):')
    if INCLUDE_COMMENTS:
        for c in comments[tid]:
            print(f"\n  [{c.get('created_at')}] {safe_text(c.get('author'))}:")
            print(safe_text(c.get('body')))
    print(f'\nATTACHMENTS ({len(attachments[tid])}):')
    for a in attachments[tid]:
        stored_path = safe_text(a.get('stored_path')) if INCLUDE_PATHS else '(redacted)'
        print(f"  {safe_text(a.get('filename'))} | {stored_path} | {a.get('size')} bytes")

print('\n' + '=' * 90)
print('EXPORT COMPLETE')
print('Total cards:', len(tasks))
for status, count in sorted(statuses.items()):
    print(f'{safe_text(status)}: {count}')
print('[Docker] Export complete.', file=sys.stderr, flush=True)
'''


def main():
    parser = argparse.ArgumentParser(description='Read-only export of Hermes Kanban cards with conservative redaction by default.')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT, help='destination report path (default: Windows Desktop)')
    parser.add_argument('--include-comments', action='store_true', help='include redacted comment bodies')
    parser.add_argument('--include-worker-errors', action='store_true', help='include redacted historical worker errors')
    parser.add_argument('--include-paths', action='store_true', help='include workspace and attachment paths')
    args = parser.parse_args()
    output_path = args.output.expanduser().resolve()
    print('[1/3] Checking validated Windows Desktop path...', flush=True)
    if not output_path.parent.is_dir():
        raise RuntimeError(f'Output directory unavailable: {output_path.parent}; no fallback path used.')
    if not shutil.which('docker'):
        raise RuntimeError('Docker CLI not found in this WSL shell.')

    print('[2/3] Exporting from Docker container hermes-agent (60-second timeout)...', flush=True)
    fd, staging = tempfile.mkstemp(prefix='.Hermes-Kanban-', suffix='.tmp', dir=output_path.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            try:
                result = subprocess.run(
                    ['docker', 'exec', '-i', '-u', 'hermes',
                     '-e', f'LV_KANBAN_INCLUDE_COMMENTS={int(args.include_comments)}',
                     '-e', f'LV_KANBAN_INCLUDE_RUN_ERRORS={int(args.include_worker_errors)}',
                     '-e', f'LV_KANBAN_INCLUDE_PATHS={int(args.include_paths)}',
                     'hermes-agent', 'python', '-'],
                    input=CONTAINER_SCRIPT.encode('utf-8'),
                    stdout=output, stderr=None, timeout=TIMEOUT_SECONDS, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(f'Docker export exceeded {TIMEOUT_SECONDS} seconds.') from exc
            if result.returncode != 0:
                raise RuntimeError(f'Docker export failed (exit {result.returncode}). See terminal error above.')
            output.flush()
            os.fsync(output.fileno())

        data = Path(staging).read_bytes()
        if b'EXPORT COMPLETE' not in data or b'HERMES KANBAN' not in data:
            raise RuntimeError('Missing completion marker in report; existing report preserved.')
        os.replace(staging, output_path)
        print('[3/3] SUCCESS — verified report saved:', output_path, flush=True)
        print(f'Size: {output_path.stat().st_size:,} bytes', flush=True)
    finally:
        try:
            Path(staging).unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('EXPORT FAILED:', exc, file=sys.stderr, flush=True)
        sys.exit(1)
