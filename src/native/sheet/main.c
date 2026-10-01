/* Native Sheet desktop application, GPL v3. */
#include "native.h"
#include "workbook.h"
#include <string.h>

uint8_t selected, top_row, left_column, mode, edit_active, confirmed, busy;
static uint8_t field[8];
static char edit[32], cell_text[32], reference[4];
char sh_number[13];
static const char *message;
static uint8_t exiting;
char sh_clip_text[32];
static const char *const errors[] = {
    "", "", "", "#SYNTAX", "#REF", "#DIV/0", "#OVERFLOW",
    "#VALUE", "#CYCLE", "#DEPTH", "#STORAGE"
};

static void line(uint8_t row, const char *text)
{
    uint16_t offset = (uint16_t)row * 40;
    uint8_t count = 0;
    while (text[count] && count < 40) ++count;
    memset(sg_chars + offset, 32, 40);
    memcpy(sg_chars + offset, text, count);
    memset(sg_colors + offset, 0x16, 40);
    sg_dirty[row] = 1;
}

static void put(uint8_t row, uint8_t column, const char *text, uint8_t width)
{
    uint8_t count = 0;
    uint16_t offset = (uint16_t)row * 40 + column;
    while (count < width && text[count]) ++count;
    memcpy(sg_chars + offset, text, count);
    sg_dirty[row] = 1;
}

/* bridge.s: the number in sh_number, longer than its 8-character cell loses
 * decimals, rounded once; only a too-long integer part stays long. */
void fit_cell(void);

static void cell_name(void)
{
    uint8_t row = selected / 8 + 1, at = 1;
    reference[0] = 'A' + selected % 8;
    if (row >= 10) reference[at++] = '0' + row / 10;
    reference[at++] = '0' + row % 10; reference[at] = 0;
}

static void status(uint8_t error)
{
    wb_error = error;
    if (!error) return;
    if (error == WB_CANCEL) message = "Cancelled; workbook kept";
    else if (error == WB_BADFILE) message = "Invalid workbook; original kept";
    else if (error == WB_MISMATCH) message = "Readback mismatch; save unconfirmed";
    else if (wb_poisoned) message = "Storage uncertain; use Open or New";
    else message = "Operation failed; workbook kept";
}

static void render_field(void)
{
    uint8_t at, view = 0, caret;
    const char *text;
    line(4, "");
    if (mode == 1 || mode == 2) {
        text = wb_path;
        caret = field[1];
        if (caret >= 34) view = caret - 33;
        put(4, 0, view ? "<" : ">", 1);
        put(4, 2, text + view, 34);
        sg_colors[4*40+2+caret-view] = 0x07;
    } else {
        cell_name(); put(4, 0, reference, 3);
        if (edit_active) text = edit;
        else {
            if (sh_read_cell(selected, cell_text)) strcpy(cell_text, "#STORAGE");
            text = cell_text;
        }
        put(4, 5, text, 31);
        if (edit_active) {
            at = field[1];
            sg_colors[4*40+5+at] = 0x07;
        }
    }
}

