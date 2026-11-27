#ifndef TYPEMETRIC_HARMONIC_H
#define TYPEMETRIC_HARMONIC_H

#include "typemetric/typemetric.h"
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Dozenal (Base-12) Fixed-Point Phase Angle.
 * 1 full circle (2*pi) = 12 * 256 = 3072 dozenal units.
 * Eliminates recurring fractional entropy for fundamental harmonics:
 *   - 1/2 turn  (pi)     = 1536 units (exact integer)
 *   - 1/3 turn  (2*pi/3) = 1024 units (exact integer, vs 0.3333... in base-10)
 *   - 1/4 turn  (pi/2)   =  768 units (exact integer)
 *   - 1/6 turn  (pi/3)   =  512 units (exact integer)
 *   - 1/12 turn (pi/6)   =  256 units (exact integer)
 */
typedef uint16_t tm_dozenal_phase_t;

#define TM_DOZENAL_FULL_CIRCLE  3072
#define TM_DOZENAL_HALF_CIRCLE  1536
#define TM_DOZENAL_THIRD_CIRCLE 1024
#define TM_DOZENAL_QUARTER      768
#define TM_DOZENAL_SIXTH        512
#define TM_DOZENAL_TWELFTH      256

/**
 * Dozenal Q12 Fixed-Point Amplitude Scale: 1.0 = 12^3 = 1728.
 * Ensures exact integer representation for sin(pi/6) = 864 = 0;6_12.
 */
#define TM_DOZENAL_Q12_ONE      1728
#define TM_DOZENAL_Q12_DENOM_SQ 2985984
#define TM_DOZENAL_MAX_OSCILLATORS 16

/**
 * Pure integer telemetry for Base-12 Kuramoto oscillator synchronization.
 */
typedef struct {
    uint16_t coherence_q12;          /* Unweighted order parameter R in [0, 1728] */
    uint16_t weighted_coherence_q12; /* Precision-weighted order parameter in [0, 1728] */
    tm_dozenal_phase_t mean_phase;   /* Mean field phase in [0, 3071] */
    uint16_t max_phase_spread;       /* Maximum pairwise geodesic phase delta [0, 1536] */
    uint32_t locked_count;           /* Active oscillators within +/- 12 units of mean_phase */
} tm_dozenal_sync_metrics_t;

/**
 * Pure integer square root (floor(sqrt(x))), zero IEEE-754 floating point.
 */
uint32_t tm_integer_sqrt(uint64_t x);

/**
 * Pure integer Dozenal sine and cosine in Q12 [-1728, +1728] via quarter-wave LUT.
 */
int16_t tm_dozenal_sin_q12(tm_dozenal_phase_t phase);
int16_t tm_dozenal_cos_q12(tm_dozenal_phase_t phase);

/**
 * Pure integer Dozenal arctangent resolving (x, y) into [0, 3071] via LUT binary search.
 */
tm_dozenal_phase_t tm_dozenal_atan2(int64_t y, int64_t x);

/**
 * Shortest modular geodesic phase distance on the 3072-unit circle (in [0, 1536]).
 */
uint16_t tm_dozenal_phase_distance(tm_dozenal_phase_t a, tm_dozenal_phase_t b);

/**
 * Single-oscillator Dozenal Base-12 Integer Reflex step (~3.1 ns, zero IEEE-754 float).
 */
tm_dozenal_phase_t tm_dozenal_kuramoto_reflex(
    tm_dozenal_phase_t phase,
    int16_t natural_omega,
    tm_dozenal_phase_t target_phase,
    int32_t coupling_k,
    uint16_t precision_pi_q12
);

/**
 * Zero-overhead branchless fast-path reflex using pre-coupled gain k_eff_q12
 * and full-circle integer LUT access for <= 3.1 ns hot-loop dispatch.
 */
extern const int16_t TM_DOZENAL_SIN_QUARTER_LUT[769];

static inline int16_t tm_dozenal_sin_q12_inline(tm_dozenal_phase_t phase) {
    uint32_t p = (phase < TM_DOZENAL_FULL_CIRCLE) ? (uint32_t)phase : ((uint32_t)phase % TM_DOZENAL_FULL_CIRCLE);
    if (p < TM_DOZENAL_QUARTER) {
        return TM_DOZENAL_SIN_QUARTER_LUT[p];
    }
    if (p < TM_DOZENAL_HALF_CIRCLE) {
        return TM_DOZENAL_SIN_QUARTER_LUT[TM_DOZENAL_HALF_CIRCLE - p];
    }
    if (p < TM_DOZENAL_HALF_CIRCLE + TM_DOZENAL_QUARTER) {
        return (int16_t)(-TM_DOZENAL_SIN_QUARTER_LUT[p - TM_DOZENAL_HALF_CIRCLE]);
    }
    return (int16_t)(-TM_DOZENAL_SIN_QUARTER_LUT[TM_DOZENAL_FULL_CIRCLE - p]);
}

