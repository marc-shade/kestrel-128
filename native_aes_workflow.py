"""The persistent AES demo's keyboard workflow, shared by the VICE test
(tests/ci_native_aes_vice.py, the oracle) and the hardware check
(hw_native_aes_check.py), so both run the identical key sequence against the
identical oracles (tests/native_aes_scene.py).

The workflow talks to a machine object:

  read(at, n=1)                 bank-0 RAM below $4000 (kernel mailbox,
                                allocation table): common RAM
  value(at, n=1, bank=0)        app or bank-1 RAM at $4000 and above
  surface(label)                the 9,216-byte VIC surface at $c000
  key(value, io=None)           one key through the native keyboard buffer,
                                consumed (event counter +1) and input ready
                                again; io names IEC traffic the key may start
                                ('scan', 'launch', 'leave') so a hardware
                                runner can stay off the bus meanwhile
  wait(predicate, label, seconds)
  pause()                       between two surface reads that differ
  scale, min_attempts           settle budget: seconds are multiplied by
                                scale; a surface is read at least
                                min_attempts times before it fails
  work                          evidence directory
"""
import hashlib
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT/'tests')]
import native_aes_scene as scene  # noqa: E402
AE_BASE = int(re.search(r'^AE_BASE = \$([0-9a-f]{4})', (ROOT/'src/native/aes-api.inc').read_text(), re.M).group(1), 16)
BLANK = bytes(8192)+b'\x16'*1024
ALERT = b'[3][Delete NOTES.TXT?|This cannot be undone.][Delete|Cancel]'
MENU = b'Desk:About AES...;File:New^N|Open...^O|-|Quit^Q;Options:Grid|Snap'


def ready(m):
    return m.read(0x3d12) == b'\1' and m.read(0xd0) == b'\0'


