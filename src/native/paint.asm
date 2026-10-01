; Native Kestrel Paint. Owned full-resolution image and undo history, GPL v3.
.include "api.inc"
NK_SAVED_BUFFER=$5600
GFX_TEXT_STORAGE=$5940
GFX_FONT_COLUMNS=1
PM_KEYS_OWNED=1               ; keep shared key ownership across the text picker
* = N_APPBASE
pa_image:
        .text "napp"
        .byte 1,1,14,0
        .word pa_end-pa_image
        .byte (pa_end-pa_image+255+48)/256,0
        .word pa_entry-pa_image
        .word 0
        .text "paint",0
        .fill N_APPBASE+32-*,0
pa_entry:
        cld
        jsr pa_work_init
        bcc +
        jmp N_EXIT
+       jsr pd_init
        bcc +
        jmp N_EXIT
+       jsr pa_keys_install
        lda N_BROWSERDEV
        sta pf_device
        lda N_BROWSERFMT
        sta pf_format
        jsr pa_normal_controls
        jsr pa_view_open
        jsr pa_cursor
        jsr pa_console
        jsr dl_claim
        bcs pa_start_request_error
        jsr pa_load_document
        jmp cloop
pa_start_request_error:
        cmp #0
        beq cloop
        jsr pa_file_error
cloop:
        lda #1
        sta N_READY
        jsr N_KEYIN
        bne pa_key_ready
        jsr pa_mouse
        jsr pa_vdc_sync
        jmp cloop
pa_key_ready:
        ldx #0
        stx N_READY
        jsr pa_key
        jsr pa_vdc_sync
        jmp cloop
.include "paint/workspace.inc"
.include "paint/document.inc"
.include "paint/line.inc"
.include "paint/file.inc"
.include "paint/view.inc"
.include "paint/renderer.inc"
.include "paint/input.inc"
.include "paint/dialog.inc"
.include "paint/console.inc"
pa_scene .block
draw_scene:
        lda #<scene_commands
        ldx #>scene_commands
        ldy #scene_commands_count
        jsr pa_scene_rects
        bcs +
        lda #<text_commands
        ldx #>text_commands
        ldy #text_commands_count
        jmp pa_scene_text
+       rts
.include "paint/scene.inc"
.bend
pa_confirm_scene .block
draw_scene:
        lda #<scene_commands
        ldx #>scene_commands
        ldy #scene_commands_count
        jsr pa_scene_rects
        bcs +
        lda #<text_commands
        ldx #>text_commands
        ldy #text_commands_count
        jmp pa_scene_text
+       rts
.include "paint/confirm-scene.inc"
.bend
pa_save_scene .block
draw_scene:
        lda #<scene_commands
        ldx #>scene_commands
        ldy #scene_commands_count
        jsr pa_scene_rects
        bcs +
        lda #<text_commands
        ldx #>text_commands
        ldy #text_commands_count
        jmp pa_scene_text
+       rts
.include "paint/save-scene.inc"
.bend
.include "paint/scenes.inc"
.include "paint/buttons.inc"
.include "graphics/buttons.inc"
.include "graphics/graphics-core.inc"
.include "graphics/text-core.inc"
.include "input/pointer.inc"
paint_picker .block
FD_VDC=1
FD_VDC_PHASE=vd_phase
FD_VDC_FAULT=vd_fault
FD_VDC_ROWS=vm_rows
FD_VDC_PENDING=vm_pending
FD_VDC_SYNC=pa_vdc_sync
FD_VDC_FULL=pa_vdc_full
FD_VDC_CLOSE=vd_close
FD_BUFFER_BASE=$5700
FD_EMBEDDED=1
FD_GUI=1
FD_GUI_SHARED=1
FD_GUI_SURFACE=pa_handle
B_COPY=0
FD_DIRECT_PAGES=6
FD_NAME_BUFFER=pf_name
FD_SCRATCH0=pf_compare
FD_SCRATCH1=pa_scratch
FD_SCRATCH2=pa_scratch+512
FD_SCRATCH3=pa_scratch+512
FD_SAFE_CHARACTER=pa_safe_character
.include "file-dialog.inc"
.bend
pa_picker_active=paint_picker.fd_active
pa_picker_get_key=paint_picker.b_get_key
pa_scratch=$5000
BP_MODE=0
BP_POINTER_STATE=pa_vdc_pointer
bp_select_surface=pa_select_view
.include "paint/vdc.inc"
.include "graphics/vdc-client.inc"
DL_KIND=2
DL_NAME=pf_name
DL_LENGTH=pf_length
DL_DEVICE=pf_device
DL_FORMAT=pf_format
DL_TYPE=pf_type
.include "document-launch.inc"
pa_end:
.cerror pa_end+48>N_APPLIMIT, "paint needs the packed-startup cleanup tail"