static void render(void)
{
    uint8_t x, y, cell, column, type, length;
    const char *text;
    uint16_t offset;
    sg_mode = mode;
    line(0, "Sheet");
    put(0, 20, wb_poisoned ? "Storage error" : wb_dirty ? "Unsaved" : "Ready", 19);
    line(1, "----------------------------------------");
    line(2, "[New] [Open][Save][Edit][Clear]   [Back]");
    line(3, "");
    render_field();
    for (y = 5; y < 23; ++y) line(y, "");
    if (mode == 1 || mode == 2) {
        line(6, mode == 1 ? "Open workbook" : "Save As - new file name");
        line(8, "Backend:");
        put(8, 10, wb_format == 0 ? "D64" : wb_format == 1 ? "D71" : wb_format == 2 ? "D81" : "Ultimate", 10);
        line(10, "Device:");
        sh_format_number(wb_device, 0, sh_number); put(10, 10, sh_number, 3);
        line(13, "F1 changes backend; F3 changes device");
        line(15, "Enter confirms; Esc cancels");
        line(17, "Ctrl-U clears name; arrows move caret");
        line(19, wb_format == 3 ? "USB: enter the full absolute path" : "Disk: SEQ filename, up to 16 bytes");
        line(21, "Failed/cancelled new files may be partial");
    } else if (mode == 3) {
        line(9, "Discard unsaved workbook?");
        line(11, "Enter discards; Escape keeps editing");
    } else {
        for (x = 0; x < 4; ++x) {
            sh_number[0] = 'A' + left_column + x; sh_number[1] = 0;
            put(5, 6 + x * 9, sh_number, 1);
        }
        for (y = 0; y < 12; ++y) {
            sh_format_number(top_row + y + 1, 0, sh_number);
            put(6+y, 0, sh_number, 2);
            for (x = 0; x < 4; ++x) {
                cell = (top_row+y)*8 + left_column+x;
                column = 3 + x*9;
                type = sh_types[cell] & SH_TYPE_MASK;
                text = "";
                if (type == SH_NUMBER) {
                    sh_format_number(sh_values[cell], sh_types[cell] >> 4, sh_number);
                    fit_cell();
                    text = sh_number;
                }
                else if (type == SH_TEXT) {
                    if (sh_read_cell(cell, cell_text)) strcpy(cell_text, "#STORAGE");
                    text = cell_text;
                    while (*text == ' ') ++text;
                    if (*text == '\'') ++text;
                } else if (type < 11) text = errors[type];
                length = strlen(text);
                if (type == SH_NUMBER && length > 8) text = "########";
                else if (type == SH_NUMBER) column += 8-length;
                put(6+y, column, text, 8);
                offset = (uint16_t)(6+y)*40 + 3+x*9;
                if (cell == selected) memset(sg_colors + offset, 0x07, 8);
                sg_chars[offset+8] = '|';
            }
        }
        line(18, "----------------------------------------");
        line(19, "Value:");
        type = sh_types[selected] & SH_TYPE_MASK;
        if (type == SH_NUMBER) {
            sh_format_number(sh_values[selected], sh_types[selected] >> 4, sh_number);
            put(19, 7, sh_number, 12);
        }
        else if (type < 11) put(19, 7, errors[type], 16);
        line(20, "Arrows: move   Enter: edit   Del: clear");
        line(21, "F1 New   F3 Open   F5 Save As   F7 Edit");
        line(22, "Ctrl-Z Undo  Ctrl-R Redo  Home A1");
    }
    if (message) line(23, message);
    else line(23, "Numbers, text, =A1+B1, =SUM(A1:A12)");
    line(24, edit_active ? "Enter accepts cell; Escape cancels edit" : "Ctrl-C Copy  Ctrl-X Cut  Ctrl-V Paste");
    if (wb_error) {
        sh_format_number(wb_error, 0, sh_number); put(24, 31, "Err ", 4); put(24, 35, sh_number, 3);
    }
}

static void field_init(char *text, uint8_t maximum)
{
    memset(field, 0, sizeof(field));
    field[0] = strlen(text); field[2] = maximum;
    field[3] = (uint16_t)text; field[4] = (uint16_t)text >> 8;
    WORD(0x3d35) = (uint16_t)field; REG(0x3d37) = 0; sh_api(19);
}

static void field_key(uint8_t key)
{
    /* Native ROM keys use PETSCII; source records and drawn labels use ASCII.
     * C128 lower/upper character set: 41..5a lowercase, c1..da uppercase. */
    if (key >= 0xc1 && key <= 0xda) key -= 0x80;
    else if (key >= 0x41 && key <= 0x5a && !mode) key += 0x20;
    WORD(0x3d35) = (uint16_t)field; REG(0x3d37) = key;
    status(sh_api(19));
    render_field();
}

static void begin_edit(uint8_t replace)
{
    if (wb_poisoned) { status(WB_RETAINED); return; }
    if (sh_read_cell(selected, edit)) { status(SH_IO); return; }
    if (replace) memset(edit, 0, 32);
    edit_active = 1; field_init(edit, 31);
    render_field(); line(24, "Enter accepts cell; Escape cancels edit");
}

static void move(uint8_t key)
{
    uint8_t row = selected / 8, column = selected % 8;
    if (key == 0x11 && row < 31) ++row;
    if (key == 0x91 && row) --row;
    if ((key == 0x1d || key == 9) && column < 7) ++column;
    if (key == 0x9d && column) --column;
    if (key == 0x13) row = column = 0;
    selected = row*8 + column;
    if (row < top_row) top_row = row;
    if (row >= top_row+12) top_row = row-11;
    left_column = column < 4 ? 0 : 4;
    render();
}

uint8_t wb_poll(void)
{
    uint8_t key;
    if (!(wb_progress & 15)) {
        line(23, busy == 1 ? "Opening cell:" : "Saving / verifying cell:");
        sh_format_number(wb_progress+1, 0, sh_number); put(23, 26, sh_number, 3);
        if (sg_present()) return 1;
    }
    if (sg_poll() == 2 && sg_hit == 5) return 1;
    if (sg_vdc_live && sg_vdc_fault) return 1;
    key = sh_api(KEYIN);
    return key == 27 || key == 3;
}

static void action(uint8_t choice)
{
    uint8_t error;
    /* 0 New, 1 Open, 2 Save, 3 Edit, 4 Clear, 5 Back. */
    if ((choice == 0 || choice == 1 || choice == 5) &&
        (wb_dirty || wb_poisoned) && !confirmed) {
        confirmed = choice+1; mode = 3; render(); return;
    }
    if (choice == 0) {
        error = wb_new(); status(error);
        if (!error) { selected = top_row = left_column = 0; message = "New workbook"; }
    } else if (choice == 1 || choice == 2) {
        mode = choice;
        field_init(wb_path, wb_format == 3 ? 255 : 16);
    } else if (choice == 3) { begin_edit(0); return; }
    else if (choice == 4) { memset(edit, 0, 32); status(wb_set(selected, edit)); }
    else exiting = 1;
    confirmed = 0;
    render();
}

