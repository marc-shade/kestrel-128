; The selected half-open byte span survives renderer/picker module swaps.
; The anchor and caret are token boundaries, including complete CRLF pairs.
es_clear:
        lda #0
        sta es_active
        sta es_mark
        sta es_drag
        lda #1
        sta es_dirty
        rts

; Carry clear means that the current token belongs to the selected span.
; Retained bounds also work while only the text fallback is available.
es_glyph:
        lda es_active
        beq es_glyph_plain
        #doc_cmp3 ed_token_start,es_first
        bcc es_glyph_plain
        #doc_cmp3 ed_token_start,es_limit
        rts
es_glyph_plain:
        sec
        rts

es_active: .byte 0
es_mark: .byte 0
es_drag: .byte 0
es_dirty: .byte 0
es_anchor: .fill 3,0
es_first: .fill 3,0
es_limit: .fill 3,0
