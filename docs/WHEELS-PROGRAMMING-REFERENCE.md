# Wheels programming reference review

Reviewed the complete 38-page
[A Thumber's Guide to Wheels Programming](https://zimmers.net/geos/wheelsProgrammingNotes.pdf):
preface plus printed pages 1–37. This 2020 edited transcription preserves
Maurice Randall's 1998–1999 programming correspondence. It is not the full
Wheels user manual. The file has 417,453 bytes and SHA-256
`9b614333636f7acd3706c898845f2670b81a7de57fc75849bdf00249bd674c40`.
Printed page 30 was also checked visually.

| Printed pages | Reference topics |
|---|---|
| 1–4 | Version checks, copying, temporary kernel groups |
| 5–7, 23, 28, 33 | Partitions, directories, driver selection, original app location |
| 8–13, 30, 32 | Application RAM, expansion allocation and transfers |
| 16–21, 29, 33 | 40/80-column coordinates, icons, dialogs, menus and color fallback |
| 24–26 | Chained desktop return contexts, up to sixteen |
| 35–37 | Input/printer installation; named persistent RAM ownership |

Page 30 describes C128 desk-accessory swapping and treats multitasking as
future SCPU work. Desktop chaining and swapped services therefore do not prove
background scheduling. Detection thresholds differ between the earlier and
later correspondence. Example transcription errors and the ambiguous MoveData
discussion on page 35 require further checking before binary compatibility work.

## Kestrel follow-up decisions

These are Kestrel acceptance requirements, not claims of implemented compatibility:

* Extend the current app-source record to include backend, media identity,
  partition and directory identity when those drivers exist. Changing a data
  disk must not silently redirect executable resources.
* Give resident drivers and expansion allocations explicit lifetimes. Reinstall,
  restart and failed initialization must preserve unrelated storage and avoid
  allocating duplicate persistent blocks.
* Treat desktop return contexts, app suspension and runnable background services
  as distinct behaviors. Test each independently with documents retained.
* Use shared coordinate and clipping rules for both displays. Include right-edge
  menus, custom icons, redraw after mode changes and unsupported color modes.
* Qualify driver installation/removal through owned APIs, including failures
  before and after allocating buffers. Do not copy reference fixed addresses
  into the native heap layout.

The [module candidate](NATIVE-MODULES.md) addresses the first executable-window
step. Expansion allocation, driver loading, GUI services, printer support and
the runtime comparison remain open in the
[completion roadmap](IMPLEMENTATION-ROADMAP.md).
The separate [owner-manual audit](WHEELS-PARITY.md) now covers all 67 pages
of the 1998 copyright edition and supplies concrete acceptance work.

## Installation reference

Also visually reviewed all seven PDF pages of Maurice Randall's 1998
[Wheels 64 & Wheels 128 Installation](https://commodore.bombjack.org/commodore/geos/Wheels_64_and_128_Installation.pdf).
The scan's metadata dates from November 2011. It has 3,520,297 bytes and SHA-256
`415d1ab3b5e2a045fde98e942164340c2211884764169836a000e87878def5ea`.
Page references below are PDF page numbers; the source has no printed numbering.

| Pages | Reference topics |
|---|---|
| 1–2 | Cover; USA/German keyboard and font selection; protected practice installation |
| 3–4 | Prior GEOS installation, RAM requirement, drive discovery at 8–11, separate 64/128 boot methods |
| 5 | Detected RAM choices, RAMLink DACC minimum 128 KiB, boot settings, keyboard operation before mouse setup |
| 6 | Input driver/port, clock source, name confirmation, protected source disk, installation result and final disk protection |
| 7 | Historical product catalog; no current availability inference |

For Kestrel, add installer acceptance with no working mouse, explicit usable-memory
choices, separate source/target write policies, locale-aware confirmation keys
and persisted device choices. Exercise interrupted installation and booting the
last verified system. These are outstanding Kestrel requirements, not compatibility
results. This installation leaflet also refers readers to the separate GEOS
and Wheels manuals; the [owner-manual audit](WHEELS-PARITY.md) now covers
that separate Wheels volume. Runtime and later-release comparisons remain open.
