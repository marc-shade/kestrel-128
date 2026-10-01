; Optional retained REU backing for the shared VDC lifetime. RAM fallback
; follows only a clean refusal/recovery. A failed probe restore stays owned.
vd_storage_alloc=vs_alloc
vd_storage_read=vs_read
vd_storage_write=vs_write
vd_storage_free=vs_free
vd_storage_close=vs_close
.weak
vs_native_alloc=N_ALLOC
vs_native_read=N_READ
vs_native_write=N_WRITE
vs_native_free=N_FREE
vs_arena_close=ru_close
.endweak

vs_alloc:
        lda #1
        sta vs_reu
        jsr ru_open
        bcc vs_reu_alloc
        ldx ru_probe_live
        bne vs_return
        jmp vs_ram
vs_reu_alloc:
        lda N_CURRENT
        sta ru_owner
        lda #0
        sta ru_pages+1
        lda vd_pages
        clc
        adc #15
        lsr
        lsr
        lsr
        lsr
        sta ru_pages
        jsr ru_alloc
        bcs vs_ram_close
        ldx #7
-       lda ru_handle,x
        sta vs_token,x
        dex
        bpl -
        ldx #3
-       lda ru_handle,x
        sta N_HANDLE,x
        dex
        bpl -
        clc
        rts
vs_ram_close:
        jsr vs_arena_close
        bcs vs_return
vs_ram:
        lda #0
        sta vs_reu
        jmp vs_native_alloc
vs_read:
        lda vs_reu
        beq +
        jsr vs_select
        jmp ru_read
+       jmp vs_native_read
vs_write:
        lda vs_reu
        beq +
        jsr vs_select
        jmp ru_write
+       jmp vs_native_write
vs_free:
        lda vs_reu
        beq +
        jsr vs_select
        jmp ru_free
+       jmp vs_native_free
vs_select:
        lda N_CURRENT
        sta ru_owner
        lda #0
        sta ru_offset+2
        ldx #1
-       lda N_OFFSET,x
        sta ru_offset,x
        lda N_COUNT,x
        sta ru_count,x
        dex
        bpl -
        ldx #7
-       lda vs_token,x
        sta ru_handle,x
        dex
        bpl -
        rts
vs_close:
        lda vs_reu
        beq +
        jsr vs_arena_close
        bcs vs_return
        lda #0
        sta vs_reu
+       clc
vs_return:
        rts
vs_reu: .byte 0
vs_token: .fill 8,0
.include "../reu.inc"
