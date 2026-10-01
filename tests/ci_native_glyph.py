#!/usr/bin/env python3
"""Compare arbitrary eight-row glyphs with an independent per-pixel oracle."""
from native_graphics_cpu import Drawing, SYMBOLS, report, ROOT, json, random, BUSY, BUFFER


def glyph(d, x, y, bits, pen, flags=0, irq=False, error=0):
    assert len(bits)==8
    d.ram[SYMBOLS['gfx_x0']:SYMBOLS['gfx_x0']+4]=(x&65535).to_bytes(2,'little')+(y&65535).to_bytes(2,'little')
    d.ram[SYMBOLS['gfx_bits']:SYMBOLS['gfx_bits']+8]=bits
    d.ram[SYMBOLS['gfx_pen']]=pen
    steps=d.call('gfx_glyph',error,flags,irq)
    if not error:
        for row,pattern in enumerate(bits):
            for column in range(8):
                px,py=x+column,y+row
                if not (0<=px<320 and 0<=py<200):continue
                ink=bool(pattern&(128>>column))
                at=py//8*320+px//8*8+py%8; mask=128>>(px%8)
                old=bool(d.expected[at]&mask)
                value=ink if pen==3 else ((old and not ink) if pen==0 else (old or ink) if pen==1 else old!=ink)
                if value:d.expected[at]|=mask
                else:d.expected[at]&=255^mask
    actual=bytes(d.m.bus.ram[d.bank][d.start:d.start+d.size])
    assert actual==d.expected,(x,y,pen,'incorrect glyph pixels',[i for i,(a,b) in enumerate(zip(actual,d.expected)) if a!=b][:16])
    if d.original_other is not None:assert bytes(d.m.bus.ram[1-d.bank])==d.original_other
    report['cases'].append(dict(bank=d.bank,x=x,y=y,bits=bytes(bits).hex(),pen=pen,error=error,flags=flags,irq=irq,instructions=steps))


try:
    rng=random.Random(12808)
    for bank in (0,1):
        d=Drawing(bank)
        for index,(x,y) in enumerate(((0,0),(7,7),(8,8),(255,6),(256,7),(313,193),(319,199),
                                    (312,192),(256,192),(248,0),
                                    (-1,-1),(-7,-7),(-8,0),(0,-8),(-32768,5),(5,-32768),
                                    (32767,0),(0,32767),(320,0),(0,200))):
            for pen in range(4):glyph(d,x,y,bytes([0x81,0x42,0x24,0x18,0xff,0x00,0x3c,0xa5]),pen,flags=(index%4)*4)
        for index in range(50):
            glyph(d,rng.randint(-10,322),rng.randint(-10,202),rng.randbytes(8),index%4,flags=(index%4)*4,irq=True)
        for x in range(-7,16):glyph(d,x,192,rng.randbytes(8),3,flags=8,irq=True)
        glyph(d,0,0,bytes(8),4,error=1)
        glyph(d,32767,32767,bytes(8),4,error=1)
        for busy in (BUSY,0x3d91,0x3d3b):
            d.ram[busy]=1; before=bytes(d.ram[BUFFER:BUFFER+512]);metadata=d.m.metadata()
            glyph(d,3,7,b'\xff'*8,3,flags=12,error=7)
            assert bytes(d.ram[BUFFER:BUFFER+512])==before and d.m.metadata()==metadata
            d.ram[busy]=0
        d.m.select(d.handle,32);d.m.invoke('free')
        glyph(d,0,0,b'\xff'*8,3,error=4)
    report['passed']=True
    print(f"PASS: {len(report['cases'])} clipped glyph cases; {report['interrupts']} modeled interrupts")
except BaseException as error:
    report['passed']=False;report['error']=str(error);raise
finally:(ROOT/'target/native-graphics/glyph-report.json').write_text(json.dumps(report,indent=2)+'\n')
