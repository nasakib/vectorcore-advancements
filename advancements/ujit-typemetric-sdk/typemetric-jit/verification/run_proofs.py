#!/usr/bin/env python3
import subprocess
import sys

def main():
    print("======================================================================")
    print(" TYPEMETRIC FORMAL VERIFICATION SUITE (Z3 SMT SOLVER)")
    print("======================================================================")
    scripts = [
        "verify_metric_axioms.py",
        "verify_gonzalez_bound.py",
        "verify_lowering_soundness.py",
        "verify_fourier_soundness.py",
        "verify_harmonic_soundness.py"
    ]
    all_ok = True
    for s in scripts:
        print(f"\n--- Running {s} ---")
        ret = subprocess.run([sys.executable, s])
        if ret.returncode != 0:
            print(f"[FAIL] {s} failed with exit code {ret.returncode}")
            all_ok = False
        else:
            print(f"[OK] {s} passed successfully.")

    print("\n======================================================================")
    if all_ok:
        print(" VERIFICATION RESULT: ALL FORMAL PROOFS PASSED (0 COUNTEREXAMPLES)")
    else:
        print(" VERIFICATION RESULT: ONE OR MORE PROOFS FAILED")
    print("======================================================================")
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
