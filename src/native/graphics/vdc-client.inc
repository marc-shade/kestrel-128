; Retained parent of the shared bank-1 VDC service. All UI/input stays in bank 0.
; BP_MODE = 0 VIC mirror, 1 native Desktop scene. bp_select_surface is supplied.
.weak
BP_POINTER_STATE=pm_seen
BP_POINTER_X=pm_x
BP_POINTER_Y=pm_y
BP_SHARED_MEMORY=0
BP_STATE_STORAGE=0
BP_TRACK_DIRTY=1
BP_HISTORY=0
.endweak
vd_open:
        lda #0
        sta N_READY
        sta vd_fault
        lda bk_state
.if BP_SHARED_MEMORY || BP_HISTORY
        ; A loaded component is reused for exactly what vd_close keeps it for.
        cmp #2
        bne +
 .if BP_SHARED_MEMORY
        lda dm_lease
  .if BP_HISTORY
        ora eh_available
  .endif
 .else
        lda eh_available
 .endif
        bne bp_loaded
        beq bp_open_bad
+       lda bk_state
.endif
        bne bp_open_bad
        jsr bp_load
        bcs bp_open_failed
bp_loaded:
        lda #1
        sta bp_started
        sta vd_phase          ; conservative until the returned state is copied
        jsr bp_arguments
        lda #1
        jsr bp_invoke
        bcc bp_presented
        ldx vd_phase
        bne bp_return
        ; A clean display refusal can release the unused component immediately.
        jmp bp_open_failed
bp_open_bad:
        lda #N_BADARG
        sec
        rts
bp_open_failed:
        sta vd_fault
        sta bp_error
        jsr vd_close
        bcs +
        lda bp_error
        sta vd_fault
+       sec
        rts
vd_close:
        lda #0
        sta N_READY
        lda bp_started
        beq bp_dispose
        lda #4
        jsr bp_invoke
        bcs bp_return
        lda #0
        sta bp_started
bp_dispose:
.if BP_HISTORY
        lda eh_available
        bne bp_closed
.endif
.if BP_SHARED_MEMORY
        lda dm_lease
        bne bp_closed
.endif
        jsr bk_close
        bcs bp_close_failed
        lda bp_file
        beq bp_closed
        lda #N_APPOWNER
        sta N_FOWNER
        ldx #3
-       lda bp_file,x
        sta N_FHANDLE,x
        dex
        bpl -
        jsr N_FCLOSE
        bcs bp_close_failed
        lda #0
        sta bp_file
bp_closed:
        lda #0
        sta vd_phase
        sta vd_live
        sta vd_handle
        sta vd_pointer_visible
        clc
        rts
bp_close_failed:
        sta vd_fault
        ldx #1
        stx vd_phase
        sec
bp_return:
        rts

 .if BP_MODE == 0
vm_present:
        lda vd_fault
        bne bp_fault
        lda vd_live
        beq bp_ok
        lda vm_pending
        beq bp_ok
 .endif
vd_select:
        lda vd_fault
        bne bp_fault
        lda vd_live
        beq bp_ok
        jsr bp_arguments
        lda #2
        jsr bp_invoke
        bcs bp_return
bp_presented:
 .if BP_MODE == 0
        ldx #24
        lda #0
-       sta vm_rows,x
        dex
        bpl -
        sta vm_pending
 .endif
bp_ok:
        lda #0
        clc
        rts
bp_fault:
        sec
        rts
vd_poll:
        lda vd_live
        beq bp_ok
        lda vd_fault
        bne bp_ok
        lda BP_POINTER_STATE
        cmp vd_pointer_visible
        bne bp_pointer
        lda BP_POINTER_STATE
        beq bp_ok
        lda BP_POINTER_X
        cmp vd_pointer_x
        bne bp_pointer
        lda BP_POINTER_X+1
        cmp vd_pointer_x+1
        bne bp_pointer
        lda BP_POINTER_Y
        cmp vd_pointer_y
        beq bp_ok
bp_pointer:
        jsr bp_arguments
        lda #3
        jmp bp_invoke

bp_invoke:
        jsr bk_call
        sta bp_result
        php
        pla
        and #1
        sta bp_carry
        lda bk_error
        bne bp_gate_failed
        lda #5
        jsr bk_call
        bcs bp_gate_failed
        ldx #40
-       lda N_BUFFER,x
        sta bp_state,x
        dex
        bpl -
        lda bp_result
        lsr bp_carry
        rts
