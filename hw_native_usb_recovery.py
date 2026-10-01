"""Finish the restoration of a hardware check that could not finish it.

Input is the check's report.json. Its report['session'] (hw_session.py)
records the drive snapshot, the check's uploads under /Temp, and the private
folders, fixtures and expected outputs it created or claimed. Scope is exactly
that record; nothing else on the Ultimate is touched:

- a drive the check used that still holds one of the check's own uploads gets
  its recorded image and mode back (a drive holding anything else is left
  alone: the owner may have changed it since), and the C128 is then reset;
- a private folder may hold only the recorded names, else nothing is deleted;
- every remaining file is retrieved over FTP first; a fixture or read-only
  upload must still have its recorded bytes, and a file the check already
  retrieved must still match that retrieval, else nothing is deleted;
- then files, uploads and folders are deleted once each and confirmed absent.

The journal is reclaim.json next to the report; a second run refuses while it
exists, so no deletion is ever replayed blindly.
(hw_ultimate_check.py --native-reclaim REPORT)
"""
import hashlib
import json
from pathlib import Path
import re

from hw_session import (CurlFTP, RestorationError, delete_confirmed, describe, drive_differences, flatten,
                        image_path, put_back)


def plan(report):
    """The drives and paths a report leaves to reclaim; refuses anything else."""
    session = report.get('session')
    assert session, 'the report has no hardware session record'
    restore = report.get('restore') or {}
    assert not restore.get('passed'), 'the check restored everything; nothing to reclaim'
    confirmed = {d['path'] for d in restore.get('deletions', []) if d.get('confirmed')}
    uploads = [u for u in session['uploads'] if u.get('path')]
    assert all(re.fullmatch(r'/Temp/[^/]+', u['path']) for u in uploads), 'an upload outside /Temp'
    folders = [d['path'] for d in session['private_dirs']]
    assert all(re.fullmatch(r'/Usb0/[^/]+(/[^/]+)*', path) for path in folders), 'a private folder outside /Usb0'
    for item in session['private_files'] + session['claims']:
        assert item['path'].rsplit('/', 1)[0] in folders, f'{item["path"]} is outside the private folders'
    unknown = [u for u in session['uploads'] if not u.get('path')]
    return dict(session=session, restore=restore, confirmed=confirmed, uploads=uploads,
                folders=folders, unknown_uploads=unknown)


