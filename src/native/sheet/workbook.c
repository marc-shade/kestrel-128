/* Owned 8 KiB source storage and transactional USHT v1 files, GPL v3. */
#include "native.h"
#include "workbook.h"
#include <string.h>

uint8_t wb_handle[4], wb_stage[4], wb_file[4];
uint8_t wb_dirty, wb_error, wb_poisoned;
uint8_t wb_history, wb_history_cell;
static char history_source[32], history_swap[32];
static uint8_t history_revision;
uint16_t wb_progress;
uint8_t wb_device, wb_format;
char wb_path[256];
static uint8_t record[32], header[16], expected[32];
static uint16_t crc;
static uint8_t calculating_stage, close_error;

static void select_memory(const uint8_t *handle, uint16_t offset, uint16_t count)
{
    OWNER = CURRENT;
    memcpy(HANDLE, handle, 4);
    OFFSET = offset; COUNT = count;
}

static uint8_t dispose(uint8_t *handle)
{
    uint8_t error;
    if (!handle[0]) return 0;
    select_memory(handle, 0, 1);
    error = sh_api(FREE);
    if (!error) memset(handle, 0, 4);
    return error;
}

static uint8_t close_file(void)
{
    uint8_t error;
    if (!wb_file[0]) return 0;
    if (close_error) return close_error;
    FOWNER = CURRENT; memcpy(FHANDLE, wb_file, 4);
    error = sh_api(FCLOSE);
    if (!error) memset(wb_file, 0, 4);
    else close_error = error;
    return error;
}

static uint8_t cleanup(void)
{
    uint8_t error = close_file();
    if (error) return error;
    return dispose(wb_stage);
}

uint8_t wb_cleanup(void)
{
    /* Entry from an explicit New/Open/Save/Back retry. A finish path never
     * automatically repeats a CLOSE that already failed in that operation. */
    close_error = 0;
    return cleanup();
}

static uint8_t stage_allocate(void)
{
    uint8_t error = wb_cleanup();
    if (error) return error;
    OWNER = CURRENT; BANK = 1; PAGES = 32;
    error = sh_api(ALLOC);
    if (!error) memcpy(wb_stage, HANDLE, 4);
    return error;
}

static uint8_t publish(void)
{
    uint8_t error;
    calculating_stage = 1;
    error = sh_recalculate();
    calculating_stage = 0;
    if (!error) error = dispose(wb_handle);
    if (error) {
        if (wb_handle[0]) sh_recalculate();
        return error;
    }
    memcpy(wb_handle, wb_stage, 4);
    memset(wb_stage, 0, 4);
    wb_dirty = wb_poisoned = 0;
    wb_history = 0;
    return 0;
}

uint8_t wb_new(void)
{
    uint16_t offset;
    uint8_t error = stage_allocate();
    if (error) return wb_error = error;
    for (offset = 0; offset < 8192; offset += 512) {
        select_memory(wb_stage, offset, 512); REG(0x3d0c) = 0;
        error = sh_api(FILL);
        if (error) break;
    }
    if (!error) error = publish();
    if (error) wb_cleanup();
    return wb_error = error;
}

uint8_t sh_read_cell(uint8_t cell, char *out)
{
    uint8_t error;
    if (calculating_stage) select_memory(wb_stage, (uint16_t)cell * 32, 32);
    else select_memory(wb_handle, (uint16_t)cell * 32, 32);
    error = sh_api(READ);
    if (!error) memcpy(out, BUFFER, 32);
    return error;
}

static uint8_t valid_record(const uint8_t *text)
{
    uint8_t i, end = 0;
    for (i = 0; i < 32; ++i) {
        if (!text[i]) end = 1;
        else if (end || text[i] < 32 || text[i] > 126) return 0;
    }
    return end;
}

uint8_t wb_set(uint8_t cell, const char *source)
{
    uint8_t error;
    if (wb_poisoned) return wb_error = WB_RETAINED;
    if (!valid_record((const uint8_t *)source)) return wb_error = WB_BADFILE;
    error = sh_read_cell(cell, (char *)record);
    if (error) return wb_error = error;
    if (!memcmp(record, source, 32)) return wb_error = sh_recalculate();
    select_memory(wb_handle, (uint16_t)cell * 32, 32);
    memcpy(BUFFER, source, 32);
    error = sh_api(WRITE);
    if (error) {
        /* A failed transfer may have changed a prefix. Refuse subsequent
         * edits/saves until New/Open replaces the uncertain workbook. */
        wb_poisoned = 1;
        return wb_error = error;
    }
    memcpy(history_source, record, 32);
    wb_history_cell = cell;
    wb_history = 1;
    ++history_revision;
    wb_dirty = 1;
    return wb_error = sh_recalculate();
}

uint8_t __fastcall__ wb_undo(uint8_t redo)
{
    uint8_t error, revision = history_revision;
    if (wb_poisoned) return wb_error = WB_RETAINED;
    if (wb_history != (redo ? 2 : 1)) return 0;
    /* wb_set captures the current source before replacing it. Keep its input
     * separate from that capture so Undo and Redo exchange complete records. */
    memcpy(history_swap, history_source, 32);
    error = wb_set(wb_history_cell, history_swap);
    if (history_revision != revision) wb_history = redo ? 1 : 2;
    return error;
}

