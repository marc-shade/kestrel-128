/* Native Kestrel spreadsheet calculation core, GPL v3. */
#ifndef KESTREL_SHEET_ENGINE_H
#define KESTREL_SHEET_ENGINE_H

#include <stdint.h>

#define SH_COLUMNS 8
#define SH_ROWS 32
#define SH_CELLS 256
#define SH_CELL_SIZE 32
#define SH_EXPRESSION_DEPTH 8
#define SH_DECIMALS 6
#define SH_TYPE_MASK 15

enum sh_type {
    SH_EMPTY, SH_NUMBER, SH_TEXT, SH_SYNTAX, SH_REFERENCE,
    SH_DIVZERO, SH_OVERFLOW, SH_VALUE, SH_CYCLE, SH_DEPTH, SH_IO
};

/* The storage adapter copies one 32-byte, NUL-terminated cell into out.
 * Return zero on success. It must not change the workbook during recalc.
 * This callback lets the app keep source cells in owned banked storage. */
uint8_t sh_read_cell(uint8_t cell, char *out);

/* A number is sh_values[i] / 10^(sh_types[i] >> 4): the low four bits of
 * sh_types are the type, the high four a number's decimals (0..6). */
extern int32_t sh_values[SH_CELLS];
extern uint8_t sh_types[SH_CELLS];

/* Recompute all cells. Empty/text/error cells have value zero. A storage
 * failure returns SH_IO and invalidates every result with SH_IO; retry after
 * recovering storage. Formula errors are per-cell and return success here.
 * The core is synchronous and non-reentrant; it does not poll user input. */
uint8_t sh_recalculate(void);

/* value / 10^decimals in decimal; out has room for twelve printable
 * characters (a sign, ten digits and a point) and the trailing NUL. */
void sh_format_number(int32_t value, uint8_t decimals, char *out);

#endif
