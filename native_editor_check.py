"""Independent text/layout and stored-byte checks for the native editor."""
import hashlib
import re
import shutil
import subprocess
import time

from hwlib import lst_symbol
from native_browser_check import BrowserClient,disk_records,browser_screen
from native_capture import ROOT,expected_screen,verify_boot_layout,wait
from native_field_check import field_cells

STATUS=(
    'HOME: LINE START  CTRL-E: LINE END',
    'SAVED AND REOPENED: ALL BYTES VERIFIED',
    'DISK ERROR; DOCUMENT KEPT',
    'NOT ENOUGH MEMORY; DOCUMENT KEPT',
    'POSITION OR DEVICE IS OUT OF RANGE',
    'DOCUMENT MEMORY ERROR; CANNOT SAVE',
    'FILE EXISTS; CHOOSE ANOTHER NAME',
    'SAVE FAILED; FILE MAY BE PARTIAL',
    'CANCELLED; DOCUMENT KEPT',
    'DISK CLOSE FAILED; DOCUMENT KEPT',
    'CANCELLED; PARTIAL FILE MAY REMAIN',
    'OPENED; OLD BUFFER CLEANUP FAILED',
    'INPUT UNAVAILABLE; ESC RETURNS',
    'FOUND AT CURSOR; CTRL-N FINDS NEXT',
    'FOUND AFTER WRAP; CTRL-N FINDS NEXT',
    'NO MATCH; DOCUMENT KEPT',
    'WORKING; ESC STOPS. CHANGED: ',
    'REPLACED (HEX): ',
    'CANCELLED; CHANGES KEPT (HEX): ',
    'NO MEMORY; CHANGES KEPT (HEX): ',
    'COPIED TO CLIPBOARD',
    'PASTED FROM CLIPBOARD',
    'SELECT TEXT FIRST',
    'CLIPBOARD IS EMPTY',
    'CLIPBOARD LIMIT: 15 KIB',
    'CLIPBOARD ERROR; TEXT RETAINED',
    'CLIPBOARD CLEARED',
    'UNDONE',
    'REDONE',
    'UNDO HISTORY CLEARED',
    'EDITED; UNDO UNAVAILABLE',
    'NO UNDO OR REDO AVAILABLE',
    'PRINTED',
    'NO PRINTER',
)


def document_lines(data):
    lines=[];start=0
    for match in re.finditer(rb'\r\n|\r|\n',data):
        lines.append((start,data[start:match.start()],match.group()))
        start=match.end()
    lines.append((start,data[start:],b''))
    return lines


