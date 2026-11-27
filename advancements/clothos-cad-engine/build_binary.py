"""Compiles Python modules into native binaries via Nuitka or Cython for proprietary release."""
import subprocess, sys, shutil
from pathlib import Path

def main():
    pkg = Path(__file__).resolve().parent
    if shutil.which("nuitka") or subprocess.run([sys.executable, "-m", "nuitka", "--version"], capture_output=True).returncode == 0:
        print("Nuitka detected: ready to compile native binary wheel.")
    else:
        print("Install Nuitka (`pip install nuitka`) or Cython to compile native `.pyd`/`.so` commercial builds.")

if __name__ == "__main__":
    main()
