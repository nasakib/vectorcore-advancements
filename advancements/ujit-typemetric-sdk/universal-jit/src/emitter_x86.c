#include "internal.h"
#include <string.h>

#if defined(_WIN32)
#include <windows.h>
#else
#include <sys/mman.h>
#include <unistd.h>
#endif

typedef struct {
    uint8_t bytes[UJIT_MAX_CODE_SIZE];
    size_t size;
    size_t inst_offsets[UJIT_MAX_INSTRUCTIONS];
} buffer_t;

static inline void emit_byte(buffer_t *b, uint8_t byte) {
    if (b->size < UJIT_MAX_CODE_SIZE) {
        b->bytes[b->size++] = byte;
    }
}

static inline void emit_u32(buffer_t *b, uint32_t val) {
    emit_byte(b, (uint8_t)(val & 0xFF));
    emit_byte(b, (uint8_t)((val >> 8) & 0xFF));
    emit_byte(b, (uint8_t)((val >> 16) & 0xFF));
    emit_byte(b, (uint8_t)((val >> 24) & 0xFF));
}

static inline void emit_u64(buffer_t *b, uint64_t val) {
    emit_u32(b, (uint32_t)(val & 0xFFFFFFFF));
    emit_u32(b, (uint32_t)((val >> 32) & 0xFFFFFFFF));
}

static inline int local_offset(int local_idx) {
    return -8 * (local_idx + 1);
}

/* Emit: mov rax, [rbp + offset] -> 48 8b 45 <disp8> or 48 8b 85 <disp32> */
static void emit_load_rax(buffer_t *b, int local_idx) {
    int off = local_offset(local_idx);
    emit_byte(b, 0x48);
    emit_byte(b, 0x8B);
    if (off >= -128 && off <= 127) {
        emit_byte(b, 0x45);
        emit_byte(b, (uint8_t)(int8_t)off);
    } else {
        emit_byte(b, 0x85);
        emit_u32(b, (uint32_t)off);
    }
}

/* Emit: mov [rbp + offset], rax -> 48 89 45 <disp8> or 48 89 85 <disp32> */
static void emit_store_rax(buffer_t *b, int local_idx) {
    int off = local_offset(local_idx);
    emit_byte(b, 0x48);
    emit_byte(b, 0x89);
    if (off >= -128 && off <= 127) {
        emit_byte(b, 0x45);
        emit_byte(b, (uint8_t)(int8_t)off);
    } else {
        emit_byte(b, 0x85);
        emit_u32(b, (uint32_t)off);
    }
}

/* Emit: mov rcx, [rbp + offset] */
static void emit_load_rcx(buffer_t *b, int local_idx) {
    int off = local_offset(local_idx);
    emit_byte(b, 0x48);
    emit_byte(b, 0x8B);
    if (off >= -128 && off <= 127) {
        emit_byte(b, 0x4D);
        emit_byte(b, (uint8_t)(int8_t)off);
    } else {
        emit_byte(b, 0x8D);
        emit_u32(b, (uint32_t)off);
    }
}

