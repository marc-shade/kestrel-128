# GEMDESK printer settings; folders merge on copy — 2026-09-30

## Change

GEMDESK ([GEM-DESKTOP](../../GEM-DESKTOP.md)):

- **Printer in the Control Panel** (TOS's Install Printer): IEC device 4 or
  5, and Lowercase (secondary address 7, the printer's upper and lower case;
  off, 0: upper case and graphics). Printing and Print Screen (GDPRT) open
  that device and secondary address, and a missing printer is named by its
  device. The settings are kept with the desktop in record bytes 60 and 61
  (records saved before hold 0 and keep device 4). A new device is probed
  again for the Printer icon and the desktop repainted; a restored desktop's
  printer is probed at start too.
- **Folders merge**: a USB folder dropped where a folder of the same name
  exists is merged into it (no `CREATE_DIR`); each file on both asks
  Replace, Skip or Stop, and the alert now names that file (the target's last
  name) rather than the dragged folder. Skip goes on with the next file; a
  Move in which a name was skipped keeps its source. A folder whose name is
  a file on the target is still refused.
- GDPRT's unreferenced second copy of the "No printer answers" alert was
  removed.

## Tests changed

- `native_gemdesk_scene`: the Control Panel is 30x13 with the printer row;
  the desktop record carries bytes 60 and 61.
- The tree test's "same folder again" case, which expected a refusal, now
  expects the merge; the refusal is tested with a file named like the
  folder.

## Evidence

The suites ran in a scratch copy whose images and tests are byte-identical
to this commit's ([build hashes](build-hashes.json): only the GEMDESK core,
its modules and `gem.d81` changed).

- **GEMDESK CPU set** ([summary](cpu-summary.json)): 12/12, among them
  [Print Screen](ci_native_gemdesk_prtscr.json) (Control Panel printer 5 with
  Lowercase off: every open of file 121 is device 5, secondary address 0,
  and the dump reaches device 5; "No printer answers on device 5"; choosing
  device 4 where nothing answers removes the Printer icon; Save Desktop
  writes 5, 0 at bytes 60 and 61, and a cold start where only device 5
  answers restores them and shows the icon) and the
  [tree test](ci_native_gemdesk_tree.json) (a folder merged: no
  `CREATE_DIR`, c.bin, a.txt and b.prg asked by name in the source's order,
  Replace deleting only the replaced file; a Move with skips deleting
  nothing; a file named like the folder refused).
- **VICE** ([summary](vice-summary.json)): 9/9 in one run. An earlier run of
  the scratch copy before the merge (same printer code) had failed the disk
  copy test once under host load: the 1351 drag was read as a double click
  (a drive window opened where the question was expected); it passed alone,
  and passed in this run.
- **Mutation check**: a build that ignores `skipped` when a row ends fails
  the tree test on "a skipped Move deletes nothing".

## Not verified

- Nothing has run on the physical C128 or a real printer. Device 5 and
  secondary address 0 are checked in the CPU model (the opens it sees and
  the bytes it receives); the VICE printer tests use device 4.
- The Editor still prints to device 4: it does not read GEMDESK's settings.
- Folder merge runs only against the CPU model of Ultimate DOS (its
  `FILE_STAT` answer for a folder, and entry order).
