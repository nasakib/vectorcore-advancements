/**
 * MiniVM JIT Adapter for Universal JIT (ujit)
 *
 * Demonstrates embedding Universal JIT directly into MiniVM or any Lua-compatible
 * runtime to compile algorithmic pseudocode / traces to bare-metal machine code.
 */

#include "ujit.h"
#include <stdio.h>
#include <stdlib.h>

/* Mock MiniVM / Lua stack interface */
typedef struct {
    ujit_ctx_t *jit_ctx;
} minivm_ujit_state_t;

minivm_ujit_state_t *minivm_ujit_init(void) {
    minivm_ujit_state_t *state = (minivm_ujit_state_t *)malloc(sizeof(minivm_ujit_state_t));
    if (!state) return NULL;
    state->jit_ctx = ujit_create();
    return state;
}

void minivm_ujit_close(minivm_ujit_state_t *state) {
    if (!state) return;
    if (state->jit_ctx) {
        ujit_destroy(state->jit_ctx);
    }
    free(state);
}

/**
 * Lower a hot loop or trace from MiniVM into bare-metal machine code.
 */
int minivm_ujit_compile_trace(minivm_ujit_state_t *state, const char *trace_code, const char *fn_name) {
    if (!state || !state->jit_ctx) return -1;
    ujit_status_t status = ujit_compile_string(state->jit_ctx, trace_code);
    if (status != UJIT_OK) return (int)status;

    void *native_ptr = ujit_get_fn(state->jit_ctx, fn_name);
    return (native_ptr != NULL) ? 0 : -1;
}

int64_t minivm_ujit_exec_trace(minivm_ujit_state_t *state, const char *fn_name, int64_t *args, size_t num_args) {
    if (!state || !state->jit_ctx) return 0;
    return ujit_call(state->jit_ctx, fn_name, args, num_args);
}
