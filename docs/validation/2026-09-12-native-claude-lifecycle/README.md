# Native Claude lifecycle qualification

The suite now keeps the serial port open until the Linux bridge acknowledges
F8. The client continues parsing queued commands and returning receive credits;
it returns through normal native teardown after acknowledgement, 1200 jiffies,
65535 polls without a clock change, or a second F8. An empty UART alone cannot
establish that the Ultimate's separate TCP relay has forwarded the request.
The bridge preserves complete pending payloads before its BYE reply and starts
the selected host program only after the first client RESYNC.

The app and setup guide now put Return before starting the Linux connection.
The committed firmware reference retained here checks DTR before accepting an
incoming caller. This source reference does not identify the deployed firmware.

Validation on the revised image passes:

- 11 native Claude CPU workflows, including a partial RUN during shutdown,
  credit return, acknowledgement, missing host, jiffy wrap, a stopped clock,
  second F8, normal host exit, RESTORE, absent/busy ACIA and TX timeout.
- Nine host stream/lifecycle checks and all 30 supplied rendering checks.
- 24 native desktop workflows and four native restart cases.
- Two final frozen VICE TCP/PTY workflows: F8 in 40-column startup and host
  process exit in 80-column startup. The client retains outcome 2 for the F8
  acknowledgement and outcome 0 for host-initiated closure. Both host processes
  exit with status 0, restore the full borrowed font and NMI vector/pointer,
  return to desktop selection 4, and finish with all 426 heap pages free.
- The stationary F8 fixture also passes four IRQ CPU captures (eight chunks)
  through the hardware observer with the serial NMI handler installed. Every
  borrowed output/scratch/metadata/resident region matches after restoration.
- A build from 298 frozen source files in an initially empty target directory
  reproduces all 19 PRG/disk images. Claude and Ultimate extract exactly from
  each suite D64. The Claude PRG is 4864 bytes including its load address and
  owns 50 pages including BSS, font storage and C stack.

The VICE fixtures exchange deterministic PTY text and keys. No authenticated
Claude session or model request is involved. Complete character planes and
desktop surface RAM are checked; this record does not capture physical video.
Serial counters are separate sequential reads, so advancing RX and NMI totals
need not be identical; both runs report zero drops and zero overruns.

Physical activity was limited to the GET requests in hardware-readiness.json:
the current Ultimate reports DE00/NMI, TCP 3000, incoming RING and DTR disconnect
enabled. Neither native app was booted on hardware, and no configuration, disk,
CPU-control or RAM-write request was issued. The ABI 1.9 physical record remains
the native physical baseline. The broader native desktop/app roadmap is open.

The VDC observer borrows the selected VDC register as well as its update address.
Only settled terminal output is qualified here. It must not be injected into
concurrent client drawing; the updating status panel is disabled in that run.

Run `python3 -B verify.py` for the offline payload, screen, font, NMI, heap and
observer audit. SHA256SUMS seals every payload. inputs.json pins the frozen
source, integration.json pins the changed main files, and provenance.json names
the base commit, final runs, source reference and external helper. Earlier
successful development runs remain at their recorded scratch paths and are not
counted as final frozen runs. The empty unittest discovery attempt is explicitly
excluded from the checks above.
