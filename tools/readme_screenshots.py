#!/usr/bin/env python3
"""Regenerate the README screenshots from the real disk images in VICE.

Boots target/native-desktop/kestrel.d81 in x128 on a private Xvfb display,
drives the desktop and each app through the native keyboard buffer (the same
injection the VICE suites use), and saves VICE's own rendered frames: the
VIC-II (40 columns) and the 8563 VDC (80 columns), fetched over the binary
monitor with their palettes. Nothing is drawn or composited by this script.

    python3 -B tools/readme_screenshots.py [--out docs/screenshots] [--only NAME ...]

Needs x128, Xvfb and ImageMagick (`magick`). Claude's terminal uses the
repository's fixture session, not a live Claude login.
"""
import argparse
import os
from pathlib import Path
import random
import shlex
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
import vice_harness as ci
from native_capture import wait


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


# Display areas of VICE's canvases, in canvas pixels (x0, y0, x1, y1).
DISPLAY = dict(vic=(320, 200), vdc=(640, 200))


def display_box(frame, chip):
    """Locate the display window: the canvas is centred on it, so derive it
    from the canvas size; confirm against the border colour when they differ."""
    want_w, want_h = DISPLAY[chip]
    width, height, data = frame['width'], frame['height'], frame['data']
    x0, y0 = (width-want_w)//2, (height-want_h)//2
    border = data[0]
    rows = [y for y in range(height) if any(v != border for v in data[y*width:(y+1)*width])]
    if rows:
        cols = [x for x in range(width) if any(data[y*width+x] != border for y in range(rows[0], rows[-1]+1, 4))]
        if cols and cols[-1]-cols[0]+1 <= want_w and rows[-1]-rows[0]+1 <= want_h:
            # Content lies inside the window; align the window to it where it touches.
            x0 = min(max(x0, cols[-1]+1-want_w), cols[0])
            y0 = min(max(y0, rows[-1]+1-want_h), rows[0])
    return x0, y0, x0+want_w, y0+want_h


# VICE x128's default VIC-II palette (binary monitor palette get, 2026-09-29),
# used to render surfaces captured from the real machine like VICE's frames.
VIC_PALETTE = [bytes.fromhex(h) for h in (
    '000000', 'ffffff', 'af3c58', '7ef3d6', 'aa40f5', '62d532', '2c3dec', 'ffff46',
    'b7631e', '775300', 'ee7b95', '626262', '949494', 'b7ff86', '7385ff', 'cdcdcd')]


