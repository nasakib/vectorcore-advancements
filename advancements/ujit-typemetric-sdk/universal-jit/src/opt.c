#include "internal.h"

void ujit_optimize_ir(ujit_func_t *fn) {
    if (fn == NULL || fn->inst_count == 0) return;

    /* Simple constant folding pass */
    int64_t const_vals[UJIT_MAX_LOCALS];
    bool is_const[UJIT_MAX_LOCALS] = {false};

    for (size_t i = 0; i < fn->inst_count; i++) {
        ir_inst_t *inst = &fn->insts[i];
        if (inst->op == IR_CONST) {
            if (inst->dst < UJIT_MAX_LOCALS) {
                const_vals[inst->dst] = inst->imm;
                is_const[inst->dst] = true;
            }
        } else if (inst->op == IR_ADD) {
            if (inst->src1 < UJIT_MAX_LOCALS && inst->src2 < UJIT_MAX_LOCALS &&
                is_const[inst->src1] && is_const[inst->src2]) {
                int64_t res = const_vals[inst->src1] + const_vals[inst->src2];
                inst->op = IR_CONST;
                inst->imm = res;
                if (inst->dst < UJIT_MAX_LOCALS) {
                    const_vals[inst->dst] = res;
                    is_const[inst->dst] = true;
                }
            } else if (inst->dst < UJIT_MAX_LOCALS) {
                is_const[inst->dst] = false;
            }
        } else if (inst->op == IR_SUB) {
            if (inst->src1 < UJIT_MAX_LOCALS && inst->src2 < UJIT_MAX_LOCALS &&
                is_const[inst->src1] && is_const[inst->src2]) {
                int64_t res = const_vals[inst->src1] - const_vals[inst->src2];
                inst->op = IR_CONST;
                inst->imm = res;
                if (inst->dst < UJIT_MAX_LOCALS) {
                    const_vals[inst->dst] = res;
                    is_const[inst->dst] = true;
                }
            } else if (inst->dst < UJIT_MAX_LOCALS) {
                is_const[inst->dst] = false;
            }
        } else if (inst->op == IR_IMUL) {
            if (inst->src1 < UJIT_MAX_LOCALS && inst->src2 < UJIT_MAX_LOCALS &&
                is_const[inst->src1] && is_const[inst->src2]) {
                int64_t res = const_vals[inst->src1] * const_vals[inst->src2];
                inst->op = IR_CONST;
                inst->imm = res;
                if (inst->dst < UJIT_MAX_LOCALS) {
                    const_vals[inst->dst] = res;
                    is_const[inst->dst] = true;
                }
            } else if (inst->dst < UJIT_MAX_LOCALS) {
                is_const[inst->dst] = false;
            }
        } else if (inst->op == IR_AND) {
            if (inst->src1 < UJIT_MAX_LOCALS && inst->src2 < UJIT_MAX_LOCALS &&
                is_const[inst->src1] && is_const[inst->src2]) {
                int64_t res = const_vals[inst->src1] & const_vals[inst->src2];
                inst->op = IR_CONST;
                inst->imm = res;
                if (inst->dst < UJIT_MAX_LOCALS) {
                    const_vals[inst->dst] = res;
                    is_const[inst->dst] = true;
                }
            } else if (inst->dst < UJIT_MAX_LOCALS) {
                is_const[inst->dst] = false;
            }
        } else if (inst->op == IR_OR) {
            if (inst->src1 < UJIT_MAX_LOCALS && inst->src2 < UJIT_MAX_LOCALS &&
                is_const[inst->src1] && is_const[inst->src2]) {
                int64_t res = const_vals[inst->src1] | const_vals[inst->src2];
                inst->op = IR_CONST;
                inst->imm = res;
                if (inst->dst < UJIT_MAX_LOCALS) {
                    const_vals[inst->dst] = res;
                    is_const[inst->dst] = true;
                }
            } else if (inst->dst < UJIT_MAX_LOCALS) {
                is_const[inst->dst] = false;
            }
        } else if (inst->op == IR_XOR) {
            if (inst->src1 < UJIT_MAX_LOCALS && inst->src2 < UJIT_MAX_LOCALS &&
                is_const[inst->src1] && is_const[inst->src2]) {
                int64_t res = const_vals[inst->src1] ^ const_vals[inst->src2];
                inst->op = IR_CONST;
                inst->imm = res;
                if (inst->dst < UJIT_MAX_LOCALS) {
                    const_vals[inst->dst] = res;
                    is_const[inst->dst] = true;
                }
            } else if (inst->dst < UJIT_MAX_LOCALS) {
                is_const[inst->dst] = false;
            }
        } else if (inst->dst < UJIT_MAX_LOCALS) {
            is_const[inst->dst] = false;
        }
    }
}
