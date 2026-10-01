; ABI 1.14 consumer. Bind DL_KIND and DL_NAME[256], DL_LENGTH, DL_DEVICE,
; DL_FORMAT, DL_TYPE to app-owned fields. C clear means a claimed document;
; C set/A=0 means none, C set/A=N_BADARG means malformed/wrong-kind request.
; No file operation occurs here. Clear the request before validating/copying,
; preserve the browser identity, and let the app's transactional Open run.
dl_claim:
        lda N_DOCREQUEST
        ldx #0
        stx N_DOCREQUEST
        cmp #0
        beq dl_none
        cmp #1
        bne dl_invalid
        lda N_DOCKIND
        cmp #DL_KIND
        bne dl_invalid
        lda N_DOCTYPE
        cmp #3
        bcs dl_invalid
        sta DL_TYPE
        lda N_BROWSERNAME_LEN
        beq dl_invalid
        lda N_BROWSERFMT
        cmp #4
        bcs dl_invalid
        sta DL_FORMAT
        lda N_BROWSERDEV
        sta DL_DEVICE
        ldy DL_FORMAT
        cpy #3
        beq dl_ultimate
        cmp #8
        bcc dl_invalid
        cmp #31
        bcs dl_invalid
        lda N_BROWSERNAME_LEN
        cmp #17
        bcs dl_invalid
        bcc dl_leaf
dl_ultimate:
        cmp #1
        bcc dl_invalid
        cmp #3
        bcs dl_invalid
        lda DL_TYPE
        bne dl_invalid
        lda N_BROWSERLEN
        beq dl_invalid
        lda N_BROWSERPATH
        cmp #$2f
        bne dl_invalid
dl_parent:
        lda N_BROWSERPATH,x
        sta DL_NAME,x
        inx
        cpx N_BROWSERLEN
        bne dl_parent
        lda DL_NAME-1,x
        cmp #$2f
        beq dl_join
        cpx #255
        beq dl_invalid
        lda #$2f
        sta DL_NAME,x
        inx
dl_join:
        txa
        clc
        adc N_BROWSERNAME_LEN
        bcs dl_invalid
dl_leaf:
        sta DL_LENGTH
        ldy #0
dl_copy_leaf:
        lda N_BROWSERNAME,y
        ; An Ultimate leaf cannot alter the retained parent or end the path.
        beq dl_invalid
        cmp #$2f
        bne +
        lda DL_FORMAT
        cmp #3
        beq dl_invalid
        lda #$2f
+
        sta DL_NAME,x
        inx
        iny
        cpy N_BROWSERNAME_LEN
        bne dl_copy_leaf
        lda #0
        sta DL_NAME,x
        clc
        rts
dl_invalid:
        lda #N_BADARG
        sec
        rts
dl_none:
        lda #0
        sec
        rts
