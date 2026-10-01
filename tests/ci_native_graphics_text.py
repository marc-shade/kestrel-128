#!/usr/bin/env python3
"""Check bounded ASCII labels, cursor advance and complete surface retention."""
from native_graphics_cpu import Drawing, SYMBOLS, report, ROOT, json, random, BUSY, BUFFER

FONT=(ROOT/'src/native/graphics/font8.bin').read_bytes()
assert len(FONT)==95*8
assert FONT[(65-32)*8:(66-32)*8]==bytes([0x38,0x44,0x44,0x7c,0x44,0x44,0x44,0])
assert FONT[(97-32)*8:(98-32)*8]!=FONT[(65-32)*8:(66-32)*8]


def text(d,x,y,data,pen=3,flags=0,irq=False,error=0,length=None):
    assert len(data)<=64
    d.ram[SYMBOLS['gfx_x0']:SYMBOLS['gfx_x0']+4]=(x&65535).to_bytes(2,'little')+(y&65535).to_bytes(2,'little')
    d.ram[SYMBOLS['gfx_text_buffer']:SYMBOLS['gfx_text_buffer']+64]=data+bytes(64-len(data))
    d.ram[SYMBOLS['gfx_text_length']]=len(data) if length is None else length
    d.ram[SYMBOLS['gfx_pen']]=pen
    steps=d.call('gfx_text',error,flags,irq)
    if not error:
        for index,code in enumerate(data):
            origin=min(32767,x+8*index)
            pattern=FONT[((code if 32<=code<127 else 63)-32)*8:][:8]
            for gy,row in enumerate(pattern):
                for gx in range(8):
                    px,py=origin+gx,y+gy
                    if not (0<=px<320 and 0<=py<200):continue
                    ink=bool(row&(128>>gx));at=py//8*320+px//8*8+py%8;mask=128>>(px%8)
                    old=bool(d.expected[at]&mask)
                    on=ink if pen==3 else ((old and not ink) if pen==0 else (old or ink) if pen==1 else old!=ink)
                    if on:d.expected[at]|=mask
                    else:d.expected[at]&=255^mask
        end=int.from_bytes(d.ram[SYMBOLS['gfx_x0']:SYMBOLS['gfx_x0']+2],'little',signed=True)
        assert end==min(32767,x+8*len(data)),(x,data,end)
        assert int.from_bytes(d.ram[SYMBOLS['gfx_y0']:SYMBOLS['gfx_y0']+2],'little',signed=True)==y
    actual=bytes(d.m.bus.ram[d.bank][d.start:d.start+d.size])
    assert actual==d.expected,(x,y,pen,data,'surface mismatch',[i for i,(a,b) in enumerate(zip(actual,d.expected)) if a!=b][:16])
    if d.original_other is not None:assert bytes(d.m.bus.ram[1-d.bank])==d.original_other
    report['cases'].append(dict(bank=d.bank,x=x,y=y,text_hex=data.hex(),length=len(data) if length is None else length,
                              pen=pen,error=error,flags=flags,irq=irq,instructions=steps))


try:
    rng=random.Random(12880)
    for bank in (0,1):
        d=Drawing(bank)
        text(d,-5,-3,b'Kestrel Native desktop',irq=True)
        text(d,0,40,bytes(range(32,96)),flags=8,irq=True)
        text(d,0,48,bytes(range(96,127))+bytes([0,31,127,128,255]),flags=8,irq=True)
        for x,y in ((-32768,0),(32767,0),(32760,0),(-257,20),(-7,-7),(0,0),(7,7),(255,7),(319,199),(0,-32768),(0,32767)):
            for pen in range(4):text(d,x,y,b'Az09?/Usb0',pen,flags=pen*4)
        for index in range(16):text(d,rng.randint(-400,325),rng.randint(-8,201),rng.randbytes(rng.randint(0,64)),index%4,flags=index%4*4,irq=True)
        text(d,0,0,b'')
        text(d,0,0,b'X',length=65,error=1)
        text(d,0,0,b'X',pen=4,error=1)
        for busy in (BUSY,0x3d91,0x3d3b):
            d.ram[busy]=1; before=bytes(d.ram[BUFFER:BUFFER+512]);metadata=d.m.metadata()
            text(d,1,1,b'busy',error=7,flags=12)
            assert bytes(d.ram[BUFFER:BUFFER+512])==before and d.m.metadata()==metadata
            d.ram[busy]=0
        d.m.select(d.handle,32);d.m.invoke('free')
        text(d,0,0,b'stale',error=4)
    report['passed']=True
    print(f"PASS: {len(report['cases'])} bounded text cases; {report['interrupts']} modeled interrupts")
except BaseException as error:
    report['passed']=False;report['error']=str(error);raise
finally:(ROOT/'target/native-graphics/text-report.json').write_text(json.dumps(report,indent=2)+'\n')
