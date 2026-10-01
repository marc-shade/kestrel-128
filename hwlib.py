"""Shared helpers for the hardware checks (hw_*) and the emulator tests.

Never hardcode addresses that move with the source: a label shifted by a few
bytes once made every script that had its literal report a false FAIL.
Resolve labels from the 64tass listings instead.
"""
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))


def lst_symbol(module, name):
    """Address of `name` in target/<module>.lst.

    Handles ordinary and relocated 64tass forms:
      ">1f31  bb bb   name: .byte"   data label with bytes on the line
      ".1f31           name:"         label alone (data on the next line)
      "=$1f31          name = *"      assignment-style label
      "=24385          name = base+1" decimal-valued address alias
      ".3e00  1300     name:"         file offset followed by runtime PC
    """
    path = os.path.join(ROOT, f"target/{module}.lst")
    lst = open(path, "rb").read().decode("latin-1", errors="replace")
    pats = (
        # Relocated sections have both a file offset and a runtime PC.
        # Prefer the PC; using the staging address silently observes old bytes.
        r"^[.>][0-9a-fA-F]{4}[ \t]+([0-9a-fA-F]{4})[ \t]+(?:(?:[0-9a-fA-F]{2} ?)+\s+)?%s:" % re.escape(name),
        r"^[.>]([0-9a-fA-F]{4})\s+(?:(?:[0-9a-fA-F]{2} ?)+\s+)?%s:" % re.escape(name),
        r"^=\$([0-9a-fA-F]{4})\s+%s\s*=" % re.escape(name),
    )
    for p in pats:
        m = re.search(p, lst, re.M)
        if m:
            return int(m.group(1), 16)
    m = re.search(r"^=([0-9]+)\s+%s\s*=" % re.escape(name), lst, re.M)
    if m and 0 <= int(m.group(1)) <= 65535:
        return int(m.group(1))
    raise SystemExit(f"FAIL: {name} not found in {module} listing ({path})")
