#!/usr/bin/python3
"""Host pointer control for emulator tests: reads commands from stdin and
sends them to the X display in $DISPLAY through the XTEST extension, so an
emulator with mouse grab (VICE -mouse with a 1351 on a control port) sees
real host mouse motion and buttons. Runs under the system Python, which has
python-xlib; each command is answered with "ok" once flushed.
  move DX DY   relative motion in host pixels
  down / up    left button press / release
  at X Y       absolute position (to put the pointer over the window first)"""
import sys
from Xlib import X, display
from Xlib.ext import xtest

d = display.Display()
if not d.has_extension('XTEST'):
    sys.exit('the X server has no XTEST extension')
for line in sys.stdin:
    words = line.split()
    if not words:
        continue
    if words[0] == 'move':
        xtest.fake_input(d, X.MotionNotify, detail=True, x=int(words[1]), y=int(words[2]))
    elif words[0] == 'at':
        xtest.fake_input(d, X.MotionNotify, detail=False, x=int(words[1]), y=int(words[2]))
    elif words[0] == 'down':
        xtest.fake_input(d, X.ButtonPress, 1)
    elif words[0] == 'up':
        xtest.fake_input(d, X.ButtonRelease, 1)
    else:
        sys.exit(f'unknown command {words[0]!r}')
    d.sync()
    print('ok', flush=True)
