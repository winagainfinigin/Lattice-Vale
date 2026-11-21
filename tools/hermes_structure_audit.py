#!/usr/bin/env python3
"""Read-only WSL + Docker Hermes structure audit. Standard library only."""
import glob
import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

_parser = argparse.ArgumentParser(description='Read-only WSL and Docker Hermes structure audit.')
_parser.add_argument('--output', type=Path, help='exact report path; default is the detected Desktop or WSL home')
_parser.add_argument('--include-all-profiles', action='store_true', help='search other Windows user profiles for an output folder')
_parser.add_argument('--include-paths', action='store_true', help='include full host/container paths and directory entry names in the report')
_args = _parser.parse_args()


def run(args, seconds=8, cwd=None):
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           encoding="utf-8", errors="replace", timeout=seconds, cwd=cwd)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"Timed out after {seconds} seconds"
    except OSError as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"


candidates = [str(_args.output.expanduser().resolve().parent)] if _args.output else []
if os.environ.get("HERMES_AUDIT_OUTDIR"):
    candidates.append(os.environ["HERMES_AUDIT_OUTDIR"])

# Ask Windows for its real Desktop, including OneDrive redirection. This is optional.
code, win, problem = run(
    ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
     "[Console]::Write([Environment]::GetFolderPath('Desktop'))"],
    seconds=6, cwd="/mnt/c" if Path("/mnt/c").is_dir() else None)
if code == 0 and win:
    rc, linux_path, _ = run(["wslpath", "-u", win.splitlines()[-1].strip()], seconds=3)
    if rc == 0 and linux_path:
        candidates.append(linux_path)

# Interop can be disabled. Probe only plausible Windows profiles, not the whole drive.
profile_names = list(dict.fromkeys([os.environ.get("USER", "")]))
for drive in ("c", "d"):
    for username in profile_names:
        if not username:
            continue
        for pattern in (f"/mnt/{drive}/Users/{username}/Desktop",
                        f"/mnt/{drive}/Users/{username}/OneDrive*/Desktop"):
            candidates.extend(glob.glob(pattern))
# Profile names may differ from the WSL username; ignore public/system profiles.
if _args.include_all_profiles:
    for drive in ("c", "d"):
        for profile in glob.glob(f"/mnt/{drive}/Users/*"):
            if Path(profile).name.lower() in {"public", "default", "default user", "all users"}:
                continue
            for pattern in (profile + "/Desktop", profile + "/OneDrive*/Desktop"):
                candidates.extend(glob.glob(pattern))
# If no Windows Desktop is accessible, Downloads is still uploadable.
for drive in ("c", "d"):
    for username in profile_names:
        if username:
            candidates.extend(glob.glob(f"/mnt/{drive}/Users/{username}/Downloads"))
    if _args.include_all_profiles:
        for profile in glob.glob(f"/mnt/{drive}/Users/*"):
            if Path(profile).name.lower() not in {"public", "default", "default user", "all users"}:
                candidates.extend(glob.glob(profile + "/Downloads"))
candidates.append(str(Path.home()))

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
output = None
output_folders = [str(_args.output.expanduser().resolve().parent)] if _args.output else list(dict.fromkeys(candidates))
for folder in output_folders:
    if not Path(folder).is_dir():
        continue
    proposed = (_args.output.expanduser().resolve() if _args.output else
                Path(folder) / f"Hermes-Structure-Audit-{stamp}.txt")
    try:
        log = proposed.open("x", encoding="utf-8")
        output = proposed
        break
    except OSError:
        continue
if output is None:
    raise SystemExit("ERROR: Could not create an audit file on Windows or in WSL home.")


def emit(line=""):
    line = str(line)
    print(line, flush=True)
    safe = line
    if not _args.include_paths:
        safe = re.sub(r"(?i)([A-Z]:\\Users\\)[^\\\s]+", r"\1[USER]", safe)
        safe = re.sub(r"(?i)(/mnt/[cd]/Users/)[^/\s]+", r"\1[USER]", safe)
        safe = re.sub(r"/home/[^/\s]+", "/home/[USER]", safe)
        safe = re.sub(r"(?<=Report created immediately at: ).*", "[selected output location]", safe)
        safe = re.sub(r"(?<=AUDIT FINISHED. File exists at: ).*", "[selected output location]", safe)
    log.write(safe + "\n")
    log.flush()


