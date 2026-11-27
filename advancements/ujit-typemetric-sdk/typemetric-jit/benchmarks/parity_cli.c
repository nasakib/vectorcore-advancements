#define _POSIX_C_SOURCE 199309L
#include "typemetric/harmonic.h"
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

/**
 * Lightweight C99 CLI parity verifier for VectorForge Level 1.
 * Usage: parity_cli <coupling_k> <p0> <w0> <t0> <pi0> ... (up to 4 oscillators)
 */
int main(int argc, char **argv) {
    tm_dozenal_phase_t phases[4] = {0, 768, 1536, 2304};
    int16_t omegas[4] = {24, 42, 12, 36};
    int8_t trits[4] = {1, 1, 1, 1};
    uint16_t precs[4] = {1728, 1152, 864, 864};
    int32_t coupling_k = 24;

    if (argc >= 2) {
        coupling_k = (int32_t)strtol(argv[1], NULL, 10);
    }
    for (int i = 0; i < 4; i++) {
        int base = 2 + i * 4;
        if (base + 3 < argc) {
            phases[i] = (tm_dozenal_phase_t)(strtoul(argv[base], NULL, 10) % TM_DOZENAL_FULL_CIRCLE);
            omegas[i] = (int16_t)strtol(argv[base + 1], NULL, 10);
            trits[i] = (int8_t)strtol(argv[base + 2], NULL, 10);
            precs[i] = (uint16_t)strtoul(argv[base + 3], NULL, 10);
        }
    }

    tm_dozenal_phase_t next_phases[4] = {0};
    tm_dozenal_sync_metrics_t metrics = {0};
    tm_dozenal_kuramoto_step_batch(phases, omegas, trits, precs, 4, coupling_k, next_phases, &metrics);

    /* Micro-benchmark single reflex step */
    const size_t iters = 2000000;
    volatile tm_dozenal_phase_t sink = phases[0];
    struct timespec ts0, ts1;
    clock_gettime(CLOCK_MONOTONIC, &ts0);
    for (size_t i = 0; i < iters; i++) {
        sink = tm_dozenal_kuramoto_reflex_fast(sink, omegas[0], TM_DOZENAL_THIRD_CIRCLE, coupling_k, precs[0]);
    }
    clock_gettime(CLOCK_MONOTONIC, &ts1);
    double ns_per_op = ((double)(ts1.tv_sec - ts0.tv_sec) * 1e9 + (double)(ts1.tv_nsec - ts0.tv_nsec)) / (double)iters;

    printf("{\"nextPhases\":[%u,%u,%u,%u],\"coherenceQ12\":%u,\"maxSpread\":%u,\"meanPhase\":%u,\"nsPerOp\":%.2f,\"sink\":%u}\n",
           (unsigned)next_phases[0], (unsigned)next_phases[1], (unsigned)next_phases[2], (unsigned)next_phases[3],
           (unsigned)metrics.coherence_q12, (unsigned)metrics.max_phase_spread, (unsigned)metrics.mean_phase,
           ns_per_op, (unsigned)sink);
    return 0;
}
