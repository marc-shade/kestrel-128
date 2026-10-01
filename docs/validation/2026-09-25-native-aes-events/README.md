# AES events and messages (GEM layer step 3) — 2026-09-25

The persistent AES gains an `evnt_multi`-style event wait and an
`appl_write`-style message queue (AES minor 2, capability bit 1): bank-1 ops
4 and 5 plus the bank-0 `ae_event`/`ae_post` client. See
[NATIVE-AES](../../NATIVE-AES.md#events).

## Evidence

`~/.venvs/uos-tests/bin/python -B tests/ci_native_aes.py` → `aes.json`,
18/18 cases. That is the 11 persistence and alert cases plus 7 event cases:

- keyboard;
- a timer at exactly 60 jiffies, not 59, across a 16-bit carry;
- single click and the already-in-state rule;
- a double-click inside the 20-jiffy window, and a single click reported
  when the window closes;
- rectangle enter/leave at the half-open cell bound;
- ordered message delivery and a refused 17th message;
- an empty queue for a newly attached app.

Mutation check: widening the click window by one jiffy, closing the
rectangle bound, and an off-by-one timer comparison each failed the test.
The source was restored byte-identical to the version that produced the
report.

Two client bugs found while qualifying:
- `ae_event` returned the fired mask in A instead of the success status.
- The first sample came after the first key poll, so the timer started late.
  The first sample is now taken at the call.

`AESVC.PRG`: 6,268 bytes, 25 pages, CRC16 `$a977`.

## Limits

CPU-level only; no physical C128 run. The CPU cost of each wait sample (one
banked call) is not measured. No suite app uses the event service yet, and
with one foreground app, messages come only from that app until desk
accessories exist.
