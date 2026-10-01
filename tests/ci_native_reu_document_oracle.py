#!/usr/bin/env python3
"""Check the VICE physical-byte oracle against the shipped Editor machine code."""
import argparse
import json
from pathlib import Path
import tempfile

from ci_native_document_reu import SharedDocument
from native_reu_document_check import ReuDocumentOracle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-reu-document-oracle-'))
    report = dict(passed=False, physical_hardware_io=False, work=str(work), documents=[])
    d = SharedDocument(kib=512)
    oracle = ReuDocumentOracle(d.original)

    class Capture:
        def capture(self, label, *, bank=0, address, count):
            return bytes(d.m.bus.ram[bank][address:address+count])

    def read(address, count):
        return bytes(d.ram[address:address+count])

    corrupt_at = None
    def snapshot(label):
        memory = bytearray(d.m.bus.reu_ram)
        if corrupt_at is not None:
            memory[corrupt_at] ^= 1
        assert memory == oracle.expected, 'complete independently modeled REU'
        return bytes(memory), dict(bytes=len(memory))

    def check(label, data, loaded=False):
        evidence = oracle.capture(Capture(), read, work, label, snapshot, data, loaded=loaded)
        report['documents'].append(evidence)

    try:
        d.append(b'C128 TEXT')
        check('typed', b'C128 TEXT', loaded=True)
        d.call('insert', pos=2, data=b'X')
        oracle.insert(2, b'X')
        check('inserted', b'C1X28 TEXT')
        d.call('dispose')
        large = (b'0123456789ABCDEF\r\n'*8000)[:131113]
        d.append(large)
        check('large', large, loaded=True)
        d.call('insert', pos=98305, data=b'REU96')
        oracle.insert(98305, b'REU96')
        edited = large[:98305]+b'REU96'+large[98305:]
        check('edited', edited)
        # The checker must detect damage in unused gap capacity as well as
        # outside every document; logical-byte equality alone is insufficient.
        for corrupt_at in (oracle.base+oracle.gap+17, len(oracle.expected)-1):
            try:
                check('corrupted-'+str(corrupt_at), edited)
            except AssertionError:
                pass
            else:
                raise AssertionError('the physical oracle accepted a changed byte')
        corrupt_at = None
        d.call('dispose')
        d.append(edited)
        check('reopened', edited, loaded=True)
        d.dispose()
        report.update(passed=True, instructions=d.instructions, calls=d.calls)
        print('PASS: VICE oracle matches complete REU after edits/reopen and rejects gap/unallocated-byte corruption', flush=True)
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
