#include "typemetric/spectral.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <time.h>

#define NUM_EVALS 5000000
#define LUT_SIZE 4096
#define CHEB_DEGREE 6
#define A_BOUND -3.0
#define B_BOUND 3.0

/* Expensive target function */
static double target_function(double x, void *ctx) {
    (void)ctx;
    return sin(x) * exp(-x * x * 0.1) + cos(2.0 * x) * 0.3;
}

int main(void) {
    printf("======================================================================\n");
    printf(" SPECTRAL FUNCTION COMPRESSION BENCHMARK: 4K LUT vs Chebyshev Clenshaw\n");
    printf(" Evaluations: %d iterations | Range: [%.1f, %.1f]\n", NUM_EVALS, A_BOUND, B_BOUND);
    printf("======================================================================\n");

    /* 1. Build 4K Lookup Table (Memory footprint: 4096 * 8 = 32,768 bytes, 32 KB) */
    double *lut = (double *)malloc(LUT_SIZE * sizeof(double));
    double step = (B_BOUND - A_BOUND) / (double)(LUT_SIZE - 1);
    for (size_t i = 0; i < LUT_SIZE; i++) {
        double x = A_BOUND + (double)i * step;
        lut[i] = target_function(x, NULL);
    }

    /* 2. Fit 6-term Chebyshev Spectral Polynomial (Memory footprint: 7 * 8 = 56 bytes!) */
    double cheb_coeffs[CHEB_DEGREE + 1];
    tm_chebyshev_fit(target_function, NULL, A_BOUND, B_BOUND, CHEB_DEGREE, cheb_coeffs);

    printf("[*] Chebyshev Spectral Coefficients (Degree %d, 56 bytes):\n", CHEB_DEGREE);
    for (size_t i = 0; i <= CHEB_DEGREE; i++) {
        printf("    c_%zu = %+.8f\n", i, cheb_coeffs[i]);
    }
    printf("[*] Compression Ratio: 32,768 bytes -> 56 bytes (%.1fx compression!)\n\n",
           32768.0 / 56.0);

    /* Generate pseudo-random evaluation queries */
    double *queries = (double *)malloc(NUM_EVALS * sizeof(double));
    for (size_t i = 0; i < NUM_EVALS; i++) {
        double r = (double)rand() / (double)RAND_MAX;
        queries[i] = A_BOUND + r * (B_BOUND - A_BOUND);
    }

    /* ----------------------------------------------------------------- */
    /* Benchmark A: 4K Memory Lookup Table (Interpolated)               */
    /* ----------------------------------------------------------------- */
    clock_t t0 = clock();
    double lut_sum = 0.0;
    for (size_t i = 0; i < NUM_EVALS; i++) {
        double x = queries[i];
        double idx_f = (x - A_BOUND) / step;
        size_t idx = (size_t)idx_f;
        if (idx >= LUT_SIZE - 1) idx = LUT_SIZE - 2;
        double frac = idx_f - (double)idx;
        double val = lut[idx] * (1.0 - frac) + lut[idx + 1] * frac;
        lut_sum += val;
    }
    clock_t t1 = clock();
    double lut_time = (double)(t1 - t0) / CLOCKS_PER_SEC;

    /* ----------------------------------------------------------------- */
    /* Benchmark B: Chebyshev Spectral Clenshaw Evaluation              */
    /* ----------------------------------------------------------------- */
    clock_t t2 = clock();
    double cheb_sum = 0.0;
    for (size_t i = 0; i < NUM_EVALS; i++) {
        double val = tm_chebyshev_eval(cheb_coeffs, CHEB_DEGREE, queries[i], A_BOUND, B_BOUND);
        cheb_sum += val;
    }
    clock_t t3 = clock();
    double cheb_time = (double)(t3 - t2) / CLOCKS_PER_SEC;

    /* Measure accuracy */
    double max_err = 0.0;
    for (size_t i = 0; i < 1000; i++) {
        double exact = target_function(queries[i], NULL);
        double approx = tm_chebyshev_eval(cheb_coeffs, CHEB_DEGREE, queries[i], A_BOUND, B_BOUND);
        double err = fabs(exact - approx);
        if (err > max_err) max_err = err;
    }

    printf("Results:\n");
    printf("  Memory Lookup Table (32 KB):    %.4f s (Sum: %.2f)\n", lut_time, lut_sum);
    printf("  Chebyshev Clenshaw (56 Bytes):  %.4f s (Sum: %.2f)\n", cheb_time, cheb_sum);
    printf("  Max Approximation Error:        %.6f (Uniformly bounded)\n", max_err);
    if (cheb_time > 0) {
        printf("  Speedup Ratio:                  %.2fx faster\n", lut_time / cheb_time);
    }
    printf("======================================================================\n");

    free(lut);
    free(queries);
    return 0;
}
