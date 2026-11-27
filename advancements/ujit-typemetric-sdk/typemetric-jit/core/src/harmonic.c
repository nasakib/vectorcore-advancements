#include "typemetric/harmonic.h"
#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/**
 * Precomputed Exact Dozenal Quarter-Wave Sine Table (769 entries: 0..pi/2).
 * Scaled by TM_DOZENAL_Q12_ONE = 1728 (12^3).
 * Zero runtime or compile-time IEEE-754 trigonometric instructions in reflex path.
 */
const int16_t TM_DOZENAL_SIN_QUARTER_LUT[769] = {
       0,    4,    7,   11,   14,   18,   21,   25,   28,   32,   35,   39,   42,   46,   49,   53,
      57,   60,   64,   67,   71,   74,   78,   81,   85,   88,   92,   95,   99,  102,  106,  109,
     113,  117,  120,  124,  127,  131,  134,  138,  141,  145,  148,  152,  155,  159,  162,  166,
     169,  173,  176,  180,  183,  187,  190,  194,  197,  201,  205,  208,  212,  215,  219,  222,
     226,  229,  233,  236,  240,  243,  247,  250,  254,  257,  261,  264,  268,  271,  275,  278,
     281,  285,  288,  292,  295,  299,  302,  306,  309,  313,  316,  320,  323,  327,  330,  334,
     337,  341,  344,  348,  351,  354,  358,  361,  365,  368,  372,  375,  379,  382,  386,  389,
     392,  396,  399,  403,  406,  410,  413,  416,  420,  423,  427,  430,  434,  437,  440,  444,
     447,  451,  454,  457,  461,  464,  468,  471,  474,  478,  481,  485,  488,  491,  495,  498,
     502,  505,  508,  512,  515,  518,  522,  525,  529,  532,  535,  539,  542,  545,  549,  552,
     555,  559,  562,  565,  569,  572,  575,  579,  582,  585,  589,  592,  595,  599,  602,  605,
     609,  612,  615,  619,  622,  625,  628,  632,  635,  638,  642,  645,  648,  651,  655,  658,
     661,  665,  668,  671,  674,  678,  681,  684,  687,  691,  694,  697,  700,  703,  707,  710,
     713,  716,  720,  723,  726,  729,  732,  736,  739,  742,  745,  748,  752,  755,  758,  761,
     764,  767,  771,  774,  777,  780,  783,  786,  790,  793,  796,  799,  802,  805,  808,  811,
     815,  818,  821,  824,  827,  830,  833,  836,  839,  842,  846,  849,  852,  855,  858,  861,
     864,  867,  870,  873,  876,  879,  882,  885,  888,  891,  894,  897,  900,  903,  906,  909,
     913,  916,  918,  921,  924,  927,  930,  933,  936,  939,  942,  945,  948,  951,  954,  957,
     960,  963,  966,  969,  972,  975,  978,  980,  983,  986,  989,  992,  995,  998, 1001, 1004,
    1007, 1009, 1012, 1015, 1018, 1021, 1024, 1027, 1029, 1032, 1035, 1038, 1041, 1044, 1046, 1049,
    1052, 1055, 1058, 1060, 1063, 1066, 1069, 1071, 1074, 1077, 1080, 1083, 1085, 1088, 1091, 1093,
    1096, 1099, 1102, 1104, 1107, 1110, 1113, 1115, 1118, 1121, 1123, 1126, 1129, 1131, 1134, 1137,
    1139, 1142, 1145, 1147, 1150, 1153, 1155, 1158, 1160, 1163, 1166, 1168, 1171, 1173, 1176, 1179,
    1181, 1184, 1186, 1189, 1192, 1194, 1197, 1199, 1202, 1204, 1207, 1209, 1212, 1214, 1217, 1219,
    1222, 1224, 1227, 1229, 1232, 1234, 1237, 1239, 1242, 1244, 1247, 1249, 1251, 1254, 1256, 1259,
    1261, 1264, 1266, 1268, 1271, 1273, 1276, 1278, 1280, 1283, 1285, 1287, 1290, 1292, 1295, 1297,
    1299, 1302, 1304, 1306, 1308, 1311, 1313, 1315, 1318, 1320, 1322, 1324, 1327, 1329, 1331, 1334,
    1336, 1338, 1340, 1342, 1345, 1347, 1349, 1351, 1354, 1356, 1358, 1360, 1362, 1364, 1367, 1369,
    1371, 1373, 1375, 1377, 1379, 1382, 1384, 1386, 1388, 1390, 1392, 1394, 1396, 1398, 1400, 1403,
    1405, 1407, 1409, 1411, 1413, 1415, 1417, 1419, 1421, 1423, 1425, 1427, 1429, 1431, 1433, 1435,
    1437, 1439, 1441, 1443, 1445, 1447, 1448, 1450, 1452, 1454, 1456, 1458, 1460, 1462, 1464, 1466,
    1467, 1469, 1471, 1473, 1475, 1477, 1479, 1480, 1482, 1484, 1486, 1488, 1489, 1491, 1493, 1495,
    1496, 1498, 1500, 1502, 1504, 1505, 1507, 1509, 1510, 1512, 1514, 1516, 1517, 1519, 1521, 1522,
    1524, 1526, 1527, 1529, 1531, 1532, 1534, 1535, 1537, 1539, 1540, 1542, 1543, 1545, 1547, 1548,
    1550, 1551, 1553, 1554, 1556, 1558, 1559, 1561, 1562, 1564, 1565, 1567, 1568, 1570, 1571, 1573,
    1574, 1575, 1577, 1578, 1580, 1581, 1583, 1584, 1585, 1587, 1588, 1590, 1591, 1592, 1594, 1595,
    1596, 1598, 1599, 1600, 1602, 1603, 1604, 1606, 1607, 1608, 1610, 1611, 1612, 1613, 1615, 1616,
    1617, 1618, 1620, 1621, 1622, 1623, 1625, 1626, 1627, 1628, 1629, 1631, 1632, 1633, 1634, 1635,
    1636, 1637, 1639, 1640, 1641, 1642, 1643, 1644, 1645, 1646, 1647, 1648, 1649, 1650, 1652, 1653,
    1654, 1655, 1656, 1657, 1658, 1659, 1660, 1661, 1662, 1663, 1664, 1664, 1665, 1666, 1667, 1668,
    1669, 1670, 1671, 1672, 1673, 1674, 1674, 1675, 1676, 1677, 1678, 1679, 1680, 1680, 1681, 1682,
    1683, 1684, 1684, 1685, 1686, 1687, 1688, 1688, 1689, 1690, 1691, 1691, 1692, 1693, 1693, 1694,
    1695, 1695, 1696, 1697, 1697, 1698, 1699, 1699, 1700, 1701, 1701, 1702, 1703, 1703, 1704, 1704,
    1705, 1705, 1706, 1707, 1707, 1708, 1708, 1709, 1709, 1710, 1710, 1711, 1711, 1712, 1712, 1713,
    1713, 1714, 1714, 1715, 1715, 1715, 1716, 1716, 1717, 1717, 1717, 1718, 1718, 1719, 1719, 1719,
    1720, 1720, 1720, 1721, 1721, 1721, 1722, 1722, 1722, 1723, 1723, 1723, 1723, 1724, 1724, 1724,
    1724, 1725, 1725, 1725, 1725, 1725, 1726, 1726, 1726, 1726, 1726, 1726, 1727, 1727, 1727, 1727,
    1727, 1727, 1727, 1727, 1727, 1728, 1728, 1728, 1728, 1728, 1728, 1728, 1728, 1728, 1728, 1728,
    1728
};

