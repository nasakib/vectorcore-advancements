#include "typemetric/spectral.h"
#include <stdlib.h>

void tm_wht_forward(int32_t *data, size_t n) {
    if (data == NULL || n <= 1) return;

    for (size_t len = 1; len < n; len <<= 1) {
        for (size_t i = 0; i < n; i += 2 * len) {
            for (size_t j = 0; j < len; j++) {
                int32_t u = data[i + j];
                int32_t v = data[i + len + j];
                data[i + j] = u + v;
                data[i + len + j] = u - v;
            }
        }
    }
}

void tm_wht_inverse(int32_t *data, size_t n) {
    if (data == NULL || n <= 1) return;

    /* Butterfly network is self-inverse up to scaling by N */
    tm_wht_forward(data, n);
    for (size_t i = 0; i < n; i++) {
        data[i] /= (int32_t)n;
    }
}

typedef struct {
    uint32_t mask;
    int32_t coeff;
    int32_t abs_coeff;
} sort_entry_t;

static int cmp_entries(const void *a, const void *b) {
    const sort_entry_t *ea = (const sort_entry_t *)a;
    const sort_entry_t *eb = (const sort_entry_t *)b;
    if (eb->abs_coeff != ea->abs_coeff) {
        return (eb->abs_coeff > ea->abs_coeff) ? 1 : -1;
    }
    return (ea->mask > eb->mask) ? 1 : -1;
}

size_t tm_wht_truncate(const int32_t *spectrum, size_t n, size_t max_terms, tm_spectral_term_t *out_terms) {
    if (spectrum == NULL || out_terms == NULL || n == 0 || max_terms == 0) {
        return 0;
    }

    /* Stack buffer for sorting entries (supports up to 4096 truth table entries) */
    sort_entry_t entries[4096];
    size_t limit = (n > 4096) ? 4096 : n;

    for (size_t i = 0; i < limit; i++) {
        entries[i].mask = (uint32_t)i;
        entries[i].coeff = spectrum[i];
        entries[i].abs_coeff = (spectrum[i] < 0) ? -spectrum[i] : spectrum[i];
    }

    qsort(entries, limit, sizeof(sort_entry_t), cmp_entries);

    size_t out_count = 0;
    for (size_t i = 0; i < limit && out_count < max_terms; i++) {
        if (entries[i].abs_coeff > 0) {
            out_terms[out_count].mask = entries[i].mask;
            out_terms[out_count].coeff = entries[i].coeff;
            out_count++;
        }
    }

    return out_count;
}

int32_t tm_wht_eval(const tm_spectral_term_t *terms, size_t count, uint32_t input_bits) {
    if (terms == NULL || count == 0) return 0;

    int32_t sum = 0;
    for (size_t i = 0; i < count; i++) {
        uint32_t masked = terms[i].mask & input_bits;
        
        /* Compute bitwise parity: (-1)^{<mask, input>} */
        /* Branchless parity check using compiler builtin */
#if defined(__GNUC__) || defined(__clang__)
        int parity = __builtin_parity(masked);
#else
        masked ^= masked >> 16;
        masked ^= masked >> 8;
        masked ^= masked >> 4;
        masked &= 0xf;
        int parity = (0x6996 >> masked) & 1;
#endif
        /* If parity == 1: sign = -1; if parity == 0: sign = +1 */
        sum += (parity ? -terms[i].coeff : terms[i].coeff);
    }

    return sum;
}