ujit_status_t ujit_emit_x86_64(ujit_func_t *fn) {
    if (fn == NULL) return UJIT_ERR_CODEGEN;

    buffer_t b;
    b.size = 0;

    /* 1. Prologue: push rbp; mov rbp, rsp; sub rsp, <stack_size> */
    emit_byte(&b, 0x55);               /* push rbp */
    emit_byte(&b, 0x48); emit_byte(&b, 0x89); emit_byte(&b, 0xE5); /* mov rbp, rsp */

    size_t stack_size = (size_t)fn->num_locals * 8 + 32;
    stack_size = (stack_size + 15) & ~15; /* 16-byte align */

    emit_byte(&b, 0x48); emit_byte(&b, 0x81); emit_byte(&b, 0xEC);
    emit_u32(&b, (uint32_t)stack_size);

    /* 2. Store incoming parameters from ABI registers into local slots */
#if defined(_WIN32)
    /* Windows x64 ABI: RCX, RDX, R8, R9 */
    if (fn->num_params > 0) { /* mov [rbp - 8], rcx -> 48 89 4d f8 */
        emit_byte(&b, 0x48); emit_byte(&b, 0x89); emit_byte(&b, 0x4D); emit_byte(&b, (uint8_t)local_offset(0));
    }
    if (fn->num_params > 1) { /* mov [rbp - 16], rdx -> 48 89 55 f0 */
        emit_byte(&b, 0x48); emit_byte(&b, 0x89); emit_byte(&b, 0x55); emit_byte(&b, (uint8_t)local_offset(1));
    }
    if (fn->num_params > 2) { /* mov [rbp - 24], r8 -> 4c 89 45 e8 */
        emit_byte(&b, 0x4C); emit_byte(&b, 0x89); emit_byte(&b, 0x45); emit_byte(&b, (uint8_t)local_offset(2));
    }
    if (fn->num_params > 3) { /* mov [rbp - 32], r9 -> 4c 89 4d e0 */
        emit_byte(&b, 0x4C); emit_byte(&b, 0x89); emit_byte(&b, 0x4D); emit_byte(&b, (uint8_t)local_offset(3));
    }
#else
    /* System V AMD64 ABI: RDI, RSI, RDX, RCX, R8, R9 */
    if (fn->num_params > 0) { /* mov [rbp - 8], rdi -> 48 89 7d f8 */
        emit_byte(&b, 0x48); emit_byte(&b, 0x89); emit_byte(&b, 0x7D); emit_byte(&b, (uint8_t)local_offset(0));
    }
    if (fn->num_params > 1) { /* mov [rbp - 16], rsi -> 48 89 75 f0 */
        emit_byte(&b, 0x48); emit_byte(&b, 0x89); emit_byte(&b, 0x75); emit_byte(&b, (uint8_t)local_offset(1));
    }
    if (fn->num_params > 2) { /* mov [rbp - 24], rdx -> 48 89 55 e8 */
        emit_byte(&b, 0x48); emit_byte(&b, 0x89); emit_byte(&b, 0x55); emit_byte(&b, (uint8_t)local_offset(2));
    }
    if (fn->num_params > 3) { /* mov [rbp - 32], rcx -> 48 89 4d e0 */
        emit_byte(&b, 0x48); emit_byte(&b, 0x89); emit_byte(&b, 0x4D); emit_byte(&b, (uint8_t)local_offset(3));
    }
#endif

    /* Track branch jump sites for back-patching */
    typedef struct {
        size_t patch_offset;
        size_t target_inst;
    } branch_patch_t;
    branch_patch_t patches[256];
    size_t patch_count = 0;

    /* 3. Emit instructions */
    for (size_t i = 0; i < fn->inst_count; i++) {
        b.inst_offsets[i] = b.size;
        ir_inst_t *inst = &fn->insts[i];

        switch (inst->op) {
            case IR_CONST:
                /* mov rax, imm64 -> 48 b8 <imm64> */
                emit_byte(&b, 0x48); emit_byte(&b, 0xB8);
                emit_u64(&b, (uint64_t)inst->imm);
                emit_store_rax(&b, inst->dst);
                break;

            case IR_MOV:
                emit_load_rax(&b, inst->src1);
                emit_store_rax(&b, inst->dst);
                break;

            case IR_ADD:
                emit_load_rax(&b, inst->src1);
                emit_load_rcx(&b, inst->src2);
                /* add rax, rcx -> 48 01 c8 */
                emit_byte(&b, 0x48); emit_byte(&b, 0x01); emit_byte(&b, 0xC8);
                emit_store_rax(&b, inst->dst);
                break;

            case IR_SUB:
                emit_load_rax(&b, inst->src1);
                emit_load_rcx(&b, inst->src2);
                /* sub rax, rcx -> 48 29 c8 */
                emit_byte(&b, 0x48); emit_byte(&b, 0x29); emit_byte(&b, 0xC8);
                emit_store_rax(&b, inst->dst);
                break;

            case IR_IMUL:
                emit_load_rax(&b, inst->src1);
                emit_load_rcx(&b, inst->src2);
                /* imul rax, rcx -> 48 0f af c1 */
                emit_byte(&b, 0x48); emit_byte(&b, 0x0F); emit_byte(&b, 0xAF); emit_byte(&b, 0xC1);
                emit_store_rax(&b, inst->dst);
                break;

            case IR_AND:
                emit_load_rax(&b, inst->src1);
                emit_load_rcx(&b, inst->src2);
                /* and rax, rcx -> 48 21 c8 */
                emit_byte(&b, 0x48); emit_byte(&b, 0x21); emit_byte(&b, 0xC8);
                emit_store_rax(&b, inst->dst);
                break;

            case IR_OR:
                emit_load_rax(&b, inst->src1);
                emit_load_rcx(&b, inst->src2);
                /* or rax, rcx -> 48 09 c8 */
                emit_byte(&b, 0x48); emit_byte(&b, 0x09); emit_byte(&b, 0xC8);
                emit_store_rax(&b, inst->dst);
                break;

            case IR_XOR:
                emit_load_rax(&b, inst->src1);
                emit_load_rcx(&b, inst->src2);
                /* xor rax, rcx -> 48 31 c8 */
                emit_byte(&b, 0x48); emit_byte(&b, 0x31); emit_byte(&b, 0xC8);
                emit_store_rax(&b, inst->dst);
                break;

            case IR_IDIV:
            case IR_MOD:
                emit_load_rax(&b, inst->src1);
                emit_load_rcx(&b, inst->src2);
                /* cqo -> 48 99 */
                emit_byte(&b, 0x48); emit_byte(&b, 0x99);
                /* idiv rcx -> 48 f7 f9 */
                emit_byte(&b, 0x48); emit_byte(&b, 0xF7); emit_byte(&b, 0xF9);
                if (inst->op == IR_IDIV) {
                    emit_store_rax(&b, inst->dst);
                } else {
                    /* mov rax, rdx -> 48 89 d0 */
                    emit_byte(&b, 0x48); emit_byte(&b, 0x89); emit_byte(&b, 0xD0);
                    emit_store_rax(&b, inst->dst);
                }
                break;

            case IR_CMP_EQ:
            case IR_CMP_NE:
            case IR_CMP_LT:
            case IR_CMP_LE:
            case IR_CMP_GT:
            case IR_CMP_GE:
                emit_load_rax(&b, inst->src1);
                emit_load_rcx(&b, inst->src2);
                /* cmp rax, rcx -> 48 39 c8 */
                emit_byte(&b, 0x48); emit_byte(&b, 0x39); emit_byte(&b, 0xC8);
                /* sete/setne/setl/setle/setg/setge al -> 0f 9x c0 */
                emit_byte(&b, 0x0F);
                if (inst->op == IR_CMP_EQ) emit_byte(&b, 0x94);
                else if (inst->op == IR_CMP_NE) emit_byte(&b, 0x95);
                else if (inst->op == IR_CMP_LT) emit_byte(&b, 0x9C);
                else if (inst->op == IR_CMP_LE) emit_byte(&b, 0x9E);
                else if (inst->op == IR_CMP_GT) emit_byte(&b, 0x9F);
                else emit_byte(&b, 0x9D);
                emit_byte(&b, 0xC0);
                /* movzx rax, al -> 48 0f b6 c0 */
                emit_byte(&b, 0x48); emit_byte(&b, 0x0F); emit_byte(&b, 0xB6); emit_byte(&b, 0xC0);
                emit_store_rax(&b, inst->dst);
                break;

            case IR_JZ:
                emit_load_rax(&b, inst->src1);
                /* test rax, rax -> 48 85 c0 */
                emit_byte(&b, 0x48); emit_byte(&b, 0x85); emit_byte(&b, 0xC0);
                /* jz rel32 -> 0f 84 <disp32> */
                emit_byte(&b, 0x0F); emit_byte(&b, 0x84);
                patches[patch_count].patch_offset = b.size;
                patches[patch_count].target_inst = (size_t)inst->imm;
                patch_count++;
                emit_u32(&b, 0); /* To be patched */
                break;

            case IR_JNZ:
                emit_load_rax(&b, inst->src1);
                /* test rax, rax -> 48 85 c0 */
                emit_byte(&b, 0x48); emit_byte(&b, 0x85); emit_byte(&b, 0xC0);
                /* jnz rel32 -> 0f 85 <disp32> */
                emit_byte(&b, 0x0F); emit_byte(&b, 0x85);
                patches[patch_count].patch_offset = b.size;
                patches[patch_count].target_inst = (size_t)inst->imm;
                patch_count++;
                emit_u32(&b, 0); /* To be patched */
                break;

            case IR_JMP:
                /* jmp rel32 -> e9 <disp32> */
                emit_byte(&b, 0xE9);
                patches[patch_count].patch_offset = b.size;
                patches[patch_count].target_inst = (size_t)inst->imm;
                patch_count++;
                emit_u32(&b, 0);
                break;

            case IR_RET:
                emit_load_rax(&b, inst->src1);
                /* mov rsp, rbp; pop rbp; ret */
                emit_byte(&b, 0x48); emit_byte(&b, 0x89); emit_byte(&b, 0xEC);
                emit_byte(&b, 0x5D);
                emit_byte(&b, 0xC3);
                break;

            default:
                break;
        }
    }

    /* Target of end-of-function */
    size_t end_offset = b.size;

    /* 4. Patch relative branch displacements */
    for (size_t p = 0; p < patch_count; p++) {
        size_t patch_pos = patches[p].patch_offset;
        size_t target_inst = patches[p].target_inst;
        size_t target_offset = (target_inst < fn->inst_count) ? b.inst_offsets[target_inst] : end_offset;

        int32_t disp = (int32_t)(target_offset - (patch_pos + 4));
        b.bytes[patch_pos] = (uint8_t)(disp & 0xFF);
        b.bytes[patch_pos + 1] = (uint8_t)((disp >> 8) & 0xFF);
        b.bytes[patch_pos + 2] = (uint8_t)((disp >> 16) & 0xFF);
        b.bytes[patch_pos + 3] = (uint8_t)((disp >> 24) & 0xFF);
    }

    /* 5. Allocate executable page via OS virtual memory */
#if defined(_WIN32)
    void *exec_mem = VirtualAlloc(NULL, b.size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (exec_mem == NULL) return UJIT_ERR_MEMORY;
    memcpy(exec_mem, b.bytes, b.size);
#else
    void *exec_mem = mmap(NULL, b.size, PROT_READ | PROT_WRITE | PROT_EXEC, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (exec_mem == MAP_FAILED) return UJIT_ERR_MEMORY;
    memcpy(exec_mem, b.bytes, b.size);
#endif

    fn->code = (uint8_t *)exec_mem;
    fn->code_size = b.size;
    return UJIT_OK;
}
