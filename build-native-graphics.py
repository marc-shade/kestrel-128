#!/usr/bin/env python3
"""Build the public drawing sources at a fixed address for CPU regression."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'target/native-graphics'


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    source = OUT/'graphics.asm'
    source.write_text('.include "../../src/native/api.inc"\n'
                      '* = $6000\n'
                      '.include "../../src/native/graphics/graphics-core.inc"\n'
                      '.include "../../src/native/graphics/text-core.inc"\n'
                      '.cerror * > $6c00, "graphics test allocation exceeded"\n')
    subprocess.run(['64tass', '-a', '-B', str(source), '-o', str(OUT/'graphics.prg'),
                    '-l', str(OUT/'graphics.sym'), '-L', str(OUT/'graphics.lst')], check=True)
    image = (OUT/'graphics.prg').read_bytes()
    result = dict(bytes=len(image), sha256=hashlib.sha256(image).hexdigest())
    (OUT/'images.json').write_text(json.dumps(result, indent=2)+'\n')
    print(f'Native graphics regression library: {OUT/"graphics.prg"}')


if __name__ == '__main__':
    build()
