# VICE suites: oracles for the current apps — 2026-09-28

## Problem

The first VICE sweep of `goal/complete-uos` passed 23 of 51 jobs
([summary](vice-sweep-before-summary.json)):
- **`aes_vice`, `gemdesk_vice`:** my regression, fixed in `3cf0e52` (see
  [aes-idle-wait](../2026-09-28-aes-idle-wait/README.md)).
- **Invalid flag combinations:** 7 of the `pointer_iec` failures came from the
  sweep's own matrix, now encoded from the suite's prerequisites.
- **The other 19:** these fail identically on `ef57914`
  ([classification](vice-old-build-classification.json)): the tests predate
  product changes.

The product changes the tests predate:
- **`c4647f7`, `0e1704f`, `d334b47`, `331a881`:** the suite apps (Calculator,
  Files, Editor, Ultimate, Paint, Claude's graphical pages) present their VIC
  surface on the VDC as a doubled bitmap mirror. Tests still compared VDC RAM
  with 80-column text oracles.
- **`5d04173`:** the launcher's VDC holds its own bitmap scene.
- **`f99fa51`:** the launcher has seven apps (Sheet). Selection sequences
  assumed six.
- **`f5d9b9a`:** the desktop installs the shared key filter, so `$033c` chains
  to `native_keycheck` (documented in NATIVE-KEYBOARD.md). A test hard-coded
  the old vector.
- **`331a881`:** Claude's pointer rest point is now the view-selector button;
  since Sheet, the launcher cards are 16 pixels high.

## Change (tests and harness only; no product code)

- **Mirrored app screens** are checked with
  `native_vdc_check.capture_frame(surface_data=…)` against the VIC surface
  the test has already verified byte for byte. It covers VDC phase, the whole
  16,000-byte bitmap, 64 KiB colour attributes, the pointer, and the rendered
  emulator canvas. Text checks remain where the program really shows text
  (fallback screens, the 40-column screen).
- **`capture_frame`:** `canvas=None` skips only the emulator-pixel comparison.
  This is for the physical-hardware workflow in `hw_native_desktop_check.py`,
  which now uses the mirror checks. That script's heap count includes the VDC
  service and its RAM snapshot.
- **Key injection and captures** wait for an idle instant (bounded).
  Pointer-driven apps clear `N_READY` while they sample the 1351.
- **`native_input_capture_vice.py`:** the expected metadata changes are derived
  from `gd_handle`, the card layout and the colour extent, and compared
  exactly. The resident-byte check now requires changes to lie in the declared
  mutable state, where it used to require one exact change; this is looser.
- **`sweep_native.py`:** the `pointer_iec` matrix encodes the flag
  prerequisites. The open-with variants run on the D81, because the shipped
  D64 has 16 free blocks and their fixtures need 36. Option-less suites are no
  longer executed to introspect them.

The CPU suites that import the changed helpers pass on the final code:
`ci_native_transport_lifecycle`, `ci_native_suite_oracles`,
`ci_hardware_transport`, `ci_hardware_uploads`, `ci_hardware_editor_restore`,
`ci_native_reu_document_oracle`, `ci_native_reu_history_oracle`.

## Evidence

`tests/sweep_native.py --group vice --jobs 2` on the final build (GEMDESK
`9f760745`): 47 of 51 jobs pass ([summary](vice-sweep-summary.json)). This
includes:
- the whole `desktop_iec` matrix;
- `keyboard_iec`, `files_copy_iec`, `suite_iec`;
- the `files_iec`, `editor_iec` and `browser_iec` formats;
- `aes_vice`, `gemdesk_vice`, `claude_iec`, `sheet_iec`;
- 12 of the 15 `pointer_iec` variants, including the qualified
  large-document configuration.

## The four jobs that failed in that sweep, now passing

- **`editor_gui_iec`: reworked around the documented memory limit.** VICE's
  C128 has a VDC and no REU, so the Editor's 80-column mirror keeps its
  snapshot in RAM (175 or 167 free pages, NATIVE-EDITOR-GUI.md).
  - The test now asserts that opening the 66,053-byte file is refused with
    status 3 and the empty document kept (`large-refused`).
  - It then runs the whole workflow with a 32,000-byte document that fits
    beside the full-D81 picker: open, go to `$4001` across a chunk boundary,
    edit, picker with 296 entries and 19 cache pages, Save As to drive 10, the
    refusal to overwrite, reopen.
  - 14 checks pass ([report](editor-gui-iec.json)). The RAM path over 64 KiB
    stays covered by `ci_native_document` and `ci_native_picker_gui --case
    large`; the REU path by `ci_native_editor_reu_documents` and the C128 runs.
- **`pointer_iec` (`--80col`, `--editor-only --editor-selection`,
  `--claude-only`): sampling at a random point of the frame.**
  - The harness waited for a typed key, or for an idle capture, until it saw
    `N_READY` set. VICE answers the monitor at a fixed point of its frame,
    and apps that sample the 1351 each frame clear `N_READY` near the same
    point.
  - Before each such sample, the suite now steps a random number of
    instructions (1..6000, about one frame) with the binary monitor's
    ADVANCE_INSTRUCTIONS command. What is checked is unchanged.
  - The full 15-variant matrix passes ([summary](pointer-matrix-summary.json)).

With these, every job of the VICE sweep has passed on the final build: 47 in
the sweep plus the four reruns above.

## Not verified

- The physical-hardware path of `hw_native_desktop_check.py` (the blue desktop
  on the C128) was changed but only run under VICE and CPU fixtures.
- `native_suite_workflow`'s hardware-only clock path still reads clock text
  from VDC row 6, which is stale now that the Ultimate app is graphical.