int main(void)
{
    uint8_t key, error, choice;
    wb_device = REG(0x3d29); wb_format = REG(0x3d2a);
    if (wb_format > 3) wb_format = 0;
    if (wb_format == 3) { if (wb_device < 1 || wb_device > 2) wb_device = 1; }
    else if (wb_device < 8 || wb_device > 30) wb_device = 8;
    error = wb_new();
    if (error) return error;
    error = sg_begin();
    if (error) {
        /* Retained restoration must finish before app-owned code can go. */
        while (sg_end()) {
            do { READY = 1; key = sh_api(KEYIN); READY = 0; } while (key != 27);
        }
        return error;
    }
    status(sh_document());
    render();
    for (;;) {
        error = sg_present();
        if (error) {
            /* No edits, transfers or app exit while the display is uncertain.
             * Escape/Ctrl-L explicitly retries its retained restoration. */
            READY = 1; key = sh_api(KEYIN); READY = 0;
            if (key == 27 || key == 12) { sg_retry(); render(); }
            continue;
        }
        if (exiting) {
            error = wb_cleanup();
            if (!error) error = sg_end();
            if (!error) return 0;
            exiting = 0; status(error); render(); continue;
        }
        READY = 1; key = sh_api(KEYIN); READY = 0;
        if (!key) {
            if (sg_poll() != 2) continue;
            if (sg_hit >= 6 && !mode && !edit_active) {
                selected = (top_row+(sg_hit-6)/4)*8 + left_column+(sg_hit-6)%4;
                render(); continue;
            }
            if (sg_hit >= 6) continue;
            if (mode || edit_active) {
                if (sg_hit == 5) key = 27;
                else if ((sg_hit == 1 && mode == 1) || (sg_hit == 2 && mode == 2) ||
                         (sg_hit == 3 && edit_active)) key = 13;
                else continue;
            } else { action(sg_hit); continue; }
        }
        if (mode == 3) {
            if (key == 27) { mode = confirmed = 0; render(); }
            else if (key == 13) { choice = confirmed-1; mode = 0; action(choice); }
            continue;
        }
        if (mode == 1 || mode == 2) {
            if (key == 27) { mode = 0; render(); }
            else if (key == 0x85) {
                wb_format = (wb_format+1)&3;
                wb_device = wb_format == 3 ? 1 : 8;
                if (wb_format != 3 && strlen(wb_path) > 16) wb_path[0] = 0;
                field_init(wb_path, wb_format == 3 ? 255 : 16); render();
            } else if (key == 0x86) {
                if (++wb_device > (wb_format == 3 ? 2 : 30)) wb_device = wb_format == 3 ? 1 : 8;
                render();
            } else if (key == 13) {
                busy = mode;
                error = mode == 1 ? wb_open() : wb_save();
                busy = 0;
                if (!error) {
                    message = mode == 1 ? "Workbook opened" : "Saved and fully verified";
                    if (mode == 1) selected = top_row = left_column = 0;
                    mode = 0;
                }
                status(error); render();
            } else field_key(key);
            continue;
        }
        if (edit_active) {
            if (key == 27) { edit_active = 0; render(); }
            else if (key == 13) {
                memset(edit+field[0], 0, 32-field[0]);
                error = wb_set(selected, edit); status(error);
                if (!error) { edit_active = 0; message = 0; }
                render();
            } else field_key(key);
            continue;
        }
        if (key == 27) action(5);
        else if (key == 3 || key == 22 || key == 24) {
            error = wb_poisoned ? WB_RETAINED : sh_read_cell(selected, sh_clip_text);
            if (!error) error = sh_clipboard(key == 22);
            if (!error && key != 3) {
                if (key == 24) memset(sh_clip_text, 0, 32);
                error = wb_set(selected, sh_clip_text);
            }
            message = error ? 0 : "Clipboard action complete";
            status(error);
            if (error == 1 && key == 22) message = "Paste needs 1-31 printable characters";
            render();
        }
        else if (key == 26 || key == 18) {
            if (wb_history == (key == 18 ? 2 : 1)) {
                error = wb_undo(key == 18); status(error);
                if (!error) { selected = wb_history_cell; message = 0; move(0); }
                else render();
            }
        }
        else if (key == 0x85) action(0);
        else if (key == 0x86) action(1);
        else if (key == 0x87) action(2);
        else if (key == 0x88 || key == 13) action(3);
        else if (key == 0x14) action(4);
        else if (key == 12) { sg_retry(); render(); }
        else if (key == 0x11 || key == 0x91 || key == 0x1d || key == 0x9d || key == 9 || key == 0x13) move(key);
        else if ((key >= 32 && key < 127) || (key >= 0xc1 && key <= 0xda)) {
            begin_edit(1); if (edit_active) field_key(key);
        }
    }
}
