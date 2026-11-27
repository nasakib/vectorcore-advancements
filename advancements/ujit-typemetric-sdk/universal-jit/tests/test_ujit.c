#include "ujit.h"
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>

static int tests_run = 0;
static int tests_passed = 0;

#define TEST_ASSERT(cond, msg) do { \
    tests_run++; \
    if (!(cond)) { \
        printf("[FAIL] %s:%d: %s\n", __FILE__, __LINE__, msg); \
    } else { \
        tests_passed++; \
        printf("[PASS] %s\n", msg); \
    } \
} while(0)

void test_basic_arithmetic(void) {
    ujit_ctx_t *ctx = ujit_create();
    const char *code =
        "fn calc(a: int, b: int) -> int {\n"
        "    let c = a + b * 2\n"
        "    return c - 4\n"
        "}\n";
    ujit_status_t status = ujit_compile_string(ctx, code);
    TEST_ASSERT(status == UJIT_OK, "compile calc");

    int64_t args[2] = {10, 5};
    int64_t res = ujit_call(ctx, "calc", args, 2);
    /* 10 + 5 * 2 = 20, 20 - 4 = 16 */
    TEST_ASSERT(res == 16, "calc(10, 5) == 16");

    ujit_destroy(ctx);
}

void test_branching(void) {
    ujit_ctx_t *ctx = ujit_create();
    const char *code =
        "fn abs_diff(a: int, b: int) -> int {\n"
        "    if a > b {\n"
        "        return a - b\n"
        "    } else {\n"
        "        return b - a\n"
        "    }\n"
        "}\n";
    ujit_status_t status = ujit_compile_string(ctx, code);
    TEST_ASSERT(status == UJIT_OK, "compile abs_diff");

    int64_t args1[2] = {25, 10};
    int64_t res1 = ujit_call(ctx, "abs_diff", args1, 2);
    TEST_ASSERT(res1 == 15, "abs_diff(25, 10) == 15");

    int64_t args2[2] = {10, 25};
    int64_t res2 = ujit_call(ctx, "abs_diff", args2, 2);
    TEST_ASSERT(res2 == 15, "abs_diff(10, 25) == 15");

    ujit_destroy(ctx);
}

void test_collatz_loop(void) {
    ujit_ctx_t *ctx = ujit_create();
    const char *code =
        "fn collatz(n: int) -> int {\n"
        "    let steps = 0\n"
        "    while n > 1 {\n"
        "        if n % 2 == 0 {\n"
        "            n = n / 2\n"
        "        } else {\n"
        "            n = 3 * n + 1\n"
        "        }\n"
        "        steps = steps + 1\n"
        "    }\n"
        "    return steps\n"
        "}\n";
    ujit_status_t status = ujit_compile_string(ctx, code);
    TEST_ASSERT(status == UJIT_OK, "compile collatz");

    /* Collatz of 27 takes exactly 111 steps */
    int64_t arg = 27;
    int64_t steps = ujit_call(ctx, "collatz", &arg, 1);
    TEST_ASSERT(steps == 111, "collatz(27) == 111 steps");

    /* Collatz of 12 takes 9 steps */
    arg = 12;
    steps = ujit_call(ctx, "collatz", &arg, 1);
    TEST_ASSERT(steps == 9, "collatz(12) == 9 steps");

    ujit_destroy(ctx);
}

void test_fibonacci(void) {
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
    ujit_status_t status = ujit_compile_string(ctx, code);
    TEST_ASSERT(status == UJIT_OK, "compile fib");

    /* Direct function pointer invocation without wrapper overhead */
    ujit_fn1_t fib_fn = (ujit_fn1_t)ujit_get_fn(ctx, "fib");
    TEST_ASSERT(fib_fn != NULL, "get direct fib function pointer");

    if (fib_fn) {
        TEST_ASSERT(fib_fn(0) == 0, "fib(0) == 0");
        TEST_ASSERT(fib_fn(1) == 1, "fib(1) == 1");
        TEST_ASSERT(fib_fn(10) == 55, "fib(10) == 55");
        TEST_ASSERT(fib_fn(20) == 6765, "fib(20) == 6765");
        TEST_ASSERT(fib_fn(30) == 832040, "fib(30) == 832040");
    }

    ujit_destroy(ctx);
}

void test_clothos_grid_kernel(void) {
    ujit_ctx_t *ctx = ujit_create();
    const char *code =
        "fn compute_grid_arbitrage(power_kw: int, tariff_rate: int) -> int {\n"
        "    let base_cost = power_kw * tariff_rate\n"
        "    let efficiency_factor = 92\n"
        "    let net_yield = (base_cost * efficiency_factor) / 100\n"
        "    if net_yield > 5000 {\n"
        "        return net_yield - 500\n"
        "    } else {\n"
        "        return net_yield\n"
        "    }\n"
        "}\n";
    ujit_status_t status = ujit_compile_string(ctx, code);
    TEST_ASSERT(status == UJIT_OK, "compile ClothOS grid kernel");

    int64_t args[2] = {100, 70}; /* base_cost = 7000, 7000 * 92 / 100 = 6440, > 5000 -> 6440 - 500 = 5940 */
    int64_t res = ujit_call(ctx, "compute_grid_arbitrage", args, 2);
    TEST_ASSERT(res == 5940, "compute_grid_arbitrage(100, 70) == 5940");

    ujit_destroy(ctx);
}

int main(void) {
    printf("=== Universal JIT Test Suite ===\n");
    test_basic_arithmetic();
    test_branching();
    test_collatz_loop();
    test_fibonacci();
    test_clothos_grid_kernel();

    printf("\nTest Results: %d/%d passed (%.1f%%)\n",
           tests_passed, tests_run, 100.0 * (double)tests_passed / (double)tests_run);

    return (tests_passed == tests_run) ? 0 : 1;
}
