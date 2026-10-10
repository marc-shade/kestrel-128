; REU module cache, GPL v3. When boot found an idle REU of 512 KiB or more,
; N_RCACHE holds the 16 4-KiB pages reserved at its top (one 64 KiB bank,
; rc_bank) and app REU arenas stop below them. Verified modules are kept
; there, keyed by name and the running app's core CRC, so loading one again
; copies it from the REU instead of reading the disk. A cached copy goes
; through the same manifest, extent and CRC checks as a disk load; anything
; that fails them falls back to the disk. Cold boot empties the directory.
;
; Directory: the bank's first 256 bytes. +0 entry count, +1 next free
; 256-byte unit (first data unit 1; 0 when the bank is full), then RC_ENTRYLEN
; bytes per entry: name length, 16 name bytes (zero padded), core CRC LE16,
; data unit, extent LE16.
RC_ENTRYLEN = 22
RC_ENTRIES = 11
RC_KEYLEN = 19                     ; length, name and core CRC

; Called with a checked N_FNAME/N_FNAMELEN, before the Ultimate path rewrite.
; Keeps the key for rc_store. C clear with rc_unit/rc_extent on a hit.
rc_lookup:
        ldx #RC_KEYLEN-3
        lda #0
-       sta rc_key+1,x
        dex
        bpl -
        ldx N_FNAMELEN
        stx rc_key
-       lda N_FNAME-1,x
        sta rc_key,x
        dex
        bne -
        lda N_APPHEADER+14
        sta rc_key+17
        lda N_APPHEADER+15
        sta rc_key+18
        lda #0
        sta rc_unit
        lda N_RCACHE
        beq rc_miss
        jsr rc_directory_read
        bcs rc_miss
        lda N_BUFFER
        cmp #RC_ENTRIES+1
        bcs rc_miss
        sta rc_count
        ldx #2
rc_lookup_entry:
        lda rc_count
        beq rc_lookup_done
        dec rc_count
        stx rc_entry
        ldy #0
-       lda N_BUFFER,x
        cmp rc_key,y
        bne rc_lookup_next
        inx
        iny
        cpy #RC_KEYLEN
        bne -
        ldx rc_entry            ; a later matching entry replaces this one
        lda N_BUFFER+RC_KEYLEN,x
        sta rc_unit
        lda N_BUFFER+RC_KEYLEN+1,x
        sta rc_extent
        lda N_BUFFER+RC_KEYLEN+2,x
        sta rc_extent+1
rc_lookup_next:
        lda rc_entry
        clc
        adc #RC_ENTRYLEN
        tax
        jmp rc_lookup_entry
rc_lookup_done:
        lda rc_unit
        beq rc_miss
        clc
        rts
rc_miss:
        sec
        rts

; Copy the hit into the module window and check it like a disk image:
; window bounds first, then manifest, extent and CRC. C clear only when the
; window holds a valid module for this app.
rc_fetch:
        lda rc_extent+1         ; at least a manifest and one body byte
        bne +
        lda rc_extent
        cmp #17
        bcc rc_fetch_bad
+       clc                     ; m_base + extent must not pass the allocation
        lda m_base
        adc rc_extent
        tax
        lda m_base+1
        adc rc_extent+1
        bcs rc_fetch_bad
        cmp field_app_end
        bcc rc_fetch_copy
        bne rc_fetch_bad
        txa
        bne rc_fetch_bad
rc_fetch_copy:
        lda m_base
        sta rc_host
        sta rc_window+1
        lda m_base+1
        sta rc_host+1
        sta rc_window+2
        lda #0
        sta rc_reu
        lda rc_unit
        sta rc_reu+1
        lda rc_extent
        sta rc_length
        lda rc_extent+1
        sta rc_length+1
        lda #$91
        jsr rc_dma
        bcs rc_fetch_bad
        ldy #15
-       jsr rc_window_byte
        sta N_MHEADER,y
        dey
        bpl -
        jsr module_validate
        bcs rc_fetch_bad
        lda N_MHEADER+8
        cmp rc_extent
        bne rc_fetch_bad
        lda N_MHEADER+9
        cmp rc_extent+1
        bne rc_fetch_bad
        lda #$ff
        sta l_crc
        sta l_crc+1
        lda rc_extent
        sta l_left
        lda rc_extent+1
        sta l_left+1
        ldy #0
        sty rc_count            ; nonzero after the first window page
rc_fetch_crc:
        jsr rc_window_byte
        ldx rc_count
        bne +
        cpy #14
        bcc +
        cpy #16
        bcs +
        lda #0                  ; the stored CRC itself counts as zero
+       jsr app_crc_byte
        iny
        bne +
        inc rc_window+2
        inc rc_count
+       lda l_left
        bne +
        dec l_left+1
+       dec l_left
        lda l_left
        ora l_left+1
        bne rc_fetch_crc
        lda l_crc
        cmp N_MHEADER+14
        bne rc_fetch_bad
        lda l_crc+1
        cmp N_MHEADER+15
        bne rc_fetch_bad
        clc
        rts
rc_fetch_bad:
        sec
        rts
rc_window_byte:
rc_window:
        lda $ffff,y
        rts

; After a verified disk load: append the window to the cache. A failure only
; leaves the module uncached. A full directory or bank starts the cache again.
rc_store:
        lda N_RCACHE
        beq rc_store_done
        jsr rc_directory_read
        bcs rc_store_done
        lda N_BUFFER
        cmp #RC_ENTRIES
        bcs rc_store_reset
        lda N_BUFFER+1
        beq rc_store_reset
        sta rc_unit
        jsr rc_store_units
        bcc rc_store_room
