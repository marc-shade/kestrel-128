#!/usr/bin/env python3
"""Offline controls for the running-kernel integrity audit; no machine I/O."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_running_layout import RunningLayout

parser = argparse.ArgumentParser()
parser.add_argument('--report', type=Path, required=True)
parser.add_argument('--observed', type=Path)
parser.add_argument('--desktop-boot', action='store_true')
args = parser.parse_args()
layout = RunningLayout(ROOT, image_dir=ROOT/('target/native-desktop' if args.desktop_boot else 'target/native'))
report = dict(passed=False, physical_hardware_io=False, cases=[])
initial = {name: data for name, (start, data) in layout.regions.items()}
result = layout.compare(initial)
assert result['passed']
report['cases'].append(dict(name='initial image', immutable_bytes=result['immutable_bytes'],
                            mutable_bytes=result['mutable_bytes']))
changed = {name: bytes(value^255 if start+i in layout.mutable else value for i, value in enumerate(data))
           for name, (start, data) in layout.regions.items()}
result = layout.compare(changed)
assert result['passed'] and result['changed_mutable_bytes'] == result['mutable_bytes']
report['cases'].append(dict(name='all declared mutable bytes change', changed_bytes=result['changed_mutable_bytes']))
for name, symbol in [('low', 'heap_buffer_read'), ('main', 'app_image_store'), ('service', 'module_store')]:
    changed = dict(initial)
    damaged = bytearray(changed[name])
    address = layout.syms[symbol]
    damaged[address-layout.regions[name][0]] ^= 1
    changed[name] = bytes(damaged)
    result = layout.compare(changed)
    assert not result['passed'] and len(result['unexpected_changes']) == 1
    assert result['unexpected_changes'][0]['address'] == address
    report['cases'].append(dict(name='reject altered opcode beside mutable operand', region=name, symbol=symbol, address=address))
for symbol, offset in [('f_mcommand', 10), ('N_BROWSERPATH', 256)]:
    address = layout.syms[symbol]+offset
    name = next(name for name, (start, data) in layout.regions.items() if start <= address < start+len(data))
    changed = dict(initial)
    damaged = bytearray(changed[name])
    damaged[address-layout.regions[name][0]] ^= 1
    changed[name] = bytes(damaged)
    result = layout.compare(changed)
    assert not result['passed'] and len(result['unexpected_changes']) == 1
    report['cases'].append(dict(name='reject constant/padding between mutable fields', address=address))
if args.observed:
    for label in ('resident-boot', 'resident-return'):
        observations = {name: (args.observed/f'{label}-{name}.bin').read_bytes() for name in layout.regions}
        result = layout.compare(observations)
        assert result['passed']
        report['cases'].append(dict(name='recheck captured running code', label=label,
            immutable_bytes=result['immutable_bytes'], changed_mutable_bytes=result['changed_mutable_bytes']))
report['passed'] = True
args.report.write_text(json.dumps(report, indent=2)+'\n')
print(f'PASS: {len(report["cases"])} running-layout controls; no physical machine I/O')
