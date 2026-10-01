"""Independent screen-cell oracle for the native focused text field."""


def viewport(length,caret,width,previous=0):
    assert 3<=width<=79 and 0<=caret<=length<=255 and 0<=previous<=255
    capacity=width-2
    return max(min(previous,caret,max(0,length+1-capacity)),caret-capacity+1)


def field_cells(value,width,caret=None,view=None):
    raw=value.encode('latin1') if isinstance(value,str) else bytes(value)
    if caret is None:caret=len(raw)
    if view is None:view=viewport(len(raw),caret,width)
    assert 0<=view<=caret<view+width-2 and view<=len(raw)
    out=bytearray([ord('<') if view else 32])
    for position in range(view,view+width-2):
        byte=raw[position] if position<len(raw) else 32
        byte=byte if 32<=byte<127 else ord('.')
        code=byte-64 if 64<=byte<96 else byte-32 if 96<=byte<128 else byte
        out.append(code|(128 if position==caret else 0))
    out.append(ord('>') if len(raw)-view>width-2 else 32)
    return bytes(out)
