#!/usr/bin/env python3
"""Build the standalone ABI 1.7 example without changing native system images."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
import native_image
import native_module


def build(output):
    output = Path(output).resolve()
    native_target = ROOT / 'target/native'
    if output == native_target or native_target in output.parents:
        raise ValueError('choose a separate example output directory')
    output.mkdir(parents=True, exist_ok=True)
    images = {}
    with tempfile.TemporaryDirectory(prefix='assemble-', dir=output) as scratch:
        for name in ('parent', 'counter'):
            raw = Path(scratch) / (name + '.prg')
            subprocess.run([
                '64tass', '-a', '-I', str(ROOT / 'src/native'), '-I', str(HERE),
                '--labels=' + str(output / (name + '.sym')),
                '--list=' + str(output / (name + '.lst')),
                '-o', str(raw), str(HERE / (name + '.asm')),
            ], check=True, capture_output=True, text=True)
            images[name] = raw.read_bytes()
    parent = native_image.seal(images['parent'])
    module = native_module.seal(images['counter'], parent)
    report = dict(
        abi='1.7', parent=native_image.validate(parent),
        module=native_module.validate(module, parent), images={},
    )
    for name, image in (('MODULEDEMO.PRG', parent), ('COUNTER.PRG', module)):
        (output / name).write_bytes(image)
        report['images'][name] = dict(bytes=len(image), sha256=hashlib.sha256(image).hexdigest())
    (output / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='separate directory for the two PRGs and listings')
    args = parser.parse_args()
    try:
        report = build(args.output)
    except subprocess.CalledProcessError as error:
        parser.exit(1, error.stdout + error.stderr)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
