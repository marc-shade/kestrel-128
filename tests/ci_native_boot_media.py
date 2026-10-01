#!/usr/bin/env python3
"""Audit boot sectors, every file chain and the entire BAM independently of the builder."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_files_check import exact_disk_files


def inspect(data, fmt, boot):
    tracks = [40]*80 if fmt == 2 else [21]*17+[19]*7+[18]*6+[17]*5
    directory_track = 40 if fmt == 2 else 18
    assert len(data) == sum(tracks)*256
    assert data[:256] == boot and data[:3] == b'CBM'

    def sector(t, s):
        assert 1 <= t <= len(tracks) and 0 <= s < tracks[t-1]
        start = (sum(tracks[:t-1])+s)*256
        return data[start:start+256]

    used = {(1, 0), (directory_track, 0)}
    if fmt == 2:
        used.update({(40, 1), (40, 2)})
    link = (40, 3) if fmt == 2 else (18, 1)
    files = 0
    while link[0]:
        assert link[0] == directory_track and link not in used
        used.add(link)
        directory = sector(*link)
        for at in range(0, 256, 32):
            if not directory[at+2] & 128:
                continue
            files += 1
            file_link = tuple(directory[at+3:at+5])
            blocks = 0
            while file_link[0]:
                assert file_link not in used, ('cross-linked sector', file_link)
                used.add(file_link)
                block = sector(*file_link)
                assert block[0] or block[1] >= 1
                file_link = tuple(block[:2])
                blocks += 1
            assert blocks == int.from_bytes(directory[at+30:at+32], 'little')
        link = tuple(directory[:2])

    free = 0
    for t, count in enumerate(tracks, 1):
        if fmt == 2:
            bam = sector(40, 1 if t <= 40 else 2)
            at = 16+((t-1) % 40)*6
        else:
            bam = sector(18, 0)
            at = t*4
        available = 0
        for s in range(count):
            is_free = bool(bam[at+1+s//8] & (1 << (s % 8)))
            assert is_free == ((t, s) not in used), ('BAM disagrees with chains', t, s)
            available += is_free
        assert bam[at] == available, ('BAM count', t, bam[at], available)
        if t != directory_track:
            free += available
    return dict(files=files, free_blocks=free, allocated_sectors=len(used),
                sha256=hashlib.sha256(data).hexdigest())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = dict(passed=False, physical_hardware_io=False, disks={})
    deployment = json.loads((ROOT/'target/native-desktop/deployment.json').read_text())
    for prefix, names in [('native', ('kestrel',)), ('native-desktop', ('kestrel', 'workspace'))]:
        folder = ROOT/'target'/prefix
        boot = (folder/'boot.prg').read_bytes()[2:]
        for stem in names:
            for fmt, ext in [(0, 'd64'), (2, 'd81')]:
                disk = folder/f'{stem}.{ext}'
                data = disk.read_bytes()
                row = inspect(data, fmt, boot)
                entries = deployment['disk_entries'] if prefix == 'native-desktop' else {
                    'u': 'kestrel-boot.prg', 'browse': 'browse.prg', 'calc': 'calc.prg',
                    'editor': 'editor.prg', 'edpick.prg': 'edpick.prg', 'edfind.prg': 'edfind.prg'}
                expected = {}
                for name, file in entries.items():
                    origin = folder
                    if name == 'u':
                        origin = ROOT/'target'/('native' if stem == 'workspace' else prefix)
                        if fmt == 2:
                            origin /= 'd81'
                    expected[name.upper().encode()] = (2, (origin/file).read_bytes())
                assert exact_disk_files(data, fmt) == expected, disk
                report['disks'][disk.relative_to(ROOT).as_posix()] = row
    # Allocate all advertised data blocks. This reaches track 1 and proves DOS
    # cannot consume the unlinked boot block even when the disk becomes full.
    with tempfile.TemporaryDirectory(prefix='kestrel-boot-media-') as temporary:
        work = Path(temporary)
        source = ROOT/'target/native-desktop/kestrel.d81'
        disk = work/'full.d81';shutil.copyfile(source, disk)
        free = report['disks']['target/native-desktop/kestrel.d81']['free_blocks']
        payload = bytes(range(254))*free
        fixture = work/'fill.seq';fixture.write_bytes(payload)
        subprocess.run(['c1541', '-attach', str(disk), '-write', str(fixture), 'fill,s'],
                       check=True, capture_output=True)
        full = disk.read_bytes()
        row = inspect(full, 2, source.read_bytes()[:256]);assert row['free_blocks'] == 0
        before = exact_disk_files(source.read_bytes(), 2)
        after = exact_disk_files(full, 2)
        assert after.pop(b'FILL') == (1, payload) and after == before
        report['full_disk'] = dict(row, payload_bytes=len(payload), shipped_files_preserved=True)
        failures = 0
        for offset, mask in [(0, 1), ((39*40+1)*256+17, 1), ((39*40+1)*256+16, 1)]:
            broken = bytearray(full);broken[offset] ^= mask
            try:
                inspect(broken, 2, source.read_bytes()[:256])
            except AssertionError:
                failures += 1
            else:
                raise AssertionError('media corruption accepted')
        report['rejected_corruptions'] = failures
    report['passed'] = True
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    print('PASS: six boot images, exact suite payloads, full D81 allocation and three corruptions')


if __name__ == '__main__':
    main()
