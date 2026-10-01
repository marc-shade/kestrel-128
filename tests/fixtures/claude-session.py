#!/usr/bin/env python3
"""Deterministic PTY peer for the native serial test; no AI service requests."""
import os
from pathlib import Path
import select
import sys
import tty

tty.setraw(0)
control=Path(sys.argv[1]) if len(sys.argv)>1 else None
os.write(1, '\x1b[2J\x1b[HKESTREL CLAUDE LINK READY\r\n'
            '\x1b[38;2;215;119;87m❯ ✳ ⏺\x1b[0m\r\n'
            'Keyboard, glyphs and return test'.encode())
while True:
    if control is not None and control.exists():
        assert control.read_text()=='update\n'
        control.unlink()
        os.write(1,'\x1b[25;78HX❯Y'.encode())
    if not select.select([0],[],[],.05)[0]:continue
    key = os.read(0, 1)
    if not key:break
    if key == b'p': os.write(1, b'\x1b[4;1HKEY RECEIVED: p')
    elif key == b'\x1b': os.write(1, b'\x1b[5;1HESCAPE RECEIVED')
    elif key == b'q':
        os.write(1, b'\x1b[6;1HHOST SESSION CLOSED')
        break