rc_store_reset:
        lda #0
        sta N_BUFFER
        lda #1
        sta rc_unit
        jsr rc_store_units
        bcs rc_store_done       ; larger than the bank: never cached
rc_store_room:
        sta rc_next
        lda m_base
        sta rc_host
        lda m_base+1
        sta rc_host+1
        lda #0
        sta rc_reu
        lda rc_unit
        sta rc_reu+1
        lda N_MHEADER+8
        sta rc_length
        sta rc_extent
        lda N_MHEADER+9
        sta rc_length+1
        sta rc_extent+1
        lda #$90
        jsr rc_dma
        bcs rc_store_done
        ldy N_BUFFER            ; entry offset = 2 + count * RC_ENTRYLEN
        lda #2
-       dey
        bmi +
        clc
        adc #RC_ENTRYLEN
        bne -
+       tax
        ldy #0
-       lda rc_key,y
        sta N_BUFFER,x
        inx
        iny
        cpy #RC_KEYLEN
        bne -
        lda rc_unit
        sta N_BUFFER,x
        lda rc_extent
        sta N_BUFFER+1,x
        lda rc_extent+1
        sta N_BUFFER+2,x
        inc N_BUFFER
        lda rc_next
        sta N_BUFFER+1
        lda #$90
        jmp rc_directory_dma
rc_store_done:
        rts
; A = rc_unit + ceil(extent / 256), the next free unit (0 = exactly full).
; C set when the module does not fit before the end of the bank.
rc_store_units:
        lda N_MHEADER+8
        cmp #1                  ; C set when the extent has a partial unit
        lda N_MHEADER+9
        adc rc_unit
        bcc +
        bne +                   ; past the end; C stays set
        clc                     ; ends exactly at the bank end
+       rts

rc_directory_read:
        lda #$91
rc_directory_dma:
        ldx #<N_BUFFER
        stx rc_host
        ldx #>N_BUFFER
        stx rc_host+1
        ldx #0
        stx rc_reu
        stx rc_reu+1
        stx rc_length
        inx
        stx rc_length+1         ; 256 bytes
; A = $90 stash (C128 -> REU) or $91 fetch of rc_length bytes between
; rc_host and offset rc_reu of bank rc_bank, in DMAs of at most 256 bytes so
; interrupts wait no longer than other native REU transfers. C set when the
; REU is busy or reports a fault; the cache is then not used for this call.
rc_dma:
        sta rc_command
rc_dma_next:
        lda rc_length+1
        beq rc_dma_last
        lda #0
        ldx #1                  ; one 256-byte chunk
        jsr rc_chunk
        bcs rc_dma_done
        inc rc_host+1
        inc rc_reu+1
        dec rc_length+1
        jmp rc_dma_next
rc_dma_last:
        ldx #0
        lda rc_length
        bne rc_chunk
        clc
        rts
rc_chunk:
        sta rc_chunklen
        php
        sei
        lda $df01
        bmi rc_chunk_busy       ; another transfer is armed
        lda $df09
        and #$e0
        bne rc_chunk_busy
        lda $d506
        pha
        and #$bf                ; DMA sees physical bank 0
        sta $d506
        lda $d030
        pha
        and #$fe                ; REU DMA at 1 MHz
        sta $d030
        lda #0
        sta $df09
        sta $df0a
        lda rc_host
        sta $df02
        lda rc_host+1
        sta $df03
        lda rc_reu
        sta $df04
        lda rc_reu+1
        sta $df05
        lda rc_bank
        sta $df06
        lda rc_chunklen
        sta $df07
        stx $df08
        lda $df00               ; acknowledge an earlier completion
        lda rc_command
        sta $df01               ; immediate; the CPU resumes after the DMA
        lda $df00
        and #$60
        eor #$40                ; zero: end of block without a fault
        tax
        lda #0
        sta $df06
        lda #$10
        sta $df01               ; disarm FF00 decode
        pla
        sta $d030
        pla
        sta $d506
        plp
        cpx #1
rc_dma_done:
        rts
rc_chunk_busy:
        plp
        sec
        rts

rc_key: .fill RC_KEYLEN,0
rc_bank: .byte 0
rc_unit: .byte 0
rc_next: .byte 0
rc_entry: .byte 0
rc_count: .byte 0
rc_extent: .word 0
rc_host: .word 0
rc_reu: .word 0
rc_length: .word 0
rc_command: .byte 0
rc_chunklen: .byte 0

; Every page of the app window must still belong to the app. The walk costs
; about 2,000 cycles and module calls run twice per jiffy in pointer apps, so
; a passed walk is kept until the heap changes any page owner (N_HEAPEPOCH),
; the app handle or the window end changes. C set when a page is not the app's.
module_pages_check:
        lda N_HEAPEPOCH
        cmp mp_epoch
        bne mp_walk
        lda N_HEAPEPOCH+1
        cmp mp_epoch+1
        bne mp_walk
        lda l_app_handle
        cmp mp_handle
        bne mp_walk
        lda field_app_end
        cmp mp_end
        beq mp_ok
mp_walk:
        ldx #>N_APPBASE
-       lda NPAGES0,x
        cmp l_app_handle
        bne mp_bad
        inx
        cpx field_app_end
        bne -
        lda N_HEAPEPOCH
        sta mp_epoch
        lda N_HEAPEPOCH+1
        sta mp_epoch+1
        lda l_app_handle
        sta mp_handle
        lda field_app_end
        sta mp_end
mp_ok:
        clc
        rts
mp_bad:
        sec
        rts
mp_epoch: .word 0
mp_handle: .byte 0
mp_end: .byte 0
