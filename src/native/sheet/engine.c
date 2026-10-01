/* Native Kestrel spreadsheet calculation core, GPL v3.
 * Numbers are decimal: a signed 32-bit mantissa and 0..6 decimals. Each step
 * is computed exactly in 64 bits, then rounded once, half away from zero, to
 * as many decimals as fit (docs/NATIVE-SHEET.md).
 * Cell dependencies use an explicit 256-cell stack, never the CPU stack.
 */
#include "engine.h"
#include <string.h>
#ifdef SH_MODULE
#define sh_recalculate sh_calculate
#endif

#define SH_MAX INT32_C(2147483647)
#define SH_MIN (-SH_MAX - 1)
#define SH_PENDING 255

/* A 64-bit magnitude, least significant byte first. */
typedef uint8_t wide[8];
#define scale sh_scale         /* decimals of the value just returned */

int32_t sh_values[SH_CELLS];
uint8_t sh_types[SH_CELLS];
static uint8_t seen[SH_CELLS];
static uint8_t cells[SH_CELLS];
static char source[SH_CELL_SIZE];
static uint8_t position, depth, error, dependency;

static uint8_t upper(uint8_t c)
{
    /* Explicit ASCII: cc65's c128 target maps letter literals to PETSCII. */
    return c >= 0x61 && c <= 0x7a ? c - 0x20 : c;
}

static uint8_t digit(uint8_t c)
{
    return c >= '0' && c <= '9';
}

static uint8_t letter(uint8_t c)
{
    c = upper(c);
    return c >= 0x41 && c <= 0x5a;
}

static void spaces(void)
{
    while (source[position] == ' ') ++position;
}

static void fail(uint8_t code)
{
    /* Complete grammar checks even while a dependency is being resolved.
     * Invalid syntax/references must not become spurious dependency cycles. */
    if ((code == SH_SYNTAX || code == SH_REFERENCE || code == SH_DEPTH) &&
        error != SH_SYNTAX && error != SH_REFERENCE && error != SH_DEPTH) {
        error = code;
        return;
    }
    if (!error) error = code;
}

#ifdef SH_MODULE
#pragma code-name(push, "CODE")
#endif
static uint32_t magnitude(int32_t value)
{
    return value < 0 ? (uint32_t)(-(value + 1)) + 1 : (uint32_t)value;
}
#ifdef SH_MODULE
#pragma code-name(pop)
#endif

static int32_t signed_value(uint32_t value, uint8_t negative)
{
    if (!negative) return (int32_t)value;
    if (value == UINT32_C(2147483648)) return SH_MIN;
    return -(int32_t)value;
}

/* Decimal operations: src/native/sheet/decimal.s on the 6502; the host has
 * the same operations in C below. Operands and results pass through these. */
int32_t sh_ma, sh_mb;
uint8_t sh_as, sh_bs, sh_na, sh_status, sh_scale;
int32_t sh_arith(uint8_t op);
int8_t sh_compare(void);
void sh_clear(void);
void sh_digit(uint8_t digit_value);
int32_t sh_fit(uint8_t decimals);

#ifndef __CC65__
static wide wa, wb, wc, wq;
static uint8_t nb, decs;

static void w_set(uint8_t *w, int32_t value, uint8_t *negative)
{
    uint32_t m = magnitude(value);
    *negative = value < 0;
    memset(w, 0, 8);
    w[0] = (uint8_t)m; w[1] = (uint8_t)(m >> 8);
    w[2] = (uint8_t)(m >> 16); w[3] = (uint8_t)(m >> 24);
}

static void w_small(uint8_t *w, uint8_t k, uint8_t add)     /* w = w*k + add */
{
    uint16_t carry = add;
    uint8_t i;
    for (i = 0; i < 8; ++i) {
        carry += (uint16_t)w[i] * k;
        w[i] = (uint8_t)carry;
        carry >>= 8;
    }
}

