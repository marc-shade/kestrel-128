#!/usr/bin/env python3
"""Check complete REU document/history bytes and reject unrelated corruption."""
import argparse
import json
from pathlib import Path
import tempfile
import traceback

from ci_native_history import History
from native_reu_document_check import ReuDocumentOracle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='kestrel-history-oracle-'))
    report = dict(passed=False, physical_hardware_io=False, work=str(work), documents=[])
    h = History(True)
    d = h.document
    oracle = ReuDocumentOracle(d.original, history=True)
    corrupt_at = None

    class Capture:
        def capture(self, label, *, bank=0, address, count):
            return bytes(d.m.bus.ram[bank][address:address+count])

    def read(address, count):
        return bytes(d.ram[address:address+count])

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
        text = h.edit(b'', 0, 0, b'ABC')
        d.append(text)
        oracle.history.edit(0, b'', b'ABC')
        check('typed', text, loaded=True)
        text = h.edit(text, 1, 1, b'XYZ')
        d.call('replace', pos=1, count=1, data=b'XYZ')
        oracle.replace(1, 1, b'XYZ')
        check('replaced', text)
        text = h.replay(text)
        position, count, data = oracle.history.replay()
        d.call('replace', pos=position, count=count, data=data)
        oracle.replace(position, count, data, record=False)
        check('undone', text)
        text = h.replay(text, True)
        position, count, data = oracle.history.replay(True)
        d.call('replace', pos=position, count=count, data=data)
        oracle.replace(position, count, data, record=False)
        check('redone', text)
        for corrupt_at in (oracle.history.entries[0]['base']+2000,
                           oracle.base+oracle.gap+17, len(oracle.expected)-1):
            try:
                check('corrupted-'+str(corrupt_at), text)
            except AssertionError:
                pass
            else:
                raise AssertionError('the oracle accepted history/document/unallocated corruption')
        corrupt_at = None
        # Clear leaves old physical bytes intact until subsequent reuse.
        h.call(24, b'\1')
        oracle.history.clear(True)
        check('cleared', text)
        d.call('dispose')
        h.close()
        report.update(passed=True, cases=[dict(name='whole REU oracle and three negative controls')],
                      instructions=h.b.instructions+d.instructions)
        print('PASS complete document/history REU oracle and negative controls', flush=True)
    except BaseException:
        report['error'] = traceback.format_exc()
        raise
    finally:
        args.report.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