CONTAINER_CODE = r'''
import os, sqlite3, itertools
from pathlib import Path
from urllib.parse import quote
SHOW_PATHS = os.environ.get('LV_AUDIT_INCLUDE_PATHS') == '1'
print("CONTAINER USER ID:", os.getuid(), flush=True)
for key in ("HOME", "HERMES_HOME", "HERMES_KANBAN_HOME", "HERMES_KANBAN_DB", "HERMES_KANBAN_BOARD"):
    print("ENV", key, "=", os.environ.get(key, "(unset)"), flush=True)
roots = [Path('/opt/data'), Path('/home/hermes/.hermes')]
try:
    from hermes_constants import get_default_hermes_root
    roots.insert(0, Path(get_default_hermes_root()))
except Exception as exc:
    print('Hermes root resolver:', type(exc).__name__, str(exc), flush=True)
for name in ('HERMES_KANBAN_HOME','HERMES_HOME'):
    if os.environ.get(name):
        roots.insert(0, Path(os.environ[name]).expanduser())
roots = list(dict.fromkeys(roots))
dbs = {}
for root in roots:
    print('\nROOT', (root if SHOW_PATHS else '[redacted]'), 'exists=', root.is_dir(), flush=True)
    if not root.is_dir(): continue
    for rel in ('.','kanban','kanban/boards','kanban/workspaces','kanban/attachments','profiles'):
        folder = root / rel
        if not folder.is_dir(): continue
        try:
            with os.scandir(folder) as it:
                names = [e.name + ('/' if e.is_dir(follow_symlinks=False) else '') for e in itertools.islice(it, 31)]
            listing = ', '.join(names[:30]) if SHOW_PATHS else f'{len(names)} names omitted'
            print('DIR', (folder if SHOW_PATHS else '[redacted]'), 'ENTRIES(first 30):', listing, ('[more]' if len(names)>30 else ''), flush=True)
        except OSError as exc:
            print('DIR ERROR', folder, str(exc), flush=True)
    for db in [root/'kanban.db', *sorted((root/'kanban/boards').glob('*/kanban.db')),
               *sorted((root/'kanban/boards/_archived').glob('*/kanban.db'))]:
        if db.is_file(): dbs[str(db.resolve())] = db
if os.environ.get('HERMES_KANBAN_DB'):
    db = Path(os.environ['HERMES_KANBAN_DB'])
    if db.is_file(): dbs[str(db.resolve())] = db
print('\nKANBAN DATABASES FOUND:', len(dbs), flush=True)
for db in dbs.values():
    print('DATABASE:', (db if SHOW_PATHS else '[redacted]'), flush=True)
    try:
        conn = sqlite3.connect('file:'+quote(str(db),safe='/')+'?mode=ro',uri=True,timeout=0.5)
        conn.execute('PRAGMA query_only=ON')
        conn.execute('PRAGMA busy_timeout=500')
        for name in ('tasks','task_runs','task_comments','task_links','task_attachments'):
            cols = [r[1] for r in conn.execute('PRAGMA table_info("'+name+'")')]
            if cols:
                count = conn.execute('SELECT COUNT(*) FROM "'+name+'"').fetchone()[0]
                print(' TABLE',name,'ROWS',count,'COLUMNS',','.join(cols),flush=True)
            else:
                print(' TABLE',name,'MISSING',flush=True)
        conn.close()
    except Exception as exc:
        print(' DATABASE ERROR:', type(exc).__name__, str(exc), flush=True)
'''

try:
    emit("HERMES / LATTICEVALE STRUCTURE AUDIT")
    emit(f"Report created immediately at: {output}")
    emit(f"Generated: {datetime.now().isoformat()}")
    if not str(output).startswith('/mnt/'):
        emit("WARNING: Windows folders were not accessible; report saved in WSL home.")
        rc, winpath, _ = run(["wslpath", "-w", str(output)], seconds=3)
        if rc == 0:
            emit("Windows Explorer path: " + winpath)
    elif output.parent.name.lower() == "downloads":
        emit("NOTE: Desktop inaccessible; report saved in a Windows Downloads folder instead.")
    emit(f"PowerShell Desktop lookup: exit={code}, result={win!r}, error={problem!r}")
    emit(f"WSL user/home: {os.environ.get('USER')}/{Path.home()}")
    emit(f"WSL current directory: {Path.cwd()}")
    emit("\n[1/3] WSL folder structure")
    for root in (Path.home()/"hermes-stack", Path.home()/"hermes-stack/data/hermes"):
        emit(f"{root}: exists={root.exists()} directory={root.is_dir()}")
        if root.is_dir():
            try:
                with os.scandir(root) as entries:
                    import itertools
                    names = [e.name + ('/' if e.is_dir(follow_symlinks=False) else '') for e in itertools.islice(entries, 41)]
                emit("  Entries (first 40): " + ', '.join(names[:40]) + (' [more]' if len(names)>40 else ''))
            except OSError as exc:
                emit(f"  Directory error: {exc}")
    emit("\n[2/3] Docker container metadata (max 10 seconds)")
    if not shutil.which('docker'):
        emit('Docker CLI missing from WSL PATH.')
    else:
        rc, stdout, stderr = run(['docker', 'inspect', 'hermes-agent'], seconds=10)
        emit(f"docker inspect exit={rc}" + (f"; error={stderr}" if stderr else ''))
        if rc == 0:
            try:
                obj = json.loads(stdout)[0]
                emit(f"Container: {obj.get('Name')} image={obj.get('Config',{}).get('Image')}")
                emit(f"State: {obj.get('State',{}).get('Status')}")
                for m in obj.get('Mounts',[]):
                    emit(f"MOUNT {m.get('Type')}: {m.get('Source')} -> {m.get('Destination')} (RW={m.get('RW')})")
            except (ValueError, IndexError, KeyError) as exc:
                emit(f"Docker inspect parsing error: {exc}")
        emit("\n[3/3] Filesystem and Kanban schema INSIDE Docker (max 25 seconds)")
        rc, stdout, stderr = run(
            ['docker', 'exec', '-u', 'hermes', '-e', f"LV_AUDIT_INCLUDE_PATHS={int(_args.include_paths)}", 'hermes-agent', 'python', '-c', CONTAINER_CODE], seconds=25)
        emit(f"docker exec exit={rc}" + (f"; error={stderr}" if stderr else ''))
        emit(stdout if stdout else '(no container output)')
    emit("\nAUDIT FINISHED. File exists at: " + str(output))
finally:
    log.close()
