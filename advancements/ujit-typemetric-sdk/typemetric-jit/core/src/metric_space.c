#include "typemetric/typemetric.h"
#include <string.h>

void tm_metric_config_init_default(tm_metric_config_t *cfg) {
    if (cfg == NULL) {
        return;
    }
    memset(cfg, 0, sizeof(tm_metric_config_t));

    /* Default parameter position weights (1000 = 1.0x, descending slightly) */
    for (int i = 0; i < TM_MAX_PARAMS; i++) {
        cfg->param_weights[i] = (uint16_t)(1000 - i * 50);
    }

    /* Initialize baseline distances between all distinct types to default 4 */
    for (int i = 0; i < TM_MAX_TYPES; i++) {
        for (int j = 0; j < TM_MAX_TYPES; j++) {
            if (i == j) {
                cfg->dist_matrix[i][j] = 0;
            } else {
                cfg->dist_matrix[i][j] = 4;
            }
        }
    }

    /* 
     * Hierarchical metric table:
     * 0: NIL, 1: BOOL, 2: INT, 3: FLOAT, 4: STRING, 5: ARRAY, 6: MAP, 7: OBJECT, 8: FUNC
     */
    /* Numeric family (INT <-> FLOAT): distance 1 */
    cfg->dist_matrix[2][3] = 1;
    cfg->dist_matrix[3][2] = 1;

    /* Primitive family (INT/FLOAT <-> BOOL): distance 2 */
    cfg->dist_matrix[1][2] = 2; cfg->dist_matrix[2][1] = 2;
    cfg->dist_matrix[1][3] = 2; cfg->dist_matrix[3][1] = 2;

    /* NIL <-> Primitives: distance 2 */
    cfg->dist_matrix[0][1] = 2; cfg->dist_matrix[1][0] = 2;
    cfg->dist_matrix[0][2] = 2; cfg->dist_matrix[2][0] = 2;
    cfg->dist_matrix[0][3] = 2; cfg->dist_matrix[3][0] = 2;

    /* NIL <-> Heap: distance 3 */
    for (int h = 4; h <= 8; h++) {
        cfg->dist_matrix[0][h] = 3;
        cfg->dist_matrix[h][0] = 3;
    }

    /* Heap intra-family (STRING, ARRAY, MAP, OBJECT, FUNC): distance 2 */
    for (int i = 4; i <= 8; i++) {
        for (int j = 4; j <= 8; j++) {
            if (i != j) {
                cfg->dist_matrix[i][j] = 2;
                cfg->dist_matrix[j][i] = 2;
            }
        }
    }

    /* Primitive vs Heap: distance 4 */
    for (int p = 1; p <= 3; p++) {
        for (int h = 4; h <= 8; h++) {
            cfg->dist_matrix[p][h] = 4;
            cfg->dist_matrix[h][p] = 4;
        }
    }

    cfg->custom_dist = NULL;
    cfg->user_ctx = NULL;
}

uint32_t tm_vector_distance(const tm_type_vector_t *a, const tm_type_vector_t *b, const tm_metric_config_t *cfg) {
    if (a == NULL || b == NULL) {
        return 0;
    }

    /* O(1) Fast-path: exact scalar key match implies identical types across all params */
    if (a->scalar_key == b->scalar_key && a->arity == b->arity) {
        return 0;
    }

    uint8_t max_arity = (a->arity > b->arity) ? a->arity : b->arity;
    uint32_t total_dist = 0;

    for (uint8_t i = 0; i < max_arity; i++) {
        tm_type_id_t ka = (i < a->arity) ? a->kinds[i] : 0;
        tm_type_id_t kb = (i < b->arity) ? b->kinds[i] : 0;

        uint32_t elem_dist;
        if (cfg != NULL && cfg->custom_dist != NULL) {
            elem_dist = cfg->custom_dist(ka, kb, cfg->user_ctx);
        } else if (cfg != NULL && ka < TM_MAX_TYPES && kb < TM_MAX_TYPES) {
            elem_dist = cfg->dist_matrix[ka][kb];
        } else {
            elem_dist = (ka == kb) ? 0 : 4;
        }

        uint16_t weight = (cfg != NULL && i < TM_MAX_PARAMS) ? cfg->param_weights[i] : 1000;
        total_dist += (elem_dist * (uint32_t)weight);
    }

    /* Penalty for arity mismatch */
    if (a->arity != b->arity) {
        uint8_t diff = (a->arity > b->arity) ? (a->arity - b->arity) : (b->arity - a->arity);
        total_dist += ((uint32_t)diff * 2000);
    }

    return total_dist;
}
