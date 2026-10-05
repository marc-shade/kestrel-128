#!/usr/bin/env python3
"""Build the native C128 kernel and allocated, autobooting D64/D81 disks.

Outputs stay in target/native so C64-mode app discovery cannot mistake a
native image for a legacy application. Uses the same 64tass/c1541 toolchain.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from native_image import seal
from native_module import seal as seal_module
from native_disk import create_boot_disk
from native_boot_pack import build as build_boot_file

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'target/native'


def build(*, out=None, desktop_boot=False):
    out = OUT if out is None else Path(out)
    out.mkdir(parents=True,exist_ok=True)
    build_kernel(out, desktop_boot=desktop_boot)
    for source,name in [('boot','boot'),('calc','calc'),('browser','browse'),('editor','editor')]:
        branch=['-B'] if source in ('browser','editor') or (source=='calc' and desktop_boot) else []
        defines=[]
        if source=='calc' and desktop_boot:defines=['-D','NATIVE_CALC_GRAPHICS=1']
        if source=='editor' and desktop_boot:defines=['-D','NATIVE_EDITOR_GRAPHICS=1']
        subprocess.run(['64tass','-a',*defines,*branch,str(ROOT/'src/native'/f'{source}.asm'),
                        '-o',str(out/f'{name}.prg'),'-L',str(out/f'{name}.lst')],check=True)
    (out/'calc.prg').write_bytes(seal((out/'calc.prg').read_bytes()))
    (out/'browse.prg').write_bytes(seal((out/'browse.prg').read_bytes()))
    editor=(out/'editor.prg').read_bytes()
    core_size=int.from_bytes(editor[10:12],'little')
    core=seal(editor[:core_size+2])
    (out/'editor.prg').write_bytes(core)
    position=core_size+2
    for name in (('edpick','edfind','edclip') if desktop_boot else ('edpick','edfind')):
        size=int.from_bytes(editor[position+8:position+10],'little')
        module=(0x6000+core_size).to_bytes(2,'little')+editor[position:position+size]
        (out/f'{name}.prg').write_bytes(seal_module(module,core))
        position+=size
    assert position==len(editor),'unexpected trailing editor module data'
    for disk_format in ('d64', 'd81'):
        kernel_dir = out if disk_format == 'd64' else out/'d81'
        if disk_format == 'd81':
            build_kernel(kernel_dir, desktop_boot=desktop_boot, boot_format=2)
        create_boot_disk(out/f'kestrel.{disk_format}', out/'boot.prg', {
            'u': kernel_dir/'kestrel-boot.prg', 'calc': out/'calc.prg',
            'browse': out/'browse.prg', 'editor': out/'editor.prg',
            'edpick.prg': out/'edpick.prg', 'edfind.prg': out/'edfind.prg',
            **({'edclip.prg':out/'edclip.prg'} if desktop_boot else {})})
    report = {p.relative_to(out).as_posix(): dict(bytes=p.stat().st_size,
                sha256=hashlib.sha256(p.read_bytes()).hexdigest())
              for p in sorted(out.rglob('*')) if p.suffix in ('.prg', '.d64', '.d81')}
    (out/'images.json').write_text(json.dumps(report,indent=2)+'\n')


def build_kernel(out, *, desktop_boot=False, boot_format=0):
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(['64tass', '-a', '-B', '-D', f'NATIVE_DESKTOP_BOOT={int(desktop_boot)}',
                    '-D', f'NATIVE_BOOT_FORMAT={boot_format}', str(ROOT/'src/native/kestrel.asm'),
                    '-o', str(out/'kestrel.prg'), '-l', str(out/'kestrel.sym'),
                    '-L', str(out/'kestrel.lst')], check=True)
    symbols=(out/'kestrel.sym').read_text()
    def address(name):
        match=re.search(r'^'+re.escape(name)+r'\s*=\s*\$([0-9a-fA-F]+)\s*$',symbols,re.M)
        assert match,name
        return int(match[1],16)
    layout=dict(boot_format=boot_format, desktop_boot=desktop_boot, main_start=0x1c01,main_end=address('native_code_end'),
                low_start=address('native_low_start'),low_end=address('native_low_end'),
                low_padded_end=address('native_low_padded_end'),low_limit=0x1c00,
                metadata_start=0x3800,metadata_end=address('native_metadata_end'),
                staging_start=address('native_low_image'),load_end=address('native_load_end'),
                service_start=address('native_service_start'),service_end=address('native_service_end'),
                module_code_start=address('module_load'),module_code_end=address('native_module_code_end'),
                module_context_start=address('module_source'),module_context_end=address('native_module_context_end'),
                module_gate_start=address('module_start'),module_gate_end=address('native_module_gate_end'),
                display_gate_start=address('display_show'),display_gate_end=address('native_display_gate_end'),
                display_show_start=address('display_prepare'),display_show_end=address('native_display_show_end'),
                display_restore_start=address('display_restore'),display_restore_end=address('native_display_restore_end'),
                display_close_start=address('display_close'),display_close_end=address('native_display_close_end'),
                source_path_start=0x3f00,source_path_end=0x4000,
                query_start=address('ultimate_query'),query_end=address('native_query_end'),
                boot_start=address('native_boot_image'),boot_end=address('native_boot_end'),
                sys_image_start=address('native_sys_image'),sys_start=address('native_sys_start'),
                sys_end=address('native_sys_end'),sys_limit=0x1000,
                keyin_start=address('native_keyin'),keyin_end=address('native_keyin_end'),
                command_start=address('ultimate_command'),command_end=address('native_command_end'),
                keycheck_start=address('native_keycheck'),keycheck_end=address('native_keycheck_end'),
                nmi_gate_start=address('native_nmi_gate'),nmi_gate_end=address('native_nmi_gate_end'),
                service_limit=0x5000,staging_limit=0x8000,app_base=0x6000,managed_pages=426,free_pages=[175,251])
    assert layout['main_end']<=layout['metadata_start'] and layout['low_padded_end']<=layout['low_limit']
    assert layout['metadata_end']<=layout['service_start']<layout['service_end']<=layout['service_limit']
    assert layout['service_limit']<=layout['staging_start'] and layout['load_end']<=layout['staging_limit']
    assert layout['boot_start']-layout['staging_start']==layout['low_padded_end']-layout['low_start']
    assert layout['boot_end']==layout['sys_image_start']<layout['load_end']
    assert layout['sys_start']==0x0c00<layout['sys_end']<=layout['sys_limit']==0x1000
    assert layout['load_end']-layout['sys_image_start']==layout['sys_end']-layout['sys_start']
    assert layout['module_code_start']==address('nu_code_end')<layout['module_code_end']<=0x4a00
    assert 0x4f20==layout['module_context_start']<layout['module_context_end']<=0x5000
    assert layout['query_start']==0x4b00<layout['query_end']<=0x4bfc
    assert layout['query_end']==layout['command_start']<layout['command_end']<=0x4bfc
    assert layout['command_start']<layout['command_end']<=0x4bfc
    assert layout['command_end']==layout['keyin_start']<layout['keyin_end']<=0x4bfc
    assert layout['main_start']<layout['keycheck_start']<layout['keycheck_end']<=0x3800
    assert layout['nmi_gate_start']==0x1bf0 and layout['nmi_gate_end']==0x1bf8
    assert layout['low_start']<layout['module_gate_start']<layout['module_gate_end']<=layout['low_limit']
    for start,end,next_boundary in (('display_gate_start','display_gate_end','metadata_start'),
                                   ('display_show_start','display_show_end',None),
                                   ('display_restore_start','display_restore_end','service_limit'),
                                   ('display_close_start','display_close_end','low_limit')):
        assert layout[start]<layout[end]<=(layout[next_boundary] if next_boundary else 0x4a00)
    assert (out/'kestrel.prg').stat().st_size==layout['load_end']-layout['main_start']+2
    (out/'layout.json').write_text(json.dumps(layout,indent=2)+'\n')
    build_boot_file(ROOT, out)


if __name__ == '__main__':
    build()
