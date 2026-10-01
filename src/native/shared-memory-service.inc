; One memory lease extends the shared arena's lifetime beyond VDC close.
; No second allocator, main-RAM workspace, or native resident ABI is needed.
.include "shared-memory-api.inc"
bm_entry:
        cmp #SM_INFO
        beq bm_info
        cmp #SM_STATS+1
        bcs bm_argument
        sta bm_operation
        jsr bm_recover
        bcs bm_recovery_failed
        lda bm_operation
        cmp #SM_OPEN
        beq bm_open
        cmp #SM_CLOSE
        beq bm_close
        lda bm_lease
        beq bm_unavailable
        jsr bm_select
        lda bm_operation
        cmp #SM_ALLOC
        beq bm_alloc
        cmp #SM_READ
        beq bm_read
        cmp #SM_WRITE
        beq bm_write
        cmp #SM_FREE
        beq bm_free
        cmp #SM_RESIZE
        beq bm_resize
        jmp bm_stats
bm_recovery_failed:
        pha
        lda bm_operation
        cmp #SM_READ
        beq +
        cmp #SM_WRITE
        bne ++
+       lda #0
        sta SM_COUNT
        sta SM_COUNT+1
+       pla
        sec
        rts
bm_argument:
        lda #N_BADARG
        sec
bm_return:
        rts
bm_unavailable:
        lda #0
        sta SM_COUNT
        sta SM_COUNT+1
        lda #N_PLATFORM
        sec
        rts
bm_info:
        lda #SM_VERSION
        sta SM_TOKEN
        lda bm_lease
        sta SM_TOKEN+1
        lda ru_active
        sta SM_TOKEN+2
        lda ru_probe_live
        sta SM_TOKEN+3
        lda bm_pending
        sta SM_TOKEN+4
        lda #0
        sta SM_TOKEN+5
        sta SM_TOKEN+6
        sta SM_TOKEN+7
        clc
        rts
bm_open:
        jsr ru_open
        php
        pha
        lda ru_active
        ora ru_probe_live
        beq +
        lda #1
+       sta bm_lease
        pla
        plp
        rts
bm_close:
        lda bm_lease
        ora ru_probe_live
        beq bm_closed
        ; The lease cannot be dropped while any document remains allocated.
        ldx #0
-       lda ru_records,x
        cmp #SM_OWNER
        beq bm_argument
        txa
        clc
        adc #8
        tax
        bne -
        lda ru_probe_live
        bne bm_close_arena
        lda vd_phase
        ora vs_reu
        bne +
bm_close_arena:
        jsr ru_close
        bcs bm_return
+
bm_closed:
        lda #0
        sta bm_lease
        clc
        rts
bm_display_close:
        lda bm_lease
        beq +
        lda #0
        clc
        rts
+       jmp ru_close
bm_select:
        lda #SM_OWNER
        sta ru_owner
        ldx #7
-       lda SM_TOKEN,x
        sta ru_handle,x
        dex
        bpl -
        ldx #2
-       lda SM_OFFSET,x
        sta ru_offset,x
        dex
        bpl -
        ldx #1
-       lda SM_COUNT,x
        sta ru_count,x
        lda SM_PAGES,x
        sta ru_pages,x
        dex
        bpl -
        rts
bm_alloc:
        jsr ru_alloc
        bcs bm_return
bm_allocated:
        ldx #7
-       lda ru_handle,x
        sta SM_TOKEN,x
        dex
        bpl -
        lda ru_page
        sta SM_PAGE
        lda ru_page+1
        sta SM_PAGE+1
        lda #0
        clc
        rts
bm_read:
        jsr ru_read
        jmp bm_transferred
bm_write:
        jsr ru_write
bm_transferred:
        php
        pha
        lda ru_actual
        sta SM_COUNT
        lda ru_actual+1
        sta SM_COUNT+1
        pla
        plp
        rts
bm_free:
        jmp ru_free
bm_stats:
        jsr ru_stats
        bcs bm_return
        ldx #1
-       lda ru_total,x
        sta SM_PAGES,x
        lda ru_available,x
        sta SM_PAGE,x
        dex
        bpl -
        lda ru_slots
        sta SM_TOKEN
        lda #0
        clc
        rts

; First try growth with the existing token. If another extent blocks it,
; copy into a new owned extent and publish only after every byte was copied.
; A failed copy leaves the caller's old token and data intact. If disposal
; fails, retain the temporary token and recover it before the next operation.
bm_resize:
        jsr ru_resize
        bcc bm_allocated
        cmp #N_NOMEM
        bne bm_return
        ldx ru_slot
        lda #0
        sta bm_bound
        sta bm_offset
        sta bm_offset+1
        sta bm_offset+2
        lda ru_records+3,x
        sta bm_bound+1
        lda ru_records+4,x
        sta bm_bound+2
        ldy #4
-       asl bm_bound+1
        rol bm_bound+2
        dey
        bne -
        ldx #7
-       lda ru_handle,x
        sta bm_original,x
        dex
        bpl -
        jsr ru_alloc
        bcs bm_return
        ldx #7
-       lda ru_handle,x
        sta bm_temporary,x
        dex
        bpl -
        lda #1
        sta bm_pending
bm_copy:
        ldx #2
-       lda bm_offset,x
        sta ru_offset,x
        dex
        bpl -
        lda #0
        sta ru_count
        lda #2
        sta ru_count+1
        ldx #7
-       lda bm_original,x
        sta ru_handle,x
        dex
        bpl -
        jsr ru_read
        bcs bm_copy_failed
        jsr bm_select_temporary
        jsr ru_write
        bcs bm_copy_failed
        clc
        lda bm_offset+1
        adc #2
        sta bm_offset+1
        bcc +
        inc bm_offset+2
+       lda bm_offset+1
        cmp bm_bound+1
        bne bm_copy
        lda bm_offset+2
        cmp bm_bound+2
        bne bm_copy
        ldx #7
-       lda bm_original,x
        sta ru_handle,x
        dex
        bpl -
        jsr ru_free
        bcs bm_copy_failed
        jsr bm_select_temporary
        lda #0
        sta bm_pending
        ; ru_page still describes the replacement allocated above.
        jmp bm_allocated
bm_copy_failed:
        sta bm_error
        jsr bm_recover
        bcs bm_return
        lda bm_error
        sec
        rts
bm_select_temporary:
        lda #SM_OWNER
        sta ru_owner
        ldx #7
-       lda bm_temporary,x
        sta ru_handle,x
        dex
        bpl -
        rts
bm_recover:
        lda bm_pending
        beq +
        jsr bm_select_temporary
        jsr ru_free
        bcs bm_return
        lda #0
        sta bm_pending
+       clc
        rts
bm_lease: .byte 0
bm_pending: .byte 0
bm_operation: .byte 0
bm_error: .byte 0
bm_original: .fill 8,0
bm_temporary: .fill 8,0
bm_offset: .fill 3,0
bm_bound: .fill 3,0
