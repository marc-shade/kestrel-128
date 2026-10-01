# README screenshots — 2026-09-29

The screenshots in the top-level README come from two sources.

- **VICE (x128):** `tools/readme_screenshots.py` boots the committed disk
  images (`target/native-desktop/uos128.d81` and `gem.d81`), drives the apps
  through the native keyboard buffer, and saves VICE's own rendered VIC-II and
  VDC frames with their palettes. For Paint it writes a UPNT picture, made by
  the script, to the disk copy and opens it from Files. Claude's terminal is
  connected to the repository's fixture session (`tests/fixtures/claude-session.py`).
- **The real C128 (Ultimate II+):** `hw_native_gem_check.py --screens DIR`
  boots `gem.d81` from drive A, captures GEMDESK and the Ultimate app's Info
  and Drives pages, and renders each VIC surface (bitmap and colour cells, no
  sprites) with VICE's palette. A shot is taken once two consecutive captures
  agree. The run passed, and drive A, the upload and the machine were
  restored ([report](hw-screens-report.json)).

`--screens` changes nothing in the other `hw_native_gem_check.py` modes.
