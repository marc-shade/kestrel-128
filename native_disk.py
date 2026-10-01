"""Create native boot media without letting DOS allocate the raw boot sector."""
from pathlib import Path
import subprocess


def create_boot_disk(disk, boot, entries):
    disk, boot = Path(disk), Path(boot)
    geometry = disk.suffix.lstrip('.').lower()
    if geometry not in ('d64', 'd81'):
        raise ValueError('native boot builder supports D64 and D81')
    payload = boot.read_bytes()
    assert payload[:2] == b'\0\x0b' and len(payload) == 258
    subprocess.run(['c1541', '-format', 'kestrel,01', geometry, str(disk)],
                   check=True, capture_output=True)
    data = bytearray(disk.read_bytes())
    # 1541: track 18 sector 0, four-byte entries starting at byte 4.
    # 1581: track 40 sectors 1/2, six-byte entries starting at byte 16.
    # The first entry in each case describes track 1 (our boot sector is 1/0).
    count = 17*21*256+4 if geometry == 'd64' else (39*40+1)*256+16
    sectors = 21 if geometry == 'd64' else 40
    assert data[count] == sectors and data[count+1] & 1
    data[count] -= 1
    data[count+1] &= 0xfe
    data[:256] = payload[2:]
    disk.write_bytes(data)
    command = ['c1541', '-attach', str(disk)]
    for name, image in entries.items():
        command.extend(['-write', str(image), name])
    subprocess.run(command, check=True, capture_output=True)
    written = disk.read_bytes()
    assert written[:256] == payload[2:] and not written[count+1] & 1
    print(f'Native C128 boot disk: {disk}')
