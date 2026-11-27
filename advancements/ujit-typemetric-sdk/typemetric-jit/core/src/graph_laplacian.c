#include "typemetric/spectral.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>

typedef struct {
    size_t node_idx;
    float fiedler_val;
} node_sort_t;

static int cmp_nodes(const void *a, const void *b) {
    const node_sort_t *na = (const node_sort_t *)a;
    const node_sort_t *nb = (const node_sort_t *)b;
    if (na->fiedler_val < nb->fiedler_val) return -1;
    if (na->fiedler_val > nb->fiedler_val) return 1;
    return 0;
}

void tm_cfg_spectral_order(const tm_cfg_graph_t *cfg, size_t *out_ordering) {
    if (cfg == NULL || out_ordering == NULL || cfg->num_nodes == 0) {
        return;
    }
    size_t n = cfg->num_nodes;
    if (n == 1) {
        out_ordering[0] = 0;
        return;
    }
    if (n > TM_MAX_CFG_NODES) {
        n = TM_MAX_CFG_NODES;
    }

    /* 1. Compute Degrees d_i and find maximum degree */
    float degrees[TM_MAX_CFG_NODES];
    float max_deg = 0.0f;
    for (size_t i = 0; i < n; i++) {
        float deg = 0.0f;
        for (size_t j = 0; j < n; j++) {
            deg += cfg->adjacency[i][j];
        }
        degrees[i] = deg;
        if (deg > max_deg) {
            max_deg = deg;
        }
    }

    /* Shift parameter mu > max eigenvalue of L (Gershgorin disc bound: lambda_max <= 2 * max_deg) */
    float mu = 2.0f * max_deg + 1.0f;

    /* Construct Shifted Matrix M = mu * I - L = mu * I - (D - A) = (mu * I - D) + A */
    float M[TM_MAX_CFG_NODES][TM_MAX_CFG_NODES];
    for (size_t i = 0; i < n; i++) {
        for (size_t j = 0; j < n; j++) {
            float val = cfg->adjacency[i][j];
            if (i == j) {
                val += (mu - degrees[i]);
            }
            M[i][j] = val;
        }
    }

    /* Initial trial vector: linear gradient orthogonalized to 1 */
    float v[TM_MAX_CFG_NODES];
    for (size_t i = 0; i < n; i++) {
        v[i] = (float)i - (float)(n - 1) / 2.0f;
    }

    /* Power iteration with deflation */
    for (int iter = 0; iter < 40; iter++) {
        /* Deflate: project out constant component (1^T v = 0) */
        float mean = 0.0f;
        for (size_t i = 0; i < n; i++) {
            mean += v[i];
        }
        mean /= (float)n;
        for (size_t i = 0; i < n; i++) {
            v[i] -= mean;
        }

        /* Matrix-vector multiplication v_next = M * v */
        float v_next[TM_MAX_CFG_NODES];
        for (size_t i = 0; i < n; i++) {
            float sum = 0.0f;
            for (size_t j = 0; j < n; j++) {
                sum += M[i][j] * v[j];
            }
            v_next[i] = sum;
        }

        /* Normalize */
        float norm = 0.0f;
        for (size_t i = 0; i < n; i++) {
            norm += v_next[i] * v_next[i];
        }
        norm = sqrtf(norm);
        if (norm < 1e-7f) {
            break;
        }
        for (size_t i = 0; i < n; i++) {
            v[i] = v_next[i] / norm;
        }
    }

    /* Sort nodes according to their Fiedler coordinates */
    node_sort_t sorted[TM_MAX_CFG_NODES];
    for (size_t i = 0; i < n; i++) {
        sorted[i].node_idx = i;
        sorted[i].fiedler_val = v[i];
    }

    qsort(sorted, n, sizeof(node_sort_t), cmp_nodes);

    for (size_t i = 0; i < n; i++) {
        out_ordering[i] = sorted[i].node_idx;
    }
}
