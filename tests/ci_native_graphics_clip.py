#!/usr/bin/env python3
"""Verify pixel-window clipping and whole-cell attribute containment."""
from native_graphics_cpu import Drawing,SYMBOLS,ROOT,report,json,BUSY,BUFFER

FONT=(ROOT/'src/native/graphics/font8.bin').read_bytes()


def coords(d,values):
    for index,value in enumerate(values):
        at=SYMBOLS['gfx_x0']+index*2;d.ram[at:at+2]=(value&65535).to_bytes(2,'little')


def clip(d,box,flags=0,error=0):
    coords(d,box);maps=len(d.m.bus.maps);buffer=bytes(d.ram[BUFFER:BUFFER+512])
    old=bytes(d.ram[SYMBOLS['gfx_clip_pixels']:SYMBOLS['gfx_clip_pixels']+16])
    steps=d.call('gfx_set_clip',error,flags)
    assert len(d.m.bus.maps)==maps and bytes(d.ram[BUFFER:BUFFER+512])==buffer
    if error:assert bytes(d.ram[SYMBOLS['gfx_clip_pixels']:SYMBOLS['gfx_clip_pixels']+16])==old
    else:
        d.clip=tuple(min((320,200)[index%2],max(0,value)) for index,value in enumerate(box))
        cells=((d.clip[0]+7)//8,(d.clip[1]+7)//8,d.clip[2]//8,d.clip[3]//8)
        assert bytes(d.ram[SYMBOLS['gfx_clip_pixels']:SYMBOLS['gfx_clip_pixels']+16])==b''.join(v.to_bytes(2,'little') for v in (*d.clip,*cells))
    report['cases'].append(dict(operation='clip',bank=d.bank,box=box,error=error,flags=flags,instructions=steps))


def pixels(d,x0,y0,bits,pen):
    for dy,row in enumerate(bits):
        for dx in range(8):
            x,y=x0+dx,y0+dy
            if not (d.clip[0]<=x<d.clip[2] and d.clip[1]<=y<d.clip[3]):continue
            at=(y//8)*320+(x//8)*8+y%8;mask=128>>(x%8);old=bool(d.expected[at]&mask);ink=bool(row&(128>>dx))
            on=ink if pen==3 else ((old and not ink) if pen==0 else (old or ink) if pen==1 else old!=ink)
            if on:d.expected[at]|=mask
            else:d.expected[at]&=255^mask


def exact(d):
    assert bytes(d.m.bus.ram[d.bank][d.start:d.start+d.size])==d.expected
    if d.original_other is not None:assert bytes(d.m.bus.ram[1-d.bank])==d.original_other


def glyph(d,x,y,pen):
    bits=bytes([0x81,0x42,0x24,0xff,0x18,0x00,0x3c,0xa5]);coords(d,(x,y))
    d.ram[SYMBOLS['gfx_bits']:SYMBOLS['gfx_bits']+8]=bits;d.ram[SYMBOLS['gfx_pen']]=pen
    steps=d.call('gfx_glyph',flags=8,irq=True);pixels(d,x,y,bits,pen);exact(d)
    report['cases'].append(dict(operation='glyph',bank=d.bank,clip=d.clip,x=x,y=y,pen=pen,instructions=steps))


def text(d,x,y,data,pen):
    coords(d,(x,y));d.ram[SYMBOLS['gfx_pen']]=pen;d.ram[SYMBOLS['gfx_text_length']]=len(data)
    at=SYMBOLS['gfx_text_buffer'];d.ram[at:at+len(data)]=data
    steps=d.call('gfx_text',flags=8,irq=True)
    for index,code in enumerate(data):pixels(d,x+index*8,y,FONT[((code if 32<=code<127 else 63)-32)*8:][:8],pen)
    exact(d)
    assert int.from_bytes(d.ram[SYMBOLS['gfx_x0']:SYMBOLS['gfx_x0']+2],'little',signed=True)==x+8*len(data)
    report['cases'].append(dict(operation='text',bank=d.bank,clip=d.clip,x=x,y=y,pen=pen,text_hex=data.hex(),instructions=steps))


try:
    boxes=((8,8,16,16),(9,9,15,15),(5,5,35,23),(256,192,319,200),
           (-12,-10,7,7),(300,193,500,500),(320,0,32767,32767),(10,10,9,9),
           (-32768,-32768,32767,32767))
    for bank in (0,1):
        d=Drawing(bank)
        for index,box in enumerate(boxes):
            clip(d,box,flags=index%4*4)
            for pen in (0,1,2):d.draw((-32768,-32768,32767,32767),pen,flags=8,irq=True)
            d.draw((-32768,-32768,32767,32767),color=0x12+index)
            x0,y0,x1,y1=d.clip
            for x,y in ((x0-5,y0-3),(x1-7,y1-7),(0,0),(7,7),(255,191)):
                for pen in range(4):glyph(d,x,y,pen)
            text(d,x0-5,y0+1,b'Az09 /Usb0',3)
            text(d,x0-1,y1-5,b'\0\xff?',2)
        clip(d,(9,9,15,15))
        for busy in (BUSY,0x3d91,0x3d3b):
            d.ram[busy]=1;clip(d,(0,0,320,200),error=7,flags=12);d.ram[busy]=0
        d.m.select(d.handle,33);d.call('gfx_bind',expected=5)
        clip(d,(0,0,320,200),error=4)
        d.m.select(d.handle,32);d.call('gfx_bind');d.clip=(0,0,320,200)
        assert bytes(d.ram[SYMBOLS['gfx_clip_pixels']:SYMBOLS['gfx_clip_pixels']+8])==b'\0\0\0\0\x40\x01\xc8\0'
        d.draw((319,199,320,200),pen=2)
    report['passed']=True
    print(f"PASS: {len(report['cases'])} window-clip operations; {report['interrupts']} modeled interrupts")
except BaseException as error:report['passed']=False;report['error']=str(error);raise
finally:(ROOT/'target/native-graphics/clip-report.json').write_text(json.dumps(report,indent=2)+'\n')
