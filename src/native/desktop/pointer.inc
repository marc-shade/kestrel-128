; Desktop hit targets; the proportional driver is shared with native apps.
pm_control_count=GD_APP_COUNT
pm_select_surface=gd_select_surface
pm_find_hit:
        ldx #$ff
        lda pm_x+1
        bne +
        lda pm_x
        cmp #16
        bcc pm_find_done
        bcs pm_find_y
+       lda pm_x
        cmp #48
        bcs pm_find_done
pm_find_y:
        ldx #GD_APP_COUNT-1
-       lda pm_y
        sec
        sbc pm_tops,x
        cmp #16
        bcc pm_find_done
        dex
        bpl -
pm_find_done:
        rts
pm_tops: .byte 40,56,72,88,104,120,136
.include "../input/pointer.inc"
