; VDSVC shared REU operations, called directly through bk_call. Version 1.
; Arguments overlay the transient heap mailbox; callers must reload ordinary
; heap arguments afterward. The entire N_BUFFER remains available for payload.
; The native app owns one idempotent memory lease. Its document extents use
; REU owner 33, distinct from the display snapshot's owner 32. Both retain the
; native app generation in their tokens. All counts/offsets are little endian.
SM_INFO=6                    ; TOKEN: version, lease, active, probe-live, pending
SM_OPEN=7                    ; acquire lease / retry a retained probe restore
SM_ALLOC=8                   ; PAGES in; TOKEN and PAGE out
SM_READ=9                    ; TOKEN/OFFSET/COUNT in; COUNT=completed bytes out
SM_WRITE=10                  ; same, N_BUFFER is never used for descriptors
SM_FREE=11                   ; TOKEN in
SM_RESIZE=12                 ; TOKEN/PAGES in; replacement TOKEN/PAGE on success
SM_CLOSE=13                  ; refuse live documents; release only memory lease
SM_STATS=14                  ; PAGES=total, PAGE=available, TOKEN=free slots
SM_TOKEN=$3d00               ; eight-byte opaque token; INFO bytes 5..7 reserved
SM_OFFSET=$3d08              ; 24-bit byte offset within extent
SM_COUNT=$3d0b               ; 16-bit transfer length, 1..512 / actual on return
SM_PAGES=$3d0d               ; 16-bit count of 4096-byte pages
SM_PAGE=$3d0f                ; 16-bit first page / available pages
SM_VERSION=1
SM_OWNER=N_APPOWNER+1
