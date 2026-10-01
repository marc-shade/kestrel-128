#!/usr/bin/env python3
"""Start the Kestrel Claude host bridge; uses only its selected serial TCP link.

Example: python3 apps/claude/run.py --connect C128_ADDRESS:3000 --cwd PROJECT
The bridge never mounts disks, boots a client, resets a machine or changes
Ultimate settings. Launch Claude from the running Kestrel desktop.
"""
from pathlib import Path
import runpy
import sys

sys.dont_write_bytecode = True
if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).resolve().parent/'host/bridge.py'), run_name='__main__')
