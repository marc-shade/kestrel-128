#!/usr/bin/env python3
"""Measurement-only build that times every 80-column desktop pointer update.

Never shipped. build() copies src/native into a work folder, replaces code at five
places in the desktop and two in the bank-1 VDC service with code of the
same length (every shipped label keeps its address), appends
probes/pointer-timing-desktop.inc and probes/pointer-timing-service.inc, and
assembles, seals and packs both exactly like build-native-desktop.py. The
result is a copy of target/native-desktop/kestrel.d64 whose `browse` and
`vdsvc.prg` are the instrumented ones. The shipped disk has almost no free
blocks, so the copy also drops `shcalc.prg`, a Sheet module the timed desktop
never loads. Nothing is written under target/.

Before the instrumented build, the same procedure assembles the unpatched
copy and must reproduce target/native-desktop/desktop.prg and vdsvc.prg byte
for byte, so the patches are the only difference.

On the C128 the instrumented desktop waits for key PT_KEY ("T"), drives the
pointer itself (no physical mouse motion: synthetic 1351 counters into the
shipped pm_poll/pm_delta path) from (160,160) along y=160 to x=308, up to
y=20, then over empty desktop space with dx +5/-5 and dy 3 (turning at
y=20 and y=179), and records PT_UPDATES updates timed with CIA2 timer B.
pointer-timing-desktop.inc explains the segments and the arithmetic.

  python3 native_pointer_timing.py --out DIR
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
SHIPPED = ROOT/'target/native-desktop'
FRAME_CYCLES = 17045          # one 60 Hz jiffy at the C128's 1.0227 MHz
COUNT = 512                   # PT_UPDATES
KEY = 0x54                    # PT_KEY
HEADER_BYTES = 35
ARRAYS = ('pre_lo', 'pre_hi', 'svc_lo', 'svc_hi', 'post_lo', 'post_hi', 'jif', 'irq')
HOOK_EXTRA = 12               # JSR pt_bp_shipped and the service hook's RTS
START, ORIGIN, Y_MAX = (160, 160), (308, 20), 179

DESKTOP = 'desktop.asm'
SERVICE = 'vdc-service.asm'
# (file under src/native, shipped text, measurement text). Each shipped text
# must occur exactly once; every replacement keeps the instruction length.
PATCHES = (
    (DESKTOP, '        jsr pm_install\n', '        jsr pt_pm_install     ; measurement build\n'),
    (DESKTOP, '        jsr N_KEYIN\n', '        jsr pt_keyin          ; measurement build\n'),
    (DESKTOP, '.include "desktop/vdc-scene.inc"\ngd_end:\n',
     '.include "desktop/vdc-scene.inc"\n.include "pointer-timing-desktop.inc"\ngd_end:\n'),
    ('input/pointer.inc', '        lda $d419\n', '        jsr pt_pot_x          ; measurement build: synthetic counters\n'),
    ('input/pointer.inc', '        lda $d41a\n', '        lda pt_pots+1         ; measurement build\n'),
    ('graphics/vdc-client.inc', 'bp_pointer:\n        jsr bp_arguments\n        lda #3\n        jmp bp_invoke\n',
     'bp_pointer:\n        jmp pt_bp_pointer     ; measurement build: the timed copy\n'
     '        .fill 5,$ea           ; never run; keeps every later shipped address\n'),
    (SERVICE, 'bv_pointer:\n        jsr vd_poll\n', 'bv_pointer:\n        jsr pt_svc_poll       ; measurement build\n'),
    (SERVICE, 'bv_open:\n        jmp bv_scene_open\n', 'bv_open:\n        jmp pt_svc_open       ; measurement build\n'),
    (SERVICE, '\nbv_end:\n', '\n.include "pointer-timing-service.inc"\nbv_end:\n'),
)
INCLUDES = ('pointer-timing-desktop.inc', 'pointer-timing-service.inc')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def symbols(path):
    """name -> value from a 64tass -l label file."""
    found = {}
    for line in Path(path).read_text().splitlines():
        match = re.fullmatch(r'(\S+?)\s*=\s*(\$[0-9a-fA-F]+|\d+)\s*', line)
        if match:
            text = match[2]
            found[match[1]] = int(text[1:], 16) if text[0] == '$' else int(text)
    return found


def assemble(source, out, name):
    result = subprocess.run(['64tass', '-a', '-B', str(source), '-o', str(out/f'{name}.prg'),
                             '-l', str(out/f'{name}.sym'), '-L', str(out/f'{name}.lst')], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'64tass failed on {source.name}:\n{result.stdout}{result.stderr}')


def build_tree(tree, out):
    """Assemble, seal and pack desktop and vdsvc from tree (a src/native copy)
    as build-native-desktop.py does; returns {name: bytes}."""
    from native_image import seal, validate
    from native_banked import seal as seal_banked, validate as validate_banked
    from native_app_pack import build as pack_app
    out.mkdir(parents=True, exist_ok=True)
    assemble(tree/DESKTOP, out, 'desktop-raw')
    raw = seal((out/'desktop-raw.prg').read_bytes())
    validate(raw)
    (out/'desktop-raw.prg').write_bytes(raw)
    desktop = pack_app(raw, listing=out/'desktop-pack.lst', symbols=out/'desktop-pack.sym')
    (out/'desktop.prg').write_bytes(desktop)
    assemble(tree/SERVICE, out, 'vdsvc')
    service = seal_banked((out/'vdsvc.prg').read_bytes())
    info = validate_banked(service)
    ae_base = int(re.search(r'^AE_BASE = \$([0-9a-f]{4})', (tree/'aes-api.inc').read_text(), re.M).group(1), 16)
    assert 0x60+info['pages'] <= ae_base >> 8, 'instrumented VDSVC overlaps the AES'
    (out/'vdsvc.prg').write_bytes(service)
    return dict(desktop=desktop, vdsvc=service)


def patch(tree):
    applied = []
    for name, shipped, measured in PATCHES:
        path = tree/name
        text = path.read_text()
        assert text.count(shipped) == 1, (name, 'anchor must occur once', shipped)
        path.write_text(text.replace(shipped, measured))
        applied.append(dict(file='src/native/'+name, shipped=shipped, measurement=measured))
    for name in INCLUDES:
        shutil.copyfile(ROOT/'probes'/name, tree/name)
    return applied


UNUSED_MODULE = 'shcalc.prg'   # room for the larger instrumented images


def build(out):
    """Build the instrumented images into out (not under target/); returns the manifest."""
    out = Path(out).resolve()
    assert not out.is_relative_to(ROOT/'target'), 'the measurement build never writes target/'
    out.mkdir(parents=True, exist_ok=True)
    shipped = {name: (SHIPPED/f'{name}.prg').read_bytes() for name in ('desktop', 'vdsvc')}
    shipped_disk = (SHIPPED/'kestrel.d64').read_bytes()
    with tempfile.TemporaryDirectory(prefix='kestrel-pointer-timing-') as temporary:
        temporary = Path(temporary)
        control_tree = temporary/'control/native'
        shutil.copytree(ROOT/'src/native', control_tree)
        control = build_tree(control_tree, out/'control')
        for name, data in control.items():
            assert data == shipped[name], f'the unpatched copy does not reproduce target/native-desktop/{name}.prg'
        tree = temporary/'measured/native'
        shutil.copytree(ROOT/'src/native', tree)
        applied = patch(tree)
        measured = build_tree(tree, out)
        shutil.copytree(tree, out/'src-native')
    moved = {}
    for name, raw in (('desktop', 'desktop-raw'), ('vdsvc', 'vdsvc')):
        before, after = symbols(out/'control'/f'{raw}.sym'), symbols(out/f'{raw}.sym')
        moved[name] = sorted(k for k in before if after.get(k) != before[k])
        # Only the image end and the sizes derived from it may change.
        assert set(moved[name]) <= {'gd_end', 'bv_end'}, (name, moved[name][:20])
    disk = out/'pointer-timing.d64'
    disk.write_bytes(shipped_disk)
    subprocess.run(['c1541', '-attach', str(disk), '-delete', 'browse', 'vdsvc.prg', UNUSED_MODULE,
                    '-write', str(out/'desktop.prg'), 'browse',
                    '-write', str(out/'vdsvc.prg'), 'vdsvc.prg'], check=True, capture_output=True)
    labels = symbols(out/'desktop-raw.sym')
    manifest = dict(
        purpose='measurement build only; never shipped',
        shipped=dict(desktop_sha256=sha256(shipped['desktop']), vdsvc_sha256=sha256(shipped['vdsvc']),
                     disk_sha256=sha256(shipped_disk)),
        control_reproduces_shipped=True,
        labels_moved=moved,
        patches=applied,
        includes={name: sha256((ROOT/'probes'/name).read_bytes()) for name in INCLUDES},
        images=dict(desktop_sha256=sha256(measured['desktop']), vdsvc_sha256=sha256(measured['vdsvc']),
                    disk_sha256=sha256(disk.read_bytes()), desktop_header=measured['desktop'][2:34].hex()),
        count=labels['PT_UPDATES'], key=labels['PT_KEY'],
        header=labels['pt_header'], arrays=labels['pt_pre_lo'],
        pointer=dict(pm_x=labels['pm_x'], pm_y=labels['pm_y'], pm_seen=labels['pm_seen']),
        frame_cycles=FRAME_CYCLES)
    assert (manifest['count'], manifest['key']) == (COUNT, KEY)
    assert manifest['arrays'] == manifest['header']+HEADER_BYTES
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


def decode_header(data):
    assert len(data) >= HEADER_BYTES and data[:5] == b'PTIM\1', ('pointer timing header', data[:8].hex())
    word = lambda at: int.from_bytes(data[at:at+2], 'little')
    return dict(phase=data[5], count=word(6), target=word(8), driven=word(10), missing=data[12],
                crb_before=data[13], crb_halt=data[14], crb_run=data[15],
                calibration=[word(16), word(18), word(20)], service_calibration=word(22),
                sprites=data[24], calls=word(31), arrays=word(33))


def decode(header_bytes, array_bytes):
    """Per-update raw records from the header and the PT_UPDATES-byte arrays."""
    header = decode_header(header_bytes)
    assert len(array_bytes) == COUNT*len(ARRAYS)
    column = {name: array_bytes[i*COUNT:(i+1)*COUNT] for i, name in enumerate(ARRAYS)}
    records = [dict(pre=column['pre_lo'][i] | column['pre_hi'][i] << 8,
                    service=column['svc_lo'][i] | column['svc_hi'][i] << 8,
                    post=column['post_lo'][i] | column['post_hi'][i] << 8,
                    jiffy=column['jif'][i], irq=column['irq'][i]) for i in range(header['count'])]
    return header, records


def distribution(values):
    values = sorted(values)
    if not values:
        return dict(count=0)
    return dict(count=len(values), min=values[0], mean=round(statistics.fmean(values), 1),
                median=statistics.median(values), p95=values[math.ceil(.95*len(values))-1], max=values[-1],
                under_frame=round(sum(v < FRAME_CYCLES for v in values)/len(values), 4))


def summarize(header, records):
    """Cycle statistics in report form; see pointer-timing-desktop.inc."""
    empty, loop1001, loop2002 = header['calibration']
    service_empty = header['service_calibration']
    service = [r['service']-service_empty for r in records]
    pre = [r['pre']-empty-HOOK_EXTRA//2 for r in records]       # less JSR pt_bp_shipped
    post = [r['post']-empty-HOOK_EXTRA//2 for r in records]     # less the service hook's RTS
    call = [a+b+c for a, b, c in zip(pre, service, post)]
    quiet = [i for i, r in enumerate(records) if not r['irq']]
    gaps = [(b['jiffy']-a['jiffy']) & 255 for a, b in zip(records, records[1:])]
    histogram = {}
    for gap in gaps:
        key = str(gap) if gap < 4 else '4+'
        histogram[key] = histogram.get(key, 0)+1
    overflow = sum(r['pre'] < empty or r['post'] < empty or r['service'] < service_empty for r in records)
    return dict(
        frame_cycles=FRAME_CYCLES,
        calibration=dict(empty_segment=empty, service_empty_segment=service_empty,
                         loop_1001=loop1001-empty, loop_2002=loop2002-empty,
                         exact=loop1001-empty == 1001 and loop2002-empty == 2002 and service_empty == empty),
        updates=len(records), driven=header['driven'], missing=header['missing'], overflow=overflow,
        service=distribution(service), call=distribution(call),
        gate_in=distribution(pre), gate_out=distribution(post),
        service_without_irq=distribution([service[i] for i in quiet]),
        call_without_irq=distribution([call[i] for i in quiet]),
        updates_with_irq=len(records)-len(quiet),
        jiffies_between_updates=dict(sorted(histogram.items())),
        consecutive_jiffy_fraction=round(histogram.get('1', 0)/len(gaps), 4) if gaps else None,
        definitions=dict(
            service='bank-1 JSR vd_poll through its RTS: hide and redraw the pointer through the VDC',
            gate_in="bp_pointer's JSR bp_arguments up to the service's JSR vd_poll",
            gate_out="after vd_poll's RTS through bp_invoke's RTS",
            call="the client's op-3 bank call: shipped bp_pointer through bp_invoke's RTS (gate, checks, "
                 'vd_poll, status record)',
            cycles='CIA2 timer B phi2 counts: wall time including VIC-stolen cycles and any IRQ',
            jiffies_between_updates='$a2 difference between consecutive recorded calls'))


def expected_position(updates):
    """Pointer position after the approach and `updates` wiggle samples."""
    x, y = ORIGIN
    direction = 3
    for step in range(updates):
        if direction > 0 and y >= Y_MAX-2:
            direction = -3
        elif direction < 0 and y < ORIGIN[1]+3:
            direction = 3
        y += direction
        x += 5 if step % 2 == 0 else -5
    return x, y


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', type=Path, required=True)
    manifest = build(parser.parse_args().out)
    print(json.dumps(manifest['images'], indent=2))


if __name__ == '__main__':
    main()
