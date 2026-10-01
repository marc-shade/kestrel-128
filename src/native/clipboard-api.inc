; Shared foreground clipboard library, protocol 1, native ABI 1.13.
; Only this library writes these session fields. Payloads are opaque byte text;
; consumers perform explicit terminal/format conversion. No data is on disk.
CB_VERSION = N_CLIPBOARD
CB_BUSY = N_CLIPBOARD+1
CB_FORMAT = N_CLIPBOARD+2         ; 0 empty, 1 byte text
CB_LENGTH = N_CLIPBOARD+3         ; published length, LE24
CB_HANDLE = N_CLIPBOARD+6         ; published owner-31 heap token
CB_PENDING = N_CLIPBOARD+10       ; unpublished allocation, recoverable after failure
CB_EXPECTED = N_CLIPBOARD+14      ; requested LE24 size; high byte $ff poisons a draft
CB_WRITTEN = N_CLIPBOARD+17       ; sequentially staged bytes, LE24
CB_COOKIE = N_CLIPBOARD+20        ; draft creator's app allocation token
CB_SEQUENCE = N_CLIPBOARD+24      ; publication counter, LE24, never wraps
CB_TEXT = 1
CB_MAX_BYTES = $3c00             ; 15 KiB fits above the reserved bank-1 code window

; Include clipboard.inc once inside the foreground app or a checked module.
; cp_begin: cp_length LE24 in; discard an abandoned draft and reserve a new one.
; cp_write: cp_count 1..512 in, N_BUFFER bytes; sequential draft append.
; cp_commit: require every byte, then atomically replace the published item.
; cp_abort: release only the unpublished draft (also recovers an abandoned one).
; cp_clear: release draft and published item; publish an empty clipboard.
; cp_info: cp_length and cp_format out. Does not consume N_BUFFER.
; cp_read: cp_offset LE24 and cp_count 1..512 in, N_BUFFER bytes out.
; Every entry preserves D/I, returns native A/carry, and requires the current
; bank-0 app, standard mapping and enabled IRQs. Heap mailboxes are scratch;
; file arguments and the complete N_BUFFER payload are preserved unless read.
; Failed writes poison the draft; only abort/begin/clear can recover it.
