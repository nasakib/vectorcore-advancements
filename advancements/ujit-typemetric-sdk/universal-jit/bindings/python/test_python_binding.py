import os
import sys

# Ensure bindings/python is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

import ujit

def test_python_binding():
    print("Testing Universal JIT Python Bindings...")

    code = """
    fn ackermann_step(m: int, n: int) -> int {
        if m == 0 {
            return n + 1
        } else {
            return m * 10 + n
        }
    }
    """

    ctx = ujit.compile(code)
    fn = ctx.get_fn("ackermann_step")

    res1 = fn(0, 5)
    assert res1 == 6, f"Expected 6, got {res1}"
    print(f"ackermann_step(0, 5) = {res1} [OK]")

    res2 = fn(3, 7)
    assert res2 == 37, f"Expected 37, got {res2}"
    print(f"ackermann_step(3, 7) = {res2} [OK]")

    # Test ClothOS kernel decorator
    @ujit.kernel("""
    fn clothos_matrix_shard(dim: int, rank: int) -> int {
        let chunk = dim / 8
        let offset = rank * chunk
        return offset + chunk
    }
    """)
    def clothos_matrix_shard(dim: int, rank: int) -> int:
        pass

    shard_end = clothos_matrix_shard(1024, 3)
    # chunk = 128, offset = 384, return 384 + 128 = 512
    assert shard_end == 512, f"Expected 512, got {shard_end}"
    print(f"clothos_matrix_shard(1024, 3) = {shard_end} [OK]")

    print("\nAll Python binding tests passed successfully!")

if __name__ == "__main__":
    test_python_binding()