def surface_png(surface, png, work):
    """Render a 9,216-byte native VIC surface (hires bitmap + colour cells) to
    a 2x PNG. Sprites, such as the pointer, are not part of the surface."""
    assert len(surface) == 9216
    pixels = bytearray()
    for y in range(200):
        for x in range(320):
            cell = surface[8192+y//8*40+x//8]
            on = surface[y//8*320+x//8*8+y % 8] & (128 >> (x % 8))
            pixels += VIC_PALETTE[cell >> 4 if on else cell & 15]
    ppm = Path(work)/(Path(png).stem+'.ppm')
    ppm.write_bytes(b'P6 320 200 255\n'+bytes(pixels))
    subprocess.run(['magick', str(ppm), '-filter', 'point', '-resize', '200%', '-strip', str(png)], check=True)


class Session:
    """One x128 run with key injection and frame grabs."""

    def __init__(self, disk, work, *, bridge=False):
        self.work = work
        self.xv = ci.cbm.Xvfb(geometry='1920x1200x24')
        self.logs = [(work/'vice.log').open('w')]
        self.procs = []
        command = ['x128', '-default', '-80col', '-8', str(disk), '-drive8true', '-drive8type', '1581',
                   '-VDC64KB', '-sounddev', 'dummy', '-jamaction', '0', '-warp']
        if bridge:
            link = free_port()
            control = work/'fixture-control.txt'
            host = [sys.executable, '-B', str(ROOT/'apps/claude/run.py'), '--listen', str(link),
                    '--command', shlex.join([sys.executable, '-B', str(ROOT/'tests/fixtures/claude-session.py'),
                                             str(control)]), '--no-panel', '-v']
            self.logs.append((work/'bridge.log').open('w'))
            self.procs.append(subprocess.Popen(host, stdout=self.logs[-1], stderr=subprocess.STDOUT))
            wait(lambda: 'listening on' in (work/'bridge.log').read_text(), 'bridge listening', 15)
            command += ['-acia1', '-acia1base', '0xDE00', '-acia1irq', '1', '-acia1mode', '1',
                        '-myaciadev', '0', '-rsdev1', f'127.0.0.1:{link}', '-rsdev1baud', '38400']
        port = free_port()
        command += ['-binarymonitor', '-binarymonitoraddress', f'ip4://127.0.0.1:{port}']
        self.emu = subprocess.Popen(command, env=dict(os.environ, DISPLAY=self.xv.display,
            __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL), stdout=self.logs[0], stderr=subprocess.STDOUT)
        self.procs.insert(0, self.emu)
        deadline = time.monotonic()+30
        self.mon = None
        while self.mon is None:
            assert self.emu.poll() is None, 'VICE exited'
            try:
                self.mon = ci.Monitor(port=port)
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(.1)
        self.mon.resume()

    def read(self, address, count=1):
        data = bytes(self.mon.read_mem(address, address+count-1))
        self.mon.resume()
        return data

    def unphase(self):
        # VICE answers the monitor at a fixed frame phase; pointer apps clear
        # N_READY near it. Step a random part of a frame before sampling.
        error, _ = self.mon._recv(self.mon._send(0x71, struct.pack('<BH', 0, random.randint(1, 6000))))
        assert not error

    def ready(self):
        self.unphase()
        return self.read(0x3d12) == b'\1' and self.read(0xd0, 2) == bytes(2)

    def boot(self):
        wait(lambda: self.read(0x1c13, 6) == b'KES128' and self.ready(), 'native desktop boot', 300)
        self.settle()

    def settle(self, seconds=1.5):
        wait(self.ready, 'idle', 180)
        time.sleep(seconds)
        wait(self.ready, 'idle', 180)

    def key(self, value):
        wait(self.ready, 'idle before key', 180)
        before = int.from_bytes(self.read(0x3d13, 2), 'little')
        deadline = time.monotonic()+60
        while True:
            self.unphase()
            if self.read(0x3d12) == b'\1' and self.read(0xd0, 2) == bytes(2):
                self.mon.write_mem(0x3d12, b'\0')
                self.mon.write_mem(0x34a, bytes([value]))
                self.mon.write_mem(0xd0, b'\1')
                self.mon.resume()
                break
            assert time.monotonic() < deadline, 'key admission'
        wait(lambda: int.from_bytes(self.read(0x3d13, 2), 'little') != before, f'key {value:02x} consumed', 120)

    def keys(self, data):
        for value in data:
            self.key(value)

    def frame(self, vic):
        error, raw = self.mon._recv(self.mon._send(0x84, bytes([1 if vic else 0, 0])))
        assert not error
        error, pal = self.mon._recv(self.mon._send(0x91, bytes([1 if vic else 0])))
        assert not error
        self.mon.resume()
        fields, = struct.unpack_from('<I', raw)
        width, height, xoff, yoff, innerw, innerh, bpp = struct.unpack_from('<6HB', raw, 4)
        length, = struct.unpack_from('<I', raw, 4+fields)
        data = raw[8+fields:8+fields+length]
        # The monitor client drops the reply's last 4 bytes (bottom-right
        # border pixels); ci_native_pointer_iec's check_canvas allows the same.
        assert bpp == 8 and length == width*height and length-len(data) in (0, 4)
        data = data+data[-1:]*(length-len(data))
        count, = struct.unpack_from('<H', pal)
        colors, at = [], 2
        for _ in range(count):
            size = pal[at]
            colors.append(bytes(pal[at+1:at+4]))
            at += size+1
        return dict(width=width, height=height, xoff=xoff, yoff=yoff, innerw=innerw, innerh=innerh,
                    data=data, colors=colors)

    def shot(self, out, name, *, vic=True, vdc=True):
        saved = []
        for chip, wanted in (('vic', vic), ('vdc', vdc)):
            if not wanted:
                continue
            frame = self.frame(chip == 'vic')
            # The canvas includes the border. Find the display area as the
            # bounding box of pixels differing from the border colour, then
            # keep a 16-pixel border ring on the VIC and none on the VDC.
            x0, y0, x1, y1 = display_box(frame, chip)
            margin = 16 if chip == 'vic' else 0
            x0, y0 = max(0, x0-margin), max(0, y0-margin)
            x1, y1 = min(frame['width'], x1+margin), min(frame['height'], y1+margin)
            w, h = x1-x0, y1-y0
            pixels = bytearray()
            for y in range(y0, y1):
                row = frame['data'][y*frame['width']+x0:y*frame['width']+x1]
                pixels += b''.join(frame['colors'][index] for index in row)
            ppm = self.work/f'{name}-{chip}.ppm'
            ppm.write_bytes(f'P6 {w} {h} 255\n'.encode()+bytes(pixels))
            png = out/f'{name}-{chip}.png'
            # Nearest-neighbour 2x; the VDC's 200 lines are doubled in height
            # only, matching its 640x200 display on a monitor.
            scale = '200%' if chip == 'vic' else '100%x200%'
            subprocess.run(['magick', str(ppm), '-filter', 'point', '-resize', scale, '-strip', str(png)],
                           check=True)
            saved.append(png)
            print('saved', png.relative_to(ROOT) if png.is_relative_to(ROOT) else png, f'({w}x{h} native)',
                  flush=True)
        return saved

    def close(self):
        try:
            self.mon.quit_emulator()
        except (OSError, EOFError, AttributeError):
            pass  # VICE already gone (or never connected); the processes are reaped below
        for proc in self.procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        self.xv.stop()
        for log in self.logs:
            log.close()


# 5x7 letters for the picture title (one row per string, '#' = ink).
GLYPHS = {
    'K': ['#   #', '#  # ', '# #  ', '##   ', '# #  ', '#  # ', '#   #'],
    'e': ['     ', '     ', ' ### ', '#   #', '#####', '#    ', ' ####'],
    's': ['     ', '     ', ' ####', '#    ', ' ### ', '    #', '#### '],
    't': ['  #  ', '  #  ', '#####', '  #  ', '  #  ', '  #  ', '   ##'],
    'r': ['     ', '     ', '# ## ', '##  #', '#    ', '#    ', '#    '],
    'l': [' ##  ', '  #  ', '  #  ', '  #  ', '  #  ', '  #  ', ' ### '],
}


def make_picture():
    """A UPNT v1 picture for Paint: night sky, stars, moon, hills and title.

    Hires colours are per 8x8 cell (one ink, one paper), so every element
    is laid out on cell boundaries where colours meet."""
    import math
    from native_paint_format import encode
    W, H = 320, 200
    color = [[0 if y < 56 else 6 for x in range(W)] for y in range(H)]   # black sky, blue lower sky
    rnd = random.Random(128)
    for _ in range(90):                                   # stars, clear of moon and title
        x, y = rnd.randrange(W), rnd.randrange(120)
        if not (208 <= x < 288 and 8 <= y < 88) and not (16 <= y < 56 and x < 200):
            color[y][x] = 1
    cx, cy, r = 248, 48, 26                               # crescent moon
    for y in range(cy-r, cy+r+1):
        for x in range(cx-r, cx+r+1):
            if math.hypot(x-cx, y-cy) <= r and math.hypot(x-cx-10, y-cy+6) > r-6:
                color[y][x] = 7
    x0 = 24                                               # title, 3x scale
    for ch in 'Kestrel':
        for gy, line in enumerate(GLYPHS[ch]):
            for gx, cell in enumerate(line):
                if cell == '#':
                    for dy in range(3):
                        for dx in range(3):
                            color[24+gy*3+dy][x0+gx*3+dx] = 14
        x0 += 18 if ch != ' ' else 12
    for x in range(W):                                    # far and near hills
        far = int(128+10*math.sin(x/37.0)+6*math.sin(x/13.0))
        near = int(156+12*math.sin(x/51.0+1.3))
        for y in range(far, H):
            color[y][x] = 13 if y < near else 5
    # Hires: each 8x8 cell shows two colours. Keep the cell's two most
    # frequent; the more frequent is paper, the other ink.
    bitmap, attrs = bytearray(8000), bytearray(1000)
    for row in range(25):
        for col in range(40):
            counts = {}
            for y in range(row*8, row*8+8):
                for x in range(col*8, col*8+8):
                    counts[color[y][x]] = counts.get(color[y][x], 0)+1
            ranked = sorted(counts, key=counts.get, reverse=True)
            bg = ranked[0]
            fg = ranked[1] if len(ranked) > 1 else 1
            for y in range(row*8, row*8+8):
                for x in range(col*8, col*8+8):
                    if color[y][x] == fg:
                        bitmap[row*320+col*8+y % 8] |= 128 >> (x % 8)
            attrs[row*40+col] = fg << 4 | bg
    return encode(bytes(bitmap)+bytes(192)+bytes(attrs)+b'\x10'*24)


ESC, RETURN, TAB = 27, 13, 9
DOWN, RIGHT, UP, LEFT = 0x11, 0x1d, 0x91, 0x9d


def scene_suite(s, out):
    s.boot()
    s.shot(out, 'desktop')
    s.key(ord('C')); s.settle()
    s.keys(b'1541*8='); s.keys(b'+128='); s.settle()
    s.shot(out, 'calculator')
    s.key(ESC); s.settle()
    s.key(ord('E')); s.settle()
    for line in (b'Kestrel 128 native editor', b'Documents live in both RAM banks',
                 b'and the REU; saves are read back', b'and compared before success.'):
        s.keys(line); s.key(RETURN)
    s.settle()
    s.shot(out, 'editor')
    s.key(ESC); s.settle(); s.key(ord('Y')); s.settle()
    s.key(ord('F')); s.settle(3)
    s.shot(out, 'files')
    s.key(ESC); s.settle()
    s.key(ord('S')); s.settle()
    for text, move in ((b'1541', DOWN), (b'1571', DOWN), (b'1581', DOWN), (b'=a1+a2+a3', None)):
        s.keys(text); s.key(RETURN)
        if move:
            s.key(move)
    s.key(RIGHT); s.key(UP); s.key(UP); s.key(UP)
    s.keys(b'170'); s.key(RETURN); s.key(DOWN)
    s.keys(b'340'); s.key(RETURN); s.key(DOWN)
    s.keys(b'800'); s.key(RETURN); s.key(DOWN)
    s.keys(b'=b1+b2+b3'); s.key(RETURN)
    s.settle()
    s.shot(out, 'sheet')
    s.key(ESC); s.settle(); s.key(RETURN); s.settle()        # discard the demo workbook
    s.key(ord('F')); s.settle(3)
    for _ in range(s.picture_index):
        s.key(DOWN)
    s.key(RETURN); s.settle(4)                              # UPNT opens in Paint
    s.shot(out, 'paint')
    s.key(ESC); s.settle(3); s.key(ESC); s.settle()         # Paint -> Files -> desktop
    s.key(ord('U')); s.settle(3)
    s.shot(out, 'ultimate')
    s.key(ESC); s.settle()


def scene_claude(s, out):
    s.boot()
    s.key(ord('A')); s.settle()
    s.shot(out, 'claude')
    s.key(RETURN); s.settle(8)
    s.shot(out, 'claude-terminal')


def scene_gem(s, out):
    gemdesk = (ROOT/'target/native-desktop/gemdesk.prg').read_bytes()[2:34]
    wait(lambda: s.read(0x1c13, 6) == b'KES128' and s.read(0x3d60, 32) == gemdesk and s.ready(),
         'GEMDESK boot', 300)
    s.settle()
    s.shot(out, 'gemdesk')
    s.key(ord('8')); s.settle(3)
    s.shot(out, 'gemdesk-window')
    s.key(0x85); s.key(RIGHT); s.settle()                   # F1 opens the menu bar; Right: File
    s.shot(out, 'gemdesk-menu')
    s.key(ESC); s.settle()
    s.key(0x85); s.key(RETURN); s.settle()                  # Desk: About
    s.shot(out, 'gemdesk-about')
    s.key(RETURN); s.settle()


# name: (function, Claude fixture bridge, disk image, add the demo picture)
SCENES = dict(suite=(scene_suite, False, 'kestrel.d81', True),
              claude=(scene_claude, True, 'kestrel.d81', False),
              gem=(scene_gem, False, 'gem.d81', False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT/'docs/screenshots')
    parser.add_argument('--only', nargs='+', choices=sorted(SCENES))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name in args.only or SCENES:
        function, bridge, image, picture = SCENES[name]
        work = Path(tempfile.mkdtemp(prefix=f'kestrel-screens-{name}-'))
        disk = work/image
        shutil.copyfile(ROOT/'target/native-desktop'/image, disk)
        index = None
        if picture:
            upnt = work/'moonrise.upnt'
            upnt.write_bytes(make_picture())
            subprocess.run(['c1541', '-attach', str(disk), '-write', str(upnt), 'moonrise.upnt,s'],
                           check=True, capture_output=True)
            listing = subprocess.run(['c1541', '-attach', str(disk), '-list'], check=True,
                                     capture_output=True, text=True).stdout.splitlines()
            entries = [line for line in listing if '"' in line][1:]  # the first quoted line is the header
            index = next(i for i, line in enumerate(entries) if '"moonrise.upnt"' in line)
        print(f'{name}: evidence {work}', flush=True)
        session = Session(disk, work, bridge=bridge)
        session.picture_index = index
        try:
            function(session, args.out)
        finally:
            session.close()

if __name__ == '__main__':
    main()
