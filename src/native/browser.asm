; Native directory browser, app discovery and bounded binary viewer. GPL v3.
.include "api.inc"
* = N_APPBASE
b_image:
        .text "napp"
        .byte 1,1,6,0
        .word b_end-b_image
        .byte (b_end-b_image+255)/256,0
        .word b_entry-b_image
        .word 0
        .text "files and apps",0
        .fill N_APPBASE+32-*,0
FD_EMBEDDED = 0
FD_RETURN_TO_DESKTOP = 0
.include "file-browser.inc"
cloop = b_loop
b_end:
        .cerror * > N_APPBASE+$2000, "browser exceeds the 8 KiB app budget"