def reclaim(ult, saved_report, *, ftp=None):
    saved_report = Path(saved_report)
    work = saved_report.parent
    report = json.loads(saved_report.read_text())
    scope = plan(report)
    session, restore = scope['session'], scope['restore']
    destination = work/'reclaim.json'
    assert not destination.exists(), 'a reclaim was already attempted; inspect reclaim.json before another'
    ftp = ftp if ftp is not None else CurlFTP(ult.host)
    journal = dict(passed=False, source_report_sha256=hashlib.sha256(saved_report.read_bytes()).hexdigest(),
                   drives_put_back=[], retrieved={}, deletions=[], skipped_confirmed=sorted(scope['confirmed']),
                   unknown_upload_paths=len(scope['unknown_uploads']), hardware_io=True)

    def save():
        destination.write_text(json.dumps(journal, indent=2)+'\n')

    def drives(label):
        data = json.loads(ult.drives())
        if data.get('errors'):
            raise RuntimeError(f'drive query reported errors: {data["errors"]}')
        (work/f'reclaim-drives-{label}.json').write_text(json.dumps(data, indent=2)+'\n')
        return flatten(data)

    save()
    try:
        uploads = {u['path']: u for u in scope['uploads']}
        # 1. Drives still holding this check's uploads get their originals back.
        current = drives('before')
        for drive in session['drives_used']:
            if image_path(current[drive]) in uploads:
                put_back(ult, drives, drive, session['restore_plan'][drive])
                journal['drives_put_back'].append(drive)
                save()
        after = drives('after')
        if journal['drives_put_back']:
            put = journal['drives_put_back']
            journal['drive_differences'] = drive_differences({d: session['drives_before'][d] for d in put},
                                                             {d: after.get(d) for d in put})
            ult.reset()
            journal['reset_after'] = True
            save()
        mounted = {image_path(v) for v in after.values()} - {''}
        pending_uploads = [p for p in uploads if p not in scope['confirmed']]
        if mounted & set(pending_uploads):
            raise RestorationError(f'uploads still mounted by another drive: {sorted(mounted & set(pending_uploads))}')
        # 2. Private folders may hold only the recorded names.
        folders = [p for p in scope['folders'] if p not in scope['confirmed']]
        owned = {item['path'] for item in session['private_files'] + session['claims']} | set(scope['folders'])
        present = set()
        journal['folder_listings'] = {}
        for folder in folders:
            if not ftp.exists(folder):
                journal.setdefault('absent_folders', []).append(folder)
                continue
            names = ftp.names(folder)
            journal['folder_listings'][folder] = names
            present |= {folder+'/'+name for name in names}
            unexpected = sorted(folder+'/'+name for name in names if folder+'/'+name not in owned)
            if unexpected:
                raise RestorationError(f'{folder} holds entries the check did not record: {unexpected}')
        # Recorded files that are gone (never created, or deleted by a DELE
        # whose reply was lost) are recorded as absent, not deleted again.
        journal['absent'] = sorted(item['path'] for item in session['private_files'] + session['claims']
                                   if item['path'] not in present and item['path'] not in scope['confirmed'])
        save()
        # 3. Retrieve and compare everything before deleting anything.
        earlier = restore.get('retrieved', {})
        files = [item for item in session['claims'] + session['private_files'][::-1]
                 if item['path'] in present and item['path'] not in scope['confirmed']
                 and item['path'] not in scope['folders']]
        index = 0
        for path in [item['path'] for item in files] + pending_uploads:
            if path in uploads and not ftp.exists(path):
                continue                      # delete_confirmed records its absence
            data = ftp.get(path)
            folder = work/'reclaim'
            folder.mkdir(exist_ok=True)
            local = folder/f'{index:02d}-{re.sub(r"[^A-Za-z0-9._-]", "_", path.rsplit("/", 1)[-1])}'
            local.write_bytes(data)
            index += 1
            digest = hashlib.sha256(data).hexdigest()
            journal['retrieved'][path] = dict(bytes=len(data), sha256=digest, local=str(local))
            save()
            fixture = next((f for f in session['private_files'] if f['path'] == path), None)
            if fixture is not None and fixture['stored'] and digest != fixture['sha256']:
                raise RestorationError(f'fixture {path} differs from what was stored; nothing deleted')
            if (path in uploads and uploads[path]['access'] == 'readonly' and uploads[path].get('mount_completed')
                    and digest != uploads[path]['sha256']):
                raise RestorationError(f'read-only upload {path} differs from what was uploaded; nothing deleted')
            if path in earlier and digest != earlier[path]['sha256']:
                raise RestorationError(f'{path} differs from the check\'s own retrieval; nothing deleted')
        # 4. Delete once each and confirm absence.
        for item in files:
            delete_confirmed(ftp, item['path'], 'file', journal['deletions'], save)
        for path in pending_uploads:
            delete_confirmed(ftp, path, 'upload', journal['deletions'], save)
        for folder in sorted((p for p in folders if p not in journal.get('absent_folders', [])), key=len, reverse=True):
            delete_confirmed(ftp, folder, 'folder', journal['deletions'], save)
        if journal.get('drive_differences'):
            raise RestorationError(f'drives differ from the snapshot after put-back: {journal["drive_differences"]}')
        journal['passed'] = True
    except BaseException as error:
        journal['error'] = describe(error)
        raise
    finally:
        save()
    print(f'PASS: reclaimed {len(journal["deletions"])} private files/folders; journal {destination}', flush=True)
    return journal