uint32_t tm_integer_sqrt(uint64_t x) {
    if (x == 0) return 0;
    uint64_t res = 0;
    uint64_t bit = (uint64_t)1 << 62;
    while (bit > x) {
        bit >>= 2;
    }
    while (bit != 0) {
        if (x >= res + bit) {
            x -= res + bit;
            res = (res >> 1) + bit;
        } else {
            res >>= 1;
        }
        bit >>= 2;
    }
    return (uint32_t)res;
}

int16_t tm_dozenal_sin_q12(tm_dozenal_phase_t phase) {
    uint32_t p = (uint32_t)phase % TM_DOZENAL_FULL_CIRCLE;
    if (p < TM_DOZENAL_QUARTER) {
        return TM_DOZENAL_SIN_QUARTER_LUT[p];
    } else if (p < TM_DOZENAL_HALF_CIRCLE) {
        return TM_DOZENAL_SIN_QUARTER_LUT[TM_DOZENAL_HALF_CIRCLE - p];
    } else if (p < TM_DOZENAL_HALF_CIRCLE + TM_DOZENAL_QUARTER) {
        return (int16_t)(-TM_DOZENAL_SIN_QUARTER_LUT[p - TM_DOZENAL_HALF_CIRCLE]);
    } else {
        return (int16_t)(-TM_DOZENAL_SIN_QUARTER_LUT[TM_DOZENAL_FULL_CIRCLE - p]);
    }
}

