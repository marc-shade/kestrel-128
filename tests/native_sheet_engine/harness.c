/* Standalone calculation harness. No native OS or GUI is simulated here. */
#include "../../src/native/sheet/engine.h"
#include <string.h>

#ifdef __CC65__
#define sh_test_cells ((char *)0x4000)
#else
char sh_test_cells[SH_CELLS * SH_CELL_SIZE];
#endif

uint16_t sh_test_fail_index;
uint16_t sh_test_reads;
int32_t sh_test_number;
uint8_t sh_test_decimals;
char sh_test_formatted[13];

uint8_t sh_read_cell(uint8_t index, char *out)
{
    ++sh_test_reads;
    if (index == sh_test_fail_index) return 1;
    memcpy(out, sh_test_cells + (uint16_t)index * SH_CELL_SIZE, SH_CELL_SIZE);
    return 0;
}

void sh_test_format(void)
{
    sh_format_number(sh_test_number, sh_test_decimals, sh_test_formatted);
}
