"""Read picker symbols from its included scope in a 64tass listing."""
from functools import lru_cache
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent

@lru_cache(None)
def picker_symbol(image,name):
    text=(ROOT/f'target/native-desktop/{image}.lst').read_text(errors='replace')
    start=re.search(r'^;\*+\s+Processing file: .*/src/native/file-dialog\.inc$',text,re.M)
    assert start,('missing picker include',image)
    text=text[start.start():]
    for pattern in (r'^[.>][0-9a-f]{4}[ \t]+([0-9a-f]{4})[ \t]+(?:(?:[0-9a-f]{2} ?)+\s+)?%s:',
                    r'^[.>]([0-9a-f]{4})\s+(?:(?:[0-9a-f]{2} ?)+\s+)?%s:',r'^=\$([0-9a-f]{4})\s+%s\s*='):
        match=re.search(pattern%re.escape(name),text,re.M)
        if match:return int(match[1],16)
    raise AssertionError(('missing picker symbol',image,name))

