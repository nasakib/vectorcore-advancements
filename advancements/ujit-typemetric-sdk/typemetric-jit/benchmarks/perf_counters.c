#include "perf_counters.h"
#include <string.h>

#if defined(__linux__)
#include <unistd.h>
#include <sys/syscall.h>
#include <linux/perf_event.h>

static int open_perf_counter(uint32_t type, uint64_t config) {
    struct perf_event_attr attr;
    memset(&attr, 0, sizeof(struct perf_event_attr));
    attr.type = type;
    attr.size = sizeof(struct perf_event_attr);
    attr.config = config;
    attr.disabled = 1;
    attr.exclude_kernel = 1;
    attr.exclude_hv = 1;

    return (int)syscall(__NR_perf_event_open, &attr, 0, -1, -1, 0);
}

bool perf_session_start(perf_session_t *session) {
    if (session == NULL) return false;
    memset(session, 0, sizeof(perf_session_t));

    session->fd_instructions = open_perf_counter(PERF_TYPE_HARDWARE, PERF_COUNT_HW_INSTRUCTIONS);
    session->fd_branch_misses = open_perf_counter(PERF_TYPE_HARDWARE, PERF_COUNT_HW_BRANCH_MISSES);
    
    /* L1 Instruction Cache Misses */
    uint64_t l1i_config = PERF_COUNT_HW_CACHE_L1I | 
                          (PERF_COUNT_HW_CACHE_OP_READ << 8) | 
                          (PERF_COUNT_HW_CACHE_RESULT_MISS << 16);
    session->fd_l1i_misses = open_perf_counter(PERF_TYPE_HW_CACHE, l1i_config);

    /* Instruction TLB Misses */
    uint64_t itlb_config = PERF_COUNT_HW_CACHE_ITLB | 
                           (PERF_COUNT_HW_CACHE_OP_READ << 8) | 
                           (PERF_COUNT_HW_CACHE_RESULT_MISS << 16);
    session->fd_itlb_misses = open_perf_counter(PERF_TYPE_HW_CACHE, itlb_config);

    if (session->fd_instructions >= 0) {
        session->is_supported = true;
        ioctl(session->fd_instructions, PERF_EVENT_IOC_ENABLE, 0);
        if (session->fd_branch_misses >= 0) ioctl(session->fd_branch_misses, PERF_EVENT_IOC_ENABLE, 0);
        if (session->fd_l1i_misses >= 0) ioctl(session->fd_l1i_misses, PERF_EVENT_IOC_ENABLE, 0);
        if (session->fd_itlb_misses >= 0) ioctl(session->fd_itlb_misses, PERF_EVENT_IOC_ENABLE, 0);
        return true;
    }

    session->is_supported = false;
    return false;
}

void perf_session_stop(perf_session_t *session, perf_hardware_stats_t *out_stats) {
    if (session == NULL || out_stats == NULL) return;
    memset(out_stats, 0, sizeof(perf_hardware_stats_t));

    if (!session->is_supported) return;

    if (session->fd_instructions >= 0) {
        read(session->fd_instructions, &out_stats->instructions, sizeof(uint64_t));
        close(session->fd_instructions);
    }
    if (session->fd_branch_misses >= 0) {
        read(session->fd_branch_misses, &out_stats->branch_misses, sizeof(uint64_t));
        close(session->fd_branch_misses);
    }
    if (session->fd_l1i_misses >= 0) {
        read(session->fd_l1i_misses, &out_stats->l1i_misses, sizeof(uint64_t));
        close(session->fd_l1i_misses);
    }
    if (session->fd_itlb_misses >= 0) {
        read(session->fd_itlb_misses, &out_stats->itlb_misses, sizeof(uint64_t));
        close(session->fd_itlb_misses);
    }
}
#else
bool perf_session_start(perf_session_t *session) {
    if (session) session->is_supported = false;
    return false;
}
void perf_session_stop(perf_session_t *session, perf_hardware_stats_t *out_stats) {
    (void)session;
    if (out_stats) memset(out_stats, 0, sizeof(perf_hardware_stats_t));
}
#endif
