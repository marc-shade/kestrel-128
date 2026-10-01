; IEC sector access through the KERNAL for a GEMDESK module (GDDSK's disk
; copy, GDDLG's read-only flag): a drive's command channel and a "#" buffer
; channel (secondary address 2), U1/U2 with the module's track and sector,
; B-P, and the status line. Included inside a module's block; the module
; defines track and sector.
; A = device, X = its command channel's file; that channel (no name), then
; the buffer channel on file X-1 (secondary address 2, "#"). Carry set with
; the status in line, or "did not answer".
open_pair:
        sta device
        stx file
        lda #15
        jsr open
        dec file
        lda #2
        jsr open
        ldx file
        inx
        jmp status
open:                           ; A = secondary address; file, device
        pha
        lda #0
        tax
        jsr $ff68               ; SETBNK
        pla
        tay
        ldx device
        lda file
        jsr $ffba               ; SETLFS
        cpy #15
        lda #0                  ; the command channel: no name (nothing is sent)
        bcs +
        lda #1                  ; "#": any free buffer
+       ldx #<s_hash
        ldy #>s_hash
        jsr $ffbd               ; SETNAM
        jmp $ffc0               ; OPEN (a failure shows when the status is read)
; A = "1" or "2", X = a command file: "U1:2 0 T S" (or U2) with this track
; and sector, then the status.
u_command:
        stx command_file
        sta u_text+1
        ldx #u_end-u_text-1
-       lda u_text,x
        sta text,x
        dex
        bpl -
        lda #u_end-u_text
        sta length
        lda track
        jsr put_number
        lda #$20
        jsr put_char
        lda sector
        jsr put_number
        ldx command_file
        jmp command
; A/Y = a zero-terminated command, X = its command file.
fixed_command:
        stx command_file
        sta fc_read+1
        sty fc_read+2
        ldx #0
fc_read:
        lda $ffff,x
        sta text,x
        beq +
        inx
        bne fc_read
+       stx length
        ldx command_file
; text[length] to command file X; then its status line. Carry clear when the
; code is below 20 (00 OK, and the drive's informational codes).
command:
        stx command_file
        jsr $ffc9               ; CHKOUT
        bcs st_absent
        lda #0
        sta index
-       ldy index
        lda text,y
        jsr $ffd2
        inc index
        lda index
        cmp length
        bne -
        jsr $ffcc               ; CLRCHN: the drive runs the command
        ldx command_file
status:                         ; X = a command file: its status line -> line
        jsr $ffc6               ; CHKIN
        bcs st_absent
        lda #0
        sta length
        sta index
st_next:
        jsr $ffcf
        pha
        jsr $ffb7               ; READST
        tax
        pla
        cmp #13
        beq st_end
        ldy length
        cpy #26
        bcs +                   ; (a longer line is cut to fit the alert)
        sta line,y
        inc length
+       inc index
        bmi st_end              ; 128 bytes without a CR: not a status line
        txa
        beq st_next
st_end:
        jsr $ffcc
        ldy length
        lda #0
        sta line,y
        cpy #2
        bcc st_bad
        jsr $ffb7
        and #$83                ; not present, or a timeout
        bne st_bad
        lda line                ; the code: two digits
        sec
        sbc #$30
        cmp #2                  ; 00..19: done
        rts
st_absent:
        jsr $ffcc
st_bad:                         ; line = "a drive did not answer."
        ldx #0
-       lda s_no_answer,x
        sta line,x
        beq +
        inx
        bne -
+       sec
        rts
; After 256 data bytes: CLRCHN; carry set when the drive stopped answering.
end_transfer:
        jsr $ffcc
        jsr $ffb7
        and #$83
        cmp #1
        rts
put_number:                     ; A = 0..99 in decimal
        ldx #$2f
        sec
-       inx
        sbc #10
        bcs -
        adc #$3a
        pha
        txa
        cmp #$30
        beq +
        jsr put_char
+       pla
put_char:
        ldy length
        sta text,y
        inc length
        rts
u_text: .byte $55,$31,$3a,$32,$20,$30,$20   ; U1:2 0 
u_end:
s_bp: .byte $42,$2d,$50,$3a,$32,$20,$30,0   ; B-P:2 0
s_hash: .byte $23
s_no_answer: .byte 97,32,100,114,105,118,101,32,100,105,100,32,110,111,116,32,97,110,115,119,101,114,46,0   ; a drive did not answer.
index: .byte 0
device: .byte 0
file: .byte 0
command_file: .byte 0
length: .byte 0
text: .fill 16,0
line: .fill 32,0
