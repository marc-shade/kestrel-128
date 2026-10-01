"""One hardware check's claim on the reference C128's Ultimate II+.

A check records the Ultimate's drives before it changes anything, works only
with private files (disk images uploaded through the REST API, and files it
creates over FTP in a private folder it also creates), and afterwards puts
every drive back exactly as recorded, deletes every private file and folder
and confirms each is absent, and resets the C128. The machine's own disks
are never written.

This is the pattern hw_native_gem_check.py established (2026-09-26), shared:

  snapshot()      record /v1/drives and, for every drive the check may change,
                  its image path, size, image type and drive mode; refuse to
                  start if an original image could not be mounted again
  upload()        mount a private image (REST) and set the drive mode its
                  image type needs
  private_dir()   create a private folder over FTP (it must not exist yet)
  private_file()  store a private file there over FTP and read it back
  claim()         name a file the native OS is expected to create in a
                  private folder, so it is retrieved and deleted too
  restore()       remount each original image (or unmount), restore each
                  mode, compare every drive with the snapshot, retrieve the
                  files the check asked for, delete every private file and
                  folder and confirm each is absent, reset the C128; the
                  result is report['restore'], and any difference raises
  run(body)       body() then restore(), whatever body() did; body's own
                  error is raised first

With dos_contexts (hw_dos_context.DosContexts), snapshot() also requires
both Ultimate DOS contexts to report no open file, and restore() closes a
file the check left open in either of them (both were idle before, so the
check opened it) before deleting the private files, and confirms both are
idle again. An open file survives a C128 reset and a cartridge reboot, and
the native service refuses a context that holds one.

Files and folders are listed, stored, read and deleted over FTP (curl, the
Ultimate's anonymous FTP server) because the REST API has no such calls. The
GEM check's FTP delete and listing of /Temp were exercised on hardware;
storing, reading, MKD and RMD, and anything under /Usb0, were not (see the
harness report).
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse

from hw_dos_context import CONTEXTS, idle

# Image types the REST mount call accepts, and the drive mode each needs.
DRIVE_MODES = {'d64': '1541', 'g64': '1541', 'd71': '1571', 'g71': '1571', 'd81': '1581'}
# Uploaded images are stored as /Temp/tempNNNN, without an extension; the
# type of such an original is taken from its size.
SIZE_TYPES = {174848: 'd64', 175531: 'd64', 196608: 'd64', 197376: 'd64',
              349696: 'd71', 351062: 'd71', 819200: 'd81', 822400: 'd81'}


class RestorationError(RuntimeError):
    """The drives or private files were not put back as recorded."""


def describe(error):
    return f'{type(error).__name__}: {error}'


def flatten(data):
    """{name: record} from the /v1/drives reply."""
    return {name: value for row in data['drives'] for name, value in row.items()}


def image_path(record):
    """Absolute path of a drive's mounted image, or '' when it has none."""
    image = record.get('image_file') or ''
    if not image:
        return ''
    return image if image.startswith('/') else record.get('image_path', '').rstrip('/') + '/' + image


def image_type(path, size):
    """REST image type of an existing image: its extension, else its size."""
    name = path.rsplit('/', 1)[-1]
    if '.' in name and name.rsplit('.', 1)[1].lower() in DRIVE_MODES:
        return name.rsplit('.', 1)[1].lower()
    if size in SIZE_TYPES:
        return SIZE_TYPES[size]
    raise RestorationError(f'cannot tell the image type of {path} ({size} bytes); refusing to start '
                           'a check that could not mount it again')


def safe_path(path):
    assert isinstance(path, str) and path.startswith('/') and '..' not in path.split('/') and '\0' not in path, path
    return path


def put_back(ult, drives, drive, plan):
    """Remount a drive's recorded image (or unmount it) and restore its mode.
    drives(label) returns the flattened /v1/drives reply."""
    if image_path(drives(f'restoring-{drive}')[drive]) != plan['path']:
        if plan['path']:
            # The REST listing does not show whether the original mount was
            # write-protected; like the GEM check, remount it read-write.
            ult.mount_existing(plan['path'], drive=drive, img_type=plan['image_type'],
                               mode='readwrite', expected_bytes=plan['bytes'])
        else:
            ult.unmount(drive)
    if drives(f'restoring-{drive}-mode')[drive].get('type') != plan['mode']:
        ult.control('PUT', f'/v1/drives/{drive}:set_mode?mode={urllib.parse.quote(plan["mode"])}')


