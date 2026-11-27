#include "cpython_tier2.h"
#include <string.h>

/* Mock / representative pointers for standard CPython type objects */
static const void *s_py_none_type = (const void *)0x1000;
static const void *s_py_bool_type = (const void *)0x1008;
static const void *s_py_long_type = (const void *)0x1010;
static const void *s_py_float_type = (const void *)0x1018;
static const void *s_py_unicode_type = (const void *)0x1020;
static const void *s_py_bytes_type = (const void *)0x1028;
static const void *s_py_tuple_type = (const void *)0x1030;
static const void *s_py_list_type = (const void *)0x1038;
static const void *s_py_dict_type = (const void *)0x1040;

py_kind_t py_map_typeobject_ptr(const void *py_type_ptr) {
    if (py_type_ptr == NULL) {
        return PY_KIND_UNKNOWN;
    }

    /* Fast pointer address checks */
    if (py_type_ptr == s_py_long_type) return PY_KIND_LONG;
    if (py_type_ptr == s_py_float_type) return PY_KIND_FLOAT;
    if (py_type_ptr == s_py_unicode_type) return PY_KIND_UNICODE;
    if (py_type_ptr == s_py_bool_type) return PY_KIND_BOOL;
    if (py_type_ptr == s_py_none_type) return PY_KIND_NONE;
    if (py_type_ptr == s_py_list_type) return PY_KIND_LIST;
    if (py_type_ptr == s_py_dict_type) return PY_KIND_DICT;
    if (py_type_ptr == s_py_tuple_type) return PY_KIND_TUPLE;
    if (py_type_ptr == s_py_bytes_type) return PY_KIND_BYTES;

    return PY_KIND_USER_HEAP;
}

void py_init_metric_config(tm_metric_config_t *cfg) {
    if (cfg == NULL) {
        return;
    }
    memset(cfg, 0, sizeof(tm_metric_config_t));

    for (int i = 0; i < TM_MAX_PARAMS; i++) {
        cfg->param_weights[i] = (uint16_t)(1000 - i * 50);
    }

    for (int i = 0; i < TM_MAX_TYPES; i++) {
        for (int j = 0; j < TM_MAX_TYPES; j++) {
            cfg->dist_matrix[i][j] = (i == j) ? 0 : 4;
        }
    }

    /* bool <-> int */
    cfg->dist_matrix[PY_KIND_BOOL][PY_KIND_LONG] = 1;
    cfg->dist_matrix[PY_KIND_LONG][PY_KIND_BOOL] = 1;

    /* int <-> float */
    cfg->dist_matrix[PY_KIND_LONG][PY_KIND_FLOAT] = 1;
    cfg->dist_matrix[PY_KIND_FLOAT][PY_KIND_LONG] = 1;

    /* str <-> bytes */
    cfg->dist_matrix[PY_KIND_UNICODE][PY_KIND_BYTES] = 1;
    cfg->dist_matrix[PY_KIND_BYTES][PY_KIND_UNICODE] = 1;

    /* tuple <-> list */
    cfg->dist_matrix[PY_KIND_TUPLE][PY_KIND_LIST] = 1;
    cfg->dist_matrix[PY_KIND_LIST][PY_KIND_TUPLE] = 1;

    /* None <-> Primitives */
    cfg->dist_matrix[PY_KIND_NONE][PY_KIND_LONG] = 2;
    cfg->dist_matrix[PY_KIND_LONG][PY_KIND_NONE] = 2;
    cfg->dist_matrix[PY_KIND_NONE][PY_KIND_FLOAT] = 2;
    cfg->dist_matrix[PY_KIND_FLOAT][PY_KIND_NONE] = 2;
    cfg->dist_matrix[PY_KIND_NONE][PY_KIND_BOOL] = 2;
    cfg->dist_matrix[PY_KIND_BOOL][PY_KIND_NONE] = 2;
}

int py_uop_stitch_trace(const tm_type_vector_t *predicted_operands,
                        const py_uop_target_t *available_uop_targets,
                        size_t target_count,
                        uint32_t max_tolerance) {
    if (predicted_operands == NULL || available_uop_targets == NULL || target_count == 0) {
        return -1;
    }

    tm_metric_config_t cfg;
    py_init_metric_config(&cfg);

    int best_idx = -1;
    uint32_t best_dist = UINT32_MAX;

    for (size_t i = 0; i < target_count; i++) {
        /* O(1) Fast-path: exact 64-bit scalar key match */
        if (predicted_operands->scalar_key == available_uop_targets[i].operand_types.scalar_key &&
            predicted_operands->arity == available_uop_targets[i].operand_types.arity) {
            return (int)i;
        }

        uint32_t dist = tm_vector_distance(predicted_operands, &available_uop_targets[i].operand_types, &cfg);
        if (dist <= max_tolerance && dist < best_dist) {
            best_dist = dist;
            best_idx = (int)i;
        }
    }

    return best_idx;
}
