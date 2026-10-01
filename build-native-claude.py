#!/usr/bin/env python3
"""Build the native MIT Claude terminal, including its owned BSS and C stack."""
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
from native_image import seal, validate

ROOT = Path(__file__).resolve().parent


def build(out=None):
    out = Path(out) if out is not None else ROOT/'target/native-desktop'
    out.mkdir(parents=True, exist_ok=True)
    obj = out/'claude-build'
    obj.mkdir(exist_ok=True)
    src = ROOT/'src/native/claude'
    from native_claude_scene import write_assembly
    write_assembly(src)
    subprocess.run(['64tass','-a','-B','-b',str(src/'gui.asm'),
                    '-o',str(obj/'gui.bin'),'-l',str(out/'claude-gui.sym'),
                    '-L',str(out/'claude-gui.lst')], check=True)
    symbols = {name:int(value,16) for name,value in re.findall(
        r'^(\w+)\s*=\s*\$([0-9a-fA-F]+)\s*$',(out/'claude-gui.sym').read_text(),re.M)}
    exports = {name:value for name,value in symbols.items() if name.startswith(
        ('cg_','pm_','pk_','gui_','bk_','bp_','vd_','vm_','vs_','ru_'))}
    exports.update({'_gui_'+name:symbols['gui_'+name] for name in ('begin','poll','key','end','dirty_all','clip_prepare','clip_chunk')})
    exports['_gui_clip_length']=symbols['cp_length']
    exports['_gui_vdc_end']=symbols['cg_vdc_close']
    exports.update({'_gui_'+name:symbols['cg_'+name] for name in
                    ('live','dirty','top','controls_dirty','font_hi','bitmap','font_ram',
                     'terminal_read','terminal_restore','view','cursor_row','cursor_col',
                     'vdc_owned','recovery','retiring','clip_count','clip_status','paste_active')})
    glue = ['.segment "GUI"', '.incbin '+json.dumps(str(obj/'gui.bin'))]
    glue += [f'.export {name} := ${value:04x}' for name,value in sorted(exports.items())]
    (obj/'gui.s').write_text('\n'.join(glue)+'\n')
    subprocess.run(['ca65','-o',str(obj/'gui.o'),str(obj/'gui.s')],check=True)
    for name in ('main.c', 'c128hw.s', 'terminal.s', 'startup.s'):
        subprocess.run(['cl65', '-t', 'c128', '-O', '-g', '-c', '-o',
                        str(obj/(Path(name).stem+'.o')), str(src/name)], check=True)
    subprocess.run(['ld65', '-C', str(src/'kestrel.cfg'), '-m', str(out/'claude.map'),
                    '-Ln', str(out/'claude.lbl'), '-o', str(out/'claude.prg'),
                    str(obj/'startup.o'), str(obj/'gui.o'), str(obj/'main.o'), str(obj/'c128hw.o'), str(obj/'terminal.o'),
                    'c128.lib'], check=True)
    image = out/'claude.prg'
    image.write_bytes(seal(image.read_bytes()))
    info = validate(image.read_bytes())
    stack = re.search(r'^CSTACK\s+[0-9A-Fa-f]+\s+([0-9A-Fa-f]+)\s',
                      (out/'claude.map').read_text(),re.M)
    assert stack, 'Claude link map is missing the C stack extent'
    info['runtime_end'] = int(stack[1],16)+1
    assert 0x6000+info['bytes'] <= info['runtime_end'] <= 0x6000+info['pages']*256
    info['sha256'] = hashlib.sha256(image.read_bytes()).hexdigest()
    (out/'claude.json').write_text(json.dumps(info, indent=2)+'\n')
    print('Native Claude:', json.dumps(info))
    return info


if __name__ == '__main__':
    build()
