; Called before source OPEN, while the original launch path is available.
module_source:
        jsr module_invalidate
        lda #0
        sta m_base
        sta m_base+1
        sta m_source_length
        lda N_DEVICE
        sta m_source_device
        lda N_APPFORMAT
        sta m_source_format
        cmp #3
        bne module_source_done
        ldx #0
module_source_save:
        lda N_UPATH,x
        sta N_SOURCEPATH,x
        cmp #$2f
        bne +
        txa
        clc
        adc #1
        sta m_source_length
+       inx
        cpx N_NAMELEN
        bne module_source_save
module_source_done:
        rts

; Original app allocation validation is shared with bounded field services.
app_owned:
        lda N_CURRENT
        cmp #N_APPOWNER
        bne app_owned_wrong
        lda N_APPSTATE
        cmp #2
        bne app_owned_wrong
        lda l_app_handle
        beq app_owned_bad
        cmp #NSLOTS+1
        bcs app_owned_bad
        sec
        sbc #1
        asl
        asl
        asl
        tax
        lda NHANDLES,x
        cmp N_CURRENT
        bne app_owned_bad
        lda NHANDLES+1,x
        bne app_owned_bad
        lda NHANDLES+2,x
        cmp #>N_APPBASE
        bne app_owned_bad
        ldy #1
app_owned_generation:
        lda NHANDLES+4,x
        cmp l_app_handle,y
        bne app_owned_bad
        inx
        iny
        cpy #4
        bne app_owned_generation
        lda NHANDLES,x
        beq app_owned_bad
        cmp N_APPHEADER+10
        bne app_owned_bad
        cmp #((N_APPLIMIT-N_APPBASE)/256)+1
        bcs app_owned_bad
        clc
        adc #>N_APPBASE
        sta field_app_end
        clc
        rts
app_owned_wrong:
        lda #N_WRONGOWNER
        sec
        rts
app_owned_bad:
        lda #N_BADHANDLE
        sec
        rts

; Private state fits unused mailbox bytes, which are initialized at boot.
m_generation = $3db0           ; LE24, never reset or wrapped during this boot
m_base = $3db3                 ; checked absolute window start from original NAPP
m_entry = $3db6                ; aligned for the NMOS indirect JMP boundary rule
m_return = $3db8
m_limit = $3dba                ; exclusive verified module image end, LE16
m_source_device = $3dbc
m_source_format = $3dbd
m_source_length = $3dbe
m_name_length = $3dbf
m_result = $3d3c
m_carry = $3d3d
