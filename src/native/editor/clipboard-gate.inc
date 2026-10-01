; Return from the renderer before replacing its checked module window.
ed_clip_launch:
        sta ed_clip_key
        lda #3
        jsr ed_module_load
        bcs ed_picker_failed
        jsr N_MCALL
        bcc +
        lda #25
        sta ed_status
+       jmp ed_refresh
ed_clip_key: .byte 0
ed_clip_copied: .text "copied to clipboard",0
ed_clip_pasted: .text "pasted from clipboard",0
ed_clip_select: .text "select text first",0
ed_clip_empty: .text "clipboard is empty",0
ed_clip_large: .text "clipboard limit: 15 kib",0
ed_clip_error: .text "clipboard error; text retained",0
ed_clip_cleared: .text "clipboard cleared",0
eh_undone: .text "undone",0
eh_redone: .text "redone",0
eh_cleared: .text "undo history cleared",0
eh_unavailable: .text "edited; undo unavailable",0
eh_empty: .text "no undo or redo available",0
ep_printed_text: .text "printed",0
ep_absent_text: .text "no printer",0
; Copy, Cut, Paste, Clear clipboard, Undo, Redo, Forget, and Print (Ctrl-P).
ed_clip_keys: .byte 3,24,22,11,26,25,21,16
ED_CLIP_KEY_COUNT = 8
