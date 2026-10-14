#!/usr/bin/env python3
"""The pointer-timing measurement build (native_pointer_timing.py) in Py65
and in VICE x128, the twin of hw_ultimate_check.py --native-pointer-timing.

Py65, 64 KiB VDC that is always ready (bench_native_perf's model):
- the shipped desktop wiggles from (308,20) with dx +5/-5, dy 3; the cycles
  of the service's JSR vd_poll and of the client's op-3 call are taken from
  the instruction stream at each frame;
- the measurement build runs the same path on its own, with CIA2 timer B
  modelled from the CPU's cycle count; every recorded update, corrected as
  pointer-timing-desktop.inc says, must equal the shipped cycles of the
  same frame, and the calibration loops must read 1001 and 2002. The
  difference in whole-frame cycles is the instrumentation overhead.

VICE (NTSC x128, 80 columns, 64 KiB VDC, true 1541): the measurement disk
boots, key T starts the run, and after all 512 updates the counters are
read from bank-0 RAM through the monitor (a monitor read stops the emulated
machine, so it adds no cycles). Calibration must be exact, every update
must be recorded, the pointer must end where the path says, and no update
may take fewer cycles than the Py65 lower bound. VICE's 8563 timing is
approximate, so the VICE figures beside Py65 are information, not a pass
condition.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
import vice_harness as ci
from native_capture_transport import PausedViceMonitor
import native_pointer_timing as timing


class Spans:
    """Cycles from an instruction at (bank, pc) until control returns past it:
    'jsr' spans end after that JSR's subroutine returns, 'call' spans end when
    the caller's return address (on the stack at the start) is reached."""
    def __init__(self, p, starts):
        self.p, self.starts, self.open, self.done = p, starts, {}, {name: [] for name in starts}
        self.began = {name: [] for name in starts}
        cpu, bus, step = p.cpu, p.m.bus, p.cpu.step

        def hooked():
            pc, sp = cpu.pc, cpu.sp
            for name, (kind, end_pc, end_sp, started) in list(self.open.items()):
                if pc == end_pc and sp == end_sp:
                    self.done[name].append(cpu.processorCycles-started)
                    del self.open[name]
            bank = (bus.config >> 6) & 1
            for name, (want_bank, start, kind) in starts.items():
                if pc == start and bank == want_bank and name not in self.open:
                    self.began[name].append(cpu.processorCycles)
                    if kind == 'jsr':
                        self.open[name] = (kind, start+3, sp, cpu.processorCycles)
                    else:
                        stack = bus.ram[0]
                        back = stack[0x100+((sp+1) & 255)] | stack[0x100+((sp+2) & 255)] << 8
                        self.open[name] = (kind, (back+1) & 65535, (sp+2) & 255, cpu.processorCycles)
            step()
        cpu.step = hooked

    def take(self):
        taken = {name: list(values) for name, values in self.done.items()}
        taken.update({name+'_began': list(values) for name, values in self.began.items()})
        for values in (*self.done.values(), *self.began.values()): values.clear()
        return taken


