"""Complete-screen oracle for the native Files copy dialog."""
from native_browser_check import screen_bytes
from native_field_check import field_cells


STATUS = (
    'NEW FILES ONLY; CHOOSE A NEW NAME',
    'COPY CLOSED, REOPENED AND VERIFIED',
    'COPY CANCELLED',
    'FILE I/O FAILED',
    'FILE EXISTS; CHOOSE ANOTHER NAME',
    'INVALID NAME, TYPE OR DEVICE',
    'FILE TYPE CANNOT BE COPIED',
    'REOPENED FILES DO NOT MATCH',
    'USE THE OTHER DOS CONTEXT (F1)',
    'CLOSE FAILED; RETRY COPY/BROWSE/BACK',
    'DESTINATION PICKER FAILED; F7 RETRIES',
    'COPYING TO A NEW FILE...',
    'REOPENING AND COMPARING EVERY BYTE...',
    'ZERO-BYTE IEC CREATE IS UNSUPPORTED',
)


def copy_screen(columns,source,name,*,source_device=9,source_format=0,
                device=9,fmt=0,kind=0,copied=0,verified=0,status=0,
                phase=0,partial=False,error=0,dos=0,caret=None,view=None,
                device_prompt=None,device_caret=None,device_view=None,graphical=False,graphical_controls=False):
    formats=('D64','D71','D81','ULT')
    safe=''.join(chr(c) if 32<=c<127 else '.' for c in source)
    width=38 if graphical else columns-1
    if len(safe)>width:safe='<'+safe[-(width-1):]
    lines=['KESTREL COPY A FILE','',f'FROM: {source_device}   FORMAT: {formats[source_format]}',safe,'',
           f'TO: {device}   FORMAT: {formats[fmt]}  TYPE: '+('SEQ','PRG','USR')[kind],'','NAME: ','',
           'ENTER COPY  TAB BROWSE  ESC FILE LIST','F1 DEVICE/DOS  F3 FORMAT  F5 FILE TYPE',
           'CTRL-U CLEAR NAME','DEVICE/DOS: ' if device_prompt is not None else '',
           '',f'COPIED: {copied}',f'VERIFIED: {verified}',STATUS[10+phase if phase else status]]
    if graphical or graphical_controls:lines[9]='F7 BROWSE  ESC FILE LIST'
    if error:lines.append(f'ERROR: {error:02X}  DOS: {dos}')
    if phase:lines.append('ESC CANCELS AFTER THE CURRENT TRANSFER')
    elif partial:lines.append('NEW FILE MAY BE INCOMPLETE')
    result=bytearray(screen_bytes(columns,lines))
    at=7*columns+6
    result[at:at+width-6]=field_cells(name,width-6,caret,view)
    if device_prompt is not None:
        at=12*columns+12
        result[at:at+5]=field_cells(device_prompt,5,device_caret,device_view)
    return bytes(result)
