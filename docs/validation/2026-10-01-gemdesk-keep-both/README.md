# GEMDESK copies: Keep both on a name conflict; build listings without host paths (2026-10-01)

## Change

- **Keep both** in GEMDESK's copy name-conflict alert, now
  `[Replace|Keep both|Skip]` with Skip the default and Esc for Stop
  ([GEM-DESKTOP](../../GEM-DESKTOP.md)). The copy goes under the source's name
  with "-2" before its extension (the last "." after the first character),
  then "-3" and on, without another question, while those names are taken
  too; after "-9" the alert is shown again. On a drive the name keeps 16
  characters: the part before the suffix is shortened, or, when the
  extension leaves too little, the name itself with the suffix last. On USB
  the path stays within 255 bytes. Keep both works inside a merged folder
  and with Move (the source is deleted after the verified copy, as for any
  copy). It is not TOS's typed name: `GDCPY.PRG` has no room for the forms
  library (2,389 bytes), and a typed name would need the copy to pause and
  resume across modules.
- GDCPY grows from 3,322 to 3,522 bytes of its 3,524-byte module window.
- GDCPY's two scans for a path's last name stopped early on paths longer than
  127 bytes (`bmi` on the index); they now stop only after index 0.
- `build-native-desktop.py` ends by rewriting the paths that 64tass and ld65
  write into `.lst`, `.sym` and `.map` files (`build_listing_paths.py`): paths
  in the tree become relative, and the app packer's temporary folder gets one
  fixed name, so the listings no longer carry the build machine's home
  directory and two builds differ only in the listings' date line.

## Tests

- `ci_native_gemdesk_copy` (18 cases): the alert text and default updated;
  new cases: Keep both on a drive gives `TWIN-2` and then `TWIN-3` with
  nothing scratched; Esc stops and changes nothing; three 16-character names
  give `SIXTEEN CHARS -2`, `REPO-2.TEXTFILE1` and `A.BCDEFGHIJKLM-2`.
- `ci_native_gemdesk_tree` (8 cases): in a folder merge, Keep both copies
  `b.prg` as `b-2.prg` next to the original.
- All GEMDESK suites, CPU and VICE, with the app and boot pack suites on the
  rebuilt images: `tests/sweep_native.py --group all --only ...` 20/20 passed.
- Two consecutive builds were compared: every program and disk image is the
  same, and listings differ only in their date line.

## Not verified

- Nothing has run on the physical C128.
- The "-9, then ask again" path is not exercised by a test (it needs eight
  taken names); it was checked by reading the code only.
- Keep both onto USB from a drive, and a USB path near 255 bytes, are not
  tested; only the folder-merge case covers USB.
