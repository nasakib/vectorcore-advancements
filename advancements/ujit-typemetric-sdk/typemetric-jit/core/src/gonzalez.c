#include "typemetric/typemetric.h"

tm_status_t tm_gonzalez_select(const tm_type_vector_t *candidates,
                              size_t candidate_count,
                              size_t k,
                              size_t primary_idx,
                              size_t *out_indices,
                              const tm_metric_config_t *cfg) {
    if (candidates == NULL || out_indices == NULL) {
        return TM_ERR_INVALID_PARAM;
    }
    if (candidate_count == 0) {
        return TM_ERR_EMPTY_SET;
    }
    if (candidate_count > TM_MAX_CANDIDATES) {
        return TM_ERR_CAPACITY_EXCEEDED;
    }
    if (k == 0) {
        return TM_ERR_INVALID_PARAM;
    }

    /* If K >= N, simply select all candidates */
    if (k >= candidate_count) {
        for (size_t i = 0; i < candidate_count; i++) {
            out_indices[i] = i;
        }
        return TM_OK;
    }

    /* Stack-allocated distance buffer: zero heap allocations */
    uint32_t min_dist[TM_MAX_CANDIDATES];

    /* Center 0: Pin to primary_idx if valid, otherwise candidate 0 */
    size_t c0 = (primary_idx < candidate_count) ? primary_idx : 0;
    out_indices[0] = c0;

    /* Initialize minimum distance of each candidate to center 0 */
    for (size_t i = 0; i < candidate_count; i++) {
        min_dist[i] = tm_vector_distance(&candidates[i], &candidates[c0], cfg);
    }

    /* Iteratively select centers 1 .. k-1 maximizing the minimum distance to existing centers */
    for (size_t step = 1; step < k; step++) {
        size_t best_cand = 0;
        uint32_t max_dist = 0;

        for (size_t i = 0; i < candidate_count; i++) {
            if (min_dist[i] > max_dist) {
                max_dist = min_dist[i];
                best_cand = i;
            }
        }

        out_indices[step] = best_cand;

        /* Update minimum distance for all candidates relative to the newly chosen center */
        for (size_t i = 0; i < candidate_count; i++) {
            uint32_t d = tm_vector_distance(&candidates[i], &candidates[best_cand], cfg);
            if (d < min_dist[i]) {
                min_dist[i] = d;
            }
        }
    }

    return TM_OK;
}
