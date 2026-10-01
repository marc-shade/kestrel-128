; File navigator launched from the graphical desktop. GPL v3.
.include "api.inc"
NK_SAVED_BUFFER=$5c00
FC_SOURCE_STORAGE=$5d00
FC_DATA_STORAGE=$5800
B_VIEW_STORAGE=$5e00
GFX_TEXT_STORAGE=$5e80
GFX_FONT_COLUMNS=1
* = N_APPBASE
FILES_PAGES = 96
b_image:
        .text "napp"
        .byte 1,1,14,<(files_module-b_image)
        .word files_module-b_image
        .byte FILES_PAGES,>(files_module-b_image)
        .word b_entry-b_image
        .word 0
        .text "files and apps",0
        .fill N_APPBASE+32-*,0
FD_VDC=1
FD_VDC_PHASE=vd_phase
FD_VDC_FAULT=vd_fault
FD_VDC_ROWS=vm_rows
FD_VDC_PENDING=vm_pending
FD_VDC_FULL=fg_vdc_full
FD_VDC_SYNC=fg_vdc_sync
FD_VDC_CLOSE=vd_close
FD_VDC_GUARD=fg_vdc_guard
FD_EMBEDDED = 0
FD_RETURN_TO_DESKTOP = 1
B_COPY = 1
B_GUI = 1
B_PAGE_STORAGE = $5b00
PM_KEYS_OWNED = 1
PM_KEYS_EXTERNAL = 1
.include "file-browser.inc"
.include "files-copy.inc"
.include "files/open-with.inc"
.include "files/presentation.inc"
.include "files/workspace.inc"
.include "input/keys.inc"
.include "files/vdc.inc"
BP_MODE=0
BP_POINTER_STATE=fg_pointer_visible
BP_POINTER_X=fg_pointer_x
BP_POINTER_Y=fg_pointer_y
bp_select_surface=fg_select_surface
.include "graphics/vdc-client.inc"
fc_safe_character = b_safe_character
; The suite Files app has no document extents to retain. Its picker fits in
; the same owned app image, with four idle transfer buffers for cache scratch.
files_module:
        .text "nmod"
        .byte 1,1,14,0
        .word files_picker_end-files_module
        .word 0
        .word copy_picker.fd_run-files_module
        .word 0
copy_picker .block
FD_VDC=1
FD_VDC_PHASE=vd_phase
FD_VDC_FAULT=vd_fault
FD_VDC_ROWS=vm_rows
FD_VDC_PENDING=vm_pending
FD_VDC_FULL=fg_vdc_full
FD_VDC_SYNC=fg_vdc_sync
FD_VDC_CLOSE=vd_close
FD_VDC_GUARD=fg_vdc_guard
FD_EMBEDDED = 1
B_COPY = 0
B_GUI = 0
FD_GUI = 1
FD_GUI_SURFACE = fg_surface
FD_BUFFER_BASE = $5000
FD_RETAINED_STORAGE = $5300
FD_DIRECT_PAGES = 4
FD_NAME_BUFFER = fc_name
FD_SCRATCH0 = fc_data
FD_SCRATCH1 = fc_data+512
FD_SCRATCH2 = fc_data
FD_SCRATCH3 = fc_data+512
FD_SAFE_CHARACTER = fc_safe_character
.include "file-dialog.inc"
.bend
files_picker_end:
        .cerror * > N_APPBASE+FILES_PAGES*256, "Files picker exceeds the module window: ", *
fc_picker_active = fg_picker_active
fc_picker_get_key = copy_picker.b_get_key
fc_picker_cache = copy_picker.b_cache
fc_picker_cursor = copy_picker.bu_cursor
fc_picker_iec_handle = copy_picker.fd_iec_handle
cloop = b_loop
        .logical files_module
files_gui_module:
        .text "nmod"
        .byte 1,1,14,0
        .word files_gui_end-files_gui_module
        .word 0
        .word fg_gui_entry-files_gui_module
        .word 0
.include "files/gui.inc"
files_gui_end:
        .cerror * > N_APPBASE+FILES_PAGES*256, "Files graphics exceed the module window"
        .here
        .logical files_module
files_open_module:
        .text "nmod"
        .byte 1,1,14,0
        .word files_open_end-files_open_module
        .word 0
        .word fl_entry-files_open_module
        .word 0
.include "files/open-with-module.inc"
files_open_end:
        .cerror * > N_APPBASE+FILES_PAGES*256, "Files associations exceed the module window"
        .here
b_end = files_module
