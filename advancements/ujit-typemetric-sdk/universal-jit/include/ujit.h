#ifndef UJIT_H
#define UJIT_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define UJIT_VERSION_MAJOR 1
#define UJIT_VERSION_MINOR 0
#define UJIT_VERSION_PATCH 0

#define UJIT_MAX_ARGS 8
#define UJIT_MAX_LOCALS 64
#define UJIT_MAX_INSTRUCTIONS 1024

typedef enum {
    UJIT_OK = 0,
    UJIT_ERR_SYNTAX = -1,
    UJIT_ERR_TYPE = -2,
    UJIT_ERR_CODEGEN = -3,
    UJIT_ERR_NOT_FOUND = -4,
    UJIT_ERR_MEMORY = -5,
} ujit_status_t;

typedef enum {
    UJIT_TARGET_AUTO = 0,
    UJIT_TARGET_X86_64,
    UJIT_TARGET_RV64,
} ujit_target_t;

typedef enum {
    UJIT_TYPE_VOID = 0,
    UJIT_TYPE_INT,
    UJIT_TYPE_FLOAT,
    UJIT_TYPE_BOOL,
} ujit_type_t;

typedef struct ujit_ctx ujit_ctx_t;

/* Function pointer types for direct hardware execution */
typedef int64_t (*ujit_fn0_t)(void);
typedef int64_t (*ujit_fn1_t)(int64_t);
typedef int64_t (*ujit_fn2_t)(int64_t, int64_t);
typedef int64_t (*ujit_fn3_t)(int64_t, int64_t, int64_t);
typedef int64_t (*ujit_fn4_t)(int64_t, int64_t, int64_t, int64_t);

/**
 * Create a new Universal JIT compiler context.
 */
ujit_ctx_t *ujit_create(void);

/**
 * Configure target architecture (default: native host).
 */
void ujit_set_target(ujit_ctx_t *ctx, ujit_target_t target);

/**
 * Destroy context and release all allocated JIT executable pages.
 */
void ujit_destroy(ujit_ctx_t *ctx);

/**
 * Compile algorithmic pseudocode into native machine code.
 */
ujit_status_t ujit_compile_string(ujit_ctx_t *ctx, const char *source);

/**
 * Compile a pseudocode source file.
 */
ujit_status_t ujit_compile_file(ujit_ctx_t *ctx, const char *filepath);

/**
 * Look up a compiled native function pointer by name.
 */
void *ujit_get_fn(ujit_ctx_t *ctx, const char *name);

/**
 * Generic caller executing a compiled function with up to 8 arguments.
 */
int64_t ujit_call(ujit_ctx_t *ctx, const char *name, const int64_t *args, size_t num_args);

/**
 * Dump human-readable intermediate representation (IR) to stdout.
 */
void ujit_dump_ir(ujit_ctx_t *ctx, const char *name);

/**
 * Dump machine code hex bytes.
 */
void ujit_dump_bytes(ujit_ctx_t *ctx, const char *name);

#ifdef __cplusplus
}
#endif

#endif /* UJIT_H */