def drive_differences(before, after):
    """{drive: {field: [before, after]}} for every drive that differs."""
    differences = {}
    for name in sorted(set(before) | set(after)):
        was, now = before.get(name) or {}, after.get(name) or {}
        if name not in before or name not in after or was != now:
            differences[name] = {k: [was.get(k), now.get(k)] for k in sorted(set(was) | set(now))
                                 if was.get(k) != now.get(k)} or {'listed': [name in before, name in after]}
    return differences


def delete_confirmed(ftp, path, kind, deletions, save):
    """Delete one private file, upload or folder once and confirm it is gone."""
    action = dict(path=path, kind=kind, started=True, acknowledged=False, confirmed=False)
    deletions.append(action)
    save()
    if kind == 'upload' and not ftp.exists(path):
        # Whether the firmware drops an unmounted upload itself is not
        # established; absence is what is required, and it is recorded.
        action.update(started=False, absent_before_delete=True, confirmed=True)
        save()
        return
    (ftp.rmdir if kind == 'folder' else ftp.delete)(path)
    action['acknowledged'] = True
    save()
    action['confirmed'] = not ftp.exists(path)
    save()
    if not action['confirmed']:
        raise RestorationError(f'{path} is still present after deletion')


class CurlFTP:
    """The Ultimate's FTP server through curl (anonymous, binary transfers)."""

    def __init__(self, host, timeout=120):
        self.host, self.timeout = host, timeout

    def _url(self, path):
        return f'ftp://{self.host}' + urllib.parse.quote(path, safe='/')

    def _curl(self, *args, data=None):
        command = ['curl', '-s', '-S', '-m', str(self.timeout), *args]
        result = subprocess.run(command, input=data, capture_output=True)
        if result.returncode:
            raise RuntimeError(f'FTP {" ".join(args[-3:])} failed (curl {result.returncode}): '
                               + result.stderr.decode('utf-8', 'replace').strip())
        return result.stdout

    def names(self, folder):
        """Entry names of a folder (NLST)."""
        listing = self._curl('--list-only', self._url(safe_path(folder).rstrip('/') + '/'))
        return [line.strip('\r').rsplit('/', 1)[-1] for line in listing.decode('latin-1').split('\n')
                if line.strip('\r')]

    def exists(self, path):
        folder, name = safe_path(path).rstrip('/').rsplit('/', 1)
        return name in self.names(folder or '/')

    def get(self, path):
        return self._curl(self._url(safe_path(path)))

    def put(self, path, data):
        self._curl('-T', '-', self._url(safe_path(path)), data=bytes(data))

    def delete(self, path):
        self._curl(f'ftp://{self.host}/', '-Q', 'DELE ' + safe_path(path))

    def mkdir(self, path):
        self._curl(f'ftp://{self.host}/', '-Q', 'MKD ' + safe_path(path))

    def rmdir(self, path):
        self._curl(f'ftp://{self.host}/', '-Q', 'RMD ' + safe_path(path))


