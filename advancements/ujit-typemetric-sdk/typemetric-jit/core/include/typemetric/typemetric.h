#ifndef TYPEMETRIC_H
#define TYPEMETRIC_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TYPEMETRIC_VERSION_MAJOR 1
#define TYPEMETRIC_VERSION_MINOR 0
#define TYPEMETRIC_VERSION_PATCH 0

#define TM_MAX_PARAMS 8
#define TM_MAX_CANDIDATES 64
#define TM_MAX_TYPES 32

typedef uint8_t tm_type_id_t;

typedef enum {
    TM_OK = 0,
    TM_ERR_INVALID_PARAM = -1,
    TM_ERR_CAPACITY_EXCEEDED = -2,
    TM_ERR_EMPTY_SET = -3,
} tm_status_t;

/**
 * Packed type vector representing a runtime specialization signature.
 * Fits within 16 bytes (cache-line friendly, 4 vectors per L1 cache line).
 */
typedef struct {
    uint64_t scalar_key;                /* Packed 8-bit kinds: k0 | (k1 << 8) | ... */
    uint8_t kinds[TM_MAX_PARAMS];       /* Unpacked kinds array */
    uint8_t arity;                      /* Number of parameters (0..8) */
    uint8_t flags;                      /* User/language-specific flags */
    uint16_t reserved;
    uint32_t payload;                   /* User payload (e.g. version index / JIT code offset) */
} tm_type_vector_t;

/**
 * Metric space configuration defining distance axioms between type tags.
 */
typedef struct {
    /* Pairwise symmetric distance lookup table between basic type IDs */
    uint16_t dist_matrix[TM_MAX_TYPES][TM_MAX_TYPES];
    /* Weight per argument position (1.0 = 1000 fixed-point) */
    uint16_t param_weights[TM_MAX_PARAMS];
    /* Custom distance callback (optional; if NULL, dist_matrix is used) */
    uint32_t (*custom_dist)(tm_type_id_t a, tm_type_id_t b, void *ctx);
    void *user_ctx;
} tm_metric_config_t;

/**
 * Pack up to 8 type IDs into a tm_type_vector_t with a 64-bit scalar key.
 */
tm_status_t tm_vector_init(tm_type_vector_t *vec, const tm_type_id_t *kinds, uint8_t arity, uint32_t payload);

/**
 * Compute the metric distance d(A, B) between two type vectors.
 * Strictly satisfies metric axioms:
 *   1. d(A, B) >= 0
 *   2. d(A, B) == 0 iff A == B
 *   3. d(A, B) == d(B, A)
 *   4. d(A, C) <= d(A, B) + d(B, C)
 */
uint32_t tm_vector_distance(const tm_type_vector_t *a, const tm_type_vector_t *b, const tm_metric_config_t *cfg);

/**
 * Initialize a standard default hierarchical type metric configuration.
 * Standard categories:
 *   - Identical: 0
 *   - Same Numeric Family (e.g. i32 vs i64 vs f64): 1
 *   - Primitive vs Primitive (e.g. int vs bool): 2
 *   - Nil/None vs Any: 3
 *   - Distinct Heap/Object Classes: 4
 *   - Primitive vs Heap/Object: 5
 */
void tm_metric_config_init_default(tm_metric_config_t *cfg);

/**
 * Gonzalez Farthest-Point Sampling algorithm for Metric k-Center selection.
 * Given N candidate type versions, selects K diverse representative centers
 * that minimize the maximum distance from any candidate to its nearest center.
 * 
 * Guarantees a theoretical factor-2 approximation to the optimal metric k-center.
 * Complexity: O(K * N) time, O(N) scratch space on stack, ZERO heap allocations.
 * 
 * @param candidates Array of candidate type vectors.
 * @param candidate_count Number of candidates (N <= TM_MAX_CANDIDATES).
 * @param k Target number of centers to retain (K <= candidate_count).
 * @param primary_idx Index to pin as the first center (e.g. the most recent or hottest). Pass (size_t)-1 to pick candidate 0.
 * @param out_indices Output array of size at least K receiving the selected indices.
 * @param cfg Metric configuration.
 */
tm_status_t tm_gonzalez_select(const tm_type_vector_t *candidates,
                              size_t candidate_count,
                              size_t k,
                              size_t primary_idx,
                              size_t *out_indices,
                              const tm_metric_config_t *cfg);

/**
 * Speculative Trace Stitcher:
 * Evaluates whether an outgoing type prediction can be pre-linked to an existing
 * compiled downstream block version without entering cold trampoline stubs.
 */
typedef struct {
    uint32_t target_block_id;
    tm_type_vector_t expected_types;
    uint32_t code_offset;
    bool is_hot;
} tm_stitch_target_t;

int tm_stitch_find_best(const tm_type_vector_t *predicted_out,
                        const tm_stitch_target_t *targets,
                        size_t target_count,
                        uint32_t max_tolerance,
                        const tm_metric_config_t *cfg);

#ifdef __cplusplus
}
#endif

#endif /* TYPEMETRIC_H */
