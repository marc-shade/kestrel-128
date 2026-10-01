"""Independent physical-REU document oracle; does not invoke the document API."""
from ci_native_reu_calc import component


def extent(editor, state):
    assert state['backing'] == 1 and state['chunks'] == 1
    token = state['handles'][:8]
    assert 1 <= token[0] <= 32
    assert component(editor, 'bm_lease') == component(editor, 'ru_active') == b'\1'
    assert token[4:] == component(editor, 'ru_cookie', 4)
    # Match the token's native app generation to the independently decoded heap.
    assert editor.ram[0x3860] == token[4]
    app_at = 0x3c00+(token[4]-1)*8
    app = bytes(editor.ram[app_at:app_at+8])
    assert app[:3] == bytes([32, 0, 0x60]) and app[4:7] == token[5:]
    records = component(editor, 'ru_records', 256)
    at = (token[0]-1)*8
    record = records[at:at+8]
    assert record[0] == 33 and record[5:8] == token[1:4]
    start, pages = int.from_bytes(record[1:3], 'little'), int.from_bytes(record[3:5], 'little')
    assert pages*4096 == state['capacity'] and pages > 0
    assert (start+pages)*4096 <= len(editor.bus.reu_ram)
    for other in range(0, 256, 8):
        if other == at or not records[other]:
            continue
        first = int.from_bytes(records[other+1:other+3], 'little')
        count = int.from_bytes(records[other+3:other+5], 'little')
        assert start+pages <= first or first+count <= start
    return start*4096, pages*4096


def physical_bytes(editor, state):
    start, count = extent(editor, state)
    return bytes(editor.bus.reu_ram[start:start+count])