def editor_screen(columns,data,cursor,*,name='',dirty=False,device=8,fmt=0,
                  view=0,horizontal=0,mode=0,field='',status=0,field_caret=None,field_view=None,
                  search_case=0,replacements=0,selection=None):
    assert 0<=cursor<=len(data) and columns in (40,80)
    def tail(text,limit):
        visible=''.join(char if 32<=ord(char)<127 else '.' for char in text)
        return visible if len(visible)<=limit else '<'+visible[-(limit-1):]
    message=STATUS[status]+(f'{replacements:06X}' if 16<=status<20 else '')
    focused=bool(mode and mode not in (5,9) and status not in (3,4,9) and status<12)
    case='ANY: ' if search_case else 'CASE: '
    prefix=('OPEN: ','SAVE AS: ','BYTE (HEX): ','DOS CONTEXT: ' if fmt==3 else 'IEC DEVICE: ',
            '', 'FIND '+case, 'REPL '+case, 'WITH: ')[mode-1] if focused else ''
    field_width=columns-(31 if mode in (1,2) else 24)
    if mode and status not in (3,4,9) and status<12:
        message='DISCARD DOCUMENT CHANGES? Y/N' if mode==5 else 'REPLACE: O ONE / A ALL / ESC CANCEL' if mode==9 else (
            prefix+' '*field_width
            +(' ENTER/ESC TAB FILES' if mode in (1,2) else ' ENTER/ESC'))
    headers=['KESTREL TEXT EDITOR','NAME: '+tail(name or 'UNTITLED',columns-8)+('*' if dirty else ''),
             f'BYTES: {len(data):06X} AT: {cursor:06X} '+('DOS' if fmt==3 else 'IEC')+f':{device:02} '+('D64','D71','D81','ULT')[fmt],
             'F1 OPEN F3 SAVE AS F5 NEW F7 GO TO','F2 TOP F4 END F6 FORMAT F8 DEVICE',
             'ARROWS MOVE  DEL ERASE  ESC RETURN',message]
    assert all(len(line)<columns for line in headers)
    def code(value):return value-64 if 64<=value<96 else value-32 if 96<=value<128 else value
    screen=bytearray(b' '*(columns*25))
    for row,line in enumerate(headers):
        screen[row*columns:row*columns+len(line)]=bytes(code(ord(char)) for char in line)
    for row,line in ((23,'CTRL-F FIND CTRL-N NEXT CTRL-R REPLACE'),
                     (24,'TAB IN QUERY: CASE / IGNORE CASE')):
        screen[row*columns:row*columns+len(line)]=bytes(code(ord(char)) for char in line)
    if focused:
        at=6*columns+len(prefix)
        screen[at:at+field_width]=field_cells(field,field_width,field_caret,field_view)
    if selection is not None:
        assert 0<=selection[0]<=selection[1]<=len(data),selection
    lines=document_lines(data);starts=[line[0] for line in lines]
    assert view in starts,(view,starts[:20])
    first=starts.index(view);width=columns-2;caret=False
    for row in range(16):
        base=(row+7)*columns
        screen[base]=ord('<') if horizontal else 32
        if first+row>=len(lines):continue
        start,content,separator=lines[first+row]
        visible=content[horizontal:horizontal+width]
        screen[base+1:base+1+len(visible)]=bytes(code(value if 32<=value<127 else 46) for value in visible)
        screen[base+columns-1]=ord('>') if len(content)>horizontal+width else 32
        end=start+len(content)
        if selection is not None:
            low,high=selection
            for col in range(len(visible)):
                if low<=start+horizontal+col<high:screen[base+1+col]|=128
            end_column=len(content)-horizontal
            if separator and low<=end<high and 0<=end_column<=width:
                screen[base+1+end_column]|=128
        owns_cursor=start<=cursor<end+len(separator) or (not separator and start<=cursor<=end)
        if owns_cursor and not caret:
            column=min(cursor-start,len(content))-horizontal
            assert 0<=column<=width,(columns,cursor,start,horizontal)
            screen[base+1+column]|=128;caret=True
    assert caret,'cursor must remain visible on both displays'
    return bytes(screen)


def prepare_editor(work,fmt=0):
    disk=work/'native.d64';shutil.copyfile(ROOT/'target/native/kestrel.d64',disk)
    # Keep the complete system disk on 8 and the document disk on 9. A D64
    # cannot hold the expanded editor, all system apps and two >64-KiB files.
    data_disk=work/('documents.'+('d64','d71','d81')[fmt])
    subprocess.run(['c1541','-format','documents,02',('d64','d71','d81')[fmt],str(data_disk)],
                   check=True,capture_output=True)
    fixtures=dict(note=b'ONE "QUOTED" LINE\r\nTWO\nTHREE\r'+bytes([0,255])+b' END\r\n'+b'X'*110+b'\r\nLAST',
                  empty=b'',large=(b'0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ\r\n'*1800)[:66053])
    for name,data in fixtures.items():
        source=work/(name+'.seq');source.write_bytes(data)
        subprocess.run(['c1541','-attach',str(data_disk),'-write',str(source),name+',s'],check=True,capture_output=True)
    if not fmt:
        bam=data_disk.read_bytes()[357*256:358*256]
        free=sum(bam[track*4] for track in range(1,36) if track!=18)
        assert free>=(len(fixtures['large'])+3+253)//254,'editor fixture cannot hold the complete saved copy'
    return disk,data_disk,fixtures


