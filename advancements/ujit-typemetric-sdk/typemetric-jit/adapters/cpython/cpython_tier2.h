#ifndef TYPEMETRIC_CPYTHON_TIER2_H
#define TYPEMETRIC_CPYTHON_TIER2_H

#include "typemetric/typemetric.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Canonical 8-bit type tags for CPython's core built-in types */
typedef enum {
    PY_KIND_UNKNOWN = 0,
    PY_KIND_NONE,
    PY_KIND_BOOL,
    PY_KIND_LONG,      /* Arbitrary precision int */
    PY_KIND_FLOAT,     /* IEEE-754 double */
    PY_KIND_UNICODE,   /* str */
    PY_KIND_BYTES,
    PY_KIND_TUPLE,
    PY_KIND_LIST,
    PY_KIND_DICT,
    PY_KIND_USER_HEAP, /* Custom user-defined class / instance */
} py_kind_t;

/**
 * Representation of a CPython Tier 2 micro-op (uop) trace exit/entry point.
 */
typedef struct {
    uint32_t uop_id;
    uint32_t target_trace_id;
    tm_type_vector_t operand_types;
    uint32_t uop_code_offset;
    bool is_loop_backedge;
} py_uop_target_t;

/**
 * Fast-path address matcher mapping common PyTypeObject* pointers
 * to canonical 8-bit kind indices during bytecode-to-uop translation.
 * O(1) pointer comparison against known type descriptors.
 */
py_kind_t py_map_typeobject_ptr(const void *py_type_ptr);

/**
 * Initialize metric space configuration tuned for Python dynamic semantics:
 * bool <-> int distance = 1 (bool subclass of int)
 * int <-> float distance = 1
 * str <-> bytes distance = 1
 * tuple <-> list distance = 1
 * None <-> Primitive distance = 2
 * Primitive <-> User Heap Object distance = 4
 */
void py_init_metric_config(tm_metric_config_t *cfg);

/**
 * Speculative Trace Stitcher for CPython Tier 2 uops:
 * Pre-links uop branch exits to existing compiled downstream micro-op traces,
 * bypassing the standard CPython _PyUOpExecute evaluation loop exits.
 * 
 * Returns target index or -1 if no suitable pre-link target is found.
 */
int py_uop_stitch_trace(const tm_type_vector_t *predicted_operands,
                        const py_uop_target_t *available_uop_targets,
                        size_t target_count,
                        uint32_t max_tolerance);

#ifdef __cplusplus
}
#endif

#endif /* TYPEMETRIC_CPYTHON_TIER2_H */
