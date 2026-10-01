#!/usr/bin/env python3
"""Build the AES demo NAPP and the persistent bank-1 AESVC component."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT))
import native_image
import native_banked

AE_BASE = int(re.search(r'^AE_BASE = \$([0-9a-f]{4})', (ROOT/'src/native/aes-api.inc').read_text(), re.M).group(1), 16)


def build(output):
    output = Path(output).resolve()
    target = ROOT/'target'
    if output == target or target in output.parents:
        raise ValueError('choose a separate example output directory')
    output.mkdir(parents=True,exist_ok=True)
    report = dict(abi='1.14',images={})
    with tempfile.TemporaryDirectory(prefix='assemble-',dir=output) as scratch:
        for name,source,dest in (('parent',HERE/'parent.asm','AESDEMO.PRG'),
                                 ('aesvc',ROOT/'src/native/aesvc.asm','AESVC.PRG')):
            raw = Path(scratch)/(name+'.prg')
            subprocess.run(['64tass','-a','-B','-I',str(ROOT/'src/native'),
                            '--labels='+str(output/(name+'.sym')),
                            '--list='+str(output/(name+'.lst')),
                            '-o',str(raw),str(source)],check=True,capture_output=True,text=True)
            if name == 'aesvc':
                image = native_banked.seal(raw.read_bytes(),base=AE_BASE)
                info = native_banked.validate(image,base=AE_BASE)
            else:
                image = native_image.seal(raw.read_bytes())
                info = native_image.validate(image)
            (output/dest).write_bytes(image)
            report['images'][dest] = dict(info,sha256=hashlib.sha256(image).hexdigest())
    (output/'build.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.output),indent=2))
    except subprocess.CalledProcessError as error:
        parser.exit(1,error.stdout+error.stderr)
    except (OSError,ValueError) as error:
        parser.exit(1,str(error)+'\n')