bp_gate_failed:
        sta vd_fault
        ldx #1
        stx vd_phase
        sec
        rts
bp_arguments:
        lda #0
        sta N_READY
        jsr bp_select_surface
        ldx #3
-       lda N_HANDLE,x
        sta N_BUFFER+1,x
        dex
        bpl -
        lda #BP_MODE
        sta N_BUFFER
 .if BP_MODE == 1
        lda gd_selected
        sta N_BUFFER+5
        lda gd_launch_error
        sta N_BUFFER+6
 .else
        lda #0
        sta N_BUFFER+5
        sta N_BUFFER+6
 .endif
        lda BP_POINTER_STATE
        sta N_BUFFER+7
        lda BP_POINTER_X
        sta N_BUFFER+8
        lda BP_POINTER_X+1
        sta N_BUFFER+9
        lda BP_POINTER_Y
        sta N_BUFFER+10
 .if BP_MODE == 0
        ldx #24
-       lda vm_rows,x
        sta N_BUFFER+11,x
        dex
        bpl -
 .endif
        rts

; The app launch source remains independent of file-dialog/browser arguments.
bp_load:
        lda N_APPFORMAT
        sta N_FFORMAT
        lda N_DEVICE
        sta N_FDEVICE
        lda #9
        sta N_FNAMELEN
        lda N_APPFORMAT
        cmp #3
        bne bp_iec_name
        ldx #0
        stx bp_prefix
-       lda N_SOURCEPATH,x
        sta N_UPATH,x
        cmp #$2f
        bne +
        txa
        clc
        adc #1
        sta bp_prefix
+       inx
        cpx N_NAMELEN
        bne -
        lda bp_prefix
        clc
        adc #9
        bcs bp_argument
        sta N_FNAMELEN
        ldx bp_prefix
        ldy #0
-       lda bp_name,y
        sta N_UPATH,x
        inx
        iny
        cpy #9
        bne -
        beq bp_open_source
bp_iec_name:
        ldx #8
-       lda bp_name,x
        sta N_FNAME,x
        dex
        bpl -
bp_open_source:
        lda #N_APPOWNER
        sta N_FOWNER
        lda #1
        sta N_FTYPE
        lda #0
        sta N_FMODE
        ldx #3
-       sta N_FHANDLE,x
        dex
        bpl -
        jsr N_FOPEN
        php
        pha
        ldx #3
-       lda N_FHANDLE,x
        sta bp_file,x
        dex
        bpl -
        pla
        plp
        bcs bp_return
        jsr bk_load
        php
        pha
        lda bk_state
        beq +
        lda #0
        sta bp_file
+       pla
        plp
        rts
bp_argument:
        lda #N_BADARG
        sec
        rts

 .if BP_MODE == 0
gfx_track_dirty=1
 .if BP_TRACK_DIRTY
vm_dirty:
        lda gfx_clipped+6
        sec
        sbc #1
        ldx gfx_operation
        cpx #1
        beq +
        lsr
        lsr
        lsr
+       tax
        lda gfx_clipped+2
        ldy gfx_operation
        cpy #1
        beq +
        lsr
        lsr
        lsr
+       sta vm_first
        lda #1
        sta vm_pending
-       sta vm_rows,x
        cpx vm_first
        beq +
        dex
        jmp -
+       rts
vm_first: .byte 0
 .endif
vm_rows: .fill 25,0
vm_pending: .byte 0
 .endif
bp_file: .fill 4,0
bp_prefix: .byte 0
bp_started: .byte 0
bp_result: .byte 0
bp_carry: .byte 0
bp_error: .byte 0
bp_name: .text "vdsvc.prg"
.if BP_STATE_STORAGE
bp_state=BP_STATE_STORAGE
.else
bp_state: .fill 41,0
.endif
vd_phase=bp_state
vd_live=bp_state+1
vd_color=bp_state+2
vd_fault=bp_state+3
vd_base=bp_state+5
vd_pages=bp_state+6
vd_handle=bp_state+7
vd_saved=bp_state+11
vd_pointer_visible=bp_state+25
vd_pointer_x=bp_state+26
vd_pointer_y=bp_state+28
vs_reu=bp_state+29
vs_token=bp_state+30
ru_active=bp_state+38
ru_probe_live=bp_state+39
bp_backend_pending=bp_state+40
.include "../banked.inc"
.include "../banked-load.inc"
