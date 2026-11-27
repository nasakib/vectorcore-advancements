#include "typemetric/typemetric.h"

int tm_stitch_find_best(const tm_type_vector_t *predicted_out,
                        const tm_stitch_target_t *targets,
                        size_t target_count,
                        uint32_t max_tolerance,
                        const tm_metric_config_t *cfg) {
    if (predicted_out == NULL || targets == NULL || target_count == 0) {
        return -1;
    }

    int best_idx = -1;
    uint32_t best_dist = UINT32_MAX;

    for (size_t i = 0; i < target_count; i++) {
        /* O(1) Fast path: exact match on 64-bit scalar key */
        if (predicted_out->scalar_key == targets[i].expected_types.scalar_key &&
            predicted_out->arity == targets[i].expected_types.arity) {
            return (int)i;
        }

        uint32_t dist = tm_vector_distance(predicted_out, &targets[i].expected_types, cfg);
        if (dist <= max_tolerance && dist < best_dist) {
            best_dist = dist;
            best_idx = (int)i;
        }
    }

    return best_idx;
}
