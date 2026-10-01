# Desktop session selection — ABI 1.9

The native desktop now keeps the selected application across app and workspace
returns. Returning from Editor selects Editor; returning from Files selects
Files. Arrow/Tab navigation and C/E/F shortcuts update the same session value.
Text fallback preserves the selection too. Native restart clears it, and an
invalid stored value recovers to Calculator.

`N_DESKTOPSEL=$3d2f` occupies the unused byte immediately before the four-byte
browser ordinal. The startup loop clears this byte and the ordinal together.
Both kernel binaries remain 15,617 bytes with identical resident intervals and
426 heap pages. Each differs from the previous kernel in only four bytes:
the reset-loop bound/address and two ABI-admission limits. The desktop grows
from 4,479 to 4,497 bytes and still occupies 18 pages; its surface still uses
36 pages, leaving 372 free. Other app and probe binaries are unchanged.

The new desktop requires ABI 1.9. Host validators and the IEC/Ultimate app
loaders and module loader accept minor 9 and reject minor 10. Older supported
application and module requirements remain accepted. Public service addresses
are unchanged. This selection belongs to the current session; disk-backed
desktop preferences remain roadmap work.

## Qualification

| Evidence | Result |
|---|---|
| Desktop CPU workflows | 18 cases on each kernel: valid/invalid stored state, all three reload selections, shortcuts, fallback and owned cleanup |
| Restart CPU execution | Four cases execute actual startup instructions and clear stale selection, ordinal and key counts before dispatch |
| App and module compatibility | 54 IEC app cases, 56 shared Ultimate-loader cases and 115 module cases pass |
| VICE desktop workflows | Direct desktop, initial 80-column mode, workspace-to-desktop and missing-app recovery pass, with selection preserved across actual app reloads |
| Complete shared app sequence | 66 restored captures, 101,274 payload bytes and 647 pause batches; Calculator, Editor, Files and final workspace audits pass |
| Input during observation | The strict observer rejects input and retains the new selection byte alongside the other changed input/fill fields |

The six VICE runs retain 2,496,000 verified rendered pixels, complete VIC
surfaces, and VDC controls. The source/target overlays and packaged images are
retained with hashes. The first CPU reload fixture incorrectly restarted its
local event count while reusing a kernel whose session counter was preserved;
both failing reports and that fixture remain in `controls/cpu-harness-history/`.
The corrected fixture starts at the retained counter, and all 265 CPU cases
pass. No observation failure is accepted as a success.

No physical hardware workflow was run for ABI 1.9. Full physical desktop
qualification remains open, with the earlier failures and their completed
restoration retained in the linked predecessor records.

## Replay and audit

`source-manifest.json` pins 38 code/build-output overlays. The preceding
[observer integration](../2026-09-12-native-observer-integration/README.md) and
[context archive](../2026-09-12-native-capture-context/README.md) retain the
unchanged inputs. `images/` contains both complete kernels and all packaged
native PRG/disk images. `SHA256SUMS` seals every payload in this archive.

```sh
python3 -B docs/validation/2026-09-12-native-desktop-selection/verify.py
python3 -B build-native-desktop.py
python3 -B tests/ci_native_desktop.py --desktop-boot --report /tmp/desktop-selection.json
python3 -B tests/ci_native_desktop_start.py --report /tmp/desktop-restart.json
python3 -u tests/run_ci.py nativedesktop nativedesktopworkspace nativedesktop80 nativedesktopmissingapp nativedesktopsequence nativecaptureinput
```

CPU commands require py65 in the selected Python environment. Replay writes
fresh reports; preserve the archived runs and their original failed attempts.
