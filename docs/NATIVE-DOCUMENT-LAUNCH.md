# Native document launch

Files can open a selected document in the native Editor or Paint and return to
the selected file when the app closes. The app and its checked modules load
from the system volume; the document retains its own device, geometry, raw
name and Ultimate directory. This is an ABI 1.14 workflow for the native suite.

## Controls and associations

The **Edit** and **Paint** buttons open the selected file explicitly. The file
list also accepts **Ctrl-E** and **Ctrl-P**. These shortcuts apply to the list;
editable fields retain their existing caret controls. Folder/volume entries
and unclosed or unsupported IEC records cannot become documents.

**Open** and Enter continue to open directories and native applications.
For other files, an `UPNT` signature chooses Paint and a `USHT` signature
Sheet; otherwise an ASCII `.TXT`
or `.SEQ` suffix, ignoring letter case, chooses Editor. Other files open in the
byte viewer. **View** always inspects bytes. Paint validates the complete UPNT
version, dimensions, length and checksum before accepting a picture; a matching
signature alone does not establish a valid image.

Editor retains source bytes, newline forms and IEC file type. Successful Open
starts a clean document and empty Undo history. Paint stages and validates the
new image separately before replacing its blank document. Failed reads, missing
documents and invalid pictures use the apps' existing error and cleanup paths.

Closing a document app reloads Files. IEC selection is restored by the exact
raw name, with the clamped previous ordinal as a fallback if the name is gone.
The Ultimate browser retains its canonical directory, raw name and four-byte
position. Closing Files then returns to the blue desktop. A missing target app
returns an error to Files; if Files itself cannot reload, the dispatcher tries
the desktop. Later ordinary launches do not reopen a previous request.

## One-launch contract

The source owns the browser identity fields until the destination has copied
them. The shared file picker already saves and restores that browser identity.
No heap handle or unvalidated executable address crosses this handoff.

| Field | Address | Meaning |
| --- | --- | --- |
| `N_DOCREQUEST` | `$3d9a` | 0 none, `$80` staged, 1 ready for this launch |
| `N_DOCKIND` | `$3d9b` | 1 Editor text, 2 Paint picture, 3 Sheet workbook |
| `N_DOCTYPE` | `$3d9c` | IEC: 0 SEQ, 1 PRG, 2 USR; Ultimate: 0 |
| `N_DOCRETURN` | `$3d9d` | 1 asks the dispatcher to return to system Files |
| `N_DOCRESUME` | `$3d9e` | Dispatcher-to-Files selection restoration flag |

The document identity uses `N_BROWSERDEV`, `N_BROWSERFMT`,
`N_BROWSERNAME_LEN`/`N_BROWSERNAME` and, for Ultimate,
`N_BROWSERLEN`/`N_BROWSERPATH`. IEC names are 1–16 bytes. Ultimate parent and
leaf must join into an absolute path of at most 255 bytes, with a separate
terminator in the consumer's 256-byte buffer. Display clipping never shortens
the path sent to the file service.

Files closes its viewer/directory streams, pointer, display leases and keyboard
ownership before publishing `$80` to `N_DOCREQUEST` and calling `N_REPLACE`.
The loader turns the request's high bit into 0 or 1 at the start of one launch
attempt. A ready but unclaimed request therefore expires on the next launch.
Dispatch fallback clears the request before loading Files or the desktop.
The return flag is cleared before attempting Files, preventing a failed Files
load from causing a retry loop; the separate resume flag is consumed on entry.

`src/native/document-launch.inc` supplies the returning consumer helper. Bind
its `DL_*` fields to owned app storage. It clears the request before validating
the kind, device, format, type and lengths, then copies the exact name/path.
Carry clear means a document was claimed; carry set with A=0 means none, and
carry set with A=`N_BADARG` means a malformed or mismatched request. It performs
no file I/O. The caller then uses its transactional Open implementation.

## Modules and memory

Files' `FSOPEN.PRG` shares the existing module window with `FSVIEW.PRG` and
`FSPICK.PRG`. Its code prepares the launch or restores a returned selection;
it returns through `N_MCALL` before the core replaces the app. Signature and
suffix checks remain in the core, so View and unknown-file previews keep their
open stream without loading an association module. All three modules bind to
the matching Files core checksum and use its original module source.

Editor claims the request through its existing `EDCLIP.PRG` window, returns
from the checked module call, initializes the display before selecting document
backing, and opens the file. This matches ordinary startup even when history
uses main RAM without an REU lease. Paint uses the same helper in its core.
Sheet claims kind 3 in its `SHCLIP.PRG` module (operation 2), which the build
assembles with the addresses of the core's `wb_path`, `wb_device` and
`wb_format` from the core's link; the core then runs its ordinary Open
(`wb_open`, "Opening cell:") before the first frame. GEMDESK and Files send a
file that starts with `USHT` there. The 426-page managed heap and
96-page application limits are unchanged.

Editor, Files and Paint store the original font as five column bytes per glyph.
The common decoder reconstructs the exact eight row bytes for labels, Editor's
fast cell renderer and Paint's shared picker. This saves executable space
without changing the glyph artwork. Other native apps retain row-form fonts.

These built-in associations do not implement a user-editable registry,
multi-document windows, suspended applications, GEOS document conversion or
physical device certification. Those remain on the completion roadmap.

The [frozen qualification record](validation/2026-09-14-native-open-with/README.md)
retains 34 CPU suites, both complete private VICE disk boots and an independent
rebuild of all 36 program/disk images. It includes directory reordering,
missing-document selection, both VDC sizes, REU startup and recovery checks.
