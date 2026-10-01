; A module's initialized state persists across calls until reload, GPL v3.
.include "api.inc"
.include "layout.inc"
* = DEMO_WINDOW
module_image:
        .text "nmod"
        .byte 1,1,7,0
        .word module_end-module_image
        .word 0                ; build.py binds this to the sealed parent's CRC
        .word module_entry-module_image
        .word 0                ; then seals the complete module
module_entry:
        inc counter
        lda counter
        beq wrapped
        clc
        rts
wrapped:
        sec                    ; application result, not a module-gate error
        rts
counter: .byte 0
module_end:
.cerror module_end > N_APPBASE+DEMO_PAGES*256, "module exceeds parent allocation"
