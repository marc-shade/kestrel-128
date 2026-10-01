"""VICE and Ultimate II+ helpers for Kestrel 128's tests: the VICE binary
monitor client, an Xvfb display for headless emulators, and the Ultimate II+
REST client used by the hardware checks. Taken from the commodore-basic tool
(the author's own `cbm` script) with its disk-building and command-line parts
left out; GPL-3.0-or-later, as the rest of Kestrel 128 (LICENSE).

Set KESTREL_ULTIMATE_HOST to the Ultimate's address for hardware runs.
"""
import argparse
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

# --------------------------------------------------------------------------
# Machine definitions
# --------------------------------------------------------------------------
# kbuf/ndx: KERNAL keyboard buffer and its pending-character count. Poking
# these makes the machine "type" a command at a READY prompt without a reset.
TARGETS = {
    "c64": {
        "petcat_tok": "-w2",
        "petcat_list": "-2",
        "emu": "x64sc",
        "load_addr": 0x0801,
        "kbuf": 0x0277,
        "ndx": 0x00C6,
        "kbuf_len": 10,
        "basic": "BASIC 2.0",
    },
    "c128": {
        "petcat_tok": "-w70",
        "petcat_list": "-70",
        "emu": "x128",
        "load_addr": 0x1C01,
        "kbuf": 0x034A,
        "ndx": 0x00D0,
        "kbuf_len": 10,
        "basic": "BASIC 7.0",
    },
}

SCREEN_BASE = 0x0400           # VIC-II text screen, both machines, 40 columns
SCREEN_SIZE = 40 * 25
MESA_EGL = "/usr/share/glvnd/egl_vendor.d/50_mesa.json"
DEFAULT_HOST = os.environ.get("KESTREL_ULTIMATE_HOST") or os.environ.get("CBM_ULTIMATE_HOST")  # no default: set it for hardware runs


def die(msg, code=1):
    print(f"cbm: {msg}", file=sys.stderr)
    sys.exit(code)


def need(tool):
    path = shutil.which(tool)
    if not path:
        die(f"required tool '{tool}' not found on PATH")
    return path


# --------------------------------------------------------------------------
# PETSCII / screen codes
# --------------------------------------------------------------------------
def screencode_to_char(code):
    """Map a VIC-II screen code to a printable ASCII approximation."""
    c = code & 0x7F                      # bit 7 = reverse video
    if c == 0:
        return "@"
    if 1 <= c <= 26:
        return chr(ord("A") + c - 1)
    if c == 27:
        return "["
    if c == 28:
        return "\\"                      # £ on real hardware
    if c == 29:
        return "]"
    if c == 30:
        return "^"                       # up arrow
    if c == 31:
        return "_"                       # left arrow
    if 32 <= c <= 63:
        return chr(c)
    return "."                           # PETSCII graphics glyph


def screen_text(mem, cols=40, rows=25):
    out = []
    for r in range(rows):
        row = mem[r * cols:(r + 1) * cols]
        out.append("".join(screencode_to_char(b) for b in row).rstrip())
    return "\n".join(out).rstrip("\n")


def framed(text, cols=40):
    top = "+" + "-" * cols + "+"
    lines = [top]
    for line in text.split("\n"):
        lines.append("|" + line.ljust(cols)[:cols] + "|")
    lines.append(top)
    return "\n".join(lines)


def petscii_bytes(s):
    """Encode an ASCII command string as PETSCII for the keyboard buffer."""
    out = bytearray()
    for ch in s:
        o = ord(ch)
        if "a" <= ch <= "z":
            out.append(o - 32)           # unshifted PETSCII: A-Z live at $41-$5A
        elif o < 128:
            out.append(o)
        else:
            die(f"cannot encode {ch!r} as PETSCII")
    return bytes(out)


# --------------------------------------------------------------------------
# VICE binary monitor client
# --------------------------------------------------------------------------
STX, API_VER = 0x02, 0x02
CMD_MEM_GET, CMD_BANKS, CMD_EXIT, CMD_QUIT = 0x01, 0x82, 0xAA, 0xBB