class EditorClient(BrowserClient):
    """Drive actual GETIN, including its programmable-key expansion path."""
    def __init__(self,mon,work,*,quiet=.2,scan_quiet=2,capture_quiet=.2,poll=.1,key_timeout=300):
        super().__init__(mon,work,quiet,scan_quiet,capture_quiet)
        self.poll,self.key_timeout=poll,key_timeout
        self.editor_active=False;self.states=[];self.observations=[];self.modules=[]
        self.addresses={name:lst_symbol('native/editor',name) for name in (
            'ed_active','ed_cursor','ed_view','ed_horizontal','ed_mode','ed_status','ed_device','ed_format',
            'ed_name','ed_field','ed_field_len','ed_field_cursor','ed_field_views','ed_field_filter','d_states','ed_saved_keys',
            'ed_s_pending_case','ed_s_count')}
        self.key_codes=bytes.fromhex('8589868a878b888c8384')

    def key(self,value,quiet=None):
        wait(lambda:self.read(0x3d12)==b'\1' and self.read(0xd0,3)==bytes(3),'native editor ready',120)
        before=int.from_bytes(self.read(0x3d13,2),'little');started=time.monotonic();last_notice=started
        self.put(0x3d12,b'\0')
        expansion=self.editor_active and value in self.key_codes
        if expansion:
            index=self.key_codes.index(value)
            assert self.read(0x1000,20)==bytes([1]*10)+self.key_codes
            # This is the ROM GETIN expansion path, not a physical matrix key.
            # Publish count/index together after the foreground loop is idle.
            self.put(0xd1,bytes([1,index]))
        else:
            self.put(0x34a,bytes([value]));self.put(0xd0,b'\1')
        time.sleep(self.quiet if quiet is None else quiet)
        while True:
            state=self.read(0x3d12,3)
            if state[0]==1 and int.from_bytes(state[1:],'little')==(before+1)&65535:break
            elapsed=time.monotonic()-started
            assert elapsed<self.key_timeout,('editor key timeout',value,elapsed,state.hex())
            if time.monotonic()-last_notice>=30:
                print(f'Native editor key {value:02X}: waiting for complete operation ({elapsed:.0f}s)',flush=True)
                last_notice=time.monotonic()
            time.sleep(self.poll)
        # KEYIDX can remain nonzero after the final expanded byte. KYNDX=0
        # means no expansion is pending; reset the idle index for the next key.
        assert self.read(0xd0,2)==bytes(2)
        self.put(0xd2,b'\0')
        self.events.append(dict(key=value,rom_expansion=expansion,elapsed_seconds=round(time.monotonic()-started,3),
                                app_state=self.read(0x3d20,13).hex(),files=self.read(0x3d80,0x64).hex()))

    def prompt(self,key,text,confirm=None):
        self.key(key)
        for value in text.encode():self.key(value)
        self.key(13,quiet=self.scan_quiet)
        if confirm is not None:self.key(ord(confirm),quiet=self.scan_quiet)

    def cpu_read(self,label,address,count):
        direct=self.read(address,count)
        actual=self.capture.capture(label,address=address,count=count)
        (self.work/(label+'-dma.bin')).write_bytes(direct)
        self.observations.append(dict(label=label,address=address,count=count,direct_matches_cpu=direct==actual,
                                      direct_sha256=hashlib.sha256(direct).hexdigest(),cpu_sha256=hashlib.sha256(actual).hexdigest()))
        return actual

    def check(self,label,data,cursor,*,dirty=False,name='',status=0,mode=0,device=8,fmt=0,
              field=None,field_caret=None,replacements=0,search_case=None):
        addresses=self.addresses;base=addresses['ed_active']
        raw=self.cpu_read(label+'-app-state',base,addresses['ed_field_filter']-base+1)
        def number(name,size=1):return int.from_bytes(raw[addresses[name]-base:addresses[name]-base+size],'little')
        def string(name):return raw[addresses[name]-base:addresses[name]-base+256].split(b'\0')[0].decode()
        context=self.cpu_read(label+'-document-state',addresses['d_states']+number('ed_active'),128)
        search=self.cpu_read(label+'-search-state',addresses['ed_s_pending_case'],5)
        assert addresses['ed_s_count']==addresses['ed_s_pending_case']+2
        changed=int.from_bytes(search[2:5],'little')
        if status>=16:assert changed==replacements,(label,changed,replacements)
        if search_case is not None:assert search[0]==search_case,(label,search[0],search_case)
        actual=dict(cursor=number('ed_cursor',3),view=number('ed_view',3),horizontal=number('ed_horizontal',3),
                    length=int.from_bytes(context[:3],'little'),dirty=context[12],chunks=context[13],fault=context[14],
                    search_case=search[0],replacements=changed,
                    name=string('ed_name'),status=number('ed_status'),mode=number('ed_mode'),
                    device=number('ed_device'),fmt=number('ed_format'),field=string('ed_field'),
                    field_caret=number('ed_field_cursor'),
                    field_views=list(raw[addresses['ed_field_views']-base:addresses['ed_field_views']-base+2]))
        self.states.append(dict(label=label,**actual))
        assert (actual['cursor'],actual['length'],actual['dirty'],actual['fault'])==(cursor,len(data),int(dirty),0),(label,actual)
        assert (actual['name'],actual['status'],actual['mode'],actual['device'],actual['fmt'])==(name,status,mode,device,fmt),(label,actual)
        if field is not None:assert actual['field']==field,(label,actual)
        if field_caret is not None:assert actual['field_caret']==field_caret,(label,actual)
        self.frames_equal(label,lambda columns:editor_screen(columns,data,cursor,name=name,dirty=dirty,device=device,fmt=fmt,
                          view=actual['view'],horizontal=actual['horizontal'],mode=mode,field=string('ed_field'),status=status,
                          field_caret=number('ed_field_cursor'),field_view=raw[addresses['ed_field_views']-base+int(columns==80)],
                          search_case=search[0],replacements=changed))
        assert self.read(0x98)==b'\0' and self.read(0x3de0,4)==bytes(4),'editor retained a file channel'
        if len(data)>65536:
            records=self.read(0x3c00,256);banks=set()
            for index in range(context[13]):
                handle=context[16+index*4:20+index*4];record=records[(handle[0]-1)*8:handle[0]*8]
                assert record[0]==32 and record[3]==16 and record[4:7]==handle[1:]
                banks.add(record[1])
            assert banks=={0,1},banks
        return actual

    def module_state(self,label,state):
        from native_module import validate
        app=(ROOT/'target/native/editor.prg').read_bytes()
        module=(ROOT/'target/native/edpick.prg').read_bytes()
        info=validate(module,app)
        record=self.cpu_read(label+'-state',0x3d17,5)
        assert record[4]==state and record[3]==0,(label,record.hex())
        token=int.from_bytes(record[:3],'little')
        assert bool(token)==bool(state)
        assert self.cpu_read(label+'-parent',0x3d60,32)==app[2:34]
        header=self.cpu_read(label+'-header',info['origin'],16)
        assert header==(module[2:18] if state else bytes(16))
        if state:
            assert self.cpu_read(label+'-manifest',0x3d50,16)==header
            at=lst_symbol('native/editor','ed_picker_token')
            assert self.cpu_read(label+'-token',at,3)==record[:3]
        source=self.cpu_read(label+'-source',lst_symbol('native/kestrel','m_source_device'),3)
        item=dict(label=label,state=state,token=token,source_device=source[0],source_format=source[1],
                  source_parent_length=source[2],**info)
        self.modules.append(item)
        return item

    def dialog_document(self,label,expected):
        """Observe every owned document byte while the picker has focus."""
        self.module_state(label+'-module',3)
        active=self.cpu_read(label+'-active',self.addresses['ed_active'],1)[0]
        context=self.cpu_read(label+'-context',self.addresses['d_states']+active,128)
        records=self.read(0x3c00,256);physical=bytearray();handles=[]
        for index in range(context[13]):
            handle=context[16+index*4:20+index*4]
            record=records[(handle[0]-1)*8:handle[0]*8]
            assert record[0]==32 and record[3]==16 and record[4:7]==handle[1:]
            chunk_label=f'{label}-chunk-{index:02}'
            data=b''.join(self.capture.capture(f'{chunk_label}-part-{offset:04x}',bank=record[1],
                          address=record[2]*256+offset,count=min(2000,4096-offset))
                          for offset in range(0,4096,2000))
            (self.work/(chunk_label+'.bin')).write_bytes(data)
            physical.extend(data)
            handles.append(dict(handle_hex=handle.hex(),bank=record[1],page=record[2],sha256=hashlib.sha256(data).hexdigest()))
        length=int.from_bytes(context[:3],'little');gap=int.from_bytes(context[3:6],'little')
        end=int.from_bytes(context[6:9],'little');capacity=int.from_bytes(context[9:12],'little')
        assert 0<=gap<=end<=capacity==len(physical)
        actual=bytes(physical[:gap]+physical[end:capacity])
        assert length==len(expected) and actual==expected and not context[14]
        return dict(label=label,bytes=length,sha256=hashlib.sha256(actual).hexdigest(),
                    gap=gap,gap_end=end,capacity=capacity,handles=handles,all_bytes_equal=True)


