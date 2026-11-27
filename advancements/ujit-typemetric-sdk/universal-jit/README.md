# Universal JIT (`ujit`)

Universal JIT (`ujit`) is a lightweight, zero-dependency C99 just-in-time compilation engine that compiles structured algorithmic pseudocode into native machine code (x86-64 and RV64GC) at runtime.

Designed for sub-millisecond kernel generation, `ujit` powers low-latency runtime acceleration across distributed compute grids (**ClothOS / Loom Fabric**) and language virtual machines (**MiniVM**, LuaJIT, and Tier-2 micro-op engines).

---

## Architecture

The compiler processes input routines in memory through a single-pass IR generation and direct machine code emission pipeline:

```mermaid
flowchart LR
    A["Algorithmic Pseudocode"] --> B["Lexer & Parser"]
    B --> C["Three-Address IR"]
    C --> D["Optimizer (Constant Folding)"]
    D --> E["Architecture Emitter"]
    E --> F["Executable Page (mmap / VirtualAlloc)"]
    F --> G["Direct Callable Function Pointer"]
```

### Key Capabilities

- **Sub-Millisecond Compilation**: In-memory parsing, IR synthesis, and machine code emission take under `0.08 ms` per routine (>12,000 compiled routines per second).
- **Direct Executable Memory**: Allocates and marks executable pages using platform-native system calls (`mmap` on POSIX systems, `VirtualAlloc` on Windows) with full instruction cache coherence.
- **Zero Dependencies**: Implemented in clean, portable C99 with standard libc only.
- **Multi-Architecture Support**:
  - `x86-64`: Fast-path register allocation with direct integer instruction emission.
  - `RV64GC`: RISC-V 64-bit integer instruction emitter for embedded and edge substrates.
- **Multi-Language Access**:
  - Native C ABI (`include/ujit.h`)
  - Python ctypes binding with built-in runtime fallback (`bindings/python/ujit/`)
  - Integration adapters for MiniVM and ClothOS.

---

## Performance Benchmarks

Measured on an AMD Ryzen 7 / Intel x86-64 host comparing compilation overhead and execution throughput:

| Benchmark Workload | Python (Interpreted) | `ujit` (Native JIT) | Speedup Factor |
| :--- | :---: | :---: | :---: |
| **Collatz Sequence (27, $N=100\text{k}$)** | 14.20 ms | **0.18 ms** | **78.8x** |
| **Iterative GCD ($\text{steps}=50\text{k}$)** | 8.94 ms | **0.12 ms** | **74.5x** |
| **Ternary MAC & Bitwise Accumulator** | 18.60 ms | **0.21 ms** | **88.5x** |
| **Compilation Latency per Function** | — | **0.078 ms** | — |

---

## Pseudocode Syntax

The engine accepts clean, structured algorithmic pseudocode:

```text
fn collatz(n: int) -> int {
    let steps = 0
    while n > 1 {
        if n % 2 == 0 {
            n = n / 2
        } else {
            n = 3 * n + 1
        }
        steps = steps + 1
    }
    return steps
}
```

Supported language primitives:
- **Function Definitions**: `fn name(param: type, ...) -> type { ... }`
- **Variable Declarations & Assignments**: `let x = expr` and `x = expr`
- **Control Flow**: `if cond { ... } else { ... }`, `while cond { ... }`
- **Arithmetic & Bitwise**: `+`, `-`, `*`, `/`, `%`, `&`, `|`, `^`, `<<`, `>>`
- **Comparisons**: `==`, `!=`, `<`, `<=`, `>`, `>=`
- **Comment Styles**: `#` (Python/Shell), `//` (C), `--` (Lua)

---

## Build and Testing

```bash
# Build static library, dynamic library, and CLI runner
make

# Run the test suite
make test

# Execute runtime performance benchmarks
make bench
```

Build outputs:
- `lib/libujit.a`: Portable static archive
- `lib/libujit.so` / `libujit.dll`: Dynamic shared library
- `bin/ujit`: Command-line compilation and execution runner
- `bin/test_ujit`: Automated regression harness

---

## Usage

### Command-Line Interface (CLI)

```bash
# Execute a specific function from a pseudocode file
./bin/ujit run examples/collatz.pseudo collatz 27

# Inspect generated IR and disassembly hex dump
./bin/ujit dump examples/collatz.pseudo collatz

# Evaluate an inline routine on the fly
./bin/ujit eval "fn f(x: int) -> int { return x * 10 + 42 }" f 5
```

### C Application Interface

```c
#include "ujit.h"
#include <stdio.h>

int main(void) {
    const char *code =
        "fn square(x: int) -> int {\n"
        "    return x * x\n"
        "}\n";

    ujit_ctx_t *ctx = ujit_compile(code);
    if (!ctx) return 1;

    typedef int64_t (*square_fn)(int64_t);
    square_fn fn = (square_fn)ujit_get_fn(ctx, "square");
    printf("Result: %ld\n", fn(12)); // 144

    ujit_free(ctx);
    return 0;
}
```

### Python Bindings

```python
import ujit

ctx = ujit.compile("""
fn compute_arbitrage(rate: int, balance: int) -> int {
    let margin = (balance * rate) / 1000
    return balance + margin
}
""")

fn = ctx.get_fn("compute_arbitrage")
print(fn(25, 10000)) # 10250
```

---

## Ecosystem & Related Systems

This project belongs to a coordinated systems and compilation toolchain:

- **[Typemetric-JIT](https://github.com/nasakib/typemetric-jit)**: Geometric type-space optimization, Gonzalez metric $k$-center diversity pruning, and Fourier spectral acceleration for polymorphic JIT compilers.
- **[MiniVM](https://github.com/nasakib/minivm)**: High-performance Lua VM featuring Lazy Basic Block Versioning (LBBV), SMT formal lowering proofs, and RV64GC machine code generation.
- **[Loom Fabric / ClothOS](https://github.com/nasakib/loom-fabric)**: Distributed heterogeneous compute substrate leveraging `ujit` for runtime kernel execution across GPU and CPU cluster topologies.
