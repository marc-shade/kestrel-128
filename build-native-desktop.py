#!/usr/bin/env python3
"""Build the native graphical desktop and retain the diagnostic workspace."""
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
OUT = ROOT/'target/native-desktop'
from native_image import seal, validate
from native_module import seal as seal_module, validate as validate_module
from native_banked import seal as seal_banked, validate as validate_banked
from native_app_pack import build as pack_app, information as packed_information


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def build():
    native = module('native_builder', ROOT/'build-native.py')
    font = module('native_font', ROOT/'src/native/graphics/font.py')
    (ROOT/'src/native/graphics/font8.bin').write_bytes(font.font())
    (ROOT/'src/native/graphics/font5.bin').write_bytes(font.columns())
    from launcher_scene import write_assembly
    write_assembly(ROOT/'src/native/desktop')
    from native_vdc_scene import write_assembly as write_vdc
    write_vdc(ROOT/'src/native/desktop')
    from native_calc_scene import write_assembly as write_calculator
    write_calculator(ROOT/'src/native/calc')
    from paint_scene import write_assembly as write_paint
    write_paint(ROOT/'src/native/paint')
    from native_controls_scene import write_assembly as write_controls
    write_controls(ROOT/'src/native/controls')
    from native_files_scene import write_assembly as write_files
    write_files(ROOT/'src/native/files')
    from native_editor_scene import write_assembly as write_editor
    write_editor(ROOT/'src/native/editor')
    from native_picker_scene import write_assembly as write_picker
    write_picker(ROOT/'src/native/picker')
    native.build()
    native.build(out=OUT, desktop_boot=True)
    claude = module('claude_builder', ROOT/'build-native-claude.py').build(OUT)
    sheet = module('sheet_builder', ROOT/'build-native-sheet.py').build(OUT)
    for name in ('desktop', 'files', 'controls', 'paint', 'gemdesk', 'vt52'):
        subprocess.run(['64tass', '-a', '-B', str(ROOT/f'src/native/{name}.asm'),
                        '-o', str(OUT/f'{name}.prg'), '-l', str(OUT/f'{name}.sym'),
                        '-L', str(OUT/f'{name}.lst')], check=True)
        path = OUT/f'{name}.prg'
        module_parts = {'files': ('fspick', 'fsview', 'fsopen')}
        if name == 'gemdesk':
            # GEMDESK's modules are assembled one by one against the core's labels
            # (gemdesk.sym), so the core and all modules together are not one image.
            combined = path.read_bytes()
            core_size = int.from_bytes(combined[10:12], 'little')
            assert len(combined) == core_size+2, (len(combined), core_size)
            core = seal(combined)
            for part in ('gddlg', 'gdset', 'gdcpy', 'gdses', 'gdusb', 'gddsk', 'gdnew', 'gdfmt', 'gdprt'):
                binary = OUT/f'{part}.bin'
                subprocess.run(['64tass', '-a', '-B', '-b', str(ROOT/f'src/native/gemdesk-{part[2:]}.asm'),
                                '-I', str(OUT), '-o', str(binary), '-l', str(OUT/f'{part}.sym'),
                                '-L', str(OUT/f'{part}.lst')], check=True)
                body = binary.read_bytes()
                binary.unlink()
                assert int.from_bytes(body[8:10], 'little') == len(body), part
                payload = (0x6000+core_size).to_bytes(2, 'little')+body
                sealed = seal_module(payload, core)
                validate_module(sealed, core)
                (OUT/f'{part}.prg').write_bytes(sealed)
        if name in module_parts:
            combined = path.read_bytes()
            core_size = int.from_bytes(combined[10:12], 'little')
            core = seal(combined[:core_size+2])
            position = core_size+2
            for part in module_parts[name]:
                size = int.from_bytes(combined[position+8:position+10], 'little')
                payload = (0x6000+core_size).to_bytes(2, 'little')+combined[position:position+size]
                sealed = seal_module(payload, core)
                validate_module(sealed, core)
                (OUT/f'{part}.prg').write_bytes(sealed)
                position += size
            assert position == len(combined), f'unexpected trailing {name} module data'
            path.write_bytes(core)
        path.write_bytes(seal(path.read_bytes()))
        validate(path.read_bytes())
    subprocess.run(['64tass', '-a', '-B', str(ROOT/'src/native/vdc-service.asm'),
                    '-o', str(OUT/'vdsvc.prg'), '-l', str(OUT/'vdsvc.sym'),
                    '-L', str(OUT/'vdsvc.lst')], check=True)
    provider = OUT/'vdsvc.prg'
    provider.write_bytes(seal_banked(provider.read_bytes()))
    vdc_component = validate_banked(provider.read_bytes())
    packing = {}
    # The persistent AES (docs/NATIVE-AES.md), sealed for bank-1 $8700 (AE_BASE).
    subprocess.run(['64tass', '-a', '-B', str(ROOT/'src/native/aesvc.asm'),
                    '-o', str(OUT/'aesvc.prg'), '-l', str(OUT/'aesvc.sym'),
                    '-L', str(OUT/'aesvc.lst')], check=True)
    import native_banked
    AE_BASE = int(re.search(r'^AE_BASE = \$([0-9a-f]{4})', (ROOT/'src/native/aes-api.inc').read_text(), re.M).group(1), 16)
    aes_image = native_banked.seal((OUT/'aesvc.prg').read_bytes(), base=AE_BASE)
    (OUT/'aesvc.prg').write_bytes(aes_image)
    aes_component = native_banked.validate(aes_image, base=AE_BASE)
    assert 0x60+vdc_component['pages'] <= AE_BASE>>8, f"VDSVC ({vdc_component['pages']} pages from $6000) overlaps the AES"
    # The Calculator desk accessory (docs/GEM-LAYER-DESIGN.md), for bank-1 AC_BASE.
    AC_BASE = int(re.search(r'^AC_BASE = \$([0-9a-f]{4})', (ROOT/'src/native/aes-api.inc').read_text(), re.M).group(1), 16)
    subprocess.run(['64tass', '-a', '-B', str(ROOT/'src/native/acc-calc.asm'),
                    '-o', str(OUT/'desk1.acc'), '-l', str(OUT/'desk1.sym'),
                    '-L', str(OUT/'desk1.lst')], check=True)
    acc_image = native_banked.seal((OUT/'desk1.acc').read_bytes(), base=AC_BASE)
    (OUT/'desk1.acc').write_bytes(acc_image)
    native_banked.validate(acc_image, base=AC_BASE)
    for name in ('desktop','calc','editor','files','controls','claude','paint','sheet','gemdesk','vt52'):
        path = OUT/f'{name}.prg'
        runtime_end = {'claude':claude['runtime_end'], 'sheet':sheet['runtime_end']}.get(name)
        packed = pack_app(path.read_bytes(), runtime_end=runtime_end,
                          listing=OUT/f'{name}-pack.lst', symbols=OUT/f'{name}-pack.sym')
        path.write_bytes(packed)
        packing[name] = packed_information(packed)
        # Module identity remains the original source's checked NAPP identity.
        for part in {'editor':('edpick','edfind','edclip'),'files':('fspick','fsview','fsopen'),'sheet':('shfont','shcalc','shclip'),'gemdesk':('gddlg','gdset','gdcpy','gdses','gdusb','gddsk','gdnew','gdfmt','gdprt')}.get(name,()):
            module_path = OUT/f'{part}.prg'
            module_path.write_bytes(seal_module(module_path.read_bytes(),packed))
            validate_module(module_path.read_bytes(),packed)
    claude.update(validate((OUT/'claude.prg').read_bytes()),startup=packing['claude'],
                  sha256=packing['claude']['packed_sha256'])
    (OUT/'claude.json').write_text(json.dumps(claude,indent=2)+'\n')
    sheet.update(validate((OUT/'sheet.prg').read_bytes()),startup=packing['sheet'],
                 sha256=packing['sheet']['packed_sha256'])
    (OUT/'sheet.json').write_text(json.dumps(sheet,indent=2)+'\n')
    for disk_format in ('d64', 'd81'):
        workspace = OUT/f'workspace.{disk_format}'
        shutil.copyfile(ROOT/f'target/native/kestrel.{disk_format}', workspace)
        subprocess.run(['c1541', '-attach', str(workspace), '-delete', 'browse', 'calc', 'editor', 'edpick.prg', 'edfind.prg',
                        '-write', str(OUT/'calc.prg'), 'calc',
                        '-write', str(OUT/'desktop.prg'), 'browse',
                        '-write', str(OUT/'editor.prg'), 'editor',
                        '-write', str(OUT/'edpick.prg'), 'edpick.prg',
                        '-write', str(OUT/'edfind.prg'), 'edfind.prg',
                        '-write', str(OUT/'edclip.prg'), 'edclip.prg',
                        '-write', str(OUT/'files.prg'), 'files',
                        '-write', str(OUT/'fspick.prg'), 'fspick.prg',
                        '-write', str(OUT/'fsview.prg'), 'fsview.prg',
                        '-write', str(OUT/'fsopen.prg'), 'fsopen.prg',
                        '-write', str(OUT/'controls.prg'), 'ultimate',
                        '-write', str(OUT/'claude.prg'), 'claude',
                        '-write', str(OUT/'paint.prg'), 'paint',
                        '-write', str(OUT/'sheet.prg'), 'sheet',
                        '-write', str(OUT/'shfont.prg'), 'shfont.prg',
                        '-write', str(OUT/'shcalc.prg'), 'shcalc.prg',
                        '-write', str(OUT/'shclip.prg'), 'shclip.prg',
                        '-write', str(OUT/'vdsvc.prg'), 'vdsvc.prg'], check=True, capture_output=True)
        desktop = OUT/f'kestrel.{disk_format}'
        shutil.copyfile(workspace, desktop)
        subprocess.run(['c1541', '-attach', str(desktop), '-delete', 'u',
                        '-write', str((OUT if disk_format == 'd64' else OUT/'d81')/'kestrel-boot.prg'), 'u'], check=True, capture_output=True)
    # GEM profile (docs/GEM-DESKTOP.md): the GEM desktop is "browse", so apps
    # return to it; the card launcher stays available as "cards". D81 only.
    gem = OUT/'gem.d81'
    shutil.copyfile(OUT/'kestrel.d81', gem)
    subprocess.run(['c1541', '-attach', str(gem), '-delete', 'browse',
                    '-write', str(OUT/'gemdesk.prg'), 'browse',
                    '-write', str(OUT/'desktop.prg'), 'cards',
                    '-write', str(OUT/'aesvc.prg'), 'aesvc.prg',
                    '-write', str(OUT/'gddlg.prg'), 'gddlg.prg',
                    '-write', str(OUT/'gdset.prg'), 'gdset.prg',
                    '-write', str(OUT/'gdcpy.prg'), 'gdcpy.prg',
                    '-write', str(OUT/'gdses.prg'), 'gdses.prg',
                    '-write', str(OUT/'gdusb.prg'), 'gdusb.prg',
                    '-write', str(OUT/'gddsk.prg'), 'gddsk.prg',
                    '-write', str(OUT/'gdnew.prg'), 'gdnew.prg',
                    '-write', str(OUT/'gdfmt.prg'), 'gdfmt.prg',
                    '-write', str(OUT/'gdprt.prg'), 'gdprt.prg',
                    '-write', str(OUT/'desk1.acc'), 'desk1.acc',
                    '-write', str(OUT/'vt52.prg'), 'vt52'], check=True, capture_output=True)
    images = {p.relative_to(OUT).as_posix(): dict(bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
              for p in sorted(OUT.rglob('*')) if p.suffix in ('.prg', '.acc', '.d64', '.d81')}
    (OUT/'images.json').write_text(json.dumps(images, indent=2)+'\n')
    deployment = dict(abi='1.14', direct_desktop_disk='kestrel.d64',
                      workspace_with_desktop_disk='workspace.d64',
                      standalone_diagnostic_disk='../native/kestrel.d64',
                      d81=dict(direct_desktop_disk='kestrel.d81',
                               workspace_with_desktop_disk='workspace.d81',
                               standalone_diagnostic_disk='../native/kestrel.d81',
                               kernel='d81/kestrel.prg', boot_format=2),
                      boot_format=0, boot_format_address=0x3de4,
                      desktop=validate((OUT/'desktop.prg').read_bytes()),
                      calculator=validate((OUT/'calc.prg').read_bytes()),
                      files=validate((OUT/'files.prg').read_bytes()),
                      controls=validate((OUT/'controls.prg').read_bytes()),
                      claude=validate((OUT/'claude.prg').read_bytes()),
                      paint=validate((OUT/'paint.prg').read_bytes()),
                      sheet=validate((OUT/'sheet.prg').read_bytes()),
                      gem=dict(disk='gem.d81', browse='gemdesk.prg', cards='desktop.prg',
                               aesvc=aes_component,
                               gemdesk=validate((OUT/'gemdesk.prg').read_bytes()),
                               vt52=validate((OUT/'vt52.prg').read_bytes())),
                      surface_pages=36, vdc_component=vdc_component, packed_apps=packing,
                      free_pages_at_desktop={str(kib):426-36-pages-vdc_component['pages']-validate((OUT/'desktop.prg').read_bytes())['pages']
                                             for kib,pages in ((16,64),(64,72))},
                      free_pages_at_desktop_reu=426-36-vdc_component['pages']-validate((OUT/'desktop.prg').read_bytes())['pages'],
                      selection_state_address=0x3d2f, selection_lifetime='until native restart',
                      disk_entries={'u': 'kestrel-boot.prg', 'browse': 'desktop.prg',
                                    'vdsvc.prg': 'vdsvc.prg',
                                    'shfont.prg': 'shfont.prg', 'shcalc.prg': 'shcalc.prg', 'shclip.prg': 'shclip.prg',
                                    'files': 'files.prg', 'calc': 'calc.prg',
                                    'fspick.prg': 'fspick.prg', 'fsview.prg': 'fsview.prg', 'fsopen.prg': 'fsopen.prg',
                                    'editor': 'editor.prg', 'edpick.prg': 'edpick.prg',
                                    'edfind.prg': 'edfind.prg', 'edclip.prg':'edclip.prg',
                                    'ultimate': 'controls.prg', 'claude': 'claude.prg', 'paint': 'paint.prg', 'sheet': 'sheet.prg'})
    (OUT/'deployment.json').write_text(json.dumps(deployment, indent=2)+'\n')
    from build_listing_paths import normalize      # last: no step reads these files after it
    normalize(ROOT, [ROOT/'target/native', ROOT/'target/native-desktop'])
    print(f'Native graphical desktop disk: {desktop}')
    print(f'Native diagnostic workspace disk: {ROOT/"target/native/kestrel.d64"}')


if __name__ == '__main__':
    build()
