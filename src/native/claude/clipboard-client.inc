/* Clipboard packets are bounded, negotiated and acknowledged. The bridge
   stages all bytes before emitting one bracketed paste, without an Enter key. */
static void paste_notice(unsigned char notice)
{
    gui_clip_status = notice;
    gui_controls_dirty = 1;
}
static void paste_cancel(void)
{
    if (gui_paste_active == 1)
        send_control(CLIENT_PASTE_ABORT);
    if (gui_paste_active == 2)
        paste_notice(12); /* END was sent: acceptance is not known yet. */
    else
        paste_notice(10);
    gui_paste_active = 0;
}
static void paste_begin(void)
{
    if (gui_clip_prepare()) {
        gui_paste_active = 0;
        paste_notice(8);
        return;
    }
    send_control(CLIENT_PASTE_BEGIN);
    acia_put(gui_clip_length[0]);
    acia_put(gui_clip_length[1]);
    gui_paste_active = 1;
    paste_notice(6);
}
static void paste_request(void)
{
    if (gui_paste_active)
        return;
    pasteJiffy = JIFFY_LOW;
    pasteTicks = 1200;
    pastePolls = 65535u;
    /* Query each time: a reconnect may reach a different bridge version. */
    gui_paste_active = 3;
    paste_notice(6);
    send_control(CLIENT_CAPABILITIES);
}
static void paste_pump(void)
{
    unsigned char i, tick;
    if (!gui_paste_active)
        return;
    N_READY = 0;
    tick = JIFFY_LOW;
    i = tick - pasteJiffy;
    pasteJiffy = tick;
    if (i >= pasteTicks) pasteTicks = 0;
    else pasteTicks -= i;
    if (pastePolls) --pastePolls;
    if (!pasteTicks || !pastePolls) {
        i = gui_paste_active;
        paste_cancel();
        paste_notice(i == 3 ? 11 : 12);
        return;
    }
    if (gui_paste_active != 1)
        return;
    if (gui_clip_chunk()) {
        paste_cancel();
        paste_notice(8);
        return;
    }
    if (!gui_clip_count) {
        send_control(CLIENT_PASTE_END);
        gui_paste_active = 2;
        pasteJiffy = JIFFY_LOW;
        pasteTicks = 1200;
        pastePolls = 65535u;
        return;
    }
    send_control(CLIENT_PASTE_CHUNK);
    acia_put(gui_clip_count);
    for (i = 0; i < gui_clip_count; ++i) {
        acia_put(((volatile unsigned char*)0x3a00)[i]);
        if (native_quit)
            return;
    }
}
