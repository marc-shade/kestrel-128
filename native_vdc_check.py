"""Independent raw VRAM and full palette-frame checks for the native VDC shell."""
import hashlib
from pathlib import Path
from hwlib import lst_symbol
from native_pointer_check import check_canvas
from native_vdc_scene import bitmap, attributes, pointer_bitmap, pixels
from native_vdc_mirror import bitmap as mirror_bitmap, attributes as mirror_attributes, pixels as mirror_pixels


def owned_service(capture, read_app, folder, label, image_prefix):
    """Read only the loaded component's owned extent, including its real REU state."""
    symbol = lambda name: lst_symbol(image_prefix,name)
    assert bytes(read_app(symbol('bk_state'),1)) == b'\2'
    assert bytes(read_app(symbol('bk_busy'),1)) == b'\0'
    token = bytes(read_app(symbol('bk_handle'),4))
    assert 1 <= token[0] <= 32
    record = bytes(read_app(0x3c00+(token[0]-1)*8,8))
    expected = (Path(__file__).resolve().parent/'target/native-desktop/vdsvc.prg').read_bytes()[2:34]
    assert record[:4] == bytes([32,1,0x60,expected[10]]) and record[4:7] == token[1:]
    assert bytes(read_app(0x3960,record[3])) == bytes([token[0]])*record[3]
    header = capture.capture(label+'-component-header',bank=1,address=0x6000,count=32)
    assert int.from_bytes(header[22:24],'little') == symbol('bk_callback')
    normalized = bytearray(header);normalized[22:24] = bytes(2)
    assert normalized == expected
    (folder/(label+'-component-header.bin')).write_bytes(header)
    def read(name, count, offset=0):
        address = lst_symbol('native-desktop/vdsvc',name)+offset
        assert 0x6020 <= address < address+count <= 0x6000+int.from_bytes(expected[8:10],'little')
        raw = capture.capture(label+'-component-'+name,bank=1,address=address,count=count)
        (folder/(label+'-component-'+name+'.bin')).write_bytes(raw)
        return raw
    return read, dict(handle=token.hex(),record=record.hex(),header_sha256=hashlib.sha256(header).hexdigest())


def capture_snapshot(capture, read_app, folder, label, *, image_prefix='native-desktop/desktop', reu_snapshot=None):
    symbol = lambda name: lst_symbol(image_prefix,name)
    state = bytes(read_app(symbol('vd_phase'),7))
    assert state[:2] == b'\2\1' and state[3] == 0
    handle = bytes(read_app(symbol('vd_handle'),4))
    assert 1 <= handle[0] <= 32
    component, code = owned_service(capture,read_app,folder,label,image_prefix)
    actual_state = component('vd_phase',7)
    assert actual_state[:4]+actual_state[5:] == state[:4]+state[5:]
    extra = dict(component=code)
    assert component('vs_reu',1) == bytes(read_app(symbol('vs_reu'),1))
    if bytes(read_app(symbol('vs_reu'),1)) == b'\1':
        assert reu_snapshot is not None, 'REU backup requires an independent emulator snapshot'
        token = bytes(read_app(symbol('vs_token'),8))
        assert component('vs_token',8) == token
        record = component('ru_records',8,(handle[0]-1)*8)
        assert token[:4] == handle and record[0] == 32 and record[5:] == handle[1:]
        assert token[4:] == component('ru_cookie',4)
        assert int.from_bytes(record[3:5],'little') == (state[6]+15)//16
        memory, info = reu_snapshot(label)
        address, count = int.from_bytes(record[1:3],'little')*4096, state[6]*256
        assert address+count <= len(memory)
        raw = memory[address:address+count]
        extra.update(storage='reu',token=token.hex(),reu_snapshot=info,reu_address=address)
    else:
        record = bytes(read_app(0x3c00+(handle[0]-1)*8,8))
        assert record[0] == 32 and record[1] in (0,1) and record[3] == state[6] and record[4:7] == handle[1:]
        address, count = record[2]*256, record[3]*256
        raw = b''.join(capture.capture(label+f'-snapshot-{offset:04x}',bank=record[1],
            address=address+offset,count=min(2000,count-offset)) for offset in range(0,count,2000))
    (folder/(label+'-snapshot.bin')).write_bytes(raw)
    saved = bytes(read_app(symbol('vd_saved'),14))
    assert component('vd_saved',14) == saved
    (folder/(label+'-saved-registers.bin')).write_bytes(saved)
    return raw, dict(label=label,handle=handle.hex(),record=record.hex(),base=state[5]*256,
        pages=state[6],color=bool(state[2]),saved_registers=saved.hex(),sha256=hashlib.sha256(raw).hexdigest(),**extra)


