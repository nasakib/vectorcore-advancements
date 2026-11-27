#ifndef TYPEMETRIC_PERF_COUNTERS_H
#define TYPEMETRIC_PERF_COUNTERS_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint64_t instructions;
    uint64_t branch_misses;
    uint64_t l1i_misses;
    uint64_t itlb_misses;
} perf_hardware_stats_t;

typedef struct {
    int fd_instructions;
    int fd_branch_misses;
    int fd_l1i_misses;
    int fd_itlb_misses;
    bool is_supported;
} perf_session_t;

/**
 * Open hardware PMU performance counter session using Linux perf_event_open.
 */
bool perf_session_start(perf_session_t *session);

/**
 * Read cumulative hardware counter deltas and close PMU session.
 */
void perf_session_stop(perf_session_t *session, perf_hardware_stats_t *out_stats);

#ifdef __cplusplus
}
#endif

#endif /* TYPEMETRIC_PERF_COUNTERS_H */