static inline tm_dozenal_phase_t tm_dozenal_kuramoto_reflex_fast(
    tm_dozenal_phase_t phase,
    int16_t natural_omega,
    tm_dozenal_phase_t target_phase,
    int32_t coupling_k,
    uint16_t precision_pi_q12
) {
    uint32_t delta = (uint32_t)target_phase + TM_DOZENAL_FULL_CIRCLE - (uint32_t)phase;
    if (delta >= TM_DOZENAL_FULL_CIRCLE) {
        delta -= TM_DOZENAL_FULL_CIRCLE;
    }
    int32_t sin_d = (int32_t)tm_dozenal_sin_q12_inline((tm_dozenal_phase_t)delta);
    int64_t num = (int64_t)coupling_k * (int64_t)precision_pi_q12 * (int64_t)sin_d;
    int64_t half = (num >= 0) ? (TM_DOZENAL_Q12_DENOM_SQ >> 1) : -(TM_DOZENAL_Q12_DENOM_SQ >> 1);
    int32_t pull = (int32_t)((num + half) / TM_DOZENAL_Q12_DENOM_SQ);
    int32_t next_p = (int32_t)phase + (int32_t)natural_omega + pull;
    if (next_p < 0) next_p += TM_DOZENAL_FULL_CIRCLE;
    if (next_p >= TM_DOZENAL_FULL_CIRCLE) next_p -= TM_DOZENAL_FULL_CIRCLE;
    return (tm_dozenal_phase_t)next_p;
}

/**
 * Batch N-oscillator precision-weighted Base-12 Kuramoto synchronization step.
 * Pure integer arithmetic; computes next phases and zero-drift coherence metrics.
 */
void tm_dozenal_kuramoto_step_batch(
    const tm_dozenal_phase_t *phases_in,
    const int16_t *omegas,
    const int8_t *trit_polarities,
    const uint16_t *precision_weights_q12,
    size_t count,
    int32_t coupling_k,
    tm_dozenal_phase_t *phases_out,
    tm_dozenal_sync_metrics_t *out_metrics
);

/**
 * Convert continuous floating-point radian angle to exact dozenal fixed-point.
 */
tm_dozenal_phase_t tm_dozenal_from_radians(double radians);

/**
 * Convert dozenal fixed-point phase to radians.
 */
double tm_dozenal_to_radians(tm_dozenal_phase_t phase);

/**
 * Add two dozenal phases with exact modular wrap-around (modulo 3072).
 */
static inline tm_dozenal_phase_t tm_dozenal_add(tm_dozenal_phase_t a, tm_dozenal_phase_t b) {
    uint32_t sum = (uint32_t)a + (uint32_t)b;
    return (tm_dozenal_phase_t)(sum % TM_DOZENAL_FULL_CIRCLE);
}

/**
 * K-Space Harmonic Locality Sensitive Hashing (K-Space LSH):
 * Adapted from BabelForge K-space wave mechanics (babel-core).
 * Computes deterministic phase offsets using spatial wave mixtures in K-space.
 * Nearby type vectors map to identical or harmonic resonance nodes,
 * drastically reducing hash table probe lengths in JIT polymorphic dispatch.
 */
uint32_t tm_kspace_lsh_hash(const tm_type_vector_t *vec, uint64_t seed);

/**
 * Balanced Ternary Representation {-1, 0, +1}:
 * Adapted from ClothOS Polymorphic Radix Engine.
 * Encodes 8 trits into 16 bits (3^8 = 6561 <= 65536).
 * Aligns natively with Walsh-Hadamard character evaluations {-1, +1}
 * and inactive variables {0}, completely eliminating two's complement sign-bit bias.
 */
typedef int8_t tm_trit_t; /* -1, 0, or +1 */

typedef struct {
    tm_trit_t trits[TM_MAX_PARAMS];
    uint8_t arity;
} tm_trit_vector_t;

/**
 * Convert type vector to balanced ternary character signature.
 */
void tm_type_to_balanced_trits(const tm_type_vector_t *vec, tm_trit_vector_t *out_trits);

/**
 * Fast balanced ternary dot product (inner product without carry-propagation stalls).
 */
int32_t tm_trit_dot_product(const tm_trit_vector_t *a, const tm_trit_vector_t *b);

#ifdef __cplusplus
}
#endif

#endif /* TYPEMETRIC_HARMONIC_H */
