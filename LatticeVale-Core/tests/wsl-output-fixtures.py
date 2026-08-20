#!/usr/bin/env python3
from __future__ import annotations
import re

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

def normalize(text: str) -> str:
    return ANSI_RE.sub("", text.replace("\x00", "").replace("\ufeff", ""))

def parse_version(text: str, name: str) -> int | None:
    escaped = re.escape(name)
    rx = re.compile(rf"^\*?\s*{escaped}(?:\s+.*?)?\s+([12])\s*$")
    for line in normalize(text).splitlines():
        m = rx.match(line.strip())
        if m:
            return int(m.group(1))
    return None

normal = """  NAME            STATE           VERSION\n* Ubuntu-24.04    Stopped         2\n  Debian          Running         1\n"""
assert parse_version(normal, "Ubuntu-24.04") == 2
assert parse_version(normal, "Debian") == 1
assert parse_version(normal, "Ubuntu") is None

nul = "".join(ch + "\x00" for ch in normal)
assert parse_version(nul, "Ubuntu-24.04") == 2
assert parse_version(nul, "Debian") == 1

localized = """  NAME            ESTADO          VERSIÓN\n* Ubuntu-24.04    Detenido        2\n"""
assert parse_version(localized, "Ubuntu-24.04") == 2

bom_ansi = "\ufeff\x1b[0m* Ubuntu-24.04    Running    2\x1b[0m\n"
assert parse_version(bom_ansi, "Ubuntu-24.04") == 2

print("WSL OUTPUT FIXTURES: PASS")