static uint8_t w_div10(uint8_t *w)                          /* returns the remainder */
{
    uint16_t rest = 0;
    uint8_t i = 8;
    while (i--) {
        rest = (uint16_t)((rest << 8) | w[i]);
        w[i] = (uint8_t)(rest / 10);
        rest %= 10;
    }
    return (uint8_t)rest;
}

static int8_t w_cmp(const uint8_t *a, const uint8_t *b)
{
    uint8_t i = 8;
    while (i--) if (a[i] != b[i]) return a[i] < b[i] ? -1 : 1;
    return 0;
}

static void w_add(uint8_t *a, const uint8_t *b)
{
    uint16_t carry = 0;
    uint8_t i;
    for (i = 0; i < 8; ++i) {
        carry += (uint16_t)a[i] + b[i];
        a[i] = (uint8_t)carry;
        carry >>= 8;
    }
}

static void w_sub(uint8_t *a, const uint8_t *b)            /* a >= b */
{
    uint16_t difference;
    uint8_t i, borrow = 0;
    for (i = 0; i < 8; ++i) {
        difference = (uint16_t)(a[i] - b[i] - borrow);
        a[i] = (uint8_t)difference;
        borrow = (uint8_t)(difference >> 8) & 1;
    }
}

static void w_scale(uint8_t *w, uint8_t from, uint8_t to)
{
    while (from++ < to) w_small(w, 10, 0);
}

static void loads(void)
{
    w_set(wa, sh_ma, &sh_na);
    w_set(wb, sh_mb, &nb);
}

static void align(void)
{
    decs = sh_as > sh_bs ? sh_as : sh_bs;
    w_scale(wa, sh_as, decs);
    w_scale(wb, sh_bs, decs);
}

/* wa (sign sh_na) with decs decimals -> the result (see decimal.s). */
static int32_t fit(void)
{
    uint8_t drop = decs > SH_DECIMALS ? decs - SH_DECIMALS : 0, i;
    uint32_t m;
    for (;;) {
        memcpy(wc, wa, 8);
        if (drop) {
            for (i = 1; i < drop; ++i) w_div10(wc);
            if (w_div10(wc) >= 5) w_small(wc, 1, 1);
        }
        if (!(wc[7] | wc[6] | wc[5] | wc[4]) &&
            (wc[3] < 0x80 || (sh_na && wc[3] == 0x80 && !(wc[2] | wc[1] | wc[0])))) break;
        if (drop == decs) { sh_status = 1; sh_scale = 0; return 0; }
        ++drop;
    }
    decs -= drop;
    while (decs) {
        memcpy(wq, wc, 8);
        if (w_div10(wq)) break;
        memcpy(wc, wq, 8);
        --decs;
    }
    m = ((uint32_t)wc[3] << 24) | ((uint32_t)wc[2] << 16) | ((uint32_t)wc[1] << 8) | wc[0];
    sh_scale = m ? decs : 0;
    return signed_value(m, sh_na);
}

int32_t sh_arith(uint8_t op)
{
    uint8_t i, digit_value;
    sh_status = 0;
    loads();
    if (op == '-') { nb ^= 1; op = '+'; }
    if (op == '+') {
        align();
        if (sh_na == nb) w_add(wa, wb);
        else if (w_cmp(wa, wb) < 0) { w_sub(wb, wa); memcpy(wa, wb, 8); sh_na = nb; }
        else w_sub(wa, wb);
        return fit();
    }
    sh_na ^= nb;
    if (op == '*') {
        memset(wq, 0, 8);                   /* by bytes of wb, most significant first */
        for (i = 4; i--;) {
            memmove(wq + 1, wq, 7);
            wq[0] = 0;
            memcpy(wc, wa, 8);
            w_small(wc, wb[i], 0);
            w_add(wq, wc);
        }
        memcpy(wa, wq, 8);
        decs = sh_as + sh_bs;
        return fit();
    }
    if (!(wb[3] | wb[2] | wb[1] | wb[0])) { sh_status = 2; sh_scale = 0; return 0; }
    w_scale(wa, 0, sh_bs);                  /* (|a|*10^bs)/(|b|*10^as) */
    w_scale(wb, 0, sh_as);
    memset(wq, 0, 8);
    memset(wc, 0, 8);
    for (i = 64; i--;) {
        w_small(wc, 2, (wa[i >> 3] >> (i & 7)) & 1);
        w_small(wq, 2, 0);
        if (w_cmp(wc, wb) >= 0) { w_sub(wc, wb); wq[0] |= 1; }
    }
    if (wq[7] | wq[6] | wq[5] | wq[4]) { sh_status = 1; sh_scale = 0; return 0; }
    for (i = 0; i <= SH_DECIMALS; ++i) {
        w_small(wc, 10, 0);
        for (digit_value = 0; w_cmp(wc, wb) >= 0; ++digit_value) w_sub(wc, wb);
        w_small(wq, 10, digit_value);
    }
    memcpy(wa, wq, 8);
    decs = SH_DECIMALS + 1;
    return fit();
}

