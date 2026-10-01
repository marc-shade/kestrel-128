; GDCPY.PRG (assembled on its own against the core's labels, gemdesk.sym,
; which build-native-desktop.py writes first; docs/NATIVE-MODULES.md).
.include "gemdesk.sym"
* = gm_module
gm_cpy:
        .text "nmod"
        .byte 1,1,14,0
        .word gm_cpy_end-gm_cpy
        .word 0
        .word copyop.entry-gm_cpy
        .word 0
.include "gemdesk-copy.inc"
gm_cpy_end:
.cerror gm_cpy_end > N_APPBASE+GM_APP_PAGES*256, "GDCPY.PRG exceeds the module window: ", gm_cpy_end
