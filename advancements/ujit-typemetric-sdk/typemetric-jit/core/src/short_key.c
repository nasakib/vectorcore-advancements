#include "typemetric/typemetric.h"
#include <string.h>

tm_status_t tm_vector_init(tm_type_vector_t *vec, const tm_type_id_t *kinds, uint8_t arity, uint32_t payload) {
    if (vec == NULL) {
        return TM_ERR_INVALID_PARAM;
    }
    if (arity > TM_MAX_PARAMS) {
        return TM_ERR_INVALID_PARAM;
    }

    vec->arity = arity;
    vec->flags = 0;
    vec->reserved = 0;
    vec->payload = payload;

    uint64_t key = 0;
    for (uint8_t i = 0; i < arity; i++) {
        tm_type_id_t k = (kinds != NULL) ? kinds[i] : 0;
        vec->kinds[i] = k;
        key |= ((uint64_t)k) << (i * 8);
    }
    for (uint8_t i = arity; i < TM_MAX_PARAMS; i++) {
        vec->kinds[i] = 0;
    }

    vec->scalar_key = key;
    return TM_OK;
}
