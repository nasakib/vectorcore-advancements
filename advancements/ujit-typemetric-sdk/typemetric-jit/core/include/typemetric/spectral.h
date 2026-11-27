#ifndef TYPEMETRIC_SPECTRAL_H
#define TYPEMETRIC_SPECTRAL_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TM_SPECTRAL_MAX_VARS 12
#define TM_SPECTRAL_MAX_TERMS 32
#define TM_MAX_CFG_NODES 64

/**
 * A sparse spectral Fourier character term chi_S(x) = (-1)^{<S, x>}.
 */
typedef struct {
    uint32_t mask;      /* Subset of variables S as a bitmask */
    int32_t coeff;      /* Fixed-point Fourier coefficient (scaled by 2^n) */
} tm_spectral_term_t;

/**
 * Fast Walsh-Hadamard Transform (FWHT) in-place:
 * Computes the spectral Fourier transform of a Boolean truth table of size N = 2^k.
 * Complexity: O(N log N) time, O(1) auxiliary space.
 */
void tm_wht_forward(int32_t *data, size_t n);

/**
 * Inverse Fast Walsh-Hadamard Transform (IFWHT) in-place.
 */
void tm_wht_inverse(int32_t *data, size_t n);

/**
 * Truncate Fourier spectrum: extracts up to `max_terms` with the highest energy
 * (absolute value of coefficients), discarding high-frequency noise.
 */
size_t tm_wht_truncate(const int32_t *spectrum, size_t n, size_t max_terms, tm_spectral_term_t *out_terms);

/**
 * Evaluate truncated Fourier polynomial in branchless integer arithmetic:
 * chi_S(x) = 1 - 2 * (popcount(mask & input_bits) & 1).
 * Completely branchless, zero instruction pipeline stalls, vectorizable with SIMD.
 */
int32_t tm_wht_eval(const tm_spectral_term_t *terms, size_t count, uint32_t input_bits);

/**
 * Spectral CFG Optimization using the Graph Laplacian L = D - A.
 * Computes the Fiedler vector (eigenvector of the second smallest eigenvalue)
 * to linearize control flow graphs for minimum cache-line crossing distance.
 */
typedef struct {
    size_t num_nodes;
    float adjacency[TM_MAX_CFG_NODES][TM_MAX_CFG_NODES]; /* Weighted edge execution frequency */
} tm_cfg_graph_t;

/**
 * Computes the 1D spectral ordering of CFG basic blocks using the Fiedler vector.
 * Nodes ordered by their Fiedler coordinates minimize jump displacement and L1i cache misses.
 */
void tm_cfg_spectral_order(const tm_cfg_graph_t *cfg, size_t *out_ordering);

/**
 * Chebyshev Spectral Function Approximation:
 * Compresses continuous math functions or discrete lookup tables into M coefficients,
 * evaluated via Clenshaw's recurrence in hardware FMA registers.
 */
void tm_chebyshev_fit(double (*fn)(double, void *), void *ctx, double a, double b, size_t degree, double *out_coeffs);

double tm_chebyshev_eval(const double *coeffs, size_t degree, double x, double a, double b);

/**
 * Discrete Spectral Phase Detector:
 * Evaluates running performance counter stream (e.g. instruction strides)
 * to identify loop periodicities and predict phase transitions.
 */
bool tm_spectral_phase_detect(const double *signal, size_t len, double *out_dominant_freq, double *out_confidence);

#ifdef __cplusplus
}
#endif

#endif /* TYPEMETRIC_SPECTRAL_H */
