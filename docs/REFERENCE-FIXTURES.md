# Local reference disks for the parity audit

The 2026-09-10 read-only inventory lists nineteen local GEOS, MegaPatch and
TopDesk disk images, with seventeen distinct SHA-256 values. Each image was
hashed before and after `c1541 -attach <image> -list`; all listings completed
and every image remained unchanged. The
[inventory](reference/2026-09-10-local-disks.json) retains exact image identities
and the command's output. The source disks remain in `<home>/geos128`;
they are not included in this repository.

Directory entries establish which reference files are available. They do not
establish the software's version, complete file integrity, successful boot or
Kestrel compatibility. Names below use readable capitalization; the inventory
retains the listing's case conversion. Preserve raw PETSCII names and GEOS
metadata when building the format fixtures.

| Local image | Listed reference software | Required comparison |
|---|---|---|
| `GEOS128.D64` | GEOS128 boot, 128 Configure/Desktop, joystick and 1351 input drivers, Preference Manager, Pad Color Manager, Alarm Clock, paint/printer drivers, Convert | Boot/configuration, desktop and input behavior, accessory return, clock, persistence and GEOS file conversion |
| `APPS128.D64` | geoWrite 128, geoPaint, Photo Manager, Calculator, Note Pad, fonts and ReadMe128 | Document layout and editing, bitmap editing, image/text transfers, calculator and note workflows, font behavior and file round trips |
| `SPELL128.D64` | geoSpell 128 and geoDictionary | Spell checking, dictionary lookup, document integration, correction and cancellation |
| `WRUTI128.D64` | geoMerge, Text Grabber 128, geoLaser, Text Manager, importer and font files | Merge data, import/export, text scraps and printer output; include supported source-format fixtures |
| `TopDesk128v5r1.d64` | `128 desktopDE` and `128 desktopUS` | Desktop navigation, file actions, app/accessory launching and preferences; establish the runtime version before claiming a release comparison |
| `mp33r12be.d71`, `mp3en-3.3r12_260220.d81` | SetupMP128E and its numbered components, readme/quickstart/manual; the D81 also lists C64 components | Identify the setup release from its own metadata, build a private reference installation and compare the [manual requirements](MEGAPATCH-3-PARITY.md) |
| `mp3-target.d81`, `mp3-target.pre-desktop.d81`, `mp3-boot-test.d81`, `mp3-megapatch128.d81` | Installed-looking GEOS128 component sets, task/input/configuration files and effects; all except `pre-desktop` list `128 desktop` | Inspect preparation history and file integrity, then boot disposable copies; a matching directory does not establish matching contents |

`geos-orig.d64` is byte-identical to `GEOS128.D64`.
`mp3-boot-test.d81` and `mp3-megapatch128.d81` are also byte-identical.
The mouse/joystick/fix images have different hashes and remain separate
configuration candidates. `mp3-source.d81` and
`mp3en-3.3r12_260220.d81` list the same names but have different image hashes.
Do not substitute those images without identifying the differences.

One misleading filename needs an explicit exclusion: `mp3_c128.d64` lists
the disk title `mp3-64 Demo E` and `STARTMP3_64`/`STARTMP64` components. It is
not evidence for a native C128 MegaPatch reference installation. The older
`mp33-en.d81` lists several one-block setup components; inspect their file
structure before selecting it as a complete installer.

No Wheels disk or manual was identified by this inventory. Subsequent primary
[owner-manual](WHEELS-PARITY.md) and [programming/installation reference](WHEELS-PROGRAMMING-REFERENCE.md)
reviews supply the documentary comparison. A Wheels runtime image and recorded
comparison remain open. This inventory covers the local directory, not the
user's complete software collection.

The subsequent [GEOS128 boot observations](reference/2026-09-11-geos-boots/README.md)
record visible desktops in VICE 3.10 after boots with initial 40- and 80-column
settings and 16 KiB VDC RAM. The original and private working disks remain
unchanged. These establish a reference boot baseline; input, runtime version,
application workflows and comparison with Kestrel remain open.

For each runtime comparison, record the original image hash, private working
copy, ROMs, display/input and memory configuration, reference version shown
on screen, steps, screenshots and resulting files. Exercise the same workflow
in Kestrel and compare the stored bytes/metadata or independently rendered output.
Keep functional parity, document-format compatibility and execution of the
original GEOS binary as separate results in the
[completion roadmap](IMPLEMENTATION-ROADMAP.md).
