#include "internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#include <windows.h>
#else
#include <sys/mman.h>
#include <unistd.h>
#endif

ujit_ctx_t *ujit_create(void) {
    ujit_ctx_t *ctx = (ujit_ctx_t *)calloc(1, sizeof(ujit_ctx_t));
    if (ctx == NULL) return NULL;
    ctx->target = UJIT_TARGET_AUTO;
    ctx->func_count = 0;
    return ctx;
}

void ujit_set_target(ujit_ctx_t *ctx, ujit_target_t target) {
    if (ctx != NULL) {
        ctx->target = target;
    }
}

void ujit_destroy(ujit_ctx_t *ctx) {
    if (ctx == NULL) return;

    for (size_t i = 0; i < ctx->func_count; i++) {
        ujit_func_t *fn = &ctx->funcs[i];
        if (fn->code != NULL) {
#if defined(_WIN32)
            VirtualFree(fn->code, 0, MEM_RELEASE);
#else
            munmap(fn->code, fn->code_size);
#endif
            fn->code = NULL;
            fn->code_size = 0;
        }
    }

    free(ctx);
}

ujit_status_t ujit_compile_string(ujit_ctx_t *ctx, const char *source) {
    if (ctx == NULL || source == NULL) return UJIT_ERR_SYNTAX;

    size_t prev_func_count = ctx->func_count;
    ujit_status_t status = ujit_parse_and_build_ir(ctx, source);
    if (status != UJIT_OK) return status;

    for (size_t i = prev_func_count; i < ctx->func_count; i++) {
        ujit_func_t *fn = &ctx->funcs[i];
        ujit_optimize_ir(fn);
        status = ujit_emit_x86_64(fn);
        if (status != UJIT_OK) return status;
    }

    return UJIT_OK;
}

ujit_status_t ujit_compile_file(ujit_ctx_t *ctx, const char *filepath) {
    if (ctx == NULL || filepath == NULL) return UJIT_ERR_SYNTAX;

    FILE *f = fopen(filepath, "rb");
    if (!f) return UJIT_ERR_NOT_FOUND;

    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (size <= 0) {
        fclose(f);
        return UJIT_OK;
    }

    char *buf = (char *)malloc((size_t)size + 1);
    if (!buf) {
        fclose(f);
        return UJIT_ERR_MEMORY;
    }

    size_t read_bytes = fread(buf, 1, (size_t)size, f);
    buf[read_bytes] = '\0';
    fclose(f);

    ujit_status_t status = ujit_compile_string(ctx, buf);
    free(buf);
    return status;
}

void *ujit_get_fn(ujit_ctx_t *ctx, const char *name) {
    if (ctx == NULL || name == NULL) return NULL;

    for (size_t i = 0; i < ctx->func_count; i++) {
        if (strncmp(ctx->funcs[i].name, name, 31) == 0) {
            return (void *)ctx->funcs[i].code;
        }
    }
    return NULL;
}

int64_t ujit_call(ujit_ctx_t *ctx, const char *name, const int64_t *args, size_t num_args) {
    void *fn_ptr = ujit_get_fn(ctx, name);
    if (fn_ptr == NULL) return 0;

    switch (num_args) {
        case 0:
            return ((ujit_fn0_t)fn_ptr)();
        case 1:
            return ((ujit_fn1_t)fn_ptr)(args ? args[0] : 0);
        case 2:
            return ((ujit_fn2_t)fn_ptr)(args ? args[0] : 0, args ? args[1] : 0);
        case 3:
            return ((ujit_fn3_t)fn_ptr)(args ? args[0] : 0, args ? args[1] : 0, args ? args[2] : 0);
        case 4:
            return ((ujit_fn4_t)fn_ptr)(args ? args[0] : 0, args ? args[1] : 0, args ? args[2] : 0, args ? args[3] : 0);
        default: {
            typedef int64_t (*ujit_fn6_t)(int64_t, int64_t, int64_t, int64_t, int64_t, int64_t);
            int64_t a[6] = {0};
            for (size_t i = 0; i < num_args && i < 6; i++) {
                if (args) a[i] = args[i];
            }
            return ((ujit_fn6_t)fn_ptr)(a[0], a[1], a[2], a[3], a[4], a[5]);
        }
    }
}

static const char *op_to_string(ir_op_t op) {
    switch (op) {
        case IR_NOP: return "NOP";
        case IR_CONST: return "CONST";
        case IR_MOV: return "MOV";
        case IR_ADD: return "ADD";
        case IR_SUB: return "SUB";
        case IR_IMUL: return "IMUL";
        case IR_IDIV: return "IDIV";
        case IR_MOD: return "MOD";
        case IR_AND: return "AND";
        case IR_OR: return "OR";
        case IR_XOR: return "XOR";
        case IR_CMP_EQ: return "CMP_EQ";
        case IR_CMP_NE: return "CMP_NE";
        case IR_CMP_LT: return "CMP_LT";
        case IR_CMP_LE: return "CMP_LE";
        case IR_CMP_GT: return "CMP_GT";
        case IR_CMP_GE: return "CMP_GE";
        case IR_JMP: return "JMP";
        case IR_JZ: return "JZ";
        case IR_JNZ: return "JNZ";
        case IR_RET: return "RET";
        default: return "UNKNOWN";
    }
}

void ujit_dump_ir(ujit_ctx_t *ctx, const char *name) {
    if (ctx == NULL) return;

    for (size_t i = 0; i < ctx->func_count; i++) {
        ujit_func_t *fn = &ctx->funcs[i];
        if (name != NULL && strncmp(fn->name, name, 31) != 0) continue;

        printf("--- IR Function: %s (params: %u, locals: %u, instructions: %zu) ---\n",
               fn->name, fn->num_params, fn->num_locals, fn->inst_count);

        for (size_t j = 0; j < fn->inst_count; j++) {
            ir_inst_t *inst = &fn->insts[j];
            printf("  %04zu: %-8s dst=r%-2d src1=r%-2d src2=r%-2d imm=%lld\n",
                   j, op_to_string(inst->op), inst->dst, inst->src1, inst->src2, (long long)inst->imm);
        }
    }
}

void ujit_dump_bytes(ujit_ctx_t *ctx, const char *name) {
    if (ctx == NULL) return;

    for (size_t i = 0; i < ctx->func_count; i++) {
        ujit_func_t *fn = &ctx->funcs[i];
        if (name != NULL && strncmp(fn->name, name, 31) != 0) continue;

        printf("--- Machine Code: %s (%zu bytes) ---\n", fn->name, fn->code_size);
        for (size_t j = 0; j < fn->code_size; j++) {
            printf("%02x ", fn->code[j]);
            if ((j + 1) % 16 == 0) printf("\n");
        }
        if (fn->code_size % 16 != 0) printf("\n");
    }
}