int8_t sh_compare(void)
{
    int8_t order;
    loads();
    if (sh_na != nb) return sh_na ? -1 : 1;
    align();
    order = w_cmp(wa, wb);
    return sh_na ? -order : order;
}

void sh_clear(void)
{
    sh_status = 0;
    memset(wa, 0, 8);
}

void sh_digit(uint8_t digit_value)
{
    if (wa[5]) { sh_status = 1; return; }  /* past 2^40: too large at any scale */
    w_small(wa, 10, digit_value);
}

int32_t sh_fit(uint8_t decimals)
{
    decs = decimals;
    sh_status = 0;
    return fit();
}
#endif

/* Digits, then optionally '.' and digits: kept to seven decimals (the rest
 * cannot change the rounding at six). */
static int32_t number(uint8_t negative)
{
    uint8_t decimals = 0, point = 0, c;
    int32_t value;
    sh_clear();
    for (;;) {
        c = source[position];
        if (c == '.' && !point) { point = 1; ++position; continue; }
        if (!digit(c)) break;
        ++position;
        if (point) {
            if (decimals > SH_DECIMALS) continue;
            ++decimals;
        }
        sh_digit(c - '0');
    }
    sh_scale = 0;
    if (sh_status) { fail(SH_OVERFLOW); return 0; }
    sh_na = negative;
    value = sh_fit(decimals);
    if (sh_status) fail(SH_OVERFLOW);
    return value;
}

static int32_t arithmetic(int32_t a, uint8_t as, int32_t b, uint8_t bs, uint8_t op)
{
    sh_scale = 0;
    if (error) return 0;
    sh_ma = a; sh_as = as; sh_mb = b; sh_bs = bs;
    a = sh_arith(op);
    if (sh_status) fail(sh_status == 2 ? SH_DIVZERO : SH_OVERFLOW);
    return a;
}

static int8_t compare(int32_t a, uint8_t as, int32_t b, uint8_t bs)
{
    sh_ma = a; sh_as = as; sh_mb = b; sh_bs = bs;
    return sh_compare();
}

/* Consume an entire reference even when it is outside the workbook. */
static uint8_t reference(void)
{
    uint8_t column, invalid = 0, first;
    uint16_t row = 0;
    spaces();
    if (!letter(source[position])) { fail(SH_SYNTAX); return 0; }
    column = upper(source[position++]) - 0x41;
    while (letter(source[position])) { ++position; invalid = 1; }
    first = source[position];
    if (!digit(first)) { fail(SH_SYNTAX); return 0; }
    while (digit(source[position])) {
        if (row <= SH_ROWS) row = row * 10 + source[position] - '0';
        ++position;
    }
    if (invalid || column >= SH_COLUMNS || first == '0' || row < 1 || row > SH_ROWS) {
        fail(SH_REFERENCE);
        return 0;
    }
    return (uint8_t)((row - 1) * SH_COLUMNS + column);
}