int16_t tm_dozenal_cos_q12(tm_dozenal_phase_t phase) {
    uint32_t shifted = (uint32_t)phase + TM_DOZENAL_QUARTER;
    if (shifted >= TM_DOZENAL_FULL_CIRCLE) {
        shifted %= TM_DOZENAL_FULL_CIRCLE;
    }
    return tm_dozenal_sin_q12((tm_dozenal_phase_t)shifted);
}

tm_dozenal_phase_t tm_dozenal_atan2(int64_t y, int64_t x) {
    if (x == 0 && y == 0) return 0;
    uint64_t ax = (x < 0) ? (uint64_t)(-x) : (uint64_t)x;
    uint64_t ay = (y < 0) ? (uint64_t)(-y) : (uint64_t)y;
    uint64_t r = (uint64_t)tm_integer_sqrt(ax * ax + ay * ay);
    if (r == 0) return 0;

    int32_t target_sin = (int32_t)((ay * (uint64_t)TM_DOZENAL_Q12_ONE) / r);
    uint32_t lo = 0;
    uint32_t hi = TM_DOZENAL_QUARTER;
    while (lo < hi) {
        uint32_t mid = (lo + hi) >> 1;
        if ((int32_t)TM_DOZENAL_SIN_QUARTER_LUT[mid] < target_sin) {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    uint32_t base = lo;

    if (x >= 0 && y >= 0) {
        return (tm_dozenal_phase_t)base;
    } else if (x < 0 && y >= 0) {
        return (tm_dozenal_phase_t)(TM_DOZENAL_HALF_CIRCLE - base);
    } else if (x < 0 && y < 0) {
        return (tm_dozenal_phase_t)(TM_DOZENAL_HALF_CIRCLE + base);
    } else {
        uint32_t res = TM_DOZENAL_FULL_CIRCLE - base;
        return (tm_dozenal_phase_t)(res % TM_DOZENAL_FULL_CIRCLE);
    }
}

uint16_t tm_dozenal_phase_distance(tm_dozenal_phase_t a, tm_dozenal_phase_t b) {
    uint32_t pa = (uint32_t)a % TM_DOZENAL_FULL_CIRCLE;
    uint32_t pb = (uint32_t)b % TM_DOZENAL_FULL_CIRCLE;
    uint32_t diff = (pa >= pb) ? (pa - pb) : (pb - pa);
    if (diff > TM_DOZENAL_HALF_CIRCLE) {
        diff = TM_DOZENAL_FULL_CIRCLE - diff;
    }
    return (uint16_t)diff;
}

tm_dozenal_phase_t tm_dozenal_kuramoto_reflex(
    tm_dozenal_phase_t phase,
    int16_t natural_omega,
    tm_dozenal_phase_t target_phase,
    int32_t coupling_k,
    uint16_t precision_pi_q12
) {
    uint32_t p = (phase < TM_DOZENAL_FULL_CIRCLE) ? (uint32_t)phase : ((uint32_t)phase % TM_DOZENAL_FULL_CIRCLE);
    uint32_t t = (target_phase < TM_DOZENAL_FULL_CIRCLE) ? (uint32_t)target_phase : ((uint32_t)target_phase % TM_DOZENAL_FULL_CIRCLE);

    uint32_t delta = t + TM_DOZENAL_FULL_CIRCLE - p;
    if (delta >= TM_DOZENAL_FULL_CIRCLE) {
        delta -= TM_DOZENAL_FULL_CIRCLE;
    }

    int32_t sin_d = (int32_t)tm_dozenal_sin_q12((tm_dozenal_phase_t)delta);
    int64_t num = (int64_t)coupling_k * (int64_t)precision_pi_q12 * (int64_t)sin_d;
    int64_t pull = 0;
    if (num > 0) {
        pull = (num + (TM_DOZENAL_Q12_DENOM_SQ >> 1)) / TM_DOZENAL_Q12_DENOM_SQ;
    } else if (num < 0) {
        pull = (num - (TM_DOZENAL_Q12_DENOM_SQ >> 1)) / TM_DOZENAL_Q12_DENOM_SQ;
    }

    int64_t next_p = (int64_t)p + (int64_t)natural_omega + pull;
    next_p %= TM_DOZENAL_FULL_CIRCLE;
    if (next_p < 0) {
        next_p += TM_DOZENAL_FULL_CIRCLE;
    }
    return (tm_dozenal_phase_t)next_p;
}

void tm_dozenal_kuramoto_step_batch(
    const tm_dozenal_phase_t *phases_in,
    const int16_t *omegas,
    const int8_t *trit_polarities,
    const uint16_t *precision_weights_q12,
    size_t count,
    int32_t coupling_k,
    tm_dozenal_phase_t *phases_out,
    tm_dozenal_sync_metrics_t *out_metrics
) {
    if (phases_in == NULL || omegas == NULL || trit_polarities == NULL ||
        precision_weights_q12 == NULL || phases_out == NULL || count == 0) {
        return;
    }

    size_t n = (count > TM_DOZENAL_MAX_OSCILLATORS) ? TM_DOZENAL_MAX_OSCILLATORS : count;
    size_t active_count = 0;
    for (size_t i = 0; i < n; i++) {
        if (trit_polarities[i] != 0) {
            active_count++;
        }
    }

    for (size_t i = 0; i < n; i++) {
        uint32_t pi = (uint32_t)phases_in[i] % TM_DOZENAL_FULL_CIRCLE;
        if (trit_polarities[i] == 0) {
            phases_out[i] = (tm_dozenal_phase_t)pi;
            continue;
        }

        int64_t weighted_sin_sum = 0;
        if (active_count > 1 && coupling_k > 0) {
            for (size_t j = 0; j < n; j++) {
                if (j == i || trit_polarities[j] == 0) continue;
                uint32_t pj = (uint32_t)phases_in[j] % TM_DOZENAL_FULL_CIRCLE;
                uint32_t delta = pj + TM_DOZENAL_FULL_CIRCLE - pi;
                if (delta >= TM_DOZENAL_FULL_CIRCLE) {
                    delta -= TM_DOZENAL_FULL_CIRCLE;
                }
                weighted_sin_sum += (int64_t)precision_weights_q12[j] *
                                    (int64_t)tm_dozenal_sin_q12((tm_dozenal_phase_t)delta);
            }
        }

        int64_t pull = 0;
        if (active_count > 1 && coupling_k > 0 && weighted_sin_sum != 0) {
            int64_t denom = (int64_t)(active_count - 1) * (int64_t)TM_DOZENAL_Q12_DENOM_SQ;
            int64_t raw_num = (int64_t)coupling_k * weighted_sin_sum;
            if (raw_num > 0) {
                pull = (raw_num + (denom >> 1)) / denom;
            } else {
                pull = (raw_num - (denom >> 1)) / denom;
            }
        }

        int64_t signed_omega = (int64_t)omegas[i] * (int64_t)trit_polarities[i];
        int64_t next_p = (int64_t)pi + signed_omega + pull;
        next_p %= TM_DOZENAL_FULL_CIRCLE;
        if (next_p < 0) {
            next_p += TM_DOZENAL_FULL_CIRCLE;
        }
        phases_out[i] = (tm_dozenal_phase_t)next_p;
    }

    if (out_metrics != NULL) {
        int64_t ux = 0;
        int64_t uy = 0;
        int64_t wx = 0;
        int64_t wy = 0;
        uint64_t total_weight = 0;

        for (size_t i = 0; i < n; i++) {
            if (trit_polarities[i] == 0) continue;
            int64_t cx = (int64_t)tm_dozenal_cos_q12(phases_out[i]);
            int64_t sy = (int64_t)tm_dozenal_sin_q12(phases_out[i]);
            uint64_t w = (uint64_t)precision_weights_q12[i];
            ux += cx;
            uy += sy;
            wx += (int64_t)w * cx;
            wy += (int64_t)w * sy;
            total_weight += w;
        }

        uint16_t coh_q12 = 0;
        if (active_count > 0) {
            uint64_t u_sq = (uint64_t)(ux * ux + uy * uy);
            uint64_t n_sq = (uint64_t)active_count * (uint64_t)active_count;
            uint32_t r_val = tm_integer_sqrt(u_sq / n_sq);
            coh_q12 = (r_val > TM_DOZENAL_Q12_ONE) ? TM_DOZENAL_Q12_ONE : (uint16_t)r_val;
        }

        uint16_t wcoh_q12 = coh_q12;
        tm_dozenal_phase_t mean_p = 0;
        if (total_weight > 0) {
            int64_t mx = wx / (int64_t)total_weight;
            int64_t my = wy / (int64_t)total_weight;
            uint32_t wr = tm_integer_sqrt((uint64_t)(mx * mx + my * my));
            wcoh_q12 = (wr > TM_DOZENAL_Q12_ONE) ? TM_DOZENAL_Q12_ONE : (uint16_t)wr;
            mean_p = tm_dozenal_atan2(wy, wx);
        } else if (active_count > 0) {
            mean_p = tm_dozenal_atan2(uy, ux);
        }

        uint16_t max_spread = 0;
        uint32_t locked = 0;
        for (size_t i = 0; i < n; i++) {
            if (trit_polarities[i] == 0) continue;
            if (tm_dozenal_phase_distance(phases_out[i], mean_p) <= 12) {
                locked++;
            }
            for (size_t j = i + 1; j < n; j++) {
                if (trit_polarities[j] == 0) continue;
                uint16_t d = tm_dozenal_phase_distance(phases_out[i], phases_out[j]);
                if (d > max_spread) {
                    max_spread = d;
                }
            }
        }

        out_metrics->coherence_q12 = coh_q12;
        out_metrics->weighted_coherence_q12 = wcoh_q12;
        out_metrics->mean_phase = mean_p;
        out_metrics->max_phase_spread = max_spread;
        out_metrics->locked_count = locked;
    }
}

tm_dozenal_phase_t tm_dozenal_from_radians(double radians) {
    double two_pi = 2.0 * M_PI;
    double normalized = fmod(radians, two_pi);
    if (normalized < 0.0) {
        normalized += two_pi;
    }
    double units = floor((normalized / two_pi) * (double)TM_DOZENAL_FULL_CIRCLE + 0.5);
    uint32_t int_units = (uint32_t)units;
    return (tm_dozenal_phase_t)(int_units % TM_DOZENAL_FULL_CIRCLE);
}

double tm_dozenal_to_radians(tm_dozenal_phase_t phase) {
    uint32_t p = (uint32_t)phase % TM_DOZENAL_FULL_CIRCLE;
    return ((double)p / (double)TM_DOZENAL_FULL_CIRCLE) * (2.0 * M_PI);
}

uint32_t tm_kspace_lsh_hash(const tm_type_vector_t *vec, uint64_t seed) {
    if (vec == NULL) return 0;

    /* Extract 3D K-space coordinates from packed parameter types */
    double u = (double)(vec->kinds[0] | ((uint32_t)vec->kinds[1] << 8));
    double v = (double)(vec->kinds[2] | ((uint32_t)vec->kinds[3] << 8));
    double w = (double)(vec->kinds[4] | ((uint32_t)vec->kinds[5] << 8));

    /* K-Space scale (1 / 32) */
    const double scale = 0.03125;
    double u_f = u * scale;
    double v_f = v * scale;
    double w_f = w * scale;

    /* Spatial wave mixtures (BabelForge K-space wave equation) */
    double wave1 = sin(sin(u_f) * cos(v_f));
    double wave2 = cos(sin(v_f) * cos(w_f));
    double wave3 = sin(sin(w_f) * cos(u_f));
    double phase = (wave1 + wave2 + wave3) * M_PI;

    /* Discretize to dozenal phase */
    tm_dozenal_phase_t d_phase = tm_dozenal_from_radians(phase);

    /* Mix with scalar key and seed */
    uint64_t h = vec->scalar_key ^ seed;
    h ^= (uint64_t)d_phase * UINT64_C(0x9e3779b97f4a7c15);
    h ^= h >> 16;
    h *= UINT64_C(0xbf58476d1ce4e5b9);
    h ^= h >> 32;

    return (uint32_t)h;
}

void tm_type_to_balanced_trits(const tm_type_vector_t *vec, tm_trit_vector_t *out_trits) {
    if (vec == NULL || out_trits == NULL) return;

    out_trits->arity = vec->arity;
    for (uint8_t i = 0; i < TM_MAX_PARAMS; i++) {
        if (i < vec->arity) {
            tm_type_id_t k = vec->kinds[i];
            if (k == 0) {
                out_trits->trits[i] = 0;   /* Nil / None -> 0 */
            } else if (k <= 3) {
                out_trits->trits[i] = 1;   /* Primitives (Bool, Int, Float) -> +1 */
            } else {
                out_trits->trits[i] = -1;  /* Heap pointers (Strings, Arrays, Objects) -> -1 */
            }
        } else {
            out_trits->trits[i] = 0;
        }
    }
}

int32_t tm_trit_dot_product(const tm_trit_vector_t *a, const tm_trit_vector_t *b) {
    if (a == NULL || b == NULL) return 0;

    int32_t sum = 0;
    uint8_t min_arity = (a->arity < b->arity) ? a->arity : b->arity;

    /* Branchless product in {-1, 0, +1}: product is simply a_i * b_i */
    for (uint8_t i = 0; i < min_arity; i++) {
        sum += ((int32_t)a->trits[i] * (int32_t)b->trits[i]);
    }

    return sum;
}