def saved_region(capture, read_app, folder, label, *, address=0x3000, count=4096):
    """Reconstruct pre-desktop logical VRAM using the snapshot and untouched RAM."""
    snapshot, info = capture_snapshot(capture,read_app,folder,label)
    mode64 = bool(bytes.fromhex(info['saved_registers'])[11]&16)
    def physical(at):
        if mode64: return at if info['color'] else (at&255)|((at&0x7e00)>>1)
        return (at&0x80ff)|((at&0x3f00)<<1)|(at&0x100) if info['color'] else at&0x3fff
    positions = [physical(at) for at in range(address,address+count)]
    outside = sorted(set(at for at in positions if not info['base'] <= at < info['base']+len(snapshot)))
    untouched = {}
    while outside:
        first = outside[0]; end = first+1
        while end-first < min(2000,len(outside)) and outside[end-first] == end: end += 1
        data = capture.capture(label+f'-untouched-{first:04x}',mode=1,address=first,count=end-first)
        untouched.update(zip(range(first,end),data)); outside = outside[end-first:]
    result = bytes(snapshot[at-info['base']] if info['base'] <= at < info['base']+len(snapshot) else untouched[at] for at in positions)
    (folder/(label+'-original-vdc.bin')).write_bytes(result)
    return result, info


def capture_frame(capture, read_app, canvas, folder, label, selected, *, color=None, error=0,
                  surface_data=None, image_prefix='native-desktop/desktop'):
    symbol = lambda name: lst_symbol(image_prefix, name)
    state = bytes(read_app(symbol('vd_phase'), 7))
    (folder/(label+'-vdc-state.bin')).write_bytes(state)
    assert state[:2] == b'\2\1' and state[3] == 0, ('VDC phase/live/fault', state.hex())
    actual_color = bool(state[2])
    if color is not None: assert actual_color == color
    base, pages = (0x4000,72) if actual_color else (0,64)
    assert state[5:] == bytes((base>>8,pages))
    point = bytes(read_app(symbol('vd_pointer_visible'), 4))
    visible, x, y = bool(point[0]), int.from_bytes(point[1:3],'little')*2, point[3]
    def region(name, address, count):
        data = b''.join(capture.capture(label+'-'+name+f'-{offset:04x}',mode=1,
            address=address+offset,count=min(2000,count-offset)) for offset in range(0,count,2000))
        (folder/(label+'-'+name+'.bin')).write_bytes(data)
        return data
    expected = (pointer_bitmap(bitmap(selected,error),x,y,visible) if surface_data is None else
                mirror_bitmap(surface_data,actual_color,x=x//2,y=y,pointer=visible))
    actual = region('vdc-bitmap',base,16000)
    assert actual == expected, ('VDC bitmap',label,[(i,a,b) for i,(a,b) in enumerate(zip(actual,expected)) if a!=b][:16])
    if actual_color:
        assert region('vdc-attributes',0x8000,2000) == (attributes(selected) if surface_data is None else mirror_attributes(surface_data))
    # canvas=None: physical-hardware workflows have no emulator frame; the
    # VDC phase, complete bitmap and attributes above are still checked.
    rectangle = None
    if canvas is not None:
        raw = canvas()
        (folder/(label+'-vdc-canvas.bin')).write_bytes(raw)
        if surface_data is None:
            expected_pixels = pixels(selected,color=actual_color,x=x,y=y,visible=visible,error=error)
            rows = [expected_pixels[at:at+640] for at in range(0,128000,640)]
        else:
            rows = mirror_pixels(surface_data,actual_color,x=x//2,y=y,pointer=visible)
        rectangle = check_canvas(raw,rows)
    return dict(label=label,selected=selected,error=error,color=actual_color,position=[x,y],
                pointer_visible=visible,rectangle=rectangle,bitmap_sha256=hashlib.sha256(expected).hexdigest(),
                pixels=128000 if canvas is not None else 0,snapshot_pages=pages)
