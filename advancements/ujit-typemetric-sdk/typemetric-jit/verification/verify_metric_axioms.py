#!/usr/bin/env python3
"""
Formal SMT Verification of Typemetric Type Space Axioms
Uses Microsoft Z3 to formally prove that the type distance metric strictly
satisfies all four metric axioms:
  1. Non-negativity: forall a, b: d(a, b) >= 0
  2. Identity of Indiscernibles: forall a, b: d(a, b) == 0 <==> a == b
  3. Symmetry: forall a, b: d(a, b) == d(b, a)
  4. Triangle Inequality: forall a, b, c: d(a, c) <= d(a, b) + d(b, c)
"""

import sys
import z3


def build_default_dist_matrix():
    N = 9
    matrix = [[4 for _ in range(N)] for _ in range(N)]
    for i in range(N):
        matrix[i][i] = 0

    # Numeric family
    matrix[2][3] = matrix[3][2] = 1

    # Primitive family
    matrix[1][2] = matrix[2][1] = 2
    matrix[1][3] = matrix[3][1] = 2

    # NIL <-> Primitives
    matrix[0][1] = matrix[1][0] = 2
    matrix[0][2] = matrix[2][0] = 2
    matrix[0][3] = matrix[3][0] = 2

    # NIL <-> Heap
    for h in range(4, 9):
        matrix[0][h] = matrix[h][0] = 3

    # Heap intra-family
    for i in range(4, 9):
        for j in range(4, 9):
            if i != j:
                matrix[i][j] = matrix[j][i] = 2

    # Primitive vs Heap
    for p in range(1, 4):
        for h in range(4, 9):
            matrix[p][h] = matrix[h][p] = 4

    return matrix, N


def verify_base_metric():
    matrix, N = build_default_dist_matrix()
    solver = z3.Solver()

    a = z3.Int('a')
    b = z3.Int('b')
    c = z3.Int('c')

    solver.add(a >= 0, a < N)
    solver.add(b >= 0, b < N)
    solver.add(c >= 0, c < N)

    d_func = z3.Function('d_base', z3.IntSort(), z3.IntSort(), z3.IntSort())
    for i in range(N):
        for j in range(N):
            solver.add(d_func(i, j) == matrix[i][j])

    # Axiom 1
    s1 = z3.Solver()
    s1.add(solver.assertions())
    s1.add(d_func(a, b) < 0)
    assert s1.check() == z3.unsat, "Non-negativity failed!"

    # Axiom 2
    s2a = z3.Solver()
    s2a.add(solver.assertions())
    s2a.add(z3.And(d_func(a, b) == 0, a != b))
    assert s2a.check() == z3.unsat, "Identity failed (false positive)!"

    s2b = z3.Solver()
    s2b.add(solver.assertions())
    s2b.add(z3.And(a == b, d_func(a, b) != 0))
    assert s2b.check() == z3.unsat, "Identity failed (false negative)!"

    # Axiom 3
    s3 = z3.Solver()
    s3.add(solver.assertions())
    s3.add(d_func(a, b) != d_func(b, a))
    assert s3.check() == z3.unsat, "Symmetry violation!"

    # Axiom 4
    s4 = z3.Solver()
    s4.add(solver.assertions())
    s4.add(d_func(a, c) > d_func(a, b) + d_func(b, c))
    assert s4.check() == z3.unsat, "Triangle inequality violation!"

    print("[+] All 4 metric axioms formally verified (Z3: unsat for all counterexamples).")
    return True


if __name__ == "__main__":
    verify_base_metric()
