#include "typemetric/typemetric.h"
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <string.h>

#define STREAM_LEN 50000
#define CACHE_K 4
#define CANDIDATES_MAX 16

/* Simple LCG pseudo-random generator */
static uint64_t s_rng = 987654321ULL;
static inline uint32_t fast_rand(void) {
    s_rng = s_rng * 6364136223846793005ULL + 1442695040888963407ULL;
    return (uint32_t)(s_rng >> 32);
}

static inline double rand_uniform(void) {
    return (double)(fast_rand() & 0x7fffffff) / (double)0x7fffffff;
}

/* Generate non-stationary Markovian stream of type IDs (0..7) */
static void generate_workload(uint8_t *stream, size_t len) {
    int regime = 0;
    for (size_t i = 0; i < len; i++) {
        if (rand_uniform() < 0.015) {
            regime = (regime + 1 + (fast_rand() % 2)) % 3;
        }

        uint8_t t;
        double r = rand_uniform();
        if (regime == 0) {
            /* Numeric: 2=INT (60%), 3=FLOAT (35%), 1=BOOL (5%) */
            t = (r < 0.60) ? 2 : ((r < 0.95) ? 3 : 1);
        } else if (regime == 1) {
            /* Serialization: 4=STR (50%), 6=MAP (30%), 5=ARRAY (20%) */
            t = (r < 0.50) ? 4 : ((r < 0.80) ? 6 : 5);
        } else {
            /* Object model: 7=OBJECT (70%), 0=NIL (20%), 1=BOOL (10%) */
            t = (r < 0.70) ? 7 : ((r < 0.90) ? 0 : 1);
        }
        stream[i] = t;
    }
}

int main(void) {
    printf("======================================================================\n");
    printf(" TYPEMETRIC EVICTION BENCHMARK: LRU vs METRIC k-CENTER\n");
    printf(" Workload: %d polymorphic events | Cache Capacity K = %d\n", STREAM_LEN, CACHE_K);
    printf("======================================================================\n");

    uint8_t *stream = (uint8_t *)malloc(STREAM_LEN);
    generate_workload(stream, STREAM_LEN);

    tm_metric_config_t cfg;
    tm_metric_config_init_default(&cfg);

    /* --------------------------------------------------------- */
    /* 1. Simulate Standard LRU Cache                            */
    /* --------------------------------------------------------- */
    clock_t t0 = clock();
    uint8_t lru_cache[CACHE_K];
    uint32_t lru_age[CACHE_K];
    size_t lru_count = 0;
    uint32_t lru_hits = 0;
    uint32_t lru_deopts = 0;

    for (size_t i = 0; i < CACHE_K; i++) {
        lru_cache[i] = 255;
        lru_age[i] = 0;
    }

    for (size_t i = 0; i < STREAM_LEN; i++) {
        uint8_t val = stream[i];
        bool hit = false;
        size_t hit_slot = 0;

        for (size_t slot = 0; slot < lru_count; slot++) {
            if (lru_cache[slot] == val) {
                hit = true;
                hit_slot = slot;
                break;
            }
        }

        if (hit) {
            lru_hits++;
            lru_age[hit_slot] = (uint32_t)i;
        } else {
            lru_deopts++;
            if (lru_count < CACHE_K) {
                lru_cache[lru_count] = val;
                lru_age[lru_count] = (uint32_t)i;
                lru_count++;
            } else {
                /* Evict oldest */
                size_t oldest = 0;
                uint32_t min_age = lru_age[0];
                for (size_t s = 1; s < CACHE_K; s++) {
                    if (lru_age[s] < min_age) {
                        min_age = lru_age[s];
                        oldest = s;
                    }
                }
                lru_cache[oldest] = val;
                lru_age[oldest] = (uint32_t)i;
            }
        }
    }
    clock_t t1 = clock();
    double lru_time_ms = (double)(t1 - t0) * 1000.0 / CLOCKS_PER_SEC;

    /* --------------------------------------------------------- */
    /* 2. Simulate Typemetric Metric k-Center Eviction           */
    /* --------------------------------------------------------- */
    clock_t t2 = clock();
    tm_type_vector_t metric_cache[CACHE_K];
    size_t metric_count = 0;
    uint32_t metric_hits = 0;
    uint32_t metric_deopts = 0;

    /* Pool of candidate versions observed */
    tm_type_vector_t candidates[CANDIDATES_MAX];
    size_t cand_count = 0;

    for (size_t i = 0; i < STREAM_LEN; i++) {
        uint8_t val = stream[i];
        bool hit = false;

        for (size_t slot = 0; slot < metric_count; slot++) {
            if (metric_cache[slot].kinds[0] == val) {
                hit = true;
                break;
            }
        }

        if (hit) {
            metric_hits++;
        } else {
            metric_deopts++;
            /* Add to candidates pool if not present */
            size_t active_idx = 0;
            bool in_pool = false;
            for (size_t c = 0; c < cand_count; c++) {
                if (candidates[c].kinds[0] == val) {
                    in_pool = true;
                    active_idx = c;
                    break;
                }
            }
            if (!in_pool && cand_count < CANDIDATES_MAX) {
                active_idx = cand_count;
                tm_vector_init(&candidates[cand_count], &val, 1, 0);
                cand_count++;
            }

            /* Resample k-centers with incoming type strictly pinned as Center 0 */
            if (cand_count > CACHE_K) {
                size_t selected[CACHE_K];
                tm_gonzalez_select(candidates, cand_count, CACHE_K, active_idx, selected, &cfg);
                for (size_t k = 0; k < CACHE_K; k++) {
                    metric_cache[k] = candidates[selected[k]];
                }
                metric_count = CACHE_K;
            } else {
                tm_vector_init(&metric_cache[metric_count], &val, 1, 0);
                metric_count++;
            }
        }
    }
    clock_t t3 = clock();
    double metric_time_ms = (double)(t3 - t2) * 1000.0 / CLOCKS_PER_SEC;

    printf("\nBenchmark Results:\n");
    printf("  Standard LRU Cache:\n");
    printf("    Hit Rate:       %.2f%% (%u hits)\n", (double)lru_hits * 100.0 / STREAM_LEN, lru_hits);
    printf("    Deopt/Misses:   %u\n", lru_deopts);
    printf("    Execution Time: %.3f ms\n", lru_time_ms);

    printf("\n  Typemetric Metric k-Center Cache:\n");
    printf("    Hit Rate:       %.2f%% (%u hits)\n", (double)metric_hits * 100.0 / STREAM_LEN, metric_hits);
    printf("    Deopt/Misses:   %u  (Deopt reduction: -%.1f%%)\n", 
           metric_deopts, (double)(lru_deopts - metric_deopts) * 100.0 / lru_deopts);
    printf("    Execution Time: %.3f ms\n", metric_time_ms);
    printf("======================================================================\n");

    free(stream);
    return 0;
}
