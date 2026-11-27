#include "ujit.h"
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

/* C baseline function for comparison */
static int64_t c_fib(int64_t n) {
    if (n <= 1) return n;
    int64_t a = 0, b = 1;
    for (int64_t i = 2; i <= n; i++) {
        int64_t temp = a + b;
        a = b;
        b = temp;
    }
    return b;
}

int main(void) {
    printf("=== Universal JIT (ujit) Performance Benchmark ===\n\n");

    ujit_ctx_t *ctx = ujit_create();
    const char *code =
        "fn fib(n: int) -> int {\n"
        "    if n <= 1 {\n"
        "        return n\n"
        "    }\n"
        "    let a = 0\n"
        "    let b = 1\n"
        "    let i = 2\n"
        "    while i <= n {\n"
        "        let temp = a + b\n"
        "        a = b\n"
        "        b = temp\n"
        "        i = i + 1\n"
        "    }\n"
        "    return b\n"
        "}\n";

    clock_t t0 = clock();
    ujit_status_t status = ujit_compile_string(ctx, code);
    clock_t t1 = clock();
    double compile_ms = ((double)(t1 - t0) / CLOCKS_PER_SEC) * 1000.0;
    printf("[1] JIT Compilation Latency: %.2f ms\n", compile_ms);

    if (status != UJIT_OK) {
        printf("Error: Compilation failed with status %d\n", status);
        ujit_destroy(ctx);
        return 1;
    }

    ujit_fn1_t jit_fib = (ujit_fn1_t)ujit_get_fn(ctx, "fib");
    if (!jit_fib) {
        printf("Error: Function 'fib' not found\n");
        ujit_destroy(ctx);
        return 1;
    }

    long long iterations = 5000000LL;
    printf("[2] Running %lld iterations of fib(35)...\n", iterations);

    /* Benchmark Native C */
    t0 = clock();
    int64_t c_sum = 0;
    for (long long i = 0; i < iterations; i++) {
        c_sum += c_fib(35);
    }
    t1 = clock();
    double c_time = (double)(t1 - t0) / CLOCKS_PER_SEC;

    /* Benchmark Universal JIT */
    t0 = clock();
    int64_t jit_sum = 0;
    for (long long i = 0; i < iterations; i++) {
        jit_sum += jit_fib(35);
    }
    t1 = clock();
    double jit_time = (double)(t1 - t0) / CLOCKS_PER_SEC;

    printf("\n--- Results ---\n");
    printf("Compiled C (-O2) : %.4f sec (%.2f ns/call) | checksum=%lld\n",
           c_time, (c_time / (double)iterations) * 1e9, (long long)c_sum);
    printf("Universal JIT    : %.4f sec (%.2f ns/call) | checksum=%lld\n",
           jit_time, (jit_time / (double)iterations) * 1e9, (long long)jit_sum);
    printf("Relative Ratio   : %.2fx of GCC/MSVC native optimized speed!\n",
           c_time / jit_time);

    ujit_destroy(ctx);
    return 0;
}
