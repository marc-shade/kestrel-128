#!/usr/bin/env python3
"""Real-ROM scans with nested scanning, using each app's emitted KEYCHK image."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tests'), str(ROOT)]
import ci_native_keyboard as keyboard
from hwlib import lst_symbol
from native_app_pack import decode
from py65.devices.mpu6502 import MPU


def filter_image(name):
    prefix = 'native-desktop/' + ('claude-gui' if name == 'claude' else name)
    image = decode((ROOT/'target/native-desktop'/(name+'.prg')).read_bytes())
    origin = int.from_bytes(image[:2], 'little')
    start = lst_symbol(prefix, 'nk_filter_image')
    entry = lst_symbol(prefix, 'pk_entry')
    end = lst_symbol(prefix, 'pk_end')
    assert entry == 0x1014 and entry < end <= 0x1100
    data = image[2+start-origin:2+start-origin+end-entry]
    assert len(data) == end-entry and data[:7] == bytes.fromhex('0878488a489848')
    return data, lst_symbol(prefix, 'pk_next'), lst_symbol(prefix, 'pk_rejects')


def machine(image=None):
    bus = keyboard.machine()
    if image:
        data, chain, rejects = image
        ram = bus.ram[0]
        ram[0x1014:0x1014+len(data)] = data
        ram[chain:chain+2] = ram[0x33c:0x33e]
        ram[0x33c:0x33e] = b'\x14\x10'
        ram[rejects:rejects+2] = bytes(2)
    return bus


def scan(bus, mapping, pressed, row_signal=255):
    bus.config = mapping
    bus.pressed = set(pressed)
    bus.row_signal = row_signal
    keyboard.invoke(bus, 0xff9f)
    assert bus.config == mapping
    bus.config = 14
    return keyboard.invoke(bus, 0x1c3b).a


def nested_scan(bus, column, *, mapping=0):
    """Interrupt one ROM scan with a second scan on a separate stack frame.

    The real ROM explicitly executes CLI before SCNKEY. This models the
    nested scanner's effect on its shared zero page and CIA state; it does
    not model the raster/IEC timing that decides when the next IRQ arrives.
    """
    bus.config = mapping
    bus.pressed = {58}  # Control alone.
    cpu = MPU(memory=bus, pc=0xff9f)
    cpu.sp = 0xc0
    cpu.stPushWord(0xb7f)
    interrupted = False
    callbacks = []
    for _ in range(30000):
        if cpu.pc == 0xb80:
            break
        # $c59d is LDA $dc01 at the start of a column in the -05 ROM.
        if cpu.pc == 0xc59d and cpu.y == column*8 and not interrupted:
            interrupted = True
            inner = MPU(memory=bus, pc=0xff9f)
            inner.sp = 0x60
            inner.stPushWord(0xb7f)
            for _ in range(30000):
                if inner.pc == 0xb80:
                    break
                inner.step()
            else:
                raise AssertionError('nested ROM scanner did not return')
            assert inner.sp == 0x60
        if cpu.pc == 0xc6ad:
            callbacks.append(dict(key=cpu.a, index=cpu.y, modifiers=cpu.x,
                                  columns=bus.ports[0xdc00], extended=bus.ports[0xd02f]))
        cpu.step()
    else:
        raise AssertionError('outer ROM scanner did not return')
    assert interrupted and cpu.sp == 0xc0 and bus.config == mapping
    assert bus.ports[0xdc00] == 0x7f
    bus.config = 14
    key = keyboard.invoke(bus, 0x1c3b).a
    return key, callbacks


def run():
    cases, images = [], {}
    for column, expected in ((8, 53), (9, 45), (10, 46)):
        key, callbacks = nested_scan(machine(), column)
        assert key == expected and callbacks == [dict(key=expected,index=column*8+2,
            modifiers=4,columns=0xf7,extended=0xf7)]
        cases.append(dict(name='unfiltered nested ROM scan reproduces phantom keypad input',
                          column=column, key=key, callbacks=callbacks))
    for name in ('desktop','calc','editor','files','controls','paint','claude'):
        emitted = filter_image(name)
        images[name] = dict(bytes=len(emitted[0]), sha256=hashlib.sha256(emitted[0]).hexdigest())
        for mapping in (0,14):
            for column in range(11):
                bus = machine(emitted)
                key, callbacks = nested_scan(bus, column, mapping=mapping)
                assert key == 0 and callbacks == [], (name,mapping,column,key,callbacks)
                rejects = int.from_bytes(bus.ram[0][emitted[2]:emitted[2]+2], 'little')
                assert rejects == int(column >= 8), (name,mapping,column,rejects)
                assert bus.ram[0][0xd0:0xd3] == bytes(3)
                assert bus.ram[0][0x3d13:0x3d15] == bytes(2)
                assert keyboard.scan(bus, mmu=mapping) == 0
                assert keyboard.scan(bus, mmu=mapping,pressed=(10,)) == 65
        cases.append(dict(name=name+': all 11 nested scan positions in both mappings; false keys rejected and later typing retained'))
        for mapping in (0,14):
            for modifiers in ((),(15,),(58,)):
                for index in range(88):
                    pressed = {*modifiers,index}
                    plain, checked = machine(), machine(emitted)
                    want = scan(plain, mapping, pressed)
                    if name == 'claude' and index == 64 and modifiers == (58,):
                        assert want == 132
                        want = 255
                    got = scan(checked, mapping, pressed)
                    assert got == want, (name,mapping,modifiers,index,want,got)
                    assert checked.ports == plain.ports
        cases.append(dict(name=name+': all 88 matrix positions with plain/Shift/Control input in both mappings'))
        # Each externally grounded row is ambiguous even when the stale code
        # names a valid key. Both common mouse buttons are included.
        for row in range(8):
            bus = machine(emitted)
            assert scan(bus,14,(10,),row_signal=255^(1<<row)) == 0
        cases.append(dict(name=name+': all eight external low-row signals rejected'))
    return dict(passed=True,physical_hardware_io=False,cases=cases,images=images,
        reference_rom_sha256=hashlib.sha256(keyboard.heap.ROM.read_bytes()).hexdigest(),
        scope='Original ROM on a CIA matrix model; nested SCNKEY is injected explicitly, without modeling IRQ arrival timing')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();report=dict(passed=False,physical_hardware_io=False)
    try:
        report=run();print('PASS:',len(report['cases']),'ROM keyboard matrix groups',flush=True)
    except BaseException as error:
        report['error']=repr(error);raise
    finally:
        args.report.write_text(json.dumps(report,indent=2)+'\n')
