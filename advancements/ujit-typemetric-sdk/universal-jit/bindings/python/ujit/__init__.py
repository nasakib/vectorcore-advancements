"""
Universal JIT (ujit) Python Interface
High-performance algorithmic pseudocode to bare-metal native machine code compiler.
Seamlessly integrates with ClothOS, Ray clusters, and heterogenous runtime environments.
"""

import ctypes
import os
import sys
from typing import List, Optional, Callable, Any, Dict

from .native_compiler import compile_pseudocode, NativeFunction

def _find_library() -> Optional[str]:
    if os.name == "nt":
        lib_names = ("libujit.dll", "ujit.dll")
    elif sys.platform == "darwin":
        lib_names = ("libujit.dylib", "libujit.so")
    else:
        lib_names = ("libujit.so",)

    base_dirs = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../lib")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../lib")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../lib")),
        os.path.abspath(os.path.dirname(__file__)),
    ]
    if os.name != "nt":
        base_dirs.append("/mnt/c/Users/natsa/Documents/universal-jit/lib")

    for d in base_dirs:
        for name in lib_names:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
    return None

_lib = None
_lib_attempted = False

def _get_lib():
    global _lib, _lib_attempted
    if not _lib_attempted:
        _lib_attempted = True
        lib_path = _find_library()
        if lib_path:
            try:
                _lib = ctypes.CDLL(lib_path)
                _lib.ujit_create.restype = ctypes.c_void_p
                _lib.ujit_create.argtypes = []
                _lib.ujit_destroy.restype = None
                _lib.ujit_destroy.argtypes = [ctypes.c_void_p]
                _lib.ujit_compile_string.restype = ctypes.c_int
                _lib.ujit_compile_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
                _lib.ujit_get_fn.restype = ctypes.c_void_p
                _lib.ujit_get_fn.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
                _lib.ujit_call.restype = ctypes.c_int64
                _lib.ujit_call.argtypes = [
                    ctypes.c_void_p,
                    ctypes.c_char_p,
                    ctypes.POINTER(ctypes.c_int64),
                    ctypes.c_size_t,
                ]
            except Exception:
                _lib = None
    return _lib


class JITFunction:
    """Callable wrapper around native bare-metal compiled function."""
    def __init__(self, backend_fn: Any):
        self._fn = backend_fn

    def __call__(self, *args: int) -> int:
        return self._fn(*args)


class Context:
    """Universal JIT Compiler Context."""
    def __init__(self):
        self.lib = _get_lib()
        self._c_ctx = None
        self._native_funcs: Dict[str, NativeFunction] = {}

        if self.lib:
            self._c_ctx = self.lib.ujit_create()

    def __del__(self):
        if self._c_ctx and self.lib:
            self.lib.ujit_destroy(self._c_ctx)
            self._c_ctx = None

    def compile(self, source: str) -> "Context":
        if self.lib and self._c_ctx:
            status = self.lib.ujit_compile_string(self._c_ctx, source.encode("utf-8"))
            if status != 0:
                raise ValueError(f"Universal JIT C-backend compilation error: {status}")
        else:
            # Native pure-Python x86-64 backend (VirtualAlloc / mmap)
            new_funcs = compile_pseudocode(source)
            self._native_funcs.update(new_funcs)
        return self

    def compile_file(self, filepath: str) -> "Context":
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return self.compile(content)

    def get_fn(self, name: str) -> Callable:
        if self.lib and self._c_ctx:
            fn_ptr = self.lib.ujit_get_fn(self._c_ctx, name.encode("utf-8"))
            if not fn_ptr:
                raise KeyError(f"Function '{name}' not found in JIT context")
            def c_caller(*args):
                c_args = (ctypes.c_int64 * len(args))(*args) if args else None
                return int(self.lib.ujit_call(self._c_ctx, name.encode("utf-8"), c_args, len(args)))
            return c_caller
        else:
            if name not in self._native_funcs:
                raise KeyError(f"Function '{name}' not found in JIT context")
            return self._native_funcs[name]

    def call(self, name: str, *args: int) -> int:
        fn = self.get_fn(name)
        return fn(*args)


def compile(source: str) -> Context:
    ctx = Context()
    ctx.compile(source)
    return ctx


def kernel(source_code: str):
    ctx = Context()
    ctx.compile(source_code)
    def decorator(fn):
        fn_name = fn.__name__
        return ctx.get_fn(fn_name)
    return decorator