def py65(build, frames):
    """Shipped spans per wiggle frame, then the measurement build's records."""
    import bench_native_perf as bench
    from ci_native_vdc_desktop import Desktop
    from ci_native_pointer import heap, calc
    service_symbols = timing.symbols(build/'vdsvc.sym')
    desktop_symbols = timing.symbols(build/'desktop-raw.sym')
    shipped_symbols = timing.symbols(build/'control/desktop-raw.sym')
    result = dict(model='Py65, 64 KiB VDC ready on the first status read (bench_native_perf)', frames=frames)
    saved = heap.Bus, calc.Machine, calc.MPU, calc.ROOT
    try:
        heap.Bus = bench.vdc()
        p = Desktop(); p.frame(); p.move(*timing.ORIGIN)
        spans = Spans(p, dict(service=(1, service_symbols['bv_pointer'], 'jsr'),
                              call=(0, shipped_symbols['bp_pointer'], 'call')))
        shipped = []
        for i in range(frames):
            at = p.position; dx = 5 if i % 2 == 0 else -5
            cycles, _ = bench.measure(p, lambda: p.frame(dx, 3))
            assert p.position == (at[0]+dx, at[1]+3), (at, p.position)
            taken = spans.take()
            assert len(taken['service']) == len(taken['call']) == 1, taken
            gate_in = taken['service_began'][0]-taken['call_began'][0]
            shipped.append(dict(frame=cycles, service=taken['service'][0], call=taken['call'][0], gate_in=gate_in,
                                gate_out=taken['call'][0]-gate_in-taken['service'][0]))
        result['shipped'] = shipped

        class TimerBus(bench.vdc()):
            """CIA2 timer B from the CPU's cycle count; raster line 250 while
            the calibration waits for it (the harness holds line 100/132)."""
            cpu = None
            def __init__(self):
                super().__init__()
                self.latch = self.counter = 0xffff; self.running = False; self.started = 0; self.crb = 8
                self.sync = [(0, desktop_symbols['pt_sync'], desktop_symbols['pt_start']),
                             (1, service_symbols['pt_svc_sync'], service_symbols['pt_svc_start'])]
            def now(self):
                return self.cpu.processorCycles+3     # the access cycle of a 4-cycle absolute instruction
            def value(self):
                if not self.running: return self.counter
                elapsed = self.now()-self.started
                assert elapsed <= self.latch, 'modelled timer B underflow'
                return self.latch-elapsed
            def __getitem__(self, address):
                if not self.config&1:
                    if address == 0xdd06: return self.value() & 255
                    if address == 0xdd07: return self.value() >> 8
                    if address == 0xdd0f: return self.crb & 0xef
                    if address == 0xd012 and any(bank == (self.config >> 6) & 1 and lo <= self.cpu.pc < hi
                                                  for bank, lo, hi in self.sync): return 250
                return super().__getitem__(address)
            def __setitem__(self, address, value):
                if not self.config&1 and address in (0xdd06, 0xdd07, 0xdd0f):
                    if address == 0xdd06: self.latch = (self.latch & 0xff00) | value
                    elif address == 0xdd07:
                        self.latch = (self.latch & 255) | value << 8
                        if not self.running: self.counter = self.latch
                    else:
                        if self.running and not value&1: self.counter = self.value()
                        if value & 0x10: self.counter = self.latch
                        if value & 1 and not (self.running and not value & 0x10):
                            self.started = self.now()-(self.latch-self.counter)
                        self.running = bool(value & 1); self.crb = value
                    return
                super().__setitem__(address, value)

        class TrackedMPU(calc.MPU):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if isinstance(self.memory, TimerBus): self.memory.cpu = self

        root = build/'py65-root'/'target/native-desktop'
        root.mkdir(parents=True, exist_ok=True)
        for name in ('desktop', 'vdsvc'): shutil.copyfile(build/f'{name}.prg', root/f'{name}.prg')
        heap.Bus, calc.MPU, calc.ROOT = TimerBus, TrackedMPU, build/'py65-root'
        q = Desktop()
        bus = q.m.bus; ram = bus.ram[0]
        header_at, arrays_at = desktop_symbols['pt_header'], desktop_symbols['pt_pre_lo']
        def header(): return timing.decode_header(bytes(ram[header_at:header_at+timing.HEADER_BYTES]))
        q.frame(); assert header()['phase'] == 0
        q.keys.append(timing.KEY); q.frame()
        assert header()['phase'] in (1, 2), header()
        approach, measured = 0, []
        while header()['count'] < frames:
            before = header()['count']
            cycles, _ = bench.measure(q, q.frame)
            if header()['count'] == before:
                assert header()['phase'] == 1 and approach < 200, ('approach', q.position, header())
                approach += 1
                continue
            assert header()['count'] == before+1, ('one update per frame', before, header())
            measured.append(cycles)
        h, records = timing.decode(bytes(ram[header_at:arrays_at]),
                                   bytes(ram[arrays_at:arrays_at+timing.COUNT*len(timing.ARRAYS)]))
        summary = timing.summarize(h, records)
        assert summary['calibration']['exact'], summary['calibration']
        empty, service_empty = h['calibration'][0], h['service_calibration']
        compared = []
        for i, (record, reference) in enumerate(zip(records, shipped)):
            service = record['service']-service_empty
            call = record['pre']+record['service']+record['post']-2*empty-service_empty-timing.HOOK_EXTRA
            compared.append(dict(service=service, call=call, frame=measured[i], overhead=measured[i]-reference['frame'],
                                 gate_in=record['pre']-empty-timing.HOOK_EXTRA//2,
                                 gate_out=record['post']-empty-timing.HOOK_EXTRA//2))
            assert [compared[-1][k] for k in ('service', 'call', 'gate_in', 'gate_out')] == \
                [reference[k] for k in ('service', 'call', 'gate_in', 'gate_out')], (i, compared[-1], reference)
        assert q.position == timing.expected_position(frames), (q.position, frames)
        result.update(approach_frames=approach, instrumented=compared, calibration=summary['calibration'],
                      records_equal_shipped_cycles=True)
        mean = lambda rows, key: round(sum(row[key] for row in rows)/len(rows), 1)
        result['means'] = dict(shipped_frame=mean(shipped, 'frame'), shipped_service=mean(shipped, 'service'),
                               shipped_call=mean(shipped, 'call'), shipped_gate_in=mean(shipped, 'gate_in'),
                               shipped_gate_out=mean(shipped, 'gate_out'), instrumented_frame=mean(compared, 'frame'),
                               overhead_per_frame=mean(compared, 'overhead'),
                               overhead_range=[min(r['overhead'] for r in compared), max(r['overhead'] for r in compared)])
        result['minimum'] = {name: min(r[name] for r in shipped) for name in ('service', 'call', 'gate_in', 'gate_out')}
    finally:
        heap.Bus, calc.Machine, calc.MPU, calc.ROOT = saved
    return result


def vice(build, manifest, work, report, save, seconds):
    disk = work/'pointer-timing.d64'; shutil.copyfile(build/'pointer-timing.d64', disk)
    labels = timing.symbols(build/'desktop-raw.sym')
    header_bytes = (build/'desktop.prg').read_bytes()[2:34]
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    command = ['x128', '-default', '-ntsc', '-80col', '-VDC64KB', '-8', str(disk), '-drive8true', '-drive8type', '1541',
               '-controlport1device', '0', '-sounddev', 'dummy', '-jamaction', '0', '-warp',
               '-binarymonitor', '-binarymonitoraddress', f'ip4://127.0.0.1:{port}']
    result = dict(command=command); report['vice'] = result
    xv = ci.cbm.Xvfb(); log = (work/'vice.log').open('w'); mon = None
    emu = subprocess.Popen(command, env=dict(os.environ, DISPLAY=xv.display, __EGL_VENDOR_LIBRARY_FILENAMES=ci.cbm.MESA_EGL),
                           stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic()+30
        while mon is None:
            assert emu.poll() is None
            try: mon = ci.Monitor(port=port)
            except OSError:
                assert time.monotonic() < deadline
                time.sleep(.1)
        banks = mon.banks(); mon.resume(); paused = PausedViceMonitor(mon)
        def read(at, n=1):
            data = bytes(paused.read_mem(at, at+n-1, bank=banks['ram00'])); paused.resume(); return data
        def wait(predicate, label, limit):
            deadline = time.monotonic()+limit
            while time.monotonic() < deadline:
                if predicate(): return
                assert emu.poll() is None, 'x128 exited'
                time.sleep(.25)
            raise AssertionError(label)
        def ready(): return read(0x3d12) == b'\1' and read(0xd0) == b'\0'
        started = time.monotonic()
        wait(lambda: read(0x1c13, 6) == b'KES128' and read(0x3d60, 32) == header_bytes and ready(),
             'measurement desktop boot', seconds)
        wait(lambda: read(labels['vd_live']) == b'\1', 'VDC service open', 60)
        result['boot_seconds'] = round(time.monotonic()-started, 1)
        assert timing.decode_header(read(manifest['header'], timing.HEADER_BYTES))['phase'] == 0
        keys = int.from_bytes(read(0x3d13, 2), 'little')
        wait(ready, 'input ready', 30)
        with paused.paused('start-key'):
            for at, data in ((0x3d12, b'\0'), (0x34a, bytes([timing.KEY])), (0xd0, b'\1')):
                paused.write_mem(at, data, bank=banks['ram00'])
        wait(lambda: int.from_bytes(read(0x3d13, 2), 'little') == keys+1, 'start key consumed', 30)
        started = time.monotonic()
        wait(lambda: timing.decode_header(read(manifest['header'], timing.HEADER_BYTES))['phase'] == 3,
             'all updates recorded', seconds)
        result['run_wall_seconds'] = round(time.monotonic()-started, 1)
        raw_header = read(manifest['header'], timing.HEADER_BYTES)
        raw_arrays = read(manifest['arrays'], timing.COUNT*len(timing.ARRAYS))
        (work/'vice-header.bin').write_bytes(raw_header); (work/'vice-arrays.bin').write_bytes(raw_arrays)
        header, records = timing.decode(raw_header, raw_arrays)
        position = (int.from_bytes(read(labels['pm_x'], 2), 'little'), read(labels['pm_y'])[0])
        result.update(header=header, position=list(position), records=records,
                      video_standard='NTSC' if read(0x0a03) == b'\0' else 'PAL ($0a03=%02x)' % read(0x0a03)[0],
                      rs232_nmi_enable=read(0x0a0f)[0], summary=timing.summarize(header, records))
        save()
        assert result['summary']['calibration']['exact'], result['summary']['calibration']
        assert (header['count'], header['driven'], header['missing'], result['summary']['overflow']) == \
            (timing.COUNT, timing.COUNT, 0, 0), header
        assert position == timing.expected_position(timing.COUNT), (position, timing.expected_position(timing.COUNT))
        assert header['crb_halt'] == header['crb_before'] & 0x80 and result['rs232_nmi_enable'] == 0
        return result
    finally:
        save()
        if mon: mon.quit_emulator()
        else: emu.terminate()
        emu.wait(timeout=15); xv.stop(); log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--py65-frames', type=int, default=30, help='wiggle frames compared exactly in Py65 (default 30)')
    parser.add_argument('--seconds', type=int, default=900, help='bound for the VICE boot and for the run')
    args = parser.parse_args()
    assert 2 <= args.py65_frames <= 53, 'the Py65 comparison stays on the first downward leg'
    work = Path(tempfile.mkdtemp(prefix='kestrel-pointer-timing-vice-'))
    print('Pointer timing evidence:', work, flush=True)
    report = dict(passed=False, physical_hardware_io=False, work=str(work),
                  target_images={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted((ROOT/'target/native-desktop').glob('*.prg'))})
    def save(): args.report.write_text(json.dumps(report, indent=2)+'\n')
    try:
        build = work/'build'
        report['manifest'] = manifest = timing.build(build); save()
        print('Measurement build:', manifest['images']['disk_sha256'], flush=True)
        report['py65'] = py65(build, args.py65_frames); save()
        means = report['py65']['means']
        print(f'Py65: shipped frame {means["shipped_frame"]}, service {means["shipped_service"]}, '
              f'call {means["shipped_call"]}; records equal the shipped cycles; overhead '
              f'{means["overhead_per_frame"]} cycles per frame', flush=True)
        result = vice(build, manifest, work, report, save, args.seconds)
        summary = result['summary']
        lower = report['py65']['minimum']
        # IRQs and VIC-stolen cycles only add time: no update may undercut Py65.
        for name in ('service', 'call', 'gate_in', 'gate_out'):
            observed = summary[name]['min']
            assert observed >= lower[name], (name, 'VICE below the Py65 lower bound', observed, lower[name])
        report['comparison'] = dict(
            py65_shipped_mean={name: means['shipped_'+name] for name in ('service', 'call', 'gate_in', 'gate_out', 'frame')},
            vice_mean={name: summary[name]['mean'] for name in ('service', 'call', 'gate_in', 'gate_out')},
            vice_over_py65={name: round(summary[name]['mean']/means['shipped_'+name], 3)
                            for name in ('service', 'call', 'gate_in', 'gate_out')},
            vice_updates_with_irq=summary['updates_with_irq'])
        for name in ('service', 'call', 'gate_in', 'gate_out'):
            print(f'VICE {name}:', json.dumps(summary[name]), flush=True)
        print('VICE jiffies between updates:', summary['jiffies_between_updates'],
              'updates with an IRQ:', summary['updates_with_irq'], flush=True)
        report['target_images_unchanged'] = report['target_images'] == {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT/'target/native-desktop').glob('*.prg'))}
        assert report['target_images_unchanged']
        report['passed'] = True
        print('PASS: pointer timing build, Py65 exact records and VICE run', flush=True)
    finally:
        save()


if __name__ == '__main__':
    main()