static void crc_add(const uint8_t *bytes, uint8_t count)
{
    uint8_t bit;
    while (count--) {
        crc ^= (uint16_t)*bytes++ << 8;
        for (bit = 0; bit < 8; ++bit)
            crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : crc << 1;
    }
}

static uint8_t open_file(uint8_t mode)
{
    uint16_t length = strlen(wb_path);
    uint8_t error;
    if (wb_file[0]) return WB_RETAINED;
    if (!length || length > (wb_format == 3 ? 255 : 16)) return 1;
    if (wb_format == 3 && wb_path[0] != '/') return 1;
    FOWNER = CURRENT; FDEVICE = wb_device; FFORMAT = wb_format;
    FMODE = mode; FTYPE = 0; FNAMELEN = (uint8_t)length;
    memcpy((void *)(wb_format == 3 ? 0x4e00 : 0x3da0), wb_path, length);
    memset(FHANDLE, 0, 4);
    error = sh_api(FOPEN);
    /* OPEN may return a retained cleanup handle even when it fails. */
    memcpy(wb_file, FHANDLE, 4);
    return error;
}

static uint8_t transfer(uint8_t operation, uint16_t count)
{
    uint8_t error;
    FOWNER = CURRENT; memcpy(FHANDLE, wb_file, 4); FCOUNT = count;
    error = sh_api(operation);
    if (!error && FACTUAL != count) error = WB_BADFILE;
    return error;
}

static uint8_t check_eof(void)
{
    uint8_t error;
    FOWNER = CURRENT; memcpy(FHANDLE, wb_file, 4); FCOUNT = 1;
    error = sh_api(FREAD);
    return error ? error : (FACTUAL || !FEOF ? WB_BADFILE : 0);
}

static uint8_t finish(uint8_t error)
{
    uint8_t failed = cleanup();
    return wb_error = failed ? failed : error;
}

uint8_t wb_open(void)
{
    uint8_t error;
    uint16_t cell;
    error = stage_allocate();
    if (error) return wb_error = error;
    error = open_file(0);
    if (!error) error = transfer(FREAD, 16);
    if (!error) {
        memcpy(header, BUFFER, 16);
        if (memcmp(header, "USHT\1\10\40\40\0\40", 10) ||
            header[12] || header[13] || header[14] || header[15]) error = WB_BADFILE;
    }
    crc = 0xffff;
    for (cell = 0; !error && cell < 256; ++cell) {
        wb_progress = cell;
        if (wb_poll()) { error = WB_CANCEL; break; }
        error = transfer(FREAD, 32);
        if (error) break;
        if (!valid_record(BUFFER)) { error = WB_BADFILE; break; }
        memcpy(record, BUFFER, 32); crc_add(record, 32);
        select_memory(wb_stage, cell * 32, 32);
        memcpy(BUFFER, record, 32);
        error = sh_api(WRITE);
    }
    if (!error && crc != ((uint16_t)header[11] << 8 | header[10])) error = WB_BADFILE;
    if (!error) error = check_eof();
    if (!error) error = close_file();
    if (!error) error = publish();
    return finish(error);
}

uint8_t wb_save(void)
{
    uint8_t error;
    uint16_t cell;
    if (wb_poisoned) return wb_error = WB_RETAINED;
    error = wb_cleanup();
    if (error) return wb_error = error;
    crc = 0xffff;
    for (cell = 0; cell < 256; ++cell) {
        wb_progress = cell;
        if (wb_poll()) return wb_error = WB_CANCEL;
        error = sh_read_cell((uint8_t)cell, (char *)record);
        if (error) return wb_error = error;
        if (!valid_record(record)) return wb_error = WB_BADFILE;
        crc_add(record, 32);
    }
    memset(header, 0, 16);
    memcpy(header, "USHT\1\10\40\40\0\40", 10);
    header[10] = (uint8_t)crc; header[11] = (uint8_t)(crc >> 8);
    error = open_file(1);
    if (!error) { memcpy(BUFFER, header, 16); error = transfer(FWRITE, 16); }
    for (cell = 0; !error && cell < 256; ++cell) {
        wb_progress = cell;
        if (wb_poll()) { error = WB_CANCEL; break; }
        error = sh_read_cell((uint8_t)cell, (char *)record);
        if (!error) { memcpy(BUFFER, record, 32); error = transfer(FWRITE, 32); }
    }
    if (!error) error = close_file();
    if (!error) error = open_file(0);
    if (!error) error = transfer(FREAD, 16);
    if (!error && memcmp(BUFFER, header, 16)) error = WB_MISMATCH;
    for (cell = 0; !error && cell < 256; ++cell) {
        wb_progress = cell;
        if (wb_poll()) { error = WB_CANCEL; break; }
        error = sh_read_cell((uint8_t)cell, (char *)expected);
        if (!error) error = transfer(FREAD, 32);
        if (!error && memcmp(BUFFER, expected, 32)) error = WB_MISMATCH;
    }
    if (!error) error = check_eof();
    if (!error) error = close_file();
    if (!error) wb_dirty = 0;
    return finish(error);
}
