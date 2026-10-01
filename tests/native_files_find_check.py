"""Independent expected text and complete bitmap for Files filename search."""
from native_browser_check import screen_bytes
from native_field_check import field_cells
from native_files_scene import surface

MESSAGES = {
    7: 'FIND PART OF A NAME; WRAPS AT THE END',
    8: 'NO MATCHING NAME IN THIS DIRECTORY',
    9: 'SEARCHING; BACK OR ESC CANCELS',
    10: 'SEARCH CANCELLED; SELECTION KEPT',
    11: 'SEARCH FAILED; SELECTION KEPT',
    12: 'ENTER PART OF A FILENAME',
}


def rows(query, *, device=9, ultimate=False, path=b'/Usb0', result=7,
         caret=None, viewport=0, error=0, dos=0, status=b''):
    if caret is None:
        caret = len(query)
    lines = [''] * 25
    lines[0] = 'FIND A FILENAME IN THIS DIRECTORY'
    lines[1] = path[-37:].decode('ascii').upper() if ultimate else 'CURRENT IEC DIRECTORY SNAPSHOT'
    lines[2] = ('DOS: ' if ultimate else 'DEVICE: ') + str(device)
    lines[9] = MESSAGES[result]
    if error:
        lines[10] = f'ERROR: {error:02X}'
    body = bytearray(screen_bytes(40, lines))
    body[280:318] = field_cells(query, 38, caret, viewport)
    def value(code):
        code &= 127
        if code < 32: code += 64
        elif code >= 64: code += 32
        if 97 <= code <= 122: code -= 32
        return code
    return [bytes(map(value, body[i:i+40])) for i in range(0, 1000, 40)]


def bitmap(query, *, focus=25, caret=None, viewport=0, result=7, **kwargs):
    if caret is None:
        caret = len(query)
    return surface(rows(query, result=result, caret=caret, viewport=viewport, **kwargs),
                   view=8, focus=focus, caret=caret-viewport+1, searching=result==9)