class ViceMonitor:
    """Speaks the VICE binary monitor protocol over TCP."""

    def __init__(self, port, host="127.0.0.1", timeout=15.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.req_id = 0

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise EOFError("VICE monitor closed the connection")
            buf += chunk
        return buf

    def _send(self, cmd, body=b""):
        self.req_id += 1
        self.sock.sendall(
            struct.pack("<BBIIB", STX, API_VER, len(body), self.req_id, cmd) + body
        )
        return self.req_id

    def _recv(self, want_id):
        # Async events (STOPPED/RESUMED) arrive with unrelated ids; skip them.
        while True:
            stx, _api, blen, _rtype, err, rid = struct.unpack(
                "<BBIBBI", self._recv_exact(12)
            )
            if stx != STX:
                raise ValueError(f"bad STX byte {stx:#x} from VICE monitor")
            body = self._recv_exact(blen) if blen else b""
            if rid == want_id:
                return err, body

    def banks(self):
        err, body = self._recv(self._send(CMD_BANKS))
        if err:
            raise RuntimeError(f"BANKS_AVAILABLE failed, error {err}")
        banks, off = {}, 2
        (count,) = struct.unpack("<H", body[:2])
        for _ in range(count):
            item_len = body[off]
            bank_id = struct.unpack("<H", body[off + 1:off + 3])[0]
            nlen = body[off + 3]
            banks[body[off + 4:off + 4 + nlen].decode("ascii", "replace")] = bank_id
            off += item_len + 1
        return banks

    def read_mem(self, start, end, bank=0, memspace=0):
        body = struct.pack("<BHHBH", 0, start, end, memspace, bank)
        err, resp = self._recv(self._send(CMD_MEM_GET, body))
        if err:
            raise RuntimeError(f"MEM_GET {start:#06x}-{end:#06x} failed, error {err}")
        (n,) = struct.unpack("<H", resp[:2])
        return resp[2:2 + n]

    def resume(self):
        """Let emulation continue; monitor commands implicitly stop the CPU."""
        self._recv(self._send(CMD_EXIT))

    def quit_emulator(self):
        """Clean shutdown, which is what makes -exitscreenshot fire."""
        self._send(CMD_QUIT)

    def close(self):
        self.sock.close()


# --------------------------------------------------------------------------
# Ultimate II+ / Ultimate 64 REST client
# --------------------------------------------------------------------------
class Ultimate:
    def __init__(self, host=DEFAULT_HOST, timeout=25.0):
        self.host = host
        self.timeout = timeout

    def _call(self, method, path, data=None):
        req = urllib.request.Request(
            f"http://{self.host}{path}", data=data, method=method
        )
        if data is not None:
            req.add_header("Content-Type", "application/octet-stream")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()
        except OSError as exc:
            die(f"cannot reach Ultimate at {self.host}: {exc}")

    def _expect_ok(self, method, path, data=None, what="request"):
        status, body = self._call(method, path, data)
        if status != 200:
            die(f"{what} failed: HTTP {status}: {body[:200].decode('utf-8', 'replace')}")
        return body

    def version(self):
        return self._expect_ok("GET", "/v1/version", what="version").decode(
            "utf-8", "replace"
        )

    def drives(self):
        return self._expect_ok("GET", "/v1/drives", what="drive query").decode(
            "utf-8", "replace"
        )

    def read_mem(self, address, length):
        body = self._expect_ok(
            "GET",
            f"/v1/machine:readmem?address={address:04X}&length={length}",
            what="readmem",
        )
        if len(body) < length:
            die(f"readmem returned {len(body)} bytes, expected {length}")
        return body[:length]

    def write_mem(self, address, data):
        hexdata = data.hex().upper()
        if len(data) > 128:
            die("writemem accepts at most 128 bytes per call")
        self._expect_ok(
            "PUT",
            f"/v1/machine:writemem?address={address:04X}&data={hexdata}",
            what="writemem",
        )

    def mount(self, image_bytes, drive="a", img_type="d64", mode="readwrite"):
        self._expect_ok(
            "POST",
            f"/v1/drives/{drive}:mount?type={img_type}&mode={mode}",
            image_bytes,
            what="disk mount",
        )

    def unmount(self, drive="a"):
        self._expect_ok("PUT", f"/v1/drives/{drive}:remove", what="disk unmount")

    def run_prg(self, prg_bytes):
        self._expect_ok("POST", "/v1/runners:run_prg", prg_bytes, what="run_prg")

    def reset(self):
        self._expect_ok("PUT", "/v1/machine:reset", what="reset")

    def screen(self):
        return screen_text(self.read_mem(SCREEN_BASE, SCREEN_SIZE))

    def screen_when_settled(self, timeout=60.0, poll=1.0, settle_polls=3):
        """Poll the real screen until it stops changing.

        Real hardware runs at 1MHz with no warp mode, so a fixed sleep either
        truncates a running program or wastes time. Settling detects the end
        of output whether or not the program returns to a READY prompt.
        """
        deadline = time.time() + timeout
        previous, stable, text = None, 0, self.screen()
        while time.time() < deadline:
            text = self.screen()
            if text == previous:
                stable += 1
                if stable >= settle_polls and text.strip():
                    return text, True
            else:
                stable, previous = 0, text
            time.sleep(poll)
        return text, False

    def type_line(self, text, spec, settle=0.25, timeout=15.0):
        """Type a command at a READY prompt by refilling the keyboard buffer.

        The buffer holds only ~10 characters, so long commands are fed in
        chunks, waiting for the editor to drain each one.
        """
        payload = petscii_bytes(text) + b"\r"
        chunk_size = spec["kbuf_len"]
        deadline = time.time() + timeout
        for i in range(0, len(payload), chunk_size):
            chunk = payload[i:i + chunk_size]
            while self.read_mem(spec["ndx"], 1)[0] != 0:
                if time.time() > deadline:
                    die("keyboard buffer never drained; is the machine at a READY prompt?")
                time.sleep(settle)
            self.write_mem(spec["kbuf"], chunk)
            self.write_mem(spec["ndx"], bytes([len(chunk)]))
            time.sleep(settle)


# --------------------------------------------------------------------------
# Build helpers
# --------------------------------------------------------------------------

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def free_display():
    for num in range(90, 130):
        if not os.path.exists(f"/tmp/.X11-unix/X{num}"):
            return num
    die("no free X display number between :90 and :129")


class Xvfb:
    """Headless X server. Forces Mesa EGL: NVIDIA's EGL aborts Xvfb here."""

    def __init__(self, geometry="800x600x24"):
        self.num = free_display()
        env = dict(os.environ, __EGL_VENDOR_LIBRARY_FILENAMES=MESA_EGL)
        need("Xvfb")
        self.proc = subprocess.Popen(
            ["Xvfb", f":{self.num}", "-screen", "0", geometry],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        for _ in range(50):
            if os.path.exists(f"/tmp/.X11-unix/X{self.num}"):
                return
            if self.proc.poll() is not None:
                die(f"Xvfb :{self.num} exited immediately (rc={self.proc.returncode})")
            time.sleep(0.1)
        die(f"Xvfb :{self.num} did not come up within 5s")

    @property
    def display(self):
        return f":{self.num}"

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


