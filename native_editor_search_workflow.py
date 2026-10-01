"""ROM-input find/replace workflow with complete independent screen checks."""
import hashlib

from native_capture import ROOT, expected_screen, verify_boot_layout
from native_browser_check import disk_records


def editor_search_workflow(client,disk,data_disk,fixtures,fmt,report,save):
    report.update(events=client.events,frames=client.frames,captures=client.capture.records,
                  heap_observations=client.heaps,editor_states=client.states,
                  ram_observations=client.observations,modules=client.modules)
    report['resident_boot']=verify_boot_layout(client.capture)
    protected=[]
    for bank in (0,1):
        client.key(ord('1')+bank);client.key(ord('A'));page=client.read(0x3d03)[0]
        client.key(ord('W'));client.key(ord('V'));assert client.read(0x3d16)==b'\0'
        protected.append((bank,page))
    original_keys=client.read(0x1000,256)
    (client.work/'function-keys-before.bin').write_bytes(original_keys)
    client.key(ord('B'),quiet=client.scan_quiet)
    client.select([r['name'] for r in disk_records(disk.read_bytes())].index(b'EDITOR'))
    client.key(13,quiet=client.scan_quiet);client.editor_active=True
    client.prompt(0x8c,'9')
    for _ in range(fmt):client.key(0x8b)
    device=9
    def text(value):
        for key in value.encode():client.key(key)
    def check(label,data,cursor,**extra):
        value=client.check(label,data,cursor,device=device,fmt=fmt,**extra);save();return value
    def query(value,key=6,fold=False):
        client.key(key);client.key(21);text(value)
        if bool(client.read(client.addresses['ed_s_pending_case'])[0])!=fold:client.key(9)
    def replacement(value,new,choice,fold=False):
        query(value,18,fold);client.key(13);text(new);client.key(13);client.key(ord(choice))

    check('search-new',b'',0)
    client.key(14);check('search-next-without-query',b'',0,mode=6,field='')
    client.key(27)
    raw=b'ABABA AbA abc ABC';text(raw.decode())
    query('ABA');check('search-query-field',raw,len(raw),dirty=True,mode=6,field='ABA',search_case=0)
    client.key(13);check('search-first-wrapped',raw,0,dirty=True,status=14)
    client.key(14);check('search-overlap',raw,2,dirty=True,status=13)
    client.key(14);check('search-wrap',raw,0,dirty=True,status=14)
    query('aba',fold=True);check('search-ignore-case-field',raw,0,dirty=True,mode=6,field='aba',search_case=1)
    client.key(13);client.key(14);client.key(14)
    check('search-mixed-case-result',raw,6,dirty=True,status=13)
    query('ABSENT');client.key(13);check('search-no-match',raw,6,dirty=True,status=15)
    query('ABA',18,True);client.key(13);text('X');client.key(13)
    check('search-one-all-choice',raw,6,dirty=True,mode=9)
    client.key(27);check('search-cancel-keeps-original',raw,6,dirty=True)
    replacement('ABA','X','A',True);want=b'XBA X abc ABC'
    check('search-all-nonoverlap',want,4,dirty=True,status=17,replacements=2)
    replacement('abc','Q','O',True);want=b'XBA X Q ABC'
    check('search-replace-one',want,6,dirty=True,status=17,replacements=1)
    replacement('ABC','','A',True);want=b'XBA X Q '
    check('search-empty-replacement',want,8,dirty=True,status=17,replacements=1)
    client.prompt(0x86,'SMALL');check('search-small-saved',want,8,name='SMALL',status=1)
    report['additional_saved_files']={'SMALL':want.hex()}
    (client.work/'small-expected.seq').write_bytes(want)
    client.key(0x87);client.prompt(0x85,'SMALL');check('search-small-reopened',want,0,name='SMALL')

    client.key(0x87);raw=fixtures['large'];client.prompt(0x85,'LARGE')
    check('search-large-open',raw,0,name='LARGE')
    at=65534
    if raw[at-1:at+1]==b'\r\n':at+=1
    client.prompt(0x88,f'{at:06X}');text('FINDME');want=raw[:at]+b'FINDME'+raw[at:]
    client.key(0x89);query('FINDME');client.key(13)
    check('search-across-64k',want,at,name='LARGE',dirty=True,status=13)
    replacement('FINDME','MATCH','O');want=raw[:at]+b'MATCH'+raw[at:]
    check('search-replaced-across-64k',want,at,name='LARGE',dirty=True,status=17,replacements=1)
    # The separately bound file picker still fits while the large document and
    # both 8 KiB workspace allocations remain live.
    client.key(0x86);text('SAVED');client.key(9,quiet=client.scan_quiet)
    report['document_during_dialog']=client.dialog_document('search-picker-document',want);save()
    client.key(27);check('search-picker-return',want,at,name='LARGE',dirty=True,mode=2,field='SAVED')
    client.module_state('search-picker-retained',2)
    client.key(13,quiet=client.scan_quiet);check('search-large-saved',want,at,name='SAVED',status=1)
    (client.work/'saved-expected.seq').write_bytes(want)
    client.key(0x87);client.prompt(0x85,'SAVED');check('search-large-reopened',want,0,name='SAVED')
    query('MATCH');client.key(13);check('search-reopened-result',want,at,name='SAVED',status=13)
    client.key(27,quiet=client.scan_quiet);client.editor_active=False;client.selected=0
    assert client.read(0x1000,256)==original_keys
    (client.work/'function-keys-after.bin').write_bytes(client.read(0x1000,256))
    client.key(27);client.heap_equal('search-workspace-after-editor',(143,219,30))
    for bank,page in protected:
        client.key(ord('1')+bank);client.key(ord('V'));assert client.read(0x3d16)==b'\0'
        actual=client.capture.capture(f'search-workspace-bank-{bank}',bank=bank,address=page*256,count=2000)
        assert actual==bytes((i&255)^(i>>8)^(0xa5 if bank else 0) for i in range(2000))
        client.key(ord('F'))
    client.frames_equal('search-workspace-restored',lambda columns:expected_screen(columns,1))
    client.heap_equal('search-all-memory-released',(175,251,32))
    assert client.read(0x98)==b'\0' and client.read(0x3de0,4)==bytes(4)
    report.update(native_checks_passed=True,large_input_bytes=len(raw),saved_bytes=len(want),edit_offset=at,
                  saved_sha256=hashlib.sha256(want).hexdigest(),data_device=device,format=fmt,
                  function_key_bytes_restored=256,rom_getin_expansion_verified=True,
                  native_workspace_verify_bytes=8192,all_owned_memory_and_files_released=True)
    save()
