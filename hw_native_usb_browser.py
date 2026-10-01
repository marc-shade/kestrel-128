"""Physical native directory checks against an independent directory reference.

The native browser shows Ultimate DOS READ_DIR packets (attribute byte + raw
name) in firmware order, under the canonical path GET_PATH returns. These
checks compare every cached packet, page and path with an independent
reference in exactly that form:

    reference(path: bytes, offsets: tuple) -> dict(
        path_hex=<canonical path>, open_code=0|1, count=<entries>,
        pages={str(offset): dict(entries_hex=[...], count, full, clipped, status)})

The only such reference was a C128-side UCI client inside the deleted legacy
desktop. The REST API has no directory listing, and an FTP listing gives
neither the attribute byte nor, as far as anything recorded here shows, the
READ_DIR order or the canonical path. So no hardware reference exists in this
tree and --native-usb-browser refuses to run (UNAVAILABLE); the checks run
offline against simulated references (tests/ci_hardware_usb_restore.py).
"""
from hwlib import lst_symbol
from native_browser_check import browser_screen,ultimate_browser_screen,preview_screen

EMPTY_FOLDER=b'EMPTY FOLDER'
LARGE_DIRECTORY=b'/Usb0/c64/#-a/'
UNAVAILABLE=('--native-usb-browser is not available: its assertions compare the native browser with '
             'Ultimate DOS READ_DIR packets (attribute bytes, firmware order at ordinals 0/248/256, '
             'canonical GET_PATH paths), and the only independent source of those was the deleted legacy '
             'desktop\'s UCI client. The REST API has no directory listing; FTP listings are not shown to '
             'match READ_DIR. Supply a directory reference (hw_native_ultimate_check.run(directory_reference=...)).')


def check_reference(result,offsets):
    assert set(result)>={'path_hex','open_code','count','pages'} and result['open_code'] in (0,1),result
    for offset in offsets:
        page=result['pages'][str(offset)]
        assert not page['clipped'] and all(2<=len(bytes.fromhex(raw))<=256 for raw in page['entries_hex'])
        assert len(page['entries_hex'])>=min(8,max(0,result['count']-offset))
    return result


def prepare_oracles(reference,directory,*,expected_names):
    results={label:check_reference(reference(path,offsets),offsets) for label,path,offsets in (
        ('root',b'/',(0,)),('usb',b'/Usb0/',(0,)),
        ('large',LARGE_DIRECTORY,(0,248,256)),('private',directory,(0,)),
        ('empty',directory+b'/'+EMPTY_FOLDER,(0,)))}
    assert 0<results['root']['count']<8 and results['large']['count']>264
    assert results['private']['count']==len(expected_names) and results['empty']['count']==0
    assert {bytes.fromhex(raw)[1:] for raw in results['private']['pages']['0']['entries_hex']}==expected_names
    return results


