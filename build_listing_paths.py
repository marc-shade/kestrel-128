"""Make the build's listings, symbol files and link maps independent of where
the tree and the temporary folders are.

64tass and ld65 write the paths they were given into .lst, .sym and .map
files. After a build, paths inside the tree become relative to it, and the
app packer's temporary folder (kestrel-app-pack-XXXXXXXX, a new random name
each build) becomes kestrel-app-pack. Only text inside those files changes:
no program or disk image is touched, and nothing reads these files during the
build after this runs.
"""
from pathlib import Path
import re

SUFFIXES = ('.lst', '.sym', '.map')
PACK = re.compile(r'[^\s"\']*/kestrel-app-pack-[A-Za-z0-9_]+/')


def normalize(root, folders):
    root = Path(root).resolve()
    prefix = str(root)+'/'
    changed = 0
    for folder in folders:
        for path in sorted(Path(folder).rglob('*')):
            if path.suffix not in SUFFIXES or not path.is_file():
                continue
            if any(part.endswith('-build') for part in path.relative_to(root).parts[:-1]):
                continue                      # cc65 intermediates, not kept in the repository
            text = path.read_text(errors='surrogateescape')
            new = PACK.sub('kestrel-app-pack/', text.replace(prefix, ''))
            if new != text:
                path.write_text(new, errors='surrogateescape')
                changed += 1
    return changed
