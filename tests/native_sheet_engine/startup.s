; Standalone CPU fixture. The source-cell region is read-only to the core.
.export __STARTUP__ : absolute = 1
.export start
.import zerobss
.import __CSTACK_RUN__, __CSTACK_SIZE__
.importzp sp
.segment "LOADADDR"
        .word $6000
.segment "STARTUP"
start:  cld
        jsr zerobss
        lda #<(__CSTACK_RUN__+__CSTACK_SIZE__)
        sta sp
        lda #>(__CSTACK_RUN__+__CSTACK_SIZE__)
        sta sp+1
        rts
.segment "CSTACK"
        .res 1024
