#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT.parent
PS_FILES = sorted((p for p in RELEASE_ROOT.rglob('*.ps1') if '.git' not in p.parts), key=lambda p: p.relative_to(RELEASE_ROOT).as_posix().lower())
assert PS_FILES, 'no shipped PowerShell files found'
assert any(p.name == 'Finalize-LatticeVale-OverwritePatch.ps1' for p in PS_FILES), 'overwrite-patch finalizer is missing from shipped PowerShell audit coverage'

# Microsoft documents these as PowerShell automatic variables. Most are engine-maintained
# and should not be written by user code; a subset are actually ReadOnly/Constant.
POWERSHELL_AUTOMATIC = {
    'args','consolefilename','enabledexperimentalfeatures','error','event','eventargs',
    'eventsubscriber','executioncontext','false','foreach','home','host','input','iscoreclr',
    'islinux','ismacos','iswindows','lastexitcode','matches','myinvocation','nestedpromptlevel',
    'null','pid','profile','psboundparameters','pscmdlet','pscommandpath','psculture',
    'psdebugcontext','psedition','pshome','psitem','psscriptroot','pssenderinfo','psuiculture',
    'psversiontable','pwd','sender','shellid','stacktrace','switch','this','true','psstyle',
}

# These are known hard-fail ReadOnly/Constant session variables in current PowerShell.
POWERSHELL_HARD_PROTECTED = {
    'enabledexperimentalfeatures','error','executioncontext','false','home','host','iscoreclr',
    'islinux','ismacos','iswindows','pid','psculture','psedition','pshome','psstyle',
    'psuiculture','psversiontable','shellid','true',
}


def strip_ps_literals(text: str) -> str:
    # Preserve newlines/offsets while removing comments and quoted/here-string contents.
    out = list(text)

    def blank(a: int, b: int) -> None:
        for i in range(a, b):
            if out[i] != '\n':
                out[i] = ' '

    # Here-strings first. PowerShell terminators must begin on their own line.
    for pat in (r"@'[^\n]*\n(?s:.*?)^[ \t]*'@[ \t]*$", r'@"[^\n]*\n(?s:.*?)^[ \t]*"@[ \t]*$'):
        for m in list(re.finditer(pat, text, flags=re.M)):
            blank(m.start(), m.end())

    i = 0
    state = 'normal'
    while i < len(text):
        if out[i] == ' ' and text[i] != ' ':
            i += 1
            continue
        ch = text[i]
        if state == 'normal':
            if ch == '#':
                j = text.find('\n', i)
                if j < 0:
                    j = len(text)
                blank(i, j)
                i = j
                continue
            if ch == "'":
                state = 'single'; out[i] = ' '; i += 1; continue
            if ch == '"':
                state = 'double'; out[i] = ' '; i += 1; continue
            i += 1
            continue
        if state == 'single':
            out[i] = '\n' if ch == '\n' else ' '
            if ch == "'":
                if i + 1 < len(text) and text[i + 1] == "'":
                    out[i + 1] = ' '; i += 2; continue
                state = 'normal'
            i += 1
            continue
        if state == 'double':
            out[i] = '\n' if ch == '\n' else ' '
            if ch == '`' and i + 1 < len(text):
                if text[i + 1] != '\n':
                    out[i + 1] = ' '
                i += 2; continue
            if ch == '"':
                state = 'normal'
            i += 1
            continue
    return ''.join(out)


def line_of(text: str, pos: int) -> int:
    return text.count('\n', 0, pos) + 1


def balanced_parens(text: str, open_pos: int) -> tuple[str, int]:
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return text[open_pos + 1:i], i
    raise AssertionError(f'unbalanced parameter list starting line {line_of(text, open_pos)}')


def split_top_level_commas(s: str) -> list[str]:
    parts, start = [], 0
    p = b = c = 0
    for i, ch in enumerate(s):
        if ch == '(':
            p += 1
        elif ch == ')':
            p -= 1
        elif ch == '[':
            b += 1
        elif ch == ']':
            b -= 1
        elif ch == '{':
            c += 1
        elif ch == '}':
            c -= 1
        elif ch == ',' and p == 0 and b == 0 and c == 0:
            parts.append(s[start:i]); start = i + 1
    parts.append(s[start:])
    return parts


