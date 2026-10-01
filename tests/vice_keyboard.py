"""Send synthetic keys only to a caller-owned private VICE X display."""
import ctypes as C
from ctypes.util import find_library
import time
import os
import select
import subprocess


class Keyboard:
    def __init__(self,display):
        self.x=C.CDLL(find_library('X11'));self.t=C.CDLL(find_library('Xtst'))
        self.x.XOpenDisplay.argtypes=[C.c_char_p];self.x.XOpenDisplay.restype=C.c_void_p
        self.x.XDefaultRootWindow.argtypes=[C.c_void_p];self.x.XDefaultRootWindow.restype=C.c_ulong
        self.x.XQueryTree.argtypes=[C.c_void_p,C.c_ulong,C.POINTER(C.c_ulong),C.POINTER(C.c_ulong),
                                    C.POINTER(C.POINTER(C.c_ulong)),C.POINTER(C.c_uint)]
        self.x.XFetchName.argtypes=[C.c_void_p,C.c_ulong,C.POINTER(C.c_char_p)]
        self.x.XFree.argtypes=[C.c_void_p]
        self.x.XSetInputFocus.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_ulong]
        self.x.XStringToKeysym.argtypes=[C.c_char_p];self.x.XStringToKeysym.restype=C.c_ulong
        self.x.XKeysymToKeycode.argtypes=[C.c_void_p,C.c_ulong];self.x.XKeysymToKeycode.restype=C.c_uint
        self.x.XFlush.argtypes=[C.c_void_p];self.x.XCloseDisplay.argtypes=[C.c_void_p]
        self.t.XTestFakeKeyEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
        self.display=self.x.XOpenDisplay(display.encode());assert self.display
        # X autorepeat creates extra host press/release events while VICE is
        # paused or busy with disk I/O. This display belongs only to the test;
        # keep repeat behavior under the emulated C128 ROM's control.
        self.x.XAutoRepeatOff.argtypes=[C.c_void_p]
        self.x.XAutoRepeatOff(self.display);self.x.XFlush(self.display)
        root=C.c_ulong();parent=C.c_ulong();children=C.POINTER(C.c_ulong)();count=C.c_uint()
        self.x.XQueryTree(self.display,self.x.XDefaultRootWindow(self.display),C.byref(root),C.byref(parent),C.byref(children),C.byref(count))
        found=[]
        for index in range(count.value):
            name=C.c_char_p()
            if self.x.XFetchName(self.display,children[index],C.byref(name)):
                if name.value and b'C128' in name.value:found.append((children[index],name.value.decode(errors='replace')))
                self.x.XFree(name)
        self.x.XFree(children)
        assert found,'private VICE window not found'
        self.window=found[0][0];self.windows=found
        self.x.XSetInputFocus(self.display,self.window,2,0);self.x.XFlush(self.display)

    def press(self,name):
        key=self.x.XKeysymToKeycode(self.display,self.x.XStringToKeysym(name.encode()))
        assert key
        self.t.XTestFakeKeyEvent(self.display,key,1,0);self.x.XFlush(self.display)
        time.sleep(.06)
        self.t.XTestFakeKeyEvent(self.display,key,0,0);self.x.XFlush(self.display)
        time.sleep(.12)

    def close(self):self.x.XCloseDisplay(self.display)



class PrivateXvfb:
    """Ask Xvfb to reserve a display atomically, including parallel launches."""
    def __init__(self,geometry='800x600x24',*,env=None):
        read_fd,write_fd=os.pipe();self.proc=None
        try:
            self.proc=subprocess.Popen(['Xvfb','-displayfd',str(write_fd),
                '-screen','0',geometry,'-nolisten','tcp'],pass_fds=(write_fd,),
                stdout=subprocess.DEVNULL,env=env)
            os.close(write_fd);write_fd=None
            if not select.select([read_fd],[],[],10)[0]:
                raise TimeoutError('private Xvfb did not publish its reserved display')
            number=os.read(read_fd,64).strip()
            assert number.isdigit() and self.proc.poll() is None,('private Xvfb startup',number)
            self.num=int(number)
            x=C.CDLL(find_library('X11'))
            x.XOpenDisplay.argtypes=[C.c_char_p];x.XOpenDisplay.restype=C.c_void_p
            x.XCloseDisplay.argtypes=[C.c_void_p]
            deadline=time.monotonic()+5
            while True:
                connection=x.XOpenDisplay(self.display.encode())
                if connection:x.XCloseDisplay(connection);break
                assert self.proc.poll() is None,('private Xvfb exited',self.proc.returncode)
                assert time.monotonic()<deadline,'private Xvfb display is not connectable'
                time.sleep(.05)
        except BaseException:
            self.stop();raise
        finally:
            os.close(read_fd)
            if write_fd is not None:os.close(write_fd)

    @property
    def display(self):return f':{self.num}'

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=5)
