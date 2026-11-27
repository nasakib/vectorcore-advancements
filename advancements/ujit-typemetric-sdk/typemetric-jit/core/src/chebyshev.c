#include "typemetric/spectral.h"
#include <math.h>
#include <stdlib.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

void tm_chebyshev_fit(double (*fn)(double, void *), void *ctx, double a, double b, size_t degree, double *out_coeffs) {
    if (fn == NULL || out_coeffs == NULL || degree == 0 || b <= a) {
        return;
    }

    size_t num_nodes = degree * 2 + 16;
    double *f_vals = (double *)malloc(num_nodes * sizeof(double));

    /* Sample function at Chebyshev Gauss-Lobatto / roots nodes */
    for (size_t k = 0; k < num_nodes; k++) {
        double theta = M_PI * ((double)k + 0.5) / (double)num_nodes;
        double z = cos(theta); /* in [-1, 1] */
        double x = 0.5 * (b - a) * z + 0.5 * (b + a);
        f_vals[k] = fn(x, ctx);
    }

    /* Compute Chebyshev spectral coefficients */
    for (size_t j = 0; j <= degree; j++) {
        double sum = 0.0;
        for (size_t k = 0; k < num_nodes; k++) {
            double theta = M_PI * ((double)k + 0.5) / (double)num_nodes;
            sum += f_vals[k] * cos((double)j * theta);
        }
        out_coeffs[j] = (2.0 / (double)num_nodes) * sum;
    }

    free(f_vals);
}

double tm_chebyshev_eval(const double *coeffs, size_t degree, double x, double a, double b) {
    if (coeffs == NULL || degree == 0) return 0.0;

    /* Normalize x to [-1, 1] */
    double y = (2.0 * x - (b + a)) / (b - a);
    double y2 = 2.0 * y;

    /* Clenshaw's recurrence algorithm */
    double d1 = 0.0;
    double d2 = 0.0;

    for (size_t j = degree; j >= 1; j--) {
        double d0 = y2 * d1 - d2 + coeffs[j];
        d2 = d1;
        d1 = d0;
    }

    return y * d1 - d2 + 0.5 * coeffs[0];
}
