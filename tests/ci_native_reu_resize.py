#!/usr/bin/env python3
"""Execute optional REU growth against independent interval and byte oracles."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import tempfile

from ci_native_reu import Arena, ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-reu-resize-'))
    subprocess.run(['64tass', '-a', '-B', '-D', 'RU_INCLUDE_RESIZE=1',
                    str(ROOT/'tests/fixtures/native-reu.asm'), '-o', str(work/'reu.prg'),
                    '-l', str(work/'reu.sym')], check=True, capture_output=True)
    image = (work/'reu.prg').read_bytes()
    symbols = {m[1]: int(m[2], 16) for m in re.finditer(
        r'^(\w+)\s*=\s*\$([a-fA-F0-9]+)$', (work/'reu.sym').read_text(), re.M)}
    report = dict(passed=False, physical_hardware_io=False, cases=[],
                  image_sha256=hashlib.sha256(image).hexdigest())

    def resize(a, token, pages, expected=0, owner=32):
        a.set('owner', owner)
        a.set('handle', token, 8)
        a.set('pages', pages, 2)
        records = symbols['ru_records']
        before = bytes(a.ram[records:records+256])
        transactions = len(a.bus.reu_transactions)
        a.call('resize', expected, flags=12)
        assert a.get('handle', 8) == token
        assert len(a.bus.reu_transactions) == transactions
        if expected:
            assert bytes(a.ram[records:records+256]) == before
        else:
            wanted = bytearray(before)
            at = ((token & 255)-1)*8
            wanted[at+3:at+5] = pages.to_bytes(2, 'little')
            assert bytes(a.ram[records:records+256]) == wanted

    def done(name, a, **extra):
        report['cases'].append(dict(name=name, calls=a.calls, **extra))
        print('PASS:', name, flush=True)

    try:
        for kib in (128, 256, 512, 1024, 2048, 4096, 8192, 16384):
            a = Arena(image, symbols, kib)
            original = bytes(a.bus.reu_ram)
            a.call('open')
            token, page = a.alloc(1)
            assert page == 0
            resize(a, token, 1)
            resize(a, token, kib//4)
            a.call('stats')
            assert a.get('available', 2) == 0 and a.get('slots') == 31
            for pages, error in ((0, 1), (kib//4-1, 1), (kib//4+1, 2), (65535, 2)):
                resize(a, token, pages, error)
            assert a.bus.reu_ram == original
            payload = bytes((i*43+7) & 255 for i in range(512))
            offset = len(original)-512
            a.ram[0x3a00:0x3c00] = payload
            a.transfer('write', token, offset, 512)
            wanted = bytearray(original)
            wanted[-512:] = payload
            assert a.bus.reu_ram == wanted
            a.ram[0x3a00:0x3c00] = bytes(512)
            a.transfer('read', token, offset, 512)
            assert a.ram[0x3a00:0x3c00] == payload
            a.free(token)
            resize(a, token, 1, 4)
            a.call('close')
            done(f'{kib} KiB: stable token, full-device growth, final-byte access and refusal integrity', a)

        a = Arena(image, symbols, 512)
        a.call('open')
        original = bytes(a.bus.reu_ram)
        first, _ = a.alloc(2, page=3)
        second, _ = a.alloc(3, page=8)
        third, _ = a.alloc(2, page=126)
        resize(a, first, 5)       # Ends exactly at the next allocation.
        resize(a, first, 6, 2)
        resize(a, second, 118)    # Ends exactly at the final allocation.
        resize(a, second, 119, 2)
        resize(a, third, 3, 2)
        resize(a, first, 5, 5, owner=33)
        resize(a, first ^ (1 << 8), 5, 4)
        resize(a, first ^ (1 << 32), 5, 4)
        a.free(second)
        resize(a, first, 123)
        resize(a, first, 124, 2)
        a.free(third)
        resize(a, first, 125)
        a.call('close', 1)
        assert a.bus.reu_ram == original
        done('adjacent extents, interior starts, 16-bit carry, owners and generations preserve all bytes', a)

        a = Arena(image, symbols, 1024)
        a.call('open')
        original = bytes(a.bus.reu_ram)
        rng, live = random.Random(78213), {}
        for _ in range(500):
            operation = rng.randrange(3) if live else 0
            if operation == 0:
                pages = rng.randrange(1, 24)
                fit = next((start for start in range(257-pages) if all(
                    start+pages <= old or old+count <= start for old, count in live.values())), None)
                error = 3 if len(live) == 32 else (2 if fit is None else 0)
                token, page = a.alloc(pages, expected=error)
                if not error:
                    assert page == fit
                    live[token] = (page, pages)
            else:
                token = rng.choice(list(live))
                if operation == 1:
                    a.free(token)
                    del live[token]
                    resize(a, token, 1, 4)
                else:
                    start, old = live[token]
                    pages = rng.randrange(0, 65)
                    fits = start+pages <= 256 and all(
                        other == token or start+pages <= at or at+count <= start
                        for other, (at, count) in live.items())
                    error = 1 if pages == 0 or pages < old else (0 if fits else 2)
                    resize(a, token, pages, error)
                    if not error:
                        live[token] = (start, pages)
            a.set('owner', 32)
            a.call('stats')
            assert a.get('available', 2) == 256-sum(count for _, count in live.values())
            assert a.get('slots') == 32-len(live)
        assert a.bus.reu_ram == original
        a.call('release')
        a.call('close')
        done('500 independent allocate/grow/free steps check non-overlap, failure atomicity and accounting', a)
        report['passed'] = True
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
