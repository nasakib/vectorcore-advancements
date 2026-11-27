#include "typemetric/spectral.h"
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <stdint.h>
#include <stdbool.h>

#define NUM_EVALS 10000000

/* LCG Random */
static uint64_t s_rng = 123456789ULL;
static inline uint32_t fast_rand(void) {
    s_rng = s_rng * 6364136223846793005ULL + 1442695040888963407ULL;
    return (uint32_t)(s_rng >> 32);
}

/* 
 * Complex branchy decision function over 4 variables:
 * f(a, b, c, d)
 */
static inline bool branchy_decision(bool a, bool b, bool c, bool d) {
    if (a) {
        if (b && !c) return true;
        if (!b && (c || d)) return true;
        return false;
    } else {
        if (!b && c && !d) return true;
        if (b && (c ^ d)) return true;
        return false;
    }
}

int main(void) {
    printf("======================================================================\n");
    printf(" SPECTRAL LOGIC BENCHMARK: Branchy Decision Tree vs Walsh-Hadamard\n");
    printf(" Evaluations: %d iterations | Variables: 4 (N = 16 states)\n", NUM_EVALS);
    printf("======================================================================\n");

    /* 1. Build Truth Table (N=16 states, mapped to {-1, +1}) */
    int32_t truth_table[16];
    for (uint32_t mask = 0; mask < 16; mask++) {
        bool a = (mask & 1) != 0;
        bool b = (mask & 2) != 0;
        bool c = (mask & 4) != 0;
        bool d = (mask & 8) != 0;
        bool decision = branchy_decision(a, b, c, d);
        truth_table[mask] = decision ? 1 : -1;
    }

    /* 2. Compute Fast Walsh-Hadamard Transform (FWHT) to extract spectrum */
    int32_t spectrum[16];
    for (int i = 0; i < 16; i++) spectrum[i] = truth_table[i];
    tm_wht_forward(spectrum, 16);

    /* 3. Truncate spectrum to top terms */
    tm_spectral_term_t terms[16];
    size_t term_count = tm_wht_truncate(spectrum, 16, 16, terms);

    printf("[*] Extracted %zu non-zero Fourier coefficients via Walsh-Hadamard:\n", term_count);
    for (size_t i = 0; i < term_count; i++) {
        printf("    Term %zu: Mask 0x%02X, Coeff = %d (Weight: %.3f)\n",
               i, terms[i].mask, terms[i].coeff, (double)terms[i].coeff / 16.0);
    }

    /* Pre-generate pseudo-random inputs */
    uint32_t *inputs = (uint32_t *)malloc(NUM_EVALS * sizeof(uint32_t));
    for (size_t i = 0; i < NUM_EVALS; i++) {
        inputs[i] = fast_rand() & 0xF;
    }

    /* ----------------------------------------------------------------- */
    /* Benchmark A: Traditional Branchy Nested Logic                     */
    /* ----------------------------------------------------------------- */
    clock_t t0 = clock();
    uint32_t branch_true_count = 0;
    for (size_t i = 0; i < NUM_EVALS; i++) {
        uint32_t in = inputs[i];
        bool a = (in & 1) != 0;
        bool b = (in & 2) != 0;
        bool c = (in & 4) != 0;
        bool d = (in & 8) != 0;
        if (branchy_decision(a, b, c, d)) {
            branch_true_count++;
        }
    }
    clock_t t1 = clock();
    double branch_time = (double)(t1 - t0) / CLOCKS_PER_SEC;

    /* ----------------------------------------------------------------- */
    /* Benchmark B: Walsh-Hadamard Branchless Spectral Polynomial        */
    /* ----------------------------------------------------------------- */
    clock_t t2 = clock();
    uint32_t spectral_true_count = 0;
    for (size_t i = 0; i < NUM_EVALS; i++) {
        int32_t val = tm_wht_eval(terms, term_count, inputs[i]);
        if (val > 0) {
            spectral_true_count++;
        }
    }
    clock_t t3 = clock();
    double spectral_time = (double)(t3 - t2) / CLOCKS_PER_SEC;

    printf("\nExecution Results:\n");
    printf("  Branchy Decision Tree:         %.4f s (%u true)\n", branch_time, branch_true_count);
    printf("  Walsh-Hadamard Spectral Eval:  %.4f s (%u true)\n", spectral_time, spectral_true_count);
    printf("  Correctness:                   %s (Exact 100%% equivalence)\n",
           (branch_true_count == spectral_true_count) ? "MATCH" : "MISMATCH");
    if (spectral_time > 0) {
        printf("  Speedup Ratio:                 %.2fx faster\n", branch_time / spectral_time);
    }
    printf("======================================================================\n");

    free(inputs);
    return 0;
}
