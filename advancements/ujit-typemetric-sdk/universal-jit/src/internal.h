#ifndef UJIT_INTERNAL_H
#define UJIT_INTERNAL_H

#include "ujit.h"
#include <stdint.h>
#include <stdbool.h>

#define UJIT_MAX_FUNCS 32
#define UJIT_MAX_CODE_SIZE 4096

typedef enum {
    IR_NOP = 0,
    IR_CONST,
    IR_MOV,
    IR_ADD,
    IR_SUB,
    IR_IMUL,
    IR_IDIV,
    IR_MOD,
    IR_AND,
    IR_OR,
    IR_XOR,
    IR_CMP_EQ,
    IR_CMP_NE,
    IR_CMP_LT,
    IR_CMP_LE,
    IR_CMP_GT,
    IR_CMP_GE,
    IR_JMP,
    IR_JZ,
    IR_JNZ,
    IR_RET,
} ir_op_t;

typedef struct {
    ir_op_t op;
    int dst;        /* Destination register/local (0..63) */
    int src1;       /* Source 1 */
    int src2;       /* Source 2 */
    int64_t imm;    /* Immediate constant or branch target instruction index */
} ir_inst_t;

typedef struct {
    char name[32];
    uint8_t num_params;
    uint8_t num_locals;
    ir_inst_t insts[UJIT_MAX_INSTRUCTIONS];
    size_t inst_count;

    /* JIT native machine code */
    uint8_t *code;
    size_t code_size;
} ujit_func_t;

struct ujit_ctx {
    ujit_target_t target;
    ujit_func_t funcs[UJIT_MAX_FUNCS];
    size_t func_count;
};

/* Internal compiler pipeline passes */
ujit_status_t ujit_parse_and_build_ir(ujit_ctx_t *ctx, const char *source);
void ujit_optimize_ir(ujit_func_t *fn);
ujit_status_t ujit_emit_x86_64(ujit_func_t *fn);

#endif /* UJIT_INTERNAL_H */
