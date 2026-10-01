#!/usr/bin/env python3
"""Build the separate bank-0 NAPP and bank-1 provider without changing system media."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT))
import native_image
import native_banked


def build(output):
    output = Path(output).resolve()
    target = ROOT/'target'
    if output == target or target in output.parents:
        raise ValueError('choose a separate example output directory')
    output.mkdir(parents=True,exist_ok=True)
    report = dict(abi='1.12',images={})
    with tempfile.TemporaryDirectory(prefix='assemble-',dir=output) as scratch:
        for name,dest,module in (('parent','BANKDEMO.PRG',native_image),
                                 ('provider','BKREU.PRG',native_banked)):
            raw = Path(scratch)/(name+'.prg')
            subprocess.run(['64tass','-a','-B','-I',str(ROOT/'src/native'),
                            '--labels='+str(output/(name+'.sym')),
                            '--list='+str(output/(name+'.lst')),
                            '-o',str(raw),str(HERE/(name+'.asm'))],check=True,capture_output=True,text=True)
            image = module.seal(raw.read_bytes())
            (output/dest).write_bytes(image)
            report['images'][dest] = dict(module.validate(image),sha256=hashlib.sha256(image).hexdigest())
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
