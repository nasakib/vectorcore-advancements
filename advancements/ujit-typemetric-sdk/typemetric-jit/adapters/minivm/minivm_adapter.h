#ifndef TYPEMETRIC_MINIVM_ADAPTER_H
#define TYPEMETRIC_MINIVM_ADAPTER_H

#include "typemetric/typemetric.h"

#ifdef __cplusplus
extern "C" {
#endif

/* MiniVM type tags matching mx_kind_t in src/ir/ir.h */
typedef enum {
    MX_KIND_NIL = 0,
    MX_KIND_BOOLEAN = 1,
    MX_KIND_NUMBER_INT = 2,
    MX_KIND_NUMBER_FLOAT = 3,
    MX_KIND_STRING = 4,
    MX_KIND_TABLE = 5,
    MX_KIND_FUNCTION = 6,
    MX_KIND_USERDATA = 7,
    MX_KIND_THREAD = 8,
} minivm_kind_t;

typedef struct {
    uint32_t block_id;
    uint32_t code_offset;
    minivm_kind_t param_kinds[TM_MAX_PARAMS];
    uint8_t num_params;
    uint32_t exec_count;
} minivm_block_version_t;

void minivm_init_metric_config(tm_metric_config_t *cfg);

tm_status_t minivm_prune_versions(const minivm_block_version_t *versions,
                                  size_t count,
                                  size_t target_k,
                                  size_t primary_idx,
                                  size_t *out_retained_indices);

#ifdef __cplusplus
}
#endif

#endif /* TYPEMETRIC_MINIVM_ADAPTER_H */