def audit_powershell_file(path: Path) -> list[str]:
    raw = path.read_text(encoding='utf-8')
    clean = strip_ps_literals(raw)
    errors: list[str] = []
    label = path.relative_to(RELEASE_ROOT).as_posix()

    # Direct writes such as $HOME=, $args+=, ++$PID, $Matches--.
    assign = re.compile(r'\$([A-Za-z_][A-Za-z0-9_]*)\s*(\+\+|--|\+=|-=|\*=|/=|%=|=)', re.I)
    for m in assign.finditer(clean):
        name = m.group(1)
        if name.lower() in POWERSHELL_AUTOMATIC:
            errors.append(f'PowerShell automatic/protected variable write in {label}:{line_of(clean,m.start())}: ${name} {m.group(2)}')

    prefix = re.compile(r'(\+\+|--)\s*\$([A-Za-z_][A-Za-z0-9_]*)', re.I)
    for m in prefix.finditer(clean):
        name = m.group(2)
        if name.lower() in POWERSHELL_AUTOMATIC:
            errors.append(f'PowerShell automatic/protected variable write in {label}:{line_of(clean,m.start())}: {m.group(1)}${name}')

    # foreach loop variables are writes too.
    for m in re.finditer(r'\bforeach\s*\(\s*\$([A-Za-z_][A-Za-z0-9_]*)\s+in\b', clean, re.I):
        name = m.group(1)
        if name.lower() in POWERSHELL_AUTOMATIC:
            errors.append(f'PowerShell automatic/protected foreach target in {label}:{line_of(clean,m.start())}: ${name}')

    # Parameter binding writes parameter variables. Inspect top-level param() and each function signature.
    starts: list[int] = []
    top = re.search(r'(?m)^\s*param\s*\(', clean, re.I)
    if top:
        starts.append(clean.find('(', top.start(), top.end()))
    for m in re.finditer(r'\bfunction\s+[^\s({]+\s*\(', clean, re.I):
        starts.append(clean.find('(', m.start(), m.end()))
    for open_pos in starts:
        body, _ = balanced_parens(clean, open_pos)
        body_start = open_pos + 1
        offset = 0
        for segment in split_top_level_commas(body):
            # Parameter attributes/types can themselves contain variables such as
            # [Parameter(Mandatory=$true)]. The actual bound parameter is the first
            # variable after the final attribute/type closing bracket.
            tail_start = segment.rfind(']') + 1
            tail = segment[tail_start:]
            vm = re.search(r'\$([A-Za-z_][A-Za-z0-9_]*)', tail)
            if vm:
                name = vm.group(1)
                if name.lower() in POWERSHELL_AUTOMATIC:
                    pos = body_start + offset + tail_start + vm.start()
                    errors.append(f'PowerShell automatic/protected parameter in {label}:{line_of(clean,pos)}: ${name}')
            offset += len(segment) + 1

    # Explicit variable-provider mutation should not target protected variables either.
    for m in re.finditer(r'\b(?:Set|New|Clear|Remove)-Variable\b[^\n;]*?(?:-Name\s+)?[\'\"]?([A-Za-z_][A-Za-z0-9_]*)', clean, re.I):
        name = m.group(1)
        if name.lower() in POWERSHELL_HARD_PROTECTED:
            errors.append(f'PowerShell protected variable-provider mutation in {label}:{line_of(clean,m.start())}: {name}')

    return errors


def bash_readonly_names() -> set[str]:
    r = subprocess.run(['bash','--noprofile','--norc','-c','readonly -p'], capture_output=True, text=True, check=True)
    names: set[str] = set()
    for line in r.stdout.splitlines():
        m = re.match(r'declare\s+-[^ ]*r[^ ]*\s+([A-Za-z_][A-Za-z0-9_]*)=', line)
        if m:
            names.add(m.group(1))
    return names


def audit_bash() -> list[str]:
    readonly = bash_readonly_names()
    errors: list[str] = []
    for rel in ('linux/bootstrap.sh','stack/configure-stack.sh','stack/manage.sh','stack/qmd-index-cycle.sh'):
        path = ROOT / rel
        text = path.read_text(encoding='utf-8')
        # Hard runtime failures appear when assigning a readonly shell variable as an actual shell assignment.
        # Match command-position assignments and local/export/declare/readonly assignment declarations.
        for i, line in enumerate(text.splitlines(), 1):
            code = line.split('#',1)[0]
            for name in readonly:
                pats = (
                    rf'^\s*{re.escape(name)}\s*=',
                    rf'^\s*(?:local|export|readonly)\s+[^#\n]*\b{re.escape(name)}\s*=',
                    rf'^\s*declare\s+[^#\n]*\b{re.escape(name)}\s*=',
                    rf'[;]\s*{re.escape(name)}\s*=',
                )
                if any(re.search(p, code) for p in pats):
                    errors.append(f'Bash readonly variable assignment in {rel}:{i}: {name}')
    return errors


errors = []
for ps_path in PS_FILES:
    errors.extend(audit_powershell_file(ps_path))
errors += audit_bash()
if errors:
    print('RUNTIME VARIABLE SAFETY: FAIL')
    for e in errors:
        print('-', e)
    raise SystemExit(1)

print('RUNTIME VARIABLE SAFETY: PASS')
print('No writes/parameter bindings to PowerShell automatic/protected names.')
print('No assignments to Bash runtime read-only variables.')
