#include "typemetric/spectral.h"
#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

bool tm_spectral_phase_detect(const double *signal, size_t len, double *out_dominant_freq, double *out_confidence) {
    if (signal == NULL || len < 8) {
        if (out_dominant_freq) *out_dominant_freq = 0.0;
        if (out_confidence) *out_confidence = 0.0;
        return false;
    }

    /* Compute DC offset (mean) and subtract */
    double mean = 0.0;
    for (size_t i = 0; i < len; i++) {
        mean += signal[i];
    }
    mean /= (double)len;

    /* Search for peak frequency in discrete bins (1 .. len/2) */
    size_t num_bins = len / 2;
    double max_power = 0.0;
    size_t best_k = 0;
    double total_power = 0.0;

    for (size_t k = 1; k < num_bins; k++) {
        double real = 0.0;
        double imag = 0.0;
        double omega = 2.0 * M_PI * (double)k / (double)len;

        for (size_t n = 0; n < len; n++) {
            double val = signal[n] - mean;
            real += val * cos(omega * (double)n);
            imag -= val * sin(omega * (double)n);
        }

        double power = real * real + imag * imag;
        total_power += power;

        if (power > max_power) {
            max_power = power;
            best_k = k;
        }
    }

    if (total_power < 1e-9) {
        if (out_dominant_freq) *out_dominant_freq = 0.0;
        if (out_confidence) *out_confidence = 0.0;
        return false;
    }

    double confidence = max_power / total_power;
    double normalized_freq = (double)best_k / (double)len;

    if (out_dominant_freq) *out_dominant_freq = normalized_freq;
    if (out_confidence) *out_confidence = confidence;

    return (confidence > 0.35); /* Detect significant periodic oscillation */
}