static int32_t cell_value(uint8_t index, uint8_t in_sum)
{
    scale = 0;
    if (error) return 0;
    if (!seen[index]) {
        dependency = index;
        error = SH_PENDING;
        return 0;
    }
    if (seen[index] == 1) { fail(SH_CYCLE); return 0; }
    switch (sh_types[index] & SH_TYPE_MASK) {
    case SH_EMPTY: return 0;
    case SH_NUMBER:
        scale = sh_types[index] >> 4;
        return sh_values[index];
    case SH_TEXT:
        if (!in_sum) fail(SH_VALUE);
        return 0;
    default:
        fail(sh_types[index]);
        return 0;
    }
}

static int32_t expression(void);

/* Aggregates accept one rectangle, ignoring empty/text cells. All resolve
 * dependencies and propagate cell errors, including COUNT. Empty sets give 0. */
static int32_t aggregate(uint8_t function)
{
    uint8_t first, last, x, y, x0, x1, y0, y1, swap, index, found = 0, vs = 0, is;
    int32_t value = 0, item;
    spaces();
    if (source[position] != '(') { fail(SH_SYNTAX); return 0; }
    ++position;
    first = reference(); spaces();
    if (source[position] != ':') { fail(SH_SYNTAX); return 0; }
    ++position;
    last = reference(); spaces();
    if (source[position] != ')') { fail(SH_SYNTAX); return 0; }
    ++position;
    if (error) return 0;
    x0 = first % SH_COLUMNS; y0 = first / SH_COLUMNS;
    x1 = last % SH_COLUMNS; y1 = last / SH_COLUMNS;
    if (x0 > x1) { swap = x0; x0 = x1; x1 = swap; }
    if (y0 > y1) { swap = y0; y0 = y1; y1 = swap; }
    for (y = y0; y <= y1; ++y) {
        for (x = x0; x <= x1; ++x) {
            index = y * SH_COLUMNS + x;
            item = cell_value(index, 1);
            is = scale;
            if (error) return 0;
            if ((sh_types[index] & SH_TYPE_MASK) != SH_NUMBER) continue;
            if (function == 0) { value = arithmetic(value, vs, item, is, '+'); vs = scale; }
            else if (function == 3) ++value;
            else if (!found || compare(item, is, value, vs) == (function == 1 ? -1 : 1)) {
                value = item; vs = is;
            }
            found = 1;
            if (error) return 0;
        }
    }
    scale = vs;
    return value;
}

static int32_t primary(void)
{
    int32_t value;
    uint8_t start, index;
    spaces();
    if (digit(source[position])) return number(0);
    if (source[position] == '(') {
        if (depth == SH_EXPRESSION_DEPTH) { fail(SH_DEPTH); return 0; }
        ++depth; ++position;
        value = expression();
        --depth; spaces();
        if (source[position] != ')') fail(SH_SYNTAX);
        else ++position;
        return value;
    }
    if (letter(source[position])) {
        start = position;
        while (letter(source[position])) ++position;
        if (position - start == 3 && upper(source[start]) == 0x53 &&
            upper(source[start+1]) == 0x55 && upper(source[start+2]) == 0x4d) return aggregate(0);
        if (position - start == 3 && upper(source[start]) == 0x4d) {
            if (upper(source[start+1]) == 0x49 && upper(source[start+2]) == 0x4e) return aggregate(1);
            if (upper(source[start+1]) == 0x41 && upper(source[start+2]) == 0x58) return aggregate(2);
        }
        if (position - start == 5 && upper(source[start]) == 0x43 &&
            upper(source[start+1]) == 0x4f && upper(source[start+2]) == 0x55 &&
            upper(source[start+3]) == 0x4e && upper(source[start+4]) == 0x54) return aggregate(3);
        position = start;
        index = reference();
        return cell_value(index, 0);
    }
    fail(SH_SYNTAX);
    return 0;
}

static int32_t unary(void)
{
    uint8_t negative = 0, signs = 0;
    int32_t value;
    spaces();
    while (source[position] == '+' || source[position] == '-') {
        if (++signs > SH_EXPRESSION_DEPTH) { fail(SH_DEPTH); return 0; }
        if (source[position] == '-') negative ^= 1;
        ++position; spaces();
    }
    if (digit(source[position])) return number(negative);
    value = primary();
    if (!negative || error) return value;
    return arithmetic(0, 0, value, scale, '-');
}

