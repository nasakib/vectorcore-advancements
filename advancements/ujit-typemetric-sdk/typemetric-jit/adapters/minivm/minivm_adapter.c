#include "minivm_adapter.h"
#include <string.h>

void minivm_init_metric_config(tm_metric_config_t *cfg) {
    tm_metric_config_init_default(cfg);
}

tm_status_t minivm_prune_versions(const minivm_block_version_t *versions,
                                  size_t count,
                                  size_t target_k,
                                  size_t primary_idx,
                                  size_t *out_retained_indices) {
    if (versions == NULL || out_retained_indices == NULL) {
        return TM_ERR_INVALID_PARAM;
    }
    if (count == 0) {
        return TM_ERR_EMPTY_SET;
    }
    if (count > TM_MAX_CANDIDATES) {
        return TM_ERR_CAPACITY_EXCEEDED;
    }

    tm_type_vector_t vec_candidates[TM_MAX_CANDIDATES];
    tm_metric_config_t cfg;
    minivm_init_metric_config(&cfg);

    for (size_t i = 0; i < count; i++) {
        tm_type_id_t kinds[TM_MAX_PARAMS];
        for (uint8_t p = 0; p < versions[i].num_params; p++) {
            kinds[p] = (tm_type_id_t)versions[i].param_kinds[p];
        }
        tm_vector_init(&vec_candidates[i], kinds, versions[i].num_params, versions[i].code_offset);
    }

    return tm_gonzalez_select(vec_candidates, count, target_k, primary_idx, out_retained_indices, &cfg);
}
