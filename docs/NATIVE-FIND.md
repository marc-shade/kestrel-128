# Finding filenames in Files

Choose **Find** or press **Ctrl-F** in the graphical Files list. Enter part of
a filename, then choose **Find** or press Enter. Files selects the next match
after the current selection and wraps at the end. Open Find again to repeat
the query; Ctrl-U clears it. Back, X or Escape cancels the dialog.

Search compares literal filename text, ignoring ASCII letter case. On IEC it
also recognizes the alternate PETSCII alphabet. Wildcards are ordinary search
characters. The field accepts up to 127 printable bytes. Ultimate matches use
the complete stored name, including parts clipped from the display.

IEC search uses the complete retained root-directory snapshot, including all
296 entries on an unpartitioned D81. Refresh first to include external changes.
Ultimate search streams the current directory through its owned cursor, using
32-bit positions. A second page buffer preserves the visible listing until a
complete page containing a match is ready. Back, X or Escape during scanning
cancels the search. A failed or cancelled search retains the old selection;
an uncertain cursor close remains owned for recovery. No file contents change.

The blue search dialog works on VIC and 16/64 KiB VDC graphics, with a keyboard
text fallback on the VDC. It keeps `FSVIEW.PRG` resident until the modal call
returns. The query is retained while that module remains loaded; entering
New folder or replacing it with the copy picker clears the previous query.

Search covers the current directory. Recursive search, sorting, persistent
filters and search in the shared Open/Save pickers remain on the completion
roadmap. The diagnostic browser and Files text-only startup fallback do not
expose this graphical command.

Build with `python3 -B build-native-desktop.py`. Run
`python3 -B tests/ci_native_find.py --report /tmp/native-find.json` with Py65,
using a fresh report name so its companion captures remain intact. The suite
checks long directories, exact names, both DOS contexts, errors, cancellation,
complete display frames and resource restoration. Physical qualification
remains separate from CPU and VICE evidence.

The [software qualification record](validation/2026-09-14-native-file-search/README.md)
retains the exact executed inputs, directory and recovery cases, complete
display captures, private VICE workflows and independent clean build.