static int32_t product(void)
{
    int32_t value = unary(), rhs;
    uint8_t op, vs = scale;
    spaces();
    while (source[position] == '*' || source[position] == '/') {
        op = source[position++];
        rhs = unary();
        value = arithmetic(value, vs, rhs, scale, op);
        vs = scale;
        spaces();
    }
    scale = vs;
    return value;
}

static int32_t expression(void)
{
    int32_t value = product(), rhs;
    uint8_t op, vs = scale;
    spaces();
    while (source[position] == '+' || source[position] == '-') {
        op = source[position++];
        rhs = product();
        value = arithmetic(value, vs, rhs, scale, op);
        vs = scale;
        spaces();
    }
    scale = vs;
    return value;
}

static uint8_t evaluate(uint8_t index, int32_t *value)
{
    uint8_t i, negative = 0, start;
    if (sh_read_cell(index, source)) return SH_IO;
    /* Never let a malformed record move the parser beyond its own buffer. */
    for (i = 0; i < SH_CELL_SIZE; ++i) {
        if (!source[i]) break;
        if ((uint8_t)source[i] < 32 || (uint8_t)source[i] > 126) return SH_SYNTAX;
    }
    if (i == SH_CELL_SIZE) return SH_SYNTAX;
    position = depth = error = 0;
    spaces();
    if (!source[position]) return SH_EMPTY;
    if (source[position] == '\'') return SH_TEXT;
    if (source[position] == '=') {
        ++position;
        *value = expression();
        spaces();
        if (source[position]) fail(SH_SYNTAX);
        return error ? error : SH_NUMBER;
    }
    if (source[position] == '-' || source[position] == '+') {
        negative = source[position] == '-'; ++position;
    }
    start = position;
    while (digit(source[position])) ++position;
    if (position == start) return SH_TEXT;
    if (source[position] == '.') {
        ++position;
        while (digit(source[position])) ++position;
    }
    spaces();
    if (source[position]) return SH_TEXT;
    position = start;
    *value = number(negative);
    return error ? error : SH_NUMBER;
}

uint8_t sh_recalculate(void)
{
    uint16_t next, level;
    uint8_t index, type;
    int32_t value;
    memset(seen, 0, sizeof(seen));
    memset(sh_values, 0, sizeof(sh_values));
    memset(sh_types, SH_EMPTY, sizeof(sh_types));
    for (next = 0; next < SH_CELLS; ++next) {
        if (seen[next]) continue;
        level = 1; cells[0] = (uint8_t)next; seen[next] = 1;
        while (level) {
            index = cells[level - 1]; value = 0;
            type = evaluate(index, &value);
            if (type == SH_IO) {
                memset(sh_values, 0, sizeof(sh_values));
                memset(sh_types, SH_IO, sizeof(sh_types));
                return SH_IO;
            }
            if (type == SH_PENDING) {
                /* An unseen cell implies at most 255 cells already stacked. */
                if (level < SH_CELLS) {
                    cells[level++] = dependency; seen[dependency] = 1;
                    continue;
                }
                type = SH_DEPTH;
            }
            sh_types[index] = type == SH_NUMBER ? SH_NUMBER | (uint8_t)(scale << 4) : type;
            sh_values[index] = type == SH_NUMBER ? value : 0;
            seen[index] = 2; --level;
        }
    }
    return 0;
}

#ifdef SH_MODULE
#pragma code-name("CODE")
#endif
void sh_format_number(int32_t value, uint8_t decimals, char *out)
{
    char reverse[10];
    uint8_t count = 0;
    uint32_t number = magnitude(value);
    if (value < 0) *out++ = '-';
    do {
        reverse[count++] = '0' + (uint8_t)(number % 10);
        number /= 10;
    } while (number);
    while (count <= decimals) reverse[count++] = '0';
    while (count) {
        if (count == decimals) *out++ = '.';
        *out++ = reverse[--count];
    }
    *out = 0;
}
