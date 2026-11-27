#!/usr/bin/env python3
"""
Polymorphic Workload Generator for JIT Compilation Stress Testing.
Generates non-stationary Markovian type-churn sequences to simulate extreme
polymorphism and evaluate cache eviction policies (LRU vs Metric k-Center).
"""

import random
import sys


TYPES = ["NIL", "BOOL", "INT", "FLOAT", "STRING", "ARRAY", "MAP", "OBJECT"]


def generate_markov_type_stream(length=10000, seed=42):
    random.seed(seed)
    # 3 latent regimes / regimes of execution:
    # Regime 0 (Numeric Processing): 60% INT, 35% FLOAT, 5% BOOL
    # Regime 1 (Data Serialization): 50% STRING, 30% MAP, 20% ARRAY
    # Regime 2 (Object Model / Metaprogramming): 70% OBJECT, 20% NIL, 10% BOOL
    regimes = [
        {"INT": 0.60, "FLOAT": 0.35, "BOOL": 0.05},
        {"STRING": 0.50, "MAP": 0.30, "ARRAY": 0.20},
        {"OBJECT": 0.70, "NIL": 0.20, "BOOL": 0.10},
    ]

    current_regime = 0
    stream = []

    for _ in range(length):
        # 2% chance to switch regime (bursty non-stationary behavior)
        if random.random() < 0.02:
            current_regime = (current_regime + random.randint(1, 2)) % 3

        dist = regimes[current_regime]
        r = random.random()
        cumulative = 0.0
        chosen = list(dist.keys())[-1]
        for t, prob in dist.items():
            cumulative += prob
            if r <= cumulative:
                chosen = t
                break
        stream.append(chosen)

    return stream


if __name__ == "__main__":
    stream = generate_markov_type_stream(100)
    print(f"Sample generated type stream (100 tokens, bursty Markovian):")
    print(", ".join(stream[:30]) + " ...")
