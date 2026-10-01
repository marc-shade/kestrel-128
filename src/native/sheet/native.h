/* Foreground native API bridge. No ROM or unowned bank pointers. */
#ifndef KESTREL_SHEET_NATIVE_H
#define KESTREL_SHEET_NATIVE_H
#include <stdint.h>
#define REG(a) (*(volatile uint8_t *)(a))
#define WORD(a) (*(volatile uint16_t *)(a))
#define BUFFER ((uint8_t *)0x3a00)
#define OWNER REG(0x3d00)
#define PAGES REG(0x3d01)
#define BANK REG(0x3d02)
#define HANDLE ((uint8_t *)0x3d04)
#define OFFSET WORD(0x3d08)
#define COUNT WORD(0x3d0a)
#define READY REG(0x3d12)
#define CURRENT REG(0x3d20)
#define FOWNER REG(0x3d80)
#define FHANDLE ((uint8_t *)0x3d81)
#define FDEVICE REG(0x3d85)
#define FNAMELEN REG(0x3d86)
#define FMODE REG(0x3d87)
#define FTYPE REG(0x3d88)
#define FCOUNT WORD(0x3d89)
#define FACTUAL WORD(0x3d8b)
#define FEOF REG(0x3d8d)
#define FFORMAT REG(0x3d96)
enum { ALLOC, FREE, READ, WRITE, FILL, STATS, RELEASE, RESERVE,
       LAUNCH, KEYIN, EXIT, FOPEN, FREAD, FWRITE, FCLOSE };
uint8_t __fastcall__ sh_api(uint8_t index);
uint8_t __fastcall__ sh_clipboard(uint8_t paste);
uint8_t sh_document(void);
uint8_t sg_begin(void);
uint8_t sg_present(void);
uint8_t sg_end(void);
uint8_t sg_poll(void);
uint8_t sg_retry(void);
extern uint8_t sg_chars[1000], sg_colors[1000], sg_dirty[25];
extern uint8_t sg_bitmap, sg_error, sg_vdc_fault, sg_vdc_live;
extern uint8_t sg_hit, sg_mode;
extern uint16_t sg_mouse_x;
extern uint8_t sg_mouse_y;
#endif
