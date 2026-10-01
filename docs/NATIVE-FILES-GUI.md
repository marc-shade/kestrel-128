# Native graphical Files

The suite Files app uses the same blue bitmap, yellow focus and port-1
1351 mouse as the desktop, Calculator, Paint and Ultimate. Open it with the
Files icon or **F** on the desktop. Its file list, byte viewer, fields, copy
dialog and destination picker appear on both displays: 320×200 VIC and
640×200 VDC. A 64 KiB VDC uses color and yellow focus; a 16 KiB VDC uses
white graphics on blue with reversed focus. Both suite disks include this interface.

## Controls

Click a file row to select it, then Open, View, Copy, Edit or Paint. Open and
Enter choose Paint for an UPNT signature and Editor for `.TXT`/`.SEQ` names;
other files use the byte viewer. Edit/Ctrl-E and Paint/Ctrl-P explicitly choose
an app. Closing it returns to the selected file. The [document launch contract](NATIVE-DOCUMENT-LAUNCH.md)
preserves the source device, file type and full Ultimate path. Up/Down select
rows, N/B change pages, R refreshes, D edits the IEC device and F changes the
format. In Ultimate mode, G edits the directory path, P opens the parent and
F1 changes DOS context. L edits an absolute Ultimate application path.

**Tab** cycles enabled buttons and fields; **Enter** activates the focused
control. Fields support the shared caret, insertion, deletion, Home/Ctrl-E and
Ctrl-U controls. Clicking inside a field places its caret in the visible text.
Long names retain every byte and show clipping markers; display truncation
never changes the path used for file I/O.

Copy proposes the selected source name. Edit it or press **F7** / Browse to
choose a destination using the [shared graphical picker](NATIVE-PICKER-GUI.md). The blue dialog returns
with the source and edited destination intact. F1 edits device/DOS, F3 changes
format and F5 changes the destination IEC type. Copy creates a new file,
closes and reopens both streams, and compares all bytes before reporting success.
Cancel is available during copy and verification. Failed writes are never
replayed, and partial new files remain available for inspection.

The byte viewer shows 128 bytes per page. Next or Enter advances and Esc returns
to the file list. Esc from the list returns to the blue desktop. An unavailable
graphics module or occupied bitmap range leaves text controls usable; Refresh
retries graphics. The text fallback also accepts Tab for the destination picker.

If the VDC or its saved-screen backing fails, Files pauses actions until
**Esc** can restore the original screen. The VIC shows “VDC paused; Esc
restores” in the main app. An active copy or verification keeps its exact
progress and open streams while paused. After restoration, Esc cancels the
operation normally, preserving the new destination bytes. Return to the file
list and press **R** to reacquire graphics. A failed restoration also prevents
app replacement and preserves the original Files launch source.

## Memory and module lifetime

Files declares 96 bank-0 app pages, with a resident core followed by one checked
module window at `$9813`, following a 14,355-byte core. `fsview.prg` contains graphics, font, controls and pointer code;
`fspick.prg` contains the 10,221-byte destination picker, ending exactly at `$c000`.
`fsopen.prg` contains 340 bytes for document launch and returned selection.
The three modules alternate. All
are bound to the exact core checksum and loaded from the original app's device,
format and folder, even after the data destination changes.

The core retains browser/copy state, raw source and destination paths, transfer
buffers, descriptors and keyboard ownership. Picker cursors and caches must
close before their module can be replaced. An uncertain module-source close
also blocks new file operations until cleanup succeeds. The app restores the
original keyboard callback, function-key table and display/pointer state on exit.

Sixteen bank-0 pages at `$5000..$5fff` hold explicitly reserved, zeroed scratch
storage. The inactive GUI and picker share their body/path buffers there;
the copy buffer, raw source name, byte viewer and saved function keys remain
separate. Editable field buffers and descriptors stay inside the app's loader
allocation. A conflicting owner refuses startup before keyboard or display
ownership. All scratch pages are released through normal app cleanup.

The suite app and its three matching modules require ABI 1.14. Its packed
PRG is 10,110 bytes. Install `FSOPEN.PRG` together with Files and its other
modules; an unavailable association module reports an error before publishing
an app replacement request.

The core retains one [VDC component](NATIVE-VDC-SERVICE.md) and original-screen
backup across GUI/picker module swaps. Copy `VDSVC.PRG` beside Files when moving
the app to another disk or Ultimate folder. The provider uses 39 bank-1 pages;
screen backing uses 64 or 72 additional main-RAM pages, or an available REU.
With the 37-page IEC cache, Files leaves 202 managed pages with REU backing,
138 with 16 KiB VDC RAM backing, or 130 with 64 KiB VDC RAM backing, before
additional directory caches. Only changed rows and pointer pixels are sent
to the VDC. Text output resumes after the saved display has been restored.

The graphical surface uses 36 pages at `$c000..$e3ff`. The IEC browser cache uses
37 bank-1 pages; Ultimate and picker caches are allocated as needed. Ordinary
field edits update changed glyph cells and the old/new caret. Pointer polling
enters the module only while a new or unfinished sample needs attention; the
app publishes readiness after the complete module call returns. The New folder
and Find modal dialogs instead publish readiness at their own keyboard loops
while the module remains active. Find clears readiness during scanning and
handles Back/X/Escape through the same keyboard and pointer controls.

The VDC service uses the existing owned display contract. Document launch adds
the ABI 1.14 request fields and dispatcher return path. All 426 managed pages
remain available after app and workspace allocations are released.

## Current scope

**Find / Ctrl-F** [searches filenames](NATIVE-FIND.md) in the complete current
directory, selects the next match and wraps at the end. The graphics module
stays resident during the scan. No additional heap allocation is needed:
the core's IEC directory-page staging buffer now shares `$5b00..$5bff` with
inactive copy/compare scratch. Directory refresh and file copying never use
that buffer concurrently. Keep all three app-bound Files modules with the
matching Files program when updating either suite disk.

**New dir / Ctrl-K** opens [Ultimate folder creation](NATIVE-FOLDERS.md) in the
current directory. Its modal call keeps the graphics module resident through
editing and command completion; the listing refresh happens after the module
returns. Both suite disks include it in `FSVIEW.PRG`. **Ctrl-R** and **Ctrl-D**
[rename or delete](NATIVE-FOLDERS.md#renaming-and-deleting) the selected Ultimate
entry through the same dialog. The dialog path and status buffers use idle
copy scratch at `$5800..$591f`; only the edited name stays in the module.

The [document launch qualification](validation/2026-09-14-native-open-with/README.md)
checks Files-to-Editor/Paint handoffs, exact identities and returned selections
with CPU execution and both private VICE disk formats.

The [frozen VDC qualification](validation/2026-09-14-native-files-vdc/README.md) retains
CPU, full mouse/keyboard VICE, exact file-copy and independent rebuild results.
The earlier [Files GUI record](validation/2026-09-13-native-files-gui/README.md)
retains its original copy and serial regression evidence. This build
has not been installed or qualified on the physical C128. The VDC integration
extends the [shared graphical picker](NATIVE-PICKER-GUI.md) to both displays.
IEC rename/delete, sorting, multi-selection,
directory copying, media identity, interrupted-copy recovery, REL/VLIR and
zero-byte IEC creation remain backend or file-manager work.

Ultimate paths may contain 255 bytes in total; each created path component is
limited to 127 bytes by the supported firmware contract. Existing files are
never replaced by Copy. See [file behavior](NATIVE-BROWSER.md#copying-from-the-suite-files-app)
and [owned file services](NATIVE-FILES.md) for the retained transport limits.
