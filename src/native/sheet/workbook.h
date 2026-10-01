#ifndef KESTREL_SHEET_WORKBOOK_H
#define KESTREL_SHEET_WORKBOOK_H
#include "engine.h"
enum { WB_BADFILE=0x40, WB_MISMATCH, WB_CANCEL, WB_RETAINED };
extern uint8_t wb_handle[4], wb_stage[4], wb_file[4];
extern uint8_t wb_dirty, wb_error, wb_poisoned;
extern uint8_t wb_history, wb_history_cell;
extern uint16_t wb_progress;
extern uint8_t wb_device, wb_format;
extern char wb_path[256];
/* Called at complete record boundaries; zero continues, nonzero cancels. */
uint8_t wb_poll(void);
uint8_t wb_new(void);
uint8_t wb_cleanup(void);
uint8_t wb_set(uint8_t cell, const char *source);
uint8_t __fastcall__ wb_undo(uint8_t redo);
uint8_t wb_open(void);
uint8_t wb_save(void);
#endif