class HardwareSession:
    """Snapshot, private uploads/files, and exact restoration for one check."""

    def __init__(self, ult, work, report, save, *, drives=('a',), ftp=None, dos_contexts=None):
        self.ult, self.work, self.report, self.save = ult, Path(work), report, save
        self.dos = dos_contexts
        self.used = tuple(drives)
        self.ftp = ftp if ftp is not None else CurlFTP(ult.host)
        self.before = None
        self.plan = {}
        self.uploads, self.private_dirs, self.private_files, self.claims = [], [], [], []
        self.retrieved = {}

    # -- observation ---------------------------------------------------------
    def drives(self, label):
        data = json.loads(self.ult.drives())
        if data.get('errors'):
            raise RuntimeError(f'drive query reported errors: {data["errors"]}')
        (self.work/f'drives-{label}.json').write_text(json.dumps(data, indent=2)+'\n')
        return flatten(data)

    def snapshot(self):
        """Precondition: the Ultimate answers and every drive the check may
        change can be put back. Nothing is changed here."""
        assert self.before is None, 'one snapshot per session'
        version = json.loads(self.ult.version())
        before = self.drives('before')
        missing = [drive for drive in self.used if drive not in before]
        if missing:
            raise RuntimeError(f'the Ultimate lists no drive {missing}; listed: {sorted(before)}')
        plan = {}
        for drive in self.used:
            record = before[drive]
            path = image_path(record)
            entry = dict(path=path, mode=record.get('type'), bytes=None, image_type=None)
            if path:
                entry['bytes'] = self.ult.path_info(path)['size']
                entry['image_type'] = image_type(path, entry['bytes'])
            plan[drive] = entry
        dos = None
        if self.dos is not None:
            dos = {context: self.dos.info(context) for context in CONTEXTS}
            self.ult.reset()               # the probe left the machine in C64 mode
        self.report['session'] = dict(ultimate_version=version, drives_before=before, drives_used=list(self.used),
                                      restore_plan=plan, uploads=self.uploads, private_dirs=self.private_dirs,
                                      private_files=self.private_files, claims=self.claims, dos_contexts_before=dos)
        self.save()
        for context, reply in (dos or {}).items():
            if not idle(reply):
                raise RuntimeError(f'DOS context {context} is not idle before the check ({reply["result"]}, '
                                   f'{reply["status"]!r}); this check did not open it. Inspect and close it with '
                                   f'hw_ultimate_check.py --close-dos-context {context}')
        self.before, self.plan = before, plan
        return before

    # -- private resources ---------------------------------------------------
    def _owned_paths(self):
        return ({u['path'] for u in self.uploads if u.get('path')} | {d['path'] for d in self.private_dirs}
                | {f['path'] for f in self.private_files} | {c['path'] for c in self.claims})

    def upload(self, data, drive, img_type, access, *, retrieve=False):
        """Mount a private image on a drive the snapshot covers; set the mode
        its type needs. retrieve=True downloads it (after it is unmounted)
        before it is deleted: read-only uploads must come back unchanged."""
        assert self.before is not None, 'snapshot() first'
        assert drive in self.used and img_type in DRIVE_MODES and access in ('readonly', 'readwrite')
        data = bytes(data)
        entry = dict(drive=drive, image_type=img_type, access=access, bytes=len(data),
                     sha256=hashlib.sha256(data).hexdigest(), retrieve=retrieve, path=None, mount_started=True,
                     mount_completed=False)
        self.uploads.append(entry)
        self.save()
        failure = None
        try:
            self.ult.mount(data, drive, img_type, access)
            entry['mount_completed'] = True        # stored size verified
        except BaseException as error:
            failure = error
            raise
        finally:
            # Whatever the drive holds now that is neither the original nor an
            # earlier upload is this upload (also when its size check failed).
            try:
                current = image_path(self.drives(f'upload-{len(self.uploads)}')[drive])
            except BaseException as error:
                entry['path_error'] = describe(error)
                if failure is None:
                    raise
            else:
                known = self._owned_paths() | {p['path'] for p in self.plan.values() if p['path']}
                if current and current not in known:
                    entry['path'] = current
                elif failure is None:
                    entry['path_error'] = f'drive {drive} shows {current!r} after the upload'
            self.save()
        if not entry['path'] or not re.fullmatch(r'/Temp/[^/]+', entry['path']):
            raise RuntimeError(f'upload to drive {drive} was not mounted from /Temp: {entry}')
        self.set_mode(drive, DRIVE_MODES[img_type])
        return entry['path']

    def set_mode(self, drive, mode):
        assert drive in self.used and mode in set(DRIVE_MODES.values())
        if self.drives(f'mode-{drive}')[drive].get('type') != mode:
            self.ult.control('PUT', f'/v1/drives/{drive}:set_mode?mode={urllib.parse.quote(mode)}')

    def _private_parent(self, path):
        parent = path.rsplit('/', 1)[0]
        assert any(d['path'] == parent and d['created'] for d in self.private_dirs), \
            f'{path} is not inside a private folder this session created'

    def private_dir(self, path):
        assert self.before is not None, 'snapshot() first'
        safe_path(path)
        assert path.count('/') >= 2 and not path.endswith('/'), path
        if self.ftp.exists(path):
            raise RuntimeError(f'private folder {path} already exists; refusing to use it')
        entry = dict(path=path, create_started=True, created=False)
        self.private_dirs.append(entry)
        self.save()
        self.ftp.mkdir(path)
        entry['created'] = self.ftp.exists(path)
        self.save()
        if not entry['created']:
            raise RuntimeError(f'private folder {path} is absent after MKD')

    def private_file(self, path, data):
        """Store a fixture and read every byte back before it is used."""
        safe_path(path)
        self._private_parent(path)
        data = bytes(data)
        entry = dict(path=path, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                     store_started=True, stored=False, readback_sha256=None)
        self.private_files.append(entry)
        self.save()
        self.ftp.put(path, data)
        entry['stored'] = True
        back = self.ftp.get(path)
        entry['readback_sha256'] = hashlib.sha256(back).hexdigest()
        self.save()
        if back != data:
            raise RuntimeError(f'fixture {path}: {len(back)} bytes read back differ from the {len(data)} stored')
        return dict(bytes=len(data), sha256=entry['sha256'], path=path)

    def claim(self, path, *, optional=False):
        """A file the native OS may create in a private folder: retrieved and
        deleted with the fixtures. A required claim must exist."""
        safe_path(path)
        self._private_parent(path)
        if path not in {c['path'] for c in self.claims}:
            self.claims.append(dict(path=path, optional=optional))
            self.save()

    # -- restoration ---------------------------------------------------------
    def run(self, body, *, cleanup_on_failure=True):
        assert self.before is not None, 'snapshot() before run()'
        error = None
        try:
            body()
        except BaseException as caught:
            error = caught
        try:
            self.restore(cleanup=error is None or cleanup_on_failure)
        except BaseException as restore_error:
            if error is None:
                raise
            print('RESTORATION FAILED after the check failed:', describe(restore_error), file=sys.stderr, flush=True)
        if error is not None:
            raise error

    def restore(self, *, cleanup=True):
        assert self.before is not None, 'nothing to restore before snapshot()'
        record = dict(passed=False, drives_restored=False, drives_match=False, cleanup_requested=cleanup,
                      cleanup_complete=False, reset_after=False, retrieved={}, deletions=[], leftovers=[])
        self.report['restore'] = record
        self.save()
        error = None
        try:
            self._restore_drives(record)
        except BaseException as caught:
            error = caught
            record['drives_error'] = describe(caught)
        else:
            if self.dos is not None:
                try:
                    self._close_dos_contexts(record)
                except BaseException as caught:
                    error = caught
                    record['dos_error'] = describe(caught)
            if cleanup:
                try:
                    self._cleanup(record)
                except BaseException as caught:
                    error = caught
                    record['cleanup_error'] = describe(caught)
            try:
                self.ult.reset()
                record['reset_after'] = True
            except BaseException as caught:
                error = error or caught
                record['reset_error'] = describe(caught)
        gone = {d['path'] for d in record['deletions'] if d['confirmed']} | set(record.get('never_created', []))
        record['leftovers'] = sorted(p for p in self._owned_paths() if p not in gone)
        record['passed'] = (error is None and record['drives_match'] and record['reset_after']
                            and (self.dos is None or record.get('dos_contexts_idle', False))
                            and (not cleanup or (record['cleanup_complete'] and not record['leftovers'])))
        self.save()
        if error is not None:
            raise error
        if not record['passed']:
            raise RestorationError(f'restoration incomplete: {record}')
        return record

    def _close_dos_contexts(self, record):
        # Both contexts were idle at snapshot(), so a file open now was opened
        # by the check: close it before its private folder is deleted.
        states = record['dos_contexts'] = []
        for context in CONTEXTS:
            entry = dict(context=context, info=self.dos.info(context))
            states.append(entry)
            self.save()
            if not idle(entry['info']):
                entry['close'] = self.dos.close(context)
                entry['info_after'] = self.dos.info(context)
                self.save()
                if not idle(entry['info_after']):
                    raise RuntimeError(f'DOS context {context} still holds a file after CLOSE: {entry}')
        record['dos_contexts_idle'] = True
        self.save()

    def _restore_drives(self, record):
        failures = {}
        for drive in self.used:            # every drive is attempted
            try:
                put_back(self.ult, self.drives, drive, self.plan[drive])
            except BaseException as error:
                failures[drive] = error
                record.setdefault('drive_errors', {})[drive] = describe(error)
                self.save()
        if failures:
            raise next(iter(failures.values()))
        record['drives_restored'] = True
        after = self.drives('after')
        record['drives_after'] = after
        differences = record['drive_differences'] = drive_differences(self.before, after)
        record['drives_match'] = not differences
        self.save()
        if differences:
            raise RestorationError(f'drives differ from the snapshot after restoration: {differences}')

    def _retrieve(self, record, path, index):
        data = self.ftp.get(path)
        folder = self.work/'retrieved'
        folder.mkdir(exist_ok=True)
        local = folder/f'{index:02d}-{re.sub(r"[^A-Za-z0-9._-]", "_", path.rsplit("/", 1)[-1])}'
        local.write_bytes(data)
        self.retrieved[path] = data
        record['retrieved'][path] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), local=str(local))
        self.save()
        return data

    def _delete(self, record, path, kind):
        delete_confirmed(self.ftp, path, kind, record['deletions'], self.save)

    def _cleanup(self, record):
        mounted = {image_path(v) for v in record['drives_after'].values()} - {''}
        still = sorted(mounted & self._owned_paths())
        if still:
            raise RestorationError(f'private files are still mounted: {still}')
        never = record['never_created'] = []
        for folder in self.private_dirs:
            # MKD was sent but not confirmed: the folder is ours if it exists.
            if not folder['created']:
                folder['created'] = self.ftp.exists(folder['path'])
                if not folder['created']:
                    never.append(folder['path'])
        # Scope: a private folder may hold only this session's files.
        record['folder_listings'] = {}
        present = set()
        for folder in (d for d in self.private_dirs if d['created']):
            names = self.ftp.names(folder['path'])
            record['folder_listings'][folder['path']] = names
            present |= {folder['path']+'/'+name for name in names}
            owned = {p.rsplit('/', 1)[1] for p in self._owned_paths() if p.rsplit('/', 1)[0] == folder['path']}
            unexpected = sorted(set(names) - owned)
            if unexpected:
                record['unexpected_entries'] = {folder['path']: unexpected}
                raise RestorationError(f'{folder["path"]} holds entries this session did not create: {unexpected}')
        # Retrieve everything first; a read-only upload must be unchanged.
        index = 0
        for upload in self.uploads:
            # An upload whose stored size never matched is deleted unread.
            if upload['path'] and upload['retrieve'] and upload['mount_completed']:
                data = self._retrieve(record, upload['path'], index)
                index += 1
                if upload['access'] == 'readonly' and hashlib.sha256(data).hexdigest() != upload['sha256']:
                    raise RestorationError(f'read-only upload {upload["path"]} changed; files kept for inspection')
        for item in self.private_files:
            if item['path'] in present:
                self._retrieve(record, item['path'], index)
                index += 1
            elif item['stored']:
                raise RestorationError(f'fixture {item["path"]} is missing')
            else:
                never.append(item['path'])     # STOR failed before creating it
        for claim in self.claims:
            if claim['path'] in present:
                self._retrieve(record, claim['path'], index)
                index += 1
            elif claim['optional']:
                never.append(claim['path'])
            else:
                raise RestorationError(f'expected output {claim["path"]} is missing')
        # Then delete: files, uploads, folders (deepest first).
        for path in [c['path'] for c in self.claims if c['path'] in present] + \
                [f['path'] for f in reversed(self.private_files) if f['path'] in present]:
            self._delete(record, path, 'file')
        for path in dict.fromkeys(u['path'] for u in self.uploads if u['path']):
            self._delete(record, path, 'upload')
        for folder in sorted((d['path'] for d in self.private_dirs if d['created']), key=len, reverse=True):
            self._delete(record, folder, 'folder')
        record['cleanup_complete'] = True
        self.save()