class Navigation:
    def __init__(self,client,work,report,directory,outputs,save,*,image='browse',report_key='usb_browser'):
        self.client,self.work,self.report,self.directory,self.outputs,self.save=client,work,report,directory,outputs,save
        assert image in ('browse','editor')
        self.image=image
        self.details=report[report_key]
        self.details.update(passed=False,pages=[],frames=[],next_seconds=[],final_order_verified=False)
        self.oracles=self.details['oracles'];self.device=1;self.error=None
        self.private_path=bytes.fromhex(self.oracles['private']['path_hex'])
        self.private_entries=[bytes.fromhex(raw) for raw in self.oracles['private']['pages']['0']['entries_hex']]
        self.selected_name=b''

    def addr(self,name):return lst_symbol('native/'+self.image,name)

    def view(self,label,base=0,selected=0):
        oracle=self.oracles[label]
        self.path=bytes.fromhex(oracle['path_hex']);self.base,self.row=base,selected
        self.entries=[bytes.fromhex(raw) for raw in oracle['pages'][str(base)]['entries_hex'][:8]]
        self.more=base+len(self.entries)<oracle['count']
        self.selected_name=self.entries[selected][1:] if self.entries else b''
        self.error=None

    def raw_page(self,label):
        client=self.client
        mailbox=client.cpu_read(label+'-browser-mailbox',0x3d20,21)
        start=self.addr('bu_cursor');end=self.addr('bu_path')+256
        state=client.cpu_read(label+'-browser-state',start,end-start)
        def value(name,size=1):
            at=self.addr(name)-start;return int.from_bytes(state[at:at+size],'little')
        count=value('bu_count');assert count<=8 and value('bu_side') in (0,16)
        if self.image=='browse':
            handle=client.cpu_read(label+'-cache-handle',self.addr('b_cache'),4)
            descriptor=client.cpu_read(label+'-cache-descriptor',0x3c00+(handle[0]-1)*8,8)
            assert descriptor[:2]==bytes([32,1]) and descriptor[3]==37 and descriptor[4:7]==handle[1:]
            address=(descriptor[2]+value('bu_side'))*256
            cache=b''.join(client.capture.capture(label+f'-cache-{offset:04x}',bank=1,address=address+offset,
                count=min(2000,count*512-offset)) for offset in range(0,count*512,2000))
            stride=512;lengths=[cache[i*512+510] for i in range(count)]
        else:
            stride=256
            lengths_data=client.cpu_read(label+'-cache-name-lengths',self.addr('fd_lengths'),16)
            handles=client.cpu_read(label+'-cache-handles',self.addr('b_cache'),40)
            cache=bytearray();lengths=[]
            # This editor build supplies three independent 512-byte buffers.
            # The final USB block contains only the remaining cache pages.
            scratch=('d_input','d_output','ed_other_page')
            direct_pages=2*len(scratch)
            for i in range(count):
                page=value('bu_side')//2+i;lengths.append(lengths_data[page])
                if page<direct_pages:
                    bank=0;address=self.addr(scratch[page//2])+(page%2)*256
                else:
                    heap_page=page-direct_pages;at=(heap_page//4)*4;handle=handles[at:at+4]
                    assert handle[0]
                    descriptor=client.cpu_read(f'{label}-cache-descriptor-{i}',0x3c00+(handle[0]-1)*8,8)
                    pages=min(4,16-direct_pages-at)
                    assert descriptor[0]==32 and descriptor[1] in (0,1) and descriptor[3]==pages and descriptor[4:7]==handle[1:]
                    bank=descriptor[1];address=(descriptor[2]+heap_page%4)*256
                cache.extend(client.capture.capture(f'{label}-cache-record-{i}',bank=bank,address=address,count=256))
            cache=bytes(cache)
        (self.work/(label+'-cache.bin')).write_bytes(cache)
        entries=[]
        for i in range(count):
            record=cache[i*stride:(i+1)*stride];length=lengths[i];assert 1<=length<=255
            entries.append(record[:length+1])
        path=client.cpu_read(label+'-retained-path',0x4a00,mailbox[14])
        # The IRQ observer borrows and restores $3e00..$3fff while input is
        # idle. It cannot capture its own scratch as a source. This name is
        # below ROM; retain the direct observation separately from CPU pages.
        name=client.read(0x3e00,mailbox[20]) if mailbox[20] else b''
        (self.work/(label+'-retained-name-direct.bin')).write_bytes(name)
        result=dict(path_hex=path.hex(),base=value('bu_base',4),selected=value('bu_row'),
            device=mailbox[9],format=mailbox[10],more=bool(value('bu_more')),
            entries_hex=[entry.hex() for entry in entries],selected_name_hex=name.hex(),
            ordinal=int.from_bytes(mailbox[16:20],'little'),cursor=value('bu_cursor',4),
            cache_record_bytes=stride,cache_name_lengths=lengths,
            retained_name_observation='direct below-ROM RAM; observer borrows this buffer')
        assert mailbox[0]==32 and result['format']==3 and result['ordinal']==result['base']+result['selected']
        assert name==(entries[result['selected']][1:] if entries else b'')
        return result,entries

    def frame(self,label,*,path_prompt=None,prompt_device=None,directory_prompt=True,error=None,
              field_caret=None,field_views=None):
        error=self.error if error is None else error
        expected=dict(path_hex=self.path.hex(),entries_hex=[entry.hex() for entry in self.entries],
            base=self.base,selected=self.row,device=self.device,more=self.more,error=error,
            path_prompt=path_prompt,prompt_device=prompt_device,directory_prompt=directory_prompt,picker=self.image=='editor')
        if field_caret is not None:expected.update(field_caret=field_caret,field_views=field_views)
        self.client.frames_equal(label,lambda cols:ultimate_browser_screen(cols,self.path,self.entries,
            self.base,self.row,self.device,self.more,error,path_prompt=path_prompt,
            prompt_device=prompt_device,directory_prompt=directory_prompt,picker=self.image=='editor',
            field_caret=field_caret,field_view=None if field_views is None else field_views[int(cols==80)]))
        self.details['frames'].append(dict(label=label,**expected));self.save()

    def check(self,label):
        actual,entries=self.raw_page(label)
        assert (bytes.fromhex(actual['path_hex']),actual['base'],actual['selected'],actual['device'],actual['more'],entries)==(
            self.path,self.base,self.row,self.device,self.more,self.entries),(label,actual)
        page=dict(label=label,**actual)
        if self.path==self.private_path and self.outputs:
            page.update(stage_names_hex=sorted(name.hex() for name in
                {entry[1:] for entry in self.private_entries}|set(self.outputs)),
                expected_selection_hex=self.selected_name.hex(),
                order_check='deferred until independent post-boot directory read')
        self.details['pages'].append(page);self.frame(label)

    def returned(self,label,error=None,*,observed=None):
        actual,entries=self.raw_page(label) if observed is None else observed
        assert bytes.fromhex(actual['path_hex'])==self.private_path and actual['device']==self.device
        allowed={entry[1:] for entry in self.private_entries}|set(self.outputs)
        base,row=actual['base'],actual['selected']
        assert base%8==0 and 0<=base<len(allowed) and len(entries)==min(8,len(allowed)-base)
        assert actual['more']==(base+len(entries)<len(allowed))
        names=[entry[1:] for entry in entries]
        assert len(set(names))==len(names) and set(names)<=allowed and names[row]==self.selected_name
        if len(allowed)<=8:assert set(names)==allowed
        self.path,self.base,self.row,self.entries,self.more=self.private_path,base,row,entries,actual['more']
        self.error=error
        self.details['pages'].append(dict(label=label,**actual,stage_names_hex=sorted(name.hex() for name in allowed),
            expected_selection_hex=self.selected_name.hex(),order_check='deferred until independent post-boot directory read'))
        self.frame(label)

    def select(self,name):
        if name not in [entry[1:] for entry in self.entries]:
            allowed={entry[1:] for entry in self.private_entries}|set(self.outputs)
            assert self.path==self.private_path and name in allowed
            def page(key,base):
                self.client.key(key,quiet=1)
                label=f'private-selection-page-{len(self.details["pages"])}'
                actual,entries=self.raw_page(label)
                assert actual['base']==base and actual['selected']==0 and entries
                self.selected_name=entries[0][1:]
                self.returned(label,observed=(actual,entries))
            while self.base:page(ord('B'),self.base-8)
            for _ in range((len(allowed)+7)//8):
                if name in [entry[1:] for entry in self.entries]:break
                assert self.more,'expected private file is absent from complete listing'
                page(ord('N'),self.base+8)
        row=[entry[1:] for entry in self.entries].index(name)
        while self.row!=row:
            step=1 if row>self.row else -1
            self.client.key(0x11 if step>0 else 0x91,quiet=.1);self.row+=step
        self.selected_name=name

    def go(self,path,label,oracle):
        self.client.key(ord('G'),quiet=.1);self.client.key(21,quiet=.1)
        self.client.literal(path.decode(),quiet=.1);self.client.key(13,quiet=1)
        self.view(oracle);self.check(label)

    def launch(self,name,label,device):
        if device!=self.device:
            self.client.key(9,quiet=1);self.device=device;self.base=self.row=0;self.error=None
            actual,entries=self.raw_page(label+'-context-page')
            assert actual['base']==0 and actual['selected']==0 and entries
            self.selected_name=entries[0][1:]
            self.returned(label+'-context-page',observed=(actual,entries))
        self.select(name);self.check(label+'-selected')
        self.client.key(13,quiet=1)

    def start(self,records,note):
        self.client.frames_equal('directory-iec-start',lambda cols:browser_screen(cols,records))
        for _ in range(3):self.client.key(ord('F'),quiet=1)
        self.view('root');self.check('directory-root')
        self.select(b'Usb0');self.client.key(13,quiet=1);self.view('usb');self.check('directory-usb')
        self.client.key(ord('P'),quiet=1);self.view('root');self.check('directory-parent-root')
        self.go(LARGE_DIRECTORY,'directory-large-first','large')
        for index in range(32):
            self.client.key(ord('N'),quiet=1)
            self.details['next_seconds'].append(self.client.events[-1]['elapsed_seconds'])
            if (index+1)%8==0:
                print(f'Native USB directory reached ordinal {(index+1)*8}',flush=True);self.save()
        self.view('large',256);self.check('directory-ordinal-256')
        self.client.key(ord('B'),quiet=1);self.view('large',248);self.check('directory-back-248')
        self.go(self.directory,'directory-private','private')
        self.select(EMPTY_FOLDER);self.client.key(13,quiet=1);self.view('empty');self.check('directory-empty')
        self.client.key(ord('P'),quiet=1);self.view('private');self.check('directory-empty-parent')
        self.select(b'NOTE.TXT');self.client.key(ord('I'),quiet=1)
        self.client.frames_equal('directory-note-preview',lambda cols:preview_screen(cols,b'NOTE.TXT',note,eof=True))
        self.client.key(27,quiet=.1);self.check('directory-after-preview')

    def verify_final(self,reference):
        """Before the private folder is deleted: every recorded page must be a
        window of the folder's final independent order."""
        oracle=check_reference(reference(self.directory,(0,)),(0,))
        self.details['final_oracle']=oracle
        assert not oracle['pages']['0']['full']
        final=[bytes.fromhex(raw) for raw in oracle['pages']['0']['entries_hex']]
        assert len(final)==len(self.private_entries)+len(self.outputs)
        assert {entry[1:] for entry in final}=={entry[1:] for entry in self.private_entries}|set(self.outputs)
        for page in self.details['pages']:
            if 'stage_names_hex' not in page:continue
            names={bytes.fromhex(raw) for raw in page['stage_names_hex']}
            stage=[entry for entry in final if entry[1:] in names]
            assert len(stage)==len(names)
            base=page['base'];entries=[bytes.fromhex(raw) for raw in page['entries_hex']]
            assert entries==stage[base:base+8],page['label']
            assert stage[page['ordinal']][1:].hex()==page['expected_selection_hex']
            page['order_check']='passed against independent post-boot directory order'
        self.details.update(final_order_verified=True,passed=True);self.save()