def expect_surface(m, want, label, seconds=0):
    """Read the VIC surface until it equals want exactly (a redraw can trail
    the key); fail after seconds*m.scale and at least m.min_attempts reads.
    Returns the surface's sha256 and the number of reads."""
    deadline = time.monotonic()+seconds*m.scale
    attempts = 0
    while True:
        m.wait(lambda: ready(m), label, 300)
        got = m.surface(f'{label}-{attempts}')
        attempts += 1
        if got == want:
            (m.work/(label+'.surface')).write_bytes(got)
            return dict(surface_sha256=hashlib.sha256(got).hexdigest(), reads=attempts)
        if time.monotonic() > deadline and attempts >= m.min_attempts:
            (m.work/(label+'-actual.bin')).write_bytes(got); (m.work/(label+'-expected.bin')).write_bytes(want)
            raise AssertionError((label, [(i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b][:12]))
        m.pause()


def build_demo(output):
    """examples/native-aes/build.py into output; the D64 the tests boot:
    target/native/kestrel.d64 with CALC replaced by AESDEMO and AESVC.PRG
    added. Returns the build report, the parent's symbols, the component
    image and the disk path."""
    output = Path(output)
    spec = importlib.util.spec_from_file_location('aes_build', ROOT/'examples/native-aes/build.py')
    build = importlib.util.module_from_spec(spec); spec.loader.exec_module(build)
    images = build.build(output)
    ps = {n: int(v, 16) for n, v in re.findall(r'^([\w.]+)\s*=\s*\$([\da-fA-F]+)',
                                                (output/'parent.sym').read_text(), re.M)}
    disk = output/'aes.d64'
    shutil.copy2(ROOT/'target/native/kestrel.d64', disk)
    subprocess.run(['c1541', '-attach', str(disk), '-delete', 'calc',
                    '-write', str(output/'AESDEMO.PRG'), 'calc',
                    '-write', str(output/'AESVC.PRG'), 'aesvc.prg'], check=True, capture_output=True)
    return dict(images=images, symbols=ps, component=(output/'AESVC.PRG').read_bytes(), disk=disk)


def aes_workflow(m, demo, check, report):
    """Cold-booted native kernel at its input wait: C loads the demo, which
    loads AESVC.PRG into bank 1; then the alert, menu and window demos and U
    (unload), each surface compared with the painter's oracle exactly."""
    ps, component = demo['symbols'], demo['component']

    def value(name, n=1): return m.value(ps[name], n)

    def expect(want, label): return expect_surface(m, want, label)

    m.wait(lambda: m.read(0x1c13, 6) == b'KES128' and ready(m), 'native boot', 240)
    m.key(ord('C'), io='launch')
    m.wait(lambda: ready(m), 'demo ready', 240)
    status = value('demo_status', 13)
    assert value('demo_error') == b'\0' and value('demo_loaded') == b'\1', (value('demo_error'), status.hex())
    assert status[0:3] == bytes([1, 7, 127]) and int.from_bytes(status[4:6], 'little') == 1
    loaded = bytearray(component[2:]); loaded[22:24] = ps['ae_callback'].to_bytes(2, 'little')
    resident = m.value(AE_BASE, 64, bank=1)
    assert resident[:22] == bytes(loaded[:22]) and resident[22:24] == bytes(loaded[22:24])
    whole = m.value(AE_BASE, len(loaded), bank=1)
    # The image's own RAM variables have run since loading; the code is fixed.
    report['image_matching_bytes'] = sum(a == b for a, b in zip(whole, loaded))
    check(f'cold boot; AESDEMO loads AESVC.PRG into bank-1 ${AE_BASE:04x} and attaches (version 1.7)',
          status=status.hex())

    surfaces = {}
    m.key(ord('A')); want, geo = scene.draw(BLANK, ALERT, 2, 2); surfaces['alert-open'] = expect(want, 'alert-open')
    m.key(9); want, _ = scene.draw(BLANK, ALERT, 2, 1); surfaces['alert-tab'] = expect(want, 'alert-tab')
    m.key(13)
    assert value('demo_choice') == b'\1' and value('demo_error') == b'\0'
    surfaces['alert-closed'] = expect(BLANK, 'alert-closed')      # exact restoration
    check('alert: exact frames on the VIC surface, Tab, Return, exact restore', surfaces=surfaces)

    surfaces = {}
    m.key(ord('M'))
    flags = {(1, 1): 2}
    want, _ = scene.menu_draw(BLANK, MENU, flags=flags); surfaces['menu-bar'] = expect(want, 'menu-bar')
    m.key(0x85); want, _ = scene.menu_draw(BLANK, MENU, open_title=0, hover=0, flags=flags)
    surfaces['menu-desk'] = expect(want, 'menu-desk')
    m.key(0x1d); m.key(0x11); want, _ = scene.menu_draw(BLANK, MENU, open_title=1, hover=3, flags=flags)
    surfaces['menu-file-quit'] = expect(want, 'menu-file-quit')
    m.key(13)
    assert value('demo_menu_title') == b'\1' and value('demo_menu_item') == b'\3'
    want, _ = scene.menu_draw(BLANK, MENU, flags=flags); surfaces['menu-closed'] = expect(want, 'menu-closed')
    m.key(27)
    assert value('demo_error') == b'\0' and value('demo_waiting') == b'\0'
    check('menu bar: F1, cursor keys past a disabled item, Return queues MN_SELECTED', surfaces=surfaces)

    K = scene.WK
    wins = {
        1: dict(id=1, kind=K['NAME'] | K['CLOSER'] | K['FULLER'] | K['MOVER'], x=1, y=2, w=20, h=10, title=b'Alpha'),
        2: dict(id=2, kind=K['NAME'] | K['CLOSER'] | K['INFO'] | K['SIZER'] | K['UP'] | K['DN'] | K['VSLIDE'],
                x=10, y=6, w=18, h=12, title=b'Beta', vpos=64, vsize=128),
        3: dict(id=3, kind=K['NAME'] | K['SIZER'] | K['LF'] | K['RT'] | K['HSLIDE'],
                x=5, y=14, w=24, h=8, title=b'Gamma', hpos=200, hsize=64),
    }
    fills = {1: (0, 0x15), 2: (1, 0xb0), 3: (0, 0x3e)}
    order = [1, 2, 3]
    base = m.surface('windows-base')
    surfaces = {}

    def windows(label):
        want = bytearray(scene.windows_draw([wins[h] for h in order], fills))
        # Row 0 keeps whatever the menu demo left there (windows never touch it).
        want[0:320] = base[0:320]; want[8192:8232] = base[8192:8232]
        surfaces[label] = expect(bytes(want), label)
    m.key(ord('W')); windows('windows-open')
    m.key(ord('1')); order[:] = [2, 3, 1]; windows('windows-top-1')
    m.key(ord('L')); wins[1].update(x=0, y=1); windows('windows-left')
    m.key(ord('M')); wins[1].update(x=1, y=2); windows('windows-move')
    m.key(ord('C')); order.remove(1); windows('windows-close')
    m.key(27)
    assert value('demo_error') == b'\0'
    check('windows: open three, top, move, close — frames, fills and markers match the painter', surfaces=surfaces)

    m.key(ord('U'))
    m.wait(lambda: m.read(0x3d20) == b'\0', 'demo exit', 240)
    records = [m.read(0x3c00+i*8, 8) for i in range(32)]
    assert not any(r[0] == 30 for r in records), 'unload freed the image and the data segment'
    assert m.read(0x3d0e, 3) == bytes([175, 251, 32])
    check('U unloads: every owner-30 page returns (175/251/32 free)')