def editor_workflow(client,disk,data_disk,fixtures,fmt,report,save):
    report.update(events=client.events,frames=client.frames,captures=client.capture.records,
                  heap_observations=client.heaps,editor_states=client.states,ram_observations=client.observations,
                  modules=client.modules)
    report['resident_boot']=verify_boot_layout(client.capture)
    protected=[]
    for bank in (0,1):
        client.key(ord('1')+bank);client.key(ord('A'));page=client.read(0x3d03)[0]
        client.key(ord('W'));client.key(ord('V'));assert client.read(0x3d16)==b'\0'
        protected.append((bank,page))
    original_keys=client.read(0x1000,256);(client.work/'function-keys-before.bin').write_bytes(original_keys)
    client.key(ord('B'),quiet=client.scan_quiet)
    boot_records=disk_records(disk.read_bytes())
    client.select([r['name'] for r in boot_records].index(b'EDITOR'))
    client.key(13,quiet=client.scan_quiet);client.editor_active=True
    assert client.cpu_read('editor-saved-function-keys',client.addresses['ed_saved_keys'],256)==original_keys
    client.heap_equal('empty-editor-with-workspace',(143-((ROOT/'target/native/editor.prg').read_bytes()[12]),219,29))
    if data_disk!=disk:
        client.prompt(0x8c,'9')
    for _ in range(fmt):client.key(0x8b)
    device=9 if data_disk!=disk else 8
    def check(label,data,cursor,**extra):
        actual=client.check(label,data,cursor,device=device,fmt=fmt,**extra);save();return actual
    check('editor-new',b'',0)
    client.module_state('editor-module-empty',0);save()
    data_records=disk_records(data_disk.read_bytes(),fmt)
    client.key(0x85);client.key(9,quiet=client.scan_quiet)
    client.module_state('editor-module-cold-picker',3)
    report['module_cold_picker_seconds']=client.events[-1]['elapsed_seconds']
    client.frames_equal('editor-open-file-picker',lambda columns:browser_screen(columns,data_records,0,device,fmt,picker=True));save()
    client.key(13);check('editor-open-file-selected',b'',0,mode=1)
    client.module_state('editor-module-returned',2);save()
    raw=fixtures['note'];client.key(13,quiet=client.scan_quiet);check('editor-open-mixed-quotes',raw,0,name='NOTE')
    client.prompt(0x88,'000005');check('editor-caret-inside-quote',raw,5,name='NOTE')
    client.key(ord('!'));want=raw[:5]+b'!'+raw[5:];check('editor-insert',want,6,dirty=True,name='NOTE')
    client.prompt(0x85,'EMPTY');check('editor-discard-prompt',want,6,dirty=True,name='NOTE',mode=5)
    client.key(ord('N'));check('editor-declined-discard',want,6,dirty=True,name='NOTE')
    client.prompt(0x85,'MISSING',confirm='Y');check('editor-failed-open-retains',want,6,dirty=True,name='NOTE',status=2)
    client.prompt(0x85,'EMPTY',confirm='Y');check('editor-empty-file',b'',0,name='EMPTY')
    raw=fixtures['large'];client.prompt(0x85,'LARGE');check('editor-large-open',raw,0,name='LARGE')
    client.prompt(0x88,'010001');at=65537
    if raw[at-1:at+1]==b'\r\n':at+=1
    check('editor-cursor-over-64k',raw,at,name='LARGE')
    for value in b'C128':client.key(value)
    client.key(20);want=raw[:at]+b'C12'+raw[at:]
    check('editor-large-edited',want,at+3,dirty=True,name='LARGE')
    (client.work/'saved-expected.seq').write_bytes(want)
    client.key(0x86)
    for key in b'SAVXD':client.key(key)
    for key in (0x13,0x1d,0x1d,0x1d,4,ord('E')):client.key(key)
    check('editor-save-field-middle',want,at+3,dirty=True,name='LARGE',mode=2,field='SAVED',field_caret=4)
    field_before=client.cpu_read('editor-field-before-picker',client.addresses['ed_field_len'],8)
    client.key(9,quiet=client.scan_quiet)
    client.frames_equal('editor-save-file-picker',lambda columns:browser_screen(columns,data_records,0,device,fmt,picker=True));save()
    report['document_during_dialog']=client.dialog_document('editor-picker-document',want);save()
    client.key(27);check('editor-picker-cancel-keeps-document',want,at+3,dirty=True,name='LARGE',mode=2,field='SAVED',field_caret=4)
    client.module_state('editor-module-large-cancel',2);save()
    field_after=client.cpu_read('editor-field-after-picker',client.addresses['ed_field_len'],8)
    assert field_before==field_after
    report['field_dialog_retention']=dict(before_hex=field_before.hex(),after_hex=field_after.hex(),
                                        text='SAVED',caret=4,identical=True);save()
    client.key(9,quiet=client.scan_quiet);client.key(ord('S'))
    check('editor-save-folder-selected',want,at+3,dirty=True,name='LARGE',mode=2)
    client.key(13,quiet=client.scan_quiet);check('editor-saved-verified',want,at+3,name='SAVED',status=1)
    client.prompt(0x86,'SAVED');check('editor-existing-file-rejected',want,at+3,name='SAVED',status=6)
    client.key(0x87);check('editor-new-after-save',b'',0)
    client.prompt(0x85,'SAVED');check('editor-reopened-saved',want,0,name='SAVED')
    client.prompt(0x88,f'{at:06X}');check('editor-reopened-edit-position',want,at,name='SAVED')
    client.key(27,quiet=client.scan_quiet);client.editor_active=False;client.selected=0
    assert client.read(0x1000,256)==original_keys
    (client.work/'function-keys-after.bin').write_bytes(client.read(0x1000,256))
    assert client.read(0x3d21)==b'\x08' and client.read(0x3d2c)==b'\0','browser system image source not restored'
    records=disk_records(data_disk.read_bytes(),fmt)
    # The physical private host image has not received drive writes; the
    # independent whole-disk readback below qualifies this expected new entry.
    if not any(r['name']==b'SAVED' for r in records):
        records.append(dict(name=b'SAVED',type=1,flags=128,blocks=(len(want)+253)//254,app=False))
    client.frames_equal('browser-after-editor',lambda columns:browser_screen(columns,records,0,device,fmt));save()
    client.key(27);client.heap_equal('workspace-after-editor',(143,219,30))
    for bank,page in protected:
        client.key(ord('1')+bank);client.key(ord('V'));assert client.read(0x3d16)==b'\0'
        actual=client.capture.capture(f'workspace-bank-{bank}',bank=bank,address=page*256,count=2000)
        assert actual==bytes((i&255)^(i>>8)^(0xa5 if bank else 0) for i in range(2000))
        client.key(ord('F'))
    client.frames_equal('workspace-restored',lambda columns:expected_screen(columns,1));save()
    client.heap_equal('all-memory-released',(175,251,32))
    assert client.read(0x98)==b'\0' and client.read(0x3de0,4)==bytes(4)
    report.update(native_checks_passed=True,large_input_bytes=len(raw),saved_bytes=len(want),edit_offset=at,
                  saved_sha256=hashlib.sha256(want).hexdigest(),data_device=device,format=fmt,
                  function_key_bytes_restored=256,rom_getin_expansion_verified=True,
                  independent_workspace_prefix_bytes=2000,native_workspace_verify_bytes=8192,
                  all_owned_memory_and_files_released=True)
    save()
