"""Controlled key injection demonstrates why a strict capture must reject activity."""
from contextlib import contextmanager

from hwlib import lst_symbol
from launcher_scene import CARDS
from native_vdc_scene import bitmap as vdc_bitmap,pointer_bitmap
from native_capture import NativeCapture, ROOT
from native_capture_transport import PausedViceMonitor
from native_running_layout import RunningLayout


def run_input_capture(mon, work, report, key):
    paused = PausedViceMonitor(mon)
    injected = []

    @contextmanager
    def batch(label):
        # Deliberately inject after all CPU VDC reads and before restoration.
        # This models a possible scheduling window, not the physical key source.
        if label == 'input-vdc-restore':
            for value in (0x11, 0x11):
                key(value)
                injected.append(value)
        with paused.paused(label):
            yield

    # Since 5d04173 the desktop's VDC holds its bitmap scene at the owned base;
    # derive base and pointer from the desktop's VDC state.
    symbol = lambda name: lst_symbol('native-desktop/desktop', name)
    state = bytes(mon.read_mem(symbol('vd_phase'), symbol('vd_phase')+6))
    point = bytes(mon.read_mem(symbol('vd_pointer_visible'), symbol('vd_pointer_visible')+3))
    handle = bytes(mon.read_mem(symbol('gd_handle'), symbol('gd_handle')+3))
    owner = bytes(mon.read_mem(0x3c00+(handle[0]-1)*8, 0x3c00+(handle[0]-1)*8+6)); mon.resume()
    assert state[:2] == b'\2\1' and state[3] == 0, state.hex()
    assert 1 <= handle[0] <= 32 and owner == bytes([32,0,0xc0,36])+handle[1:], (handle.hex(), owner.hex())
    scene = pointer_bitmap(vdc_bitmap(0), int.from_bytes(point[1:3],'little')*2, point[3], bool(point[0]))
    capture = NativeCapture(paused, work, quiet=.1, kernel_prefix='native-desktop', batch=batch)
    report['captures'] = capture.records
    report['paused_capture_batches'] = paused.batches
    try:
        capture.capture('input-vdc', mode=1, address=state[5]*256, count=2000)
    except AssertionError as error:
        # The message names only the first eight changes per region; the
        # complete change lists are checked below.
        assert str(error).startswith('native metadata/ABI changed during observation')
        assert 'resident low kernel changed during observation' in str(error)
        report['expected_capture_error'] = str(error)
    else:
        raise AssertionError('Activity during observation must be rejected')
    assert injected == [0x11, 0x11]
    assert (work/'input-vdc.bin').read_bytes() == scene[:2000]
    row = capture.records[0]
    assert not row['restored']
    assert [failure['region'] for failure in row['borrower_failures']] == ['metadata', 'resident']
    assert row['input_observation']['keys_before'] == 0 and row['input_observation']['keys_after'] == 2
    assert row['input_observation']['last_key_after'] == 17
    before = (work/'input-vdc-borrower-metadata-before.bin').read_bytes()
    after = (work/'input-vdc-borrower-metadata-after.bin').read_bytes()
    changes = [dict(address=0x3800+i, before=a, after=b)
               for i, (a, b) in enumerate(zip(before, after)) if a != b]
    # Two Downs: N_KEYS 2, N_LASTKEY 17, N_DESKTOPSEL 2. The redraw (gd_highlight,
    # f99fa51 seven cards) colours each card's two rows through gfx_colors on the
    # desktop surface; its last call leaves N_HANDLE = gd_handle and N_OFFSET/N_COUNT
    # at the last card's second color row, columns 2..37.
    offset = 8192+(CARDS[-1]//8+1)*40+2
    wanted = dict(zip(range(0x3d04,0x3d0c), handle+offset.to_bytes(2,'little')+(36).to_bytes(2,'little')))
    wanted.update({0x3d13:2, 0x3d14:0, 0x3d15:17, 0x3d2f:2})
    expected = [dict(address=at, before=before[at-0x3800], after=value)
                for at, value in sorted(wanted.items()) if before[at-0x3800] != value]
    assert changes == expected, (changes, expected)
    assert all(row['borrower_checks'][name]['matches'] for name in ('output', 'scratch'))
    resident = (work/row['borrower_checks']['resident']['after_file']).read_bytes()
    before_resident = (work/'input-vdc-borrower-resident-before.bin').read_bytes()
    resident_changes = [dict(address=0x1300+i, before=a, after=b)
                        for i, (a, b) in enumerate(zip(before_resident, resident)) if a != b]
    layout = RunningLayout(ROOT, image_dir=ROOT/'target/native-desktop')
    # Heap transfers retain their last byte and pointers in explicitly mutable
    # state; the last colour written is the unselected card's $1b.
    assert layout.syms['hbyte'] == 0x17d0 and layout.mutable[0x17d0] == 'hbank'
    assert resident[0x17d0-0x1300] == 0x1b
    assert all(change['address'] in layout.mutable for change in resident_changes), resident_changes
    report['input_control'] = dict(passed=True, injected_keys=injected,
        expected_input_metadata_changes=changes, physical_failure_cause_proven=False,
        activity_rejected=True, original_vdc_payload_matches=True,
        resident_after_changes=resident_changes, all_first_readbacks_retained=True,
        resident_immutable_bytes_match=True)
