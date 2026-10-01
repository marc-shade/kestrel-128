#!/usr/bin/env python3
"""Run selected emulator suites, preserving logs and exact build hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SUITES = {
    "native": ["ci_native.py"],
    "nativedesktop": ["ci_native_desktop_iec.py", "--desktop-boot", "--running-layout"],
    "nativedesktopworkspace": ["ci_native_desktop_iec.py"],
    "nativedesktop80": ["ci_native_desktop_iec.py", "--desktop-boot", "--80col"],
    "nativeclaude": ["ci_native_claude_iec.py"],
    "nativeclaudehostexit": ["ci_native_claude_iec.py", "--host-exit", "--80col"],
    "nativedesktopmissingapp": ["ci_native_desktop_iec.py", "--desktop-boot", "--missing-calc"],
    "nativedesktopmissing": ["ci_native_desktop_iec.py", "--desktop-boot", "--missing-desktop"],
    "nativedesktopsequence": ["ci_native_desktop_iec.py", "--desktop-boot", "--hardware-sequence"],
    "nativecapturetransport": ["ci_native_desktop_iec.py", "--desktop-boot", "--transport-sequence"],
    "nativecapturenested": ["ci_native_desktop_iec.py", "--desktop-boot", "--nested-irq"],
    "nativecaptureinput": ["ci_native_desktop_iec.py", "--desktop-boot", "--input-during-capture"],
    "nativefiles": ["ci_native_files_iec.py"],
    "nativefiles71": ["ci_native_files_iec.py", "--format", "d71"],
    "nativefiles81": ["ci_native_files_iec.py", "--format", "d81"],
    "nativebrowse": ["ci_native_browser_iec.py"],
    "nativebrowse71": ["ci_native_browser_iec.py", "--format", "d71"],
    "nativebrowse81": ["ci_native_browser_iec.py", "--format", "d81"],
    "nativeeditor": ["ci_native_editor_iec.py"],
    "nativeeditor71": ["ci_native_editor_iec.py", "--format", "d71"],
    "nativeeditor81": ["ci_native_editor_iec.py", "--format", "d81"],
    "nativeeditorsearch": ["ci_native_editor_iec.py", "--format", "d81", "--search"],
    "nativepointer": ["ci_native_pointer_iec.py"],
    "nativepointer80": ["ci_native_pointer_iec.py", "--80col"],
    "nativefilescopy": ["ci_native_files_copy_iec.py"],
}


def build_hashes():
    files = sorted((ROOT / "target/native").glob("*.prg"))
    files += sorted((ROOT / "target/native").glob("*.d64"))
    files += sorted((ROOT / "target/native-desktop").glob("*.prg"))
    files += sorted((ROOT / "target/native-desktop").glob("*.d64"))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("suites", choices=list(SUITES), nargs="+")
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="kestrel-regressions-"))
    report = {"build": build_hashes(), "suites": {}}
    print(f"Regression evidence: {work}", flush=True)
    for suite in args.suites:
        entry, *extra = SUITES[suite]
        print(f"Running {suite}", flush=True)
        with (work / f"{suite}.log").open("w") as log:
            process = subprocess.Popen(
                [sys.executable, "-u", str(ROOT / "tests" / entry), *extra],
                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            try:
                for line in process.stdout:
                    log.write(line)
                    log.flush()
                    print(line, end="", flush=True)
                code = process.wait()
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait()
        report["suites"][suite] = {"exit_code": code}
        assert report["build"] == build_hashes(), "Build changed during regression"
        (work / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        if code:
            return code
    print(f"PASS: {len(args.suites)} suites; evidence at {work}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
