#!/usr/bin/env python3
"""Clipped rectangle regression against real heap transfers."""
from native_graphics_cpu import Drawing, report, random, json, ROOT, BUSY, BUFFER, SYMBOLS, RECORDS

try:
    rng=random.Random(128)
    for bank in (0,1):
        d=Drawing(bank)
        for coords in ((0,0,1,1),(7,7,9,9),(255,7,258,10),(311,191,320,200),
                       (-5,-3,7,9),(318,198,400,400),(10,10,9,20),(-20,-20,-1,-1),
                       (320,0,32767,200),(-32768,199,32767,200)):
            for pen in (0,1,2):d.draw(coords,pen)
        for index in range(40):
            x=rng.randint(-20,340);y=rng.randint(-15,215)
            d.draw((x,y,x+rng.randint(-2,22),y+rng.randint(-2,12)),rng.randrange(3),flags=(0,4,8,12)[index%4])
        d.draw((-32768,-32768,32767,32767),2,flags=8,irq=True)
        for coords in ((0,0,320,200),(0,0,8,8),(0,0,256,8),(0,0,264,8),
                       (8,3,320,19),(248,0,264,16),(312,192,320,200),
                       (-7,-7,32767,32767),(0,199,320,200),(0,1,8,9),(8,7,16,24)):
            for pen in (0,1,2):d.draw(coords,pen,flags=8,irq=True)
        for coords in ((1,0,319,200),(4,4,316,196),(7,7,9,25),(249,8,258,24),
                       (1,0,2,8),(-7,192,3,200),(318,192,32767,32767),(6,0,7,16)):
            for pen in (0,1,2):d.draw(coords,pen,flags=8,irq=True)
        for coords in ((0,0,40,25),(0,0,1,1),(39,24,41,27),(-5,-5,3,3),(17,9,19,12),(40,0,50,25),(5,5,4,8)):
            d.draw(coords,color=rng.randrange(256),flags=12)
        before=len(d.m.bus.maps);d.draw((0,0,10,10),pen=3,expected=1)
        assert len(d.m.bus.maps)==before,'invalid pen accessed a banked surface'
        for busy in (BUSY,0x3d91,0x3d3b):
            d.ram[busy]=1;buffer=bytes(d.ram[BUFFER:BUFFER+512]);metadata=d.m.metadata()
            d.draw((0,0,10,10),expected=7,flags=12)
            assert d.m.metadata()==metadata and bytes(d.ram[BUFFER:BUFFER+512])==buffer
            d.ram[busy]=0
        d.m.select(d.handle,32);d.m.invoke('free')
        newer=d.m.alloc(36,bank,32,page=d.start//256)
        assert newer!=d.handle
        d.draw((0,0,10,10),expected=4)
        d.m.select(newer,33);d.call('gfx_bind',expected=5)
        d.draw((0,0,10,10),expected=4)
        d.m.select(newer,32);d.call('gfx_bind')
        at=RECORDS+(newer[0]-1)*8
        tag_at=0x3800+bank*256+d.start//256
        tag=d.ram[tag_at];d.ram[tag_at]=0
        d.draw((0,0,10,10),expected=9)
        d.ram[tag_at]=tag
        d.draw((0,0,10,10),pen=2)
    short=Drawing(0,pages=35);short.draw((0,0,10,10),expected=4)
    report['passed']=True
    print(f"PASS: {len(report['cases'])} clipped pixel/color rectangles and failure guards; {report['interrupts']} modeled interrupts")
except BaseException as error:
    report['error']=str(error);raise
finally:(ROOT/'target/native-graphics/report.json').write_text(json.dumps(report,indent=2)+'\n')
