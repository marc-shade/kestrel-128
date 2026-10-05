"""Audit running native code, retaining each explicitly declared mutable byte."""
import hashlib
import json
from pathlib import Path
import re


class RunningLayout:
    def __init__(self, root, *, image_dir=None):
        root = Path(root)
        image_dir = root/'target/native' if image_dir is None else Path(image_dir)
        self.layout = json.loads((image_dir/'layout.json').read_text())
        self.image = (image_dir/'kestrel.prg').read_bytes()
        self.syms = {m[1]: int(m[2], 16) for m in re.finditer(
            r'^(\w+)\s*=\s*\$([0-9a-f]+)',
            (image_dir/'kestrel.sym').read_text(), re.M)}
        origin = int.from_bytes(self.image[:2], 'little')
        assert origin == self.layout['main_start']
        assert origin + len(self.image) - 2 == self.layout['load_end']
        self.regions = {}
        for name, start, end, source in (
            ('low', self.layout['low_start'], self.layout['low_padded_end'], self.layout['staging_start']),
            ('main', origin, self.layout['main_end'], origin),
            ('service', self.layout['service_start'], self.layout['service_end'], self.layout['service_start']),
            ('sys', self.layout['sys_start'], self.layout['sys_end'], self.layout['sys_image_start'])):
            expected = self.image[2+source-origin:2+source-origin+end-start]
            assert len(expected) == end-start
            self.regions[name] = (start, expected)
        self.mutable = {}
        self.declarations = []

        def declare(name, start, end, kind):
            assert start < end
            assert any(base <= start < end <= base+len(data) for base, data in self.regions.values()), name
            for address in range(start, end):
                assert address not in self.mutable, (name, address)
                self.mutable[address] = name
            self.declarations.append(dict(name=name, start=start, bytes=end-start, kind=kind))

        # These are the operands actually modified by the assembly routines.
        # The opcode byte is always compared with the pinned boot image.
        for name in ('heap_buffer_read', 'heap_buffer_write', 'field_record_read',
                     'field_record_write', 'field_read', 'field_write',
                     'ui_text_byte',
                     'app_image_store', 'app_buffer_read', 'fs_buffer_read',
                     'fs_buffer_write', 'nd_path_byte', 'nu_command_byte',
                     'nu_data_store', 'module_store', 'rc_window'):
            declare(name, self.syms[name]+1, self.syms[name]+3, 'modified 16-bit address operand')
        declare('app_zero', self.syms['app_zero']+2, self.syms['app_zero']+3,
                'modified high address byte; low operand and opcode remain checked')

        # Explicit assembly data declarations; alignment/padding stays checked.
        for first, last, length in (
            ('hbank', 'hbyte', 1), ('field_state', 'field_columns', 1),
            ('l_handle', 'l_left', 2), ('l_entry', 'l_entry', 2),
            ('f_mtrack', 'f_dskip', 1),
            ('f_filename', 'f_left', 2), ('nd_slot', 'nd_path', 256),
            ('ui_handles', 'ui_test_operation', 1), ('ui_system_device', 'ui_browser_stage', 1),
            ('nu_high', 'nu_part_state', 1), ('rc_key', 'rc_chunklen', 1),
            ('v_tag', 'v_port', 1)):
            declare(first, self.syms[first], self.syms[last]+length, 'declared mutable state')
        for offset in (8, 11):
            declare(f'f_mcommand_digits_{offset}', self.syms['f_mcommand']+offset,
                    self.syms['f_mcommand']+offset+2, 'decimal track/sector command digits')
        for name, length in (('N_BROWSERPATH', 256), ('NU_COMMAND', 516),
                             ('N_UPATH', 256), ('N_USTATUS', 32)):
            declare(name, self.syms[name], self.syms[name]+length, 'declared service buffer')

    def compare(self, observations):
        assert set(observations) == set(self.regions)
        result = dict(passed=True, kernel_sha256=hashlib.sha256(self.image).hexdigest(),
                      layout=self.layout, declarations=self.declarations, regions=[],
                      mutable_state_semantics='Captured in full; checked separately by the workflow',
                      immutable_bytes=0, mutable_bytes=0, changed_mutable_bytes=0,
                      unexpected_changes=[])
        for name, (start, expected) in self.regions.items():
            actual = observations[name]
            assert len(actual) == len(expected), name
            mutable = [i for i in range(len(actual)) if start+i in self.mutable]
            changes = [dict(address=start+i, initial=expected[i], observed=actual[i],
                            declaration=self.mutable[start+i])
                       for i in mutable if actual[i] != expected[i]]
            unexpected = [dict(region=name, address=start+i, initial=expected[i], observed=actual[i])
                          for i in range(len(actual)) if start+i not in self.mutable and actual[i] != expected[i]]
            result['unexpected_changes'].extend(unexpected)
            result['immutable_bytes'] += len(actual)-len(mutable)
            result['mutable_bytes'] += len(mutable)
            result['changed_mutable_bytes'] += len(changes)
            result['regions'].append(dict(name=name, start=start, bytes=len(actual),
                sha256=hashlib.sha256(actual).hexdigest(), immutable_bytes=len(actual)-len(mutable),
                mutable_bytes=len(mutable), changed_mutable_bytes=changes))
        result['passed'] = not result['unexpected_changes']
        return result


def verify_running_layout(capture, root, label, *, image_dir=None):
    layout = RunningLayout(root, image_dir=image_dir)
    observations = {}
    for name, (start, expected) in layout.regions.items():
        data = b''.join(capture.capture(f'{label}-{name}-{offset:04x}', address=start+offset,
                       count=min(2000, len(expected)-offset))
                       for offset in range(0, len(expected), 2000))
        (capture.work/f'{label}-{name}.bin').write_bytes(data)
        observations[name] = data
    result = layout.compare(observations)
    (capture.work/f'{label}-layout.json').write_text(json.dumps(result, indent=2)+'\n')
    assert result['passed'], ('running kernel bytes differ outside declared mutable locations', result['unexpected_changes'][:20])
    return result
